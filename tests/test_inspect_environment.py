import importlib.util
import json
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

        vscode = project / ".vscode"
        vscode.mkdir()
        (vscode / "settings.json").write_text(
            """{
  // JSONC is valid in VS Code configuration files.
  "python.analysis.extraPaths": [
    "${workspaceFolder}/res/scripts/client",
    "${workspaceFolder}/wot-src/sources/res/scripts/client",
    "${workspaceFolder}/wot-src/sources/res/scripts/common",
    "${workspaceFolder}/wot-src/sources/res/scripts/client_common",
    "${workspaceFolder}/wot-src/stubs",
  ],
  "python.autoComplete.extraPaths": [
    "${workspaceFolder}/res/scripts/client",
    "${workspaceFolder}/wot-src/sources/res/scripts/client",
    "${workspaceFolder}/wot-src/sources/res/scripts/common",
    "${workspaceFolder}/wot-src/sources/res/scripts/client_common",
    "${workspaceFolder}/wot-src/stubs",
  ],
  "python.analysis.indexing": true,
  "python.analysis.autoImportCompletions": true,
  "python.analysis.userFileIndexingLimit": 20000,
}
""",
            encoding="utf-8",
        )
        (vscode / "extensions.json").write_text(
            json.dumps(
                {
                    "recommendations": [
                        "ms-python.python",
                        "ms-python.vscode-pylance",
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )

        for relative in MODULE.SOURCE_ROOTS:
            (source / relative).mkdir(parents=True, exist_ok=True)
        for relative in ("sources-as3", "sources-gameface", "stubs"):
            (source / relative).mkdir(parents=True, exist_ok=True)
        (source / ".version_name").write_text("1.44.0.7794\n", encoding="utf-8")

        (source / ".publication.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "snapshot_contract_version": "1.1.0",
                    "branch": "mt-ru",
                    "target": "mt-ru",
                    "publisher": "lesta",
                    "version_name": "1.44.0.7794",
                    "commit_subject": "v.1.44.0.0 #2254",
                    "snapshot_created_at": "2026-08-01T00:00:00Z",
                    "counts": {"sources": 17017},
                }
            )
            + "\n",
            encoding="utf-8",
        )

        self._run(["git", "init", "-b", "mt-ru"], source)
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

    def _add_as3_project(self, project):
        as3 = project / "as3"
        main_class = as3 / "src/example/Main.as"
        main_class.parent.mkdir(parents=True)
        main_class.write_text(
            "package example { public class Main {} }\n",
            encoding="utf-8",
        )
        libs = as3 / "libs"
        libs.mkdir()
        (libs / "game.swc").write_bytes(b"test")
        (libs / "playerglobal.swc").write_bytes(b"test")
        (as3 / "asconfig.json").write_text(
            json.dumps(
                {
                    "config": "royale",
                    "compilerOptions": {
                        "targets": ["SWF"],
                        "target-player": "17.0",
                        "swf-version": 17,
                        "source-path": ["src"],
                        "external-library-path": [
                            "libs/game.swc",
                            "libs/playerglobal.swc",
                        ],
                        "output": "bin/example.swf",
                    },
                    "mainClass": "example.Main",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (as3 / "build-config.xml").write_text(
            """<config>
  <compilerOptions>
    <targets><target>SWF</target></targets>
    <target-player>17.0</target-player>
    <swf-version>17</swf-version>
    <output>bin/example.swf</output>
  </compilerOptions>
  <mainClass>example.Main</mainClass>
</config>
""",
            encoding="utf-8",
        )
        extensions = project / ".vscode/extensions.json"
        extensions.write_text(
            json.dumps(
                {
                    "recommendations": [
                        "ms-python.python",
                        "ms-python.vscode-pylance",
                        "bowlerhatllc.vscode-as3mxml",
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return as3

    def test_ready_gate_and_stack_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            project, source, game = self._fixture(Path(temp))
            report = MODULE.build_report(
                project,
                source_path=source,
                game_dir=game,
                expected_source_branch="mt-ru",
            )

        self.assertEqual(report["gate"]["status"], "ready")
        self.assertEqual(report["gate"]["confidence"], "high")
        self.assertEqual(report["gate"]["version_alignment"], "exact")
        self.assertEqual(report["gate"]["blockers"], [])
        self.assertEqual(report["gate"]["warnings"], [])
        self.assertEqual(report["project"]["mode"], "existing")
        self.assertIn("python", report["project"]["ui_stack_hints"])
        self.assertIn("gameface-or-unbound", report["project"]["ui_stack_hints"])
        self.assertEqual(report["source"]["git"]["branch"], "mt-ru")
        self.assertEqual(report["source"]["publication"]["target"], "mt-ru")
        self.assertEqual(report["source"]["publication"]["publisher"], "lesta")
        self.assertTrue(report["source"]["has_as3_sources"])
        self.assertTrue(report["source"]["has_gameface_sources"])
        self.assertTrue(report["source"]["has_stubs"])
        self.assertEqual(report["ide"]["static_status"], "ready")
        self.assertTrue(report["ide"]["runtime_editor_check_required"])
        self.assertEqual(report["ide"]["python"]["static_status"], "ready")
        self.assertEqual(report["build_hygiene"]["status"], "ready")
        self.assertEqual(report["build_hygiene"]["python_artifacts"], [])
        python_profile = report["ide"]["python"]["profiles"][0]
        self.assertEqual(python_profile["source_file_count"], 17017)
        self.assertTrue(
            all(
                root["in_analysis_extra_paths"]
                and root["in_autocomplete_extra_paths"]
                for root in python_profile["required_roots"]
            )
        )

    def test_as3_editor_and_release_configs_are_checked_separately(self):
        with tempfile.TemporaryDirectory() as temp:
            project, source, game = self._fixture(Path(temp))
            self._add_as3_project(project)
            report = MODULE.build_report(
                project,
                source_path=source,
                game_dir=game,
                expected_source_branch="mt-ru",
            )

        self.assertEqual(report["ide"]["static_status"], "ready")
        self.assertEqual(report["ide"]["as3"]["static_status"], "ready")
        config = report["ide"]["as3"]["configs"][0]
        self.assertEqual(config["targets"], ["SWF"])
        self.assertEqual(config["target_player"], "17.0")
        self.assertEqual(config["swf_version"], 17)
        self.assertTrue(config["main_class_resolves"])
        self.assertEqual(config["build_config"]["swf_version"], "17")

    def test_strict_ide_fails_on_asconfig_build_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            project, source, _game = self._fixture(Path(temp))
            as3 = self._add_as3_project(project)
            asconfig = json.loads((as3 / "asconfig.json").read_text(encoding="utf-8"))
            asconfig["compilerOptions"]["swf-version"] = 18
            (as3 / "asconfig.json").write_text(
                json.dumps(asconfig) + "\n", encoding="utf-8"
            )

            report = MODULE.build_report(
                project,
                source_path=source,
                target_version="v.1.44.0.0 #2254",
                expected_source_branch="mt-ru",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    str(project),
                    "--source",
                    str(source),
                    "--target-version",
                    "v.1.44.0.0 #2254",
                    "--expected-source-branch",
                    "mt-ru",
                    "--strict-ide",
                    "--compact",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        self.assertEqual(report["gate"]["status"], "ready")
        self.assertEqual(report["ide"]["as3"]["static_status"], "warning")
        self.assertIn(
            "swf-version differs between asconfig.json and build-config.xml",
            report["ide"]["as3"]["configs"][0]["warnings"],
        )
        self.assertEqual(completed.returncode, 3)

    def test_build_hygiene_reports_compiler_artifacts_in_runtime_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            project, source, _game = self._fixture(Path(temp))
            runtime_root = project / "res/scripts/client/gui/mods"
            (runtime_root / "mod_example.pyc").write_bytes(b"compiled")
            cache_dir = runtime_root / "__pycache__"
            cache_dir.mkdir()
            (cache_dir / "mod_example.cpython-314.pyc").write_bytes(b"compiled")

            report = MODULE.build_report(
                project,
                source_path=source,
                target_version="v.1.44.0.0 #2254",
                expected_source_branch="mt-ru",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    str(project),
                    "--source",
                    str(source),
                    "--target-version",
                    "v.1.44.0.0 #2254",
                    "--expected-source-branch",
                    "mt-ru",
                    "--strict-build-hygiene",
                    "--compact",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        self.assertEqual(report["gate"]["status"], "ready")
        self.assertEqual(report["build_hygiene"]["status"], "warning")
        self.assertEqual(
            report["build_hygiene"]["python_artifacts"],
            [
                "res/scripts/client/gui/mods/__pycache__/",
                "res/scripts/client/gui/mods/mod_example.pyc",
            ],
        )
        self.assertEqual(completed.returncode, 4)

    def test_older_source_version_warns_but_does_not_block(self):
        with tempfile.TemporaryDirectory() as temp:
            project, source, _game = self._fixture(Path(temp))
            report = MODULE.build_report(
                project,
                source_path=source,
                target_version="v.2.0.0.0 #3000",
                expected_source_branch="mt-ru",
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
                    "mt-ru",
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
                expected_source_branch="mt-ru",
            )

        self.assertEqual(report["gate"]["status"], "warning")
        self.assertEqual(report["gate"]["blockers"], [])
        self.assertIn(
            "wot-src git identity is unavailable",
            report["gate"]["warnings"],
        )

    def test_publication_manifest_identifies_detached_data_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "mod-project"
            source = project / "wot-src"
            for relative in MODULE.SOURCE_ROOTS:
                (source / relative).mkdir(parents=True, exist_ok=True)
            (source / ".publication.json").write_text(
                json.dumps(
                    {
                        "branch": "wot-eu",
                        "target": "wot-eu",
                        "publisher": "wargaming",
                        "commit_subject": "2.3.1.3 #926",
                    }
                ),
                encoding="utf-8",
            )

            report = MODULE.build_report(
                project,
                source_path=source,
                target_version="2.3.1.3 #926",
                expected_source_branch="wot-eu",
            )

        self.assertEqual(report["gate"]["status"], "warning")
        self.assertEqual(report["gate"]["version_alignment"], "exact")
        self.assertNotIn(
            "source commit is not contained in the expected branch",
            report["gate"]["warnings"],
        )
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
                expected_source_branch="mt-ru",
            )

        self.assertEqual(report["project"]["mode"], "greenfield")
        self.assertEqual(report["gate"]["status"], "blocked")
        self.assertEqual(report["gate"]["confidence"], "none")
        self.assertIn("wot-src directory is missing", report["gate"]["blockers"])


if __name__ == "__main__":
    unittest.main()
