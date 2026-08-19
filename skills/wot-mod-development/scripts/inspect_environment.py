#!/usr/bin/env python3
"""Read-only inspection for WoT / Mir Tankov mod projects.

Missing or unusable source code blocks game-coupled work. Branch and version
alignment are confidence signals: mismatches are warnings, not blockers.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


VERSION_RE = re.compile(
    r"(?i)(?:\bv\.?\s*)?(\d+(?:\.\d+){2,4})(?:\s*#\s*(\d+))?"
)
SOURCE_ROOTS = (
    "sources/res/scripts/client",
    "sources/res/scripts/common",
    "sources/res/scripts/client_common",
)
PRUNED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "wot-src",
}
MAX_SCANNED_FILES = 50000


def _read_text(path: Path, limit: int = 2_000_000) -> Optional[str]:
    try:
        with path.open("rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        return None
    if len(data) > limit:
        data = data[:limit]
    return data.decode("utf-8", errors="replace")


def parse_version(text: Optional[str]) -> Optional[Dict[str, Optional[str]]]:
    if not text:
        return None
    matches = list(VERSION_RE.finditer(text))
    if not matches:
        return None
    match = next((item for item in matches if item.group(2)), matches[0])
    return {
        "version": match.group(1),
        "build": match.group(2),
        "matched": match.group(0).strip(),
    }


def _run_git(path: Path, args: Sequence[str]) -> Optional[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _git_identity(path: Path, include_dirty: bool = False) -> Dict[str, Any]:
    inside = _run_git(path, ["rev-parse", "--is-inside-work-tree"])
    if inside != "true":
        return {"is_git_repository": False}

    branch = _run_git(path, ["branch", "--show-current"]) or None
    refs_text = _run_git(
        path,
        ["for-each-ref", "--contains", "HEAD", "--format=%(refname:short)"],
    )
    identity: Dict[str, Any] = {
        "is_git_repository": True,
        "branch": branch,
        "commit": _run_git(path, ["rev-parse", "HEAD"]),
        "commit_subject": _run_git(path, ["log", "-1", "--format=%s"]),
        "containing_refs": sorted(
            line.strip() for line in (refs_text or "").splitlines() if line.strip()
        ),
    }
    if include_dirty:
        status = _run_git(path, ["status", "--porcelain=v1"])
        identity["dirty"] = bool(status)
    return identity


def inspect_source(source_path: Path) -> Dict[str, Any]:
    source_path = source_path.expanduser().resolve()
    result: Dict[str, Any] = {
        "path": str(source_path),
        "exists": source_path.is_dir(),
        "required_roots": {},
        "layout_valid": False,
    }
    if not source_path.is_dir():
        return result

    roots = {
        relative: (source_path / relative).is_dir() for relative in SOURCE_ROOTS
    }
    result["required_roots"] = roots
    result["layout_valid"] = all(roots.values())
    result["has_as3_sources"] = (source_path / "sources-as3").is_dir()

    version_name_text = _read_text(source_path / ".version_name")
    result["version_name"] = (
        version_name_text.strip() if version_name_text is not None else None
    )
    result["git"] = _git_identity(source_path)
    result["commit_version"] = parse_version(
        result["git"].get("commit_subject") if result["git"] else None
    )
    return result


def _candidate_game_version_files(game_dir: Path) -> Iterable[Path]:
    yield game_dir / "version.xml"
    yield game_dir / "win64" / "version.xml"
    yield game_dir / "win32" / "version.xml"


def inspect_game(game_dir: Optional[Path]) -> Dict[str, Any]:
    if game_dir is None:
        return {"provided": False}

    game_dir = game_dir.expanduser().resolve()
    result: Dict[str, Any] = {
        "provided": True,
        "path": str(game_dir),
        "exists": game_dir.is_dir(),
        "version_file": None,
        "version": None,
    }
    if not game_dir.is_dir():
        return result

    for candidate in _candidate_game_version_files(game_dir):
        if not candidate.is_file():
            continue
        raw = _read_text(candidate)
        result["version_file"] = str(candidate)
        result["version"] = parse_version(raw)
        break

    executables = {
        "mir_tankov": (
            game_dir / "win64" / "Tanki.exe",
            game_dir / "Tanki.exe",
        ),
        "world_of_tanks": (
            game_dir / "win64" / "WorldOfTanks.exe",
            game_dir / "WorldOfTanks.exe",
        ),
    }
    present = {
        product: [str(path) for path in paths if path.is_file()]
        for product, paths in executables.items()
    }
    result["executables"] = {key: value for key, value in present.items() if value}
    if len(result["executables"]) == 1:
        result["product_hint"] = next(iter(result["executables"]))
    else:
        result["product_hint"] = None
    return result


def _walk_project(root: Path) -> Tuple[List[str], bool]:
    files: List[str] = []
    truncated = False
    for current, dirs, names in os.walk(str(root)):
        dirs[:] = sorted(directory for directory in dirs if directory not in PRUNED_DIRS)
        for name in sorted(names):
            if name in {".DS_Store"}:
                continue
            absolute = Path(current) / name
            try:
                relative = absolute.relative_to(root).as_posix()
            except ValueError:
                continue
            files.append(relative)
            if len(files) >= MAX_SCANNED_FILES:
                truncated = True
                return files, truncated
    return files, truncated


def inspect_project(project_root: Path) -> Dict[str, Any]:
    project_root = project_root.expanduser().resolve()
    result: Dict[str, Any] = {
        "path": str(project_root),
        "exists": project_root.is_dir(),
        "mode": "unknown",
        "entrypoints": [],
        "metadata": [],
        "build_files": [],
        "ui_stack_hints": [],
        "scan_truncated": False,
    }
    if not project_root.is_dir():
        return result

    files, truncated = _walk_project(project_root)
    lower_files = {item.lower(): item for item in files}
    result["scan_truncated"] = truncated
    result["git"] = _git_identity(project_root, include_dirty=True)

    entrypoints = sorted(
        item
        for item in files
        if item.endswith(".py")
        and Path(item).name.startswith("mod_")
        and "/gui/mods/" in "/" + item
    )
    metadata = sorted(item for item in files if Path(item).name.lower() == "meta.xml")
    build_names = {
        "build.bat",
        "build.sh",
        "makefile",
        "package.json",
        "pyproject.toml",
        "tox.ini",
    }
    build_files = sorted(
        item
        for item in files
        if Path(item).name.lower() in build_names
        or item.lower().startswith(".github/workflows/")
    )

    hints: Set[str] = set()
    has_runtime_python = bool(entrypoints) or any(
        item.endswith(".py") and "/res/scripts/" in "/" + item for item in files
    )
    has_scaleform = any(
        item.endswith((".as", ".swf")) or item.lower().startswith("as3/")
        for item in lower_files
    )
    has_res_map = any(
        "mods/configs/res_map/" in item.lower() and item.lower().endswith(".json")
        for item in files
    )
    has_gameface_path = any("/gameface/" in "/" + item.lower() for item in files)
    has_web_candidate = any(
        item.lower().endswith((".html", ".css", ".js", ".ts", ".tsx"))
        for item in files
    )
    has_res = any(item.lower().startswith("res/") for item in files)

    if has_runtime_python:
        hints.add("python")
    if has_scaleform:
        hints.add("scaleform-as3")
    if has_res_map or has_gameface_path:
        hints.add("gameface-or-unbound")
    elif has_web_candidate:
        hints.add("web-ui-candidate")
    if has_res and not (has_runtime_python or has_scaleform or has_res_map or has_gameface_path):
        hints.add("resource-only-candidate")

    signals = bool(entrypoints or metadata or build_files or has_res)
    result.update(
        {
            "mode": "existing" if signals else "greenfield",
            "entrypoints": entrypoints,
            "metadata": metadata,
            "build_files": build_files,
            "ui_stack_hints": sorted(hints),
            "scanned_file_count": len(files),
        }
    )
    return result


def _branch_matches(expected: str, source: Dict[str, Any]) -> bool:
    git = source.get("git") or {}
    candidates = set(git.get("containing_refs") or [])
    if git.get("branch"):
        candidates.add(git["branch"])
    for candidate in candidates:
        normalized = (
            candidate[len("remotes/") :]
            if candidate.startswith("remotes/")
            else candidate
        )
        if normalized == expected or normalized.endswith("/" + expected):
            return True
    return False


def _same_exact_version(
    target: Optional[Dict[str, Optional[str]]],
    source: Optional[Dict[str, Optional[str]]],
) -> bool:
    if not target or not source:
        return False
    if not target.get("version") or not source.get("version"):
        return False
    if not target.get("build") or not source.get("build"):
        return False
    return (
        target["version"] == source["version"]
        and target["build"] == source["build"]
    )


def _version_alignment(
    target: Optional[Dict[str, Optional[str]]],
    source: Optional[Dict[str, Optional[str]]],
) -> str:
    if not target or not source:
        return "unknown"
    if not target.get("version") or not source.get("version"):
        return "unknown"
    if _same_exact_version(target, source):
        return "exact"
    if target["version"] == source["version"]:
        return "same-version-build-diff-or-unknown"
    return "different-version"


def evaluate_gate(
    source: Dict[str, Any],
    game: Dict[str, Any],
    target_version_text: Optional[str],
    expected_branch: Optional[str],
) -> Dict[str, Any]:
    blockers: List[str] = []
    warnings: List[str] = []
    explicit_target = parse_version(target_version_text)
    game_target = game.get("version") if game.get("provided") else None

    if explicit_target and game_target and not _same_exact_version(explicit_target, game_target):
        warnings.append("--target-version does not exactly match game version.xml")

    target = explicit_target or game_target
    if not source.get("exists"):
        blockers.append("wot-src directory is missing")
    elif not source.get("layout_valid"):
        blockers.append("wot-src is missing one or more required script roots")

    source_git = source.get("git") or {}
    source_version = source.get("commit_version")
    source_usable = source.get("exists") and source.get("layout_valid")
    if source_usable:
        if not source_git.get("is_git_repository"):
            warnings.append("wot-src git identity is unavailable")
        if not source_git.get("commit"):
            warnings.append("wot-src commit SHA is unavailable")

        if not expected_branch:
            warnings.append("expected source branch was not provided")
        elif not _branch_matches(expected_branch, source):
            warnings.append("source commit is not contained in the expected branch")

        if not target:
            warnings.append("target client version/build is unavailable")
        elif not target.get("build"):
            warnings.append("target client build number after # is unavailable")

        if not source_version:
            warnings.append("source commit subject has no parseable client version")
        elif not source_version.get("build"):
            warnings.append("source commit subject has no build number after #")

        if target and source_version and not _same_exact_version(target, source_version):
            warnings.append("source commit version/build does not exactly match target client")

    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    status = "blocked" if blockers else "warning" if warnings else "ready"
    return {
        "status": status,
        "confidence": "none" if blockers else "reduced" if warnings else "high",
        "target_version": target,
        "expected_source_branch": expected_branch,
        "source_version": source_version,
        "version_alignment": _version_alignment(target, source_version),
        "blockers": blockers,
        "warnings": warnings,
        "reasons": blockers + warnings,
    }


def build_report(
    project_root: Path,
    source_path: Optional[Path] = None,
    game_dir: Optional[Path] = None,
    target_version: Optional[str] = None,
    expected_source_branch: Optional[str] = None,
) -> Dict[str, Any]:
    project = inspect_project(project_root)
    resolved_source = source_path or (project_root / "wot-src")
    source = inspect_source(resolved_source)
    game = inspect_game(game_dir)
    gate = evaluate_gate(source, game, target_version, expected_source_branch)
    return {
        "schema_version": 1,
        "project": project,
        "source": source,
        "game": game,
        "gate": gate,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only inspection of a WoT / Mir Tankov mod environment."
    )
    parser.add_argument("project_root", type=Path, help="Mod project root")
    parser.add_argument(
        "--source",
        type=Path,
        help="wot-src checkout (defaults to <project-root>/wot-src)",
    )
    parser.add_argument("--game-dir", type=Path, help="Installed game root")
    parser.add_argument(
        "--target-version",
        help='Exact target text, for example "v.1.44.0.0 #2254"',
    )
    parser.add_argument(
        "--expected-source-branch",
        help="Expected wot-src branch for the product/region",
    )
    parser.add_argument(
        "--compact", action="store_true", help="Emit compact JSON"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 2 only when source code is missing or unusable",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    report = build_report(
        project_root=args.project_root,
        source_path=args.source,
        game_dir=args.game_dir,
        target_version=args.target_version,
        expected_source_branch=args.expected_source_branch,
    )
    if args.compact:
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and report["gate"]["status"] == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
