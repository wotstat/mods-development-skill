import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "skills"
    / "wot-mod-development"
    / "scripts"
    / "inspect_environment.py"
)
SPEC = importlib.util.spec_from_file_location("inspect_environment", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class InspectEnvironmentTests(unittest.TestCase):
    def _run(self, args, cwd):
        subprocess.run(
            args,
            cwd=str(cwd),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def _fixture(self, root):
        project = root / "mod-project"
        source = project / "wot-src"
        game = root / "game"

        entry = project / "res/scripts/client/gui/mods/mod_example.py"
        entry.parent.mkdir(parents=True)
        entry.write_text("MOD_VERSION = '{{VERSION}}'\n", encoding="utf-8")
        (project / "meta.xml").write_text("<mod/>\n", encoding="utf-8")
        gf = project / "res/gui/gameface/mods/example/index.html"
        gf.parent.mkdir(parents=True)
        gf.write_text("<div></div>\n", encoding="utf-8")

        for relative in MODULE.SOURCE_ROOTS:
            (source / relative).mkdir(parents=True, exist_ok=True)
        (source / ".version_name").write_text("1.44.0.7794\n", encoding="utf-8")

        self._run(["git", "init", "-b", "RU"], source)
        self._run(["git", "config", "user.email", "test@example.invalid"], source)
        self._run(["git", "config", "user.name", "Skill Test"], source)
        self._run(["git", "add", "."], source)
        self._run(["git", "commit", "-m", "v.1.44.0.0 #2254"], source)

        game.mkdir()
        (game / "version.xml").write_text(
            "<root><version>v.1.44.0.0 #2254</version></root>\n",
            encoding="utf-8",
        )
        return project, source, game

    def test_ready_gate_and_stack_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            project, source, game = self._fixture(Path(temp))
            report = MODULE.build_report(
                project,
                source_path=source,
                game_dir=game,
                expected_source_branch="RU",
            )

        self.assertEqual(report["gate"]["status"], "ready")
        self.assertEqual(report["gate"]["confidence"], "high")
        self.assertEqual(report["gate"]["version_alignment"], "exact")
        self.assertEqual(report["gate"]["blockers"], [])
        self.assertEqual(report["gate"]["warnings"], [])
        self.assertEqual(report["project"]["mode"], "existing")
        self.assertIn("python", report["project"]["ui_stack_hints"])
        self.assertIn("gameface-or-unbound", report["project"]["ui_stack_hints"])
        self.assertEqual(report["source"]["git"]["branch"], "RU")

    def test_older_source_version_warns_but_does_not_block(self):
        with tempfile.TemporaryDirectory() as temp:
            project, source, _game = self._fixture(Path(temp))
            report = MODULE.build_report(
                project,
                source_path=source,
                target_version="v.2.0.0.0 #3000",
                expected_source_branch="RU",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    str(project),
                    "--source",
                    str(source),
                    "--target-version",
                    "v.2.0.0.0 #3000",
                    "--expected-source-branch",
                    "RU",
                    "--strict",
                    "--compact",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.assertEqual(report["gate"]["status"], "warning")
            self.assertEqual(report["gate"]["confidence"], "reduced")
            self.assertEqual(report["gate"]["blockers"], [])
            self.assertEqual(
                report["gate"]["version_alignment"], "different-version"
            )
            self.assertIn(
                "source commit version/build does not exactly match target client",
                report["gate"]["warnings"],
            )
            self.assertEqual(completed.returncode, 0)

    def test_source_without_git_metadata_warns_but_does_not_block(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "mod-project"
            source = project / "wot-src"
            for relative in MODULE.SOURCE_ROOTS:
                (source / relative).mkdir(parents=True, exist_ok=True)

            report = MODULE.build_report(
                project,
                source_path=source,
                target_version="v.1.44.0.0 #2254",
                expected_source_branch="RU",
            )

        self.assertEqual(report["gate"]["status"], "warning")
        self.assertEqual(report["gate"]["blockers"], [])
        self.assertIn(
            "wot-src git identity is unavailable",
            report["gate"]["warnings"],
        )

    def test_missing_source_blocks_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "empty-project"
            project.mkdir()
            report = MODULE.build_report(
                project,
                target_version="v.1.44.0.0 #2254",
                expected_source_branch="RU",
            )

        self.assertEqual(report["project"]["mode"], "greenfield")
        self.assertEqual(report["gate"]["status"], "blocked")
        self.assertEqual(report["gate"]["confidence"], "none")
        self.assertIn("wot-src directory is missing", report["gate"]["blockers"])


if __name__ == "__main__":
    unittest.main()
