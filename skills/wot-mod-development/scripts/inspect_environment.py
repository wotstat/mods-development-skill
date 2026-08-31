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
import xml.etree.ElementTree as ET
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
PUBLICATION_FIELDS = (
    "schema_version",
    "snapshot_contract_version",
    "branch",
    "target",
    "publisher",
    "client_type",
    "version_name",
    "commit_subject",
    "snapshot_created_at",
    "snapshot_id",
    "counts",
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
PYLANCE_DEFAULT_INDEX_LIMIT = 2000
PYTHON_EXTENSION_IDS = ("ms-python.python", "ms-python.vscode-pylance")
AS3_EXTENSION_ID = "bowlerhatllc.vscode-as3mxml"


def _read_text(path: Path, limit: int = 2_000_000) -> Optional[str]:
    try:
        with path.open("rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        return None
    if len(data) > limit:
        data = data[:limit]
    return data.decode("utf-8", errors="replace")


def _strip_jsonc_comments(text: str) -> str:
    """Remove JSONC comments without touching comment-like text in strings."""

    output: List[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < len(text):
            marker = text[index + 1]
            if marker == "/":
                index += 2
                while index < len(text) and text[index] not in "\r\n":
                    index += 1
                continue
            if marker == "*":
                index += 2
                while index + 1 < len(text):
                    if text[index] == "*" and text[index + 1] == "/":
                        index += 2
                        break
                    if text[index] in "\r\n":
                        output.append(text[index])
                    index += 1
                continue
        output.append(char)
        index += 1
    return "".join(output)


def _strip_jsonc_trailing_commas(text: str) -> str:
    output: List[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < len(text) and text[lookahead].isspace():
                lookahead += 1
            if lookahead < len(text) and text[lookahead] in "}]":
                index += 1
                continue
        output.append(char)
        index += 1
    return "".join(output)


def _read_jsonc(path: Path) -> Tuple[Optional[Any], Optional[str]]:
    raw = _read_text(path)
    if raw is None:
        return None, "file is missing or unreadable"
    try:
        value = json.loads(
            _strip_jsonc_trailing_commas(_strip_jsonc_comments(raw))
        )
    except (TypeError, ValueError) as error:
        return None, str(error)
    return value, None


def _unique(items: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(items))


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


def _read_publication(path: Path) -> Optional[Dict[str, Any]]:
    raw = _read_text(path)
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(value, dict):
        return None
    return {key: value[key] for key in PUBLICATION_FIELDS if key in value}


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
    result["has_gameface_sources"] = (source_path / "sources-gameface").is_dir()
    result["has_stubs"] = (source_path / "stubs").is_dir()

    version_name_text = _read_text(source_path / ".version_name")
    result["version_name"] = (
        version_name_text.strip() if version_name_text is not None else None
    )
    result["publication"] = _read_publication(source_path / ".publication.json")
    result["git"] = _git_identity(source_path)
    git_subject = result["git"].get("commit_subject") if result["git"] else None
    publication_subject = (
        result["publication"].get("commit_subject")
        if result["publication"]
        else None
    )
    if not isinstance(publication_subject, str):
        publication_subject = None
    result["commit_version"] = parse_version(git_subject) or parse_version(
        publication_subject
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


def _resolve_config_path(
    value: str,
    base_dir: Path,
    workspace_root: Path,
) -> Optional[Path]:
    expanded = value.replace("${workspaceFolder}", str(workspace_root)).replace(
        "${workspaceRoot}", str(workspace_root)
    )
    if "${" in expanded:
        return None
    if os.sep == "/":
        expanded = expanded.replace("\\", "/")
    candidate = Path(expanded).expanduser()
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    return candidate.resolve()


def _recommendations(value: Any) -> List[str]:
    if not isinstance(value, dict):
        return []
    raw = value.get("recommendations")
    if not isinstance(raw, list):
        return []
    return sorted(
        {
            item.strip().lower()
            for item in raw
            if isinstance(item, str) and item.strip()
        }
    )


def _workspace_root(
    workspace_value: Dict[str, Any],
    workspace_path: Path,
    fallback: Path,
) -> Path:
    folders = workspace_value.get("folders")
    if not isinstance(folders, list) or len(folders) != 1:
        return fallback
    folder = folders[0]
    if not isinstance(folder, dict) or not isinstance(folder.get("path"), str):
        return fallback
    resolved = _resolve_config_path(
        folder["path"], workspace_path.parent, fallback
    )
    return resolved or fallback


def _collect_vscode_profiles(
    project_root: Path,
    project_files: Sequence[str],
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    profiles: List[Dict[str, Any]] = []
    collection_warnings: List[str] = []

    extensions_path = project_root / ".vscode" / "extensions.json"
    global_recommendations: List[str] = []
    extensions_error: Optional[str] = None
    if extensions_path.is_file():
        extensions_value, extensions_error = _read_jsonc(extensions_path)
        if extensions_error:
            collection_warnings.append(
                ".vscode/extensions.json is invalid JSONC: " + extensions_error
            )
        elif not isinstance(extensions_value, dict):
            extensions_error = "top-level value must be an object"
            collection_warnings.append(
                ".vscode/extensions.json top-level value must be an object"
            )
        else:
            global_recommendations = _recommendations(extensions_value)

    settings_path = project_root / ".vscode" / "settings.json"
    settings_value: Any = None
    settings_error: Optional[str] = None
    if settings_path.is_file():
        settings_value, settings_error = _read_jsonc(settings_path)
        if settings_error is None and not isinstance(settings_value, dict):
            settings_error = "top-level value must be an object"
    profiles.append(
        {
            "kind": "folder",
            "path": str(settings_path),
            "exists": settings_path.is_file(),
            "workspace_root": project_root,
            "settings": settings_value if isinstance(settings_value, dict) else {},
            "settings_error": settings_error,
            "recommendations": global_recommendations,
            "extensions_path": str(extensions_path),
            "extensions_exists": extensions_path.is_file(),
            "extensions_error": extensions_error,
        }
    )

    for relative in sorted(
        item for item in project_files if item.lower().endswith(".code-workspace")
    ):
        workspace_path = project_root / relative
        workspace_value, workspace_error = _read_jsonc(workspace_path)
        if workspace_error is None and not isinstance(workspace_value, dict):
            workspace_error = "top-level value must be an object"
        workspace_object = (
            workspace_value if isinstance(workspace_value, dict) else {}
        )
        workspace_extensions = workspace_object.get("extensions")
        recommendations = sorted(
            set(global_recommendations)
            | set(_recommendations(workspace_extensions))
        )
        profiles.append(
            {
                "kind": "workspace",
                "path": str(workspace_path),
                "exists": True,
                "workspace_root": _workspace_root(
                    workspace_object, workspace_path, project_root
                ),
                "settings": (
                    workspace_object.get("settings")
                    if isinstance(workspace_object.get("settings"), dict)
                    else {}
                ),
                "settings_error": workspace_error,
                "recommendations": recommendations,
                "extensions_path": str(workspace_path),
                "extensions_exists": bool(recommendations),
                "extensions_error": None,
            }
        )

    all_recommendations = sorted(
        {
            recommendation
            for profile in profiles
            for recommendation in profile["recommendations"]
        }
    )
    return profiles, all_recommendations, collection_warnings


def _string_list_setting(
    settings: Dict[str, Any],
    key: str,
    warnings: List[str],
) -> List[str]:
    raw = settings.get(key)
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        warnings.append(key + " must be an array of paths")
        return []
    return list(raw)


def _resolve_path_list(
    values: Sequence[str],
    base_dir: Path,
    workspace_root: Path,
    setting_name: str,
    warnings: List[str],
) -> List[Path]:
    resolved: List[Path] = []
    for value in values:
        candidate = _resolve_config_path(value, base_dir, workspace_root)
        if candidate is None:
            warnings.append(
                setting_name + " contains an unresolved variable: " + value
            )
            continue
        resolved.append(candidate)
        if not candidate.exists():
            warnings.append(
                setting_name + " points to a missing path: " + value
            )
    return resolved


def _snapshot_base(path: Path) -> Optional[Path]:
    parts = path.parts
    lowered = tuple(part.lower() for part in parts)
    suffixes = (
        ("sources", "res", "scripts", "client"),
        ("sources", "res", "scripts", "common"),
        ("sources", "res", "scripts", "client_common"),
    )
    for suffix in suffixes:
        if len(parts) >= len(suffix) and lowered[-len(suffix) :] == suffix:
            return Path(*parts[: -len(suffix)])
    if lowered and lowered[-1] == "stubs":
        return path.parent
    return None


def _source_file_count(source: Dict[str, Any]) -> Optional[int]:
    publication = source.get("publication") or {}
    counts = publication.get("counts")
    if not isinstance(counts, dict):
        return None
    value = counts.get("sources")
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _inspect_python_profile(
    profile: Dict[str, Any],
    project_root: Path,
    source: Dict[str, Any],
) -> Dict[str, Any]:
    warnings: List[str] = []
    if not profile["exists"]:
        warnings.append("VS Code settings file is missing")
    if profile["settings_error"]:
        warnings.append(
            "VS Code settings are invalid JSONC: " + profile["settings_error"]
        )

    settings = profile["settings"]
    workspace_root = profile["workspace_root"]
    base_dir = workspace_root
    analysis_values = _string_list_setting(
        settings, "python.analysis.extraPaths", warnings
    )
    autocomplete_values = _string_list_setting(
        settings, "python.autoComplete.extraPaths", warnings
    )
    analysis_paths = _resolve_path_list(
        analysis_values,
        base_dir,
        workspace_root,
        "python.analysis.extraPaths",
        warnings,
    )
    autocomplete_paths = _resolve_path_list(
        autocomplete_values,
        base_dir,
        workspace_root,
        "python.autoComplete.extraPaths",
        warnings,
    )

    required: List[Tuple[str, Path]] = []
    project_source = project_root / "res" / "scripts" / "client"
    if project_source.is_dir():
        required.append(("project", project_source.resolve()))
    source_root = Path(source["path"])
    if source.get("layout_valid"):
        required.extend(
            (relative, (source_root / relative).resolve())
            for relative in SOURCE_ROOTS
        )
    else:
        warnings.append("selected wot-src script roots are unavailable")
    if source.get("has_stubs"):
        required.append(("stubs", (source_root / "stubs").resolve()))
    else:
        warnings.append("selected wot-src has no stubs directory")

    required_report: List[Dict[str, Any]] = []
    for label, required_path in required:
        in_analysis = required_path in analysis_paths
        in_autocomplete = required_path in autocomplete_paths
        required_report.append(
            {
                "name": label,
                "path": str(required_path),
                "in_analysis_extra_paths": in_analysis,
                "in_autocomplete_extra_paths": in_autocomplete,
            }
        )
        if not in_analysis:
            warnings.append(
                "python.analysis.extraPaths is missing required root: " + label
            )
        if not in_autocomplete:
            warnings.append(
                "python.autoComplete.extraPaths is missing required root: " + label
            )

    snapshot_bases = {
        str(base.resolve())
        for candidate in analysis_paths
        for base in [_snapshot_base(candidate)]
        if base is not None
    }
    if len(snapshot_bases) > 1:
        warnings.append(
            "python.analysis.extraPaths mixes multiple game snapshots; use separate workspace profiles"
        )

    if settings.get("python.analysis.indexing", True) is not True:
        warnings.append("python.analysis.indexing must be enabled")
    if settings.get("python.analysis.autoImportCompletions") is not True:
        warnings.append("python.analysis.autoImportCompletions must be enabled")

    source_count = _source_file_count(source)
    indexing_limit = settings.get("python.analysis.userFileIndexingLimit")
    indexing_limit_valid = (
        isinstance(indexing_limit, int)
        and not isinstance(indexing_limit, bool)
        and (indexing_limit == -1 or indexing_limit >= 0)
    )
    if source_count is not None and source_count > PYLANCE_DEFAULT_INDEX_LIMIT:
        if not indexing_limit_valid:
            warnings.append(
                "python.analysis.userFileIndexingLimit is missing or invalid for this snapshot"
            )
        elif indexing_limit != -1 and indexing_limit < source_count:
            warnings.append(
                "python.analysis.userFileIndexingLimit is lower than counts.sources"
            )

    recommendations = set(profile["recommendations"])
    for extension_id in PYTHON_EXTENSION_IDS:
        if extension_id not in recommendations:
            warnings.append("extension recommendation is missing: " + extension_id)

    warnings = _unique(warnings)
    return {
        "kind": profile["kind"],
        "path": profile["path"],
        "workspace_root": str(workspace_root),
        "status": "ready" if not warnings else "warning",
        "recommendations": profile["recommendations"],
        "analysis_extra_paths": [str(path) for path in analysis_paths],
        "autocomplete_extra_paths": [str(path) for path in autocomplete_paths],
        "required_roots": required_report,
        "snapshot_roots": sorted(snapshot_bases),
        "indexing": settings.get("python.analysis.indexing", True),
        "auto_import_completions": settings.get(
            "python.analysis.autoImportCompletions"
        ),
        "user_file_indexing_limit": indexing_limit,
        "source_file_count": source_count,
        "warnings": warnings,
    }


def _inspect_python_ide(
    applicable: bool,
    profiles: Sequence[Dict[str, Any]],
    project_root: Path,
    source: Dict[str, Any],
) -> Dict[str, Any]:
    if not applicable:
        return {
            "applicable": False,
            "static_status": "not-applicable",
            "profiles": [],
            "warnings": [],
        }

    reports = [
        _inspect_python_profile(profile, project_root, source)
        for profile in profiles
    ]
    ready = [report for report in reports if report["status"] == "ready"]
    warnings: List[str] = []
    if not ready:
        warnings.append("no VS Code profile fully configures Python tooling")
        if reports:
            best = min(reports, key=lambda report: len(report["warnings"]))
            warnings.extend(best["warnings"])
    return {
        "applicable": True,
        "static_status": "ready" if ready else "warning",
        "ready_profiles": [report["path"] for report in ready],
        "profiles": reports,
        "warnings": _unique(warnings),
    }


def _xml_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].replace("-", "").replace("_", "").lower()


def _xml_values(root: ET.Element, name: str) -> List[str]:
    normalized = _xml_tag(name)
    return [
        element.text.strip()
        for element in root.iter()
        if _xml_tag(element.tag) == normalized
        and element.text
        and element.text.strip()
    ]


def _inspect_build_config(path: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {"path": str(path), "parse_error": None}
    try:
        root = ET.parse(str(path)).getroot()
    except (OSError, ET.ParseError) as error:
        result["parse_error"] = str(error)
        return result

    target_players = _xml_values(root, "target-player")
    swf_versions = _xml_values(root, "swf-version")
    main_classes = _xml_values(root, "mainClass")
    outputs = _xml_values(root, "output")
    result.update(
        {
            "target_player": target_players[0] if target_players else None,
            "swf_version": swf_versions[0] if swf_versions else None,
            "targets": sorted(
                {value.upper() for value in _xml_values(root, "target")}
            ),
            "main_class": main_classes[0] if main_classes else None,
            "output": outputs[0] if outputs else None,
        }
    )
    return result


def _select_build_config(
    asconfig_path: Path,
    project_root: Path,
    project_files: Sequence[str],
) -> Optional[Path]:
    candidates = [
        asconfig_path.parent / "build-config.xml",
        project_root / "build-config.xml",
    ]
    discovered = [
        project_root / relative
        for relative in project_files
        if Path(relative).name.lower() == "build-config.xml"
    ]
    candidates.extend(discovered)
    unique_candidates: List[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in unique_candidates:
            unique_candidates.append(resolved)
    existing = [candidate for candidate in unique_candidates if candidate.is_file()]
    if not existing:
        return None
    sibling = (asconfig_path.parent / "build-config.xml").resolve()
    if sibling in existing:
        return sibling
    if len(existing) == 1:
        return existing[0]
    return None


def _as3_string_list(
    compiler_options: Dict[str, Any],
    key: str,
    warnings: List[str],
) -> List[str]:
    raw = compiler_options.get(key)
    if not isinstance(raw, list) or not raw or not all(
        isinstance(item, str) and item for item in raw
    ):
        warnings.append(key + " must be a non-empty array of paths")
        return []
    return list(raw)


def _inspect_asconfig(
    path: Path,
    project_root: Path,
    project_files: Sequence[str],
) -> Dict[str, Any]:
    warnings: List[str] = []
    value, error = _read_jsonc(path)
    if error:
        return {
            "path": str(path),
            "status": "warning",
            "parse_error": error,
            "warnings": ["asconfig.json is invalid JSONC: " + error],
        }
    if not isinstance(value, dict):
        return {
            "path": str(path),
            "status": "warning",
            "parse_error": "top-level value must be an object",
            "warnings": ["asconfig.json top-level value must be an object"],
        }

    compiler_options = value.get("compilerOptions")
    if not isinstance(compiler_options, dict):
        compiler_options = {}
        warnings.append("compilerOptions must be an object")

    config = value.get("config")
    royale = config is None or config == "royale"
    if royale and config != "royale":
        warnings.append('new Royale projects should declare config: "royale" explicitly')

    source_values = _as3_string_list(
        compiler_options, "source-path", warnings
    )
    external_values = _as3_string_list(
        compiler_options, "external-library-path", warnings
    )
    source_paths = _resolve_path_list(
        source_values, path.parent, path.parent, "source-path", warnings
    )
    external_paths = _resolve_path_list(
        external_values,
        path.parent,
        path.parent,
        "external-library-path",
        warnings,
    )

    targets = compiler_options.get("targets")
    normalized_targets = (
        sorted({item.upper() for item in targets if isinstance(item, str)})
        if isinstance(targets, list)
        else []
    )
    target_player = compiler_options.get("target-player")
    swf_version = compiler_options.get("swf-version")
    output = compiler_options.get("output")
    main_class = value.get("mainClass")

    if royale:
        if "SWF" not in normalized_targets:
            warnings.append('compilerOptions.targets must include "SWF"')
        if not isinstance(target_player, str) or not target_player.strip():
            warnings.append("compilerOptions.target-player must be a non-empty string")
        if not (
            isinstance(swf_version, int)
            and not isinstance(swf_version, bool)
            and swf_version >= 9
        ):
            warnings.append("compilerOptions.swf-version must be an integer >= 9")
        if not isinstance(output, str) or not output.strip():
            warnings.append("compilerOptions.output must name the SWF output")

    if not isinstance(main_class, str) or not main_class.strip():
        warnings.append("mainClass must be a non-empty fully qualified class name")
        main_class_resolves = False
    else:
        class_relative = Path(*main_class.split(".")).with_suffix(".as")
        main_class_resolves = any(
            (source_path / class_relative).is_file()
            for source_path in source_paths
        )
        if not main_class_resolves:
            warnings.append("mainClass does not resolve through source-path")

    playerglobal_paths = [
        candidate
        for candidate in external_paths
        if candidate.name.lower() == "playerglobal.swc"
    ]
    if royale and not playerglobal_paths:
        warnings.append(
            "playerglobal.swc is not declared in external-library-path; verify the SDK catalog for target-player"
        )

    build_path = _select_build_config(path, project_root, project_files)
    build_report = _inspect_build_config(build_path) if build_path else None
    if build_report and build_report.get("parse_error"):
        warnings.append("build-config.xml is invalid: " + build_report["parse_error"])
    elif build_report:
        comparisons = (
            ("target-player", target_player, build_report.get("target_player")),
            (
                "swf-version",
                str(swf_version) if isinstance(swf_version, int) else swf_version,
                build_report.get("swf_version"),
            ),
            ("mainClass", main_class, build_report.get("main_class")),
            ("output", output, build_report.get("output")),
        )
        for name, editor_value, build_value in comparisons:
            if editor_value is not None and build_value is not None:
                if str(editor_value).strip() != str(build_value).strip():
                    warnings.append(
                        name + " differs between asconfig.json and build-config.xml"
                    )
        build_targets = build_report.get("targets") or []
        if normalized_targets and build_targets:
            if set(normalized_targets) != set(build_targets):
                warnings.append(
                    "targets differ between asconfig.json and build-config.xml"
                )

    warnings = _unique(warnings)
    return {
        "path": str(path),
        "status": "ready" if not warnings else "warning",
        "parse_error": None,
        "toolchain": config or "royale-default",
        "targets": normalized_targets,
        "target_player": target_player,
        "swf_version": swf_version,
        "source_paths": [str(candidate) for candidate in source_paths],
        "external_library_paths": [str(candidate) for candidate in external_paths],
        "playerglobal_paths": [str(candidate) for candidate in playerglobal_paths],
        "main_class": main_class,
        "main_class_resolves": main_class_resolves,
        "output": output,
        "build_config": build_report,
        "warnings": warnings,
    }


def _inspect_as3_ide(
    applicable: bool,
    project_root: Path,
    project_files: Sequence[str],
    all_recommendations: Sequence[str],
) -> Dict[str, Any]:
    if not applicable:
        return {
            "applicable": False,
            "static_status": "not-applicable",
            "configs": [],
            "warnings": [],
        }

    warnings: List[str] = []
    if AS3_EXTENSION_ID not in all_recommendations:
        warnings.append("extension recommendation is missing: " + AS3_EXTENSION_ID)
    paths = sorted(
        project_root / relative
        for relative in project_files
        if Path(relative).name.lower() == "asconfig.json"
    )
    if not paths:
        warnings.append("AS3 sources exist but no asconfig.json was found")
    configs = [
        _inspect_asconfig(path, project_root, project_files) for path in paths
    ]
    for config in configs:
        warnings.extend(
            config["path"] + ": " + warning for warning in config["warnings"]
        )
    warnings = _unique(warnings)
    return {
        "applicable": True,
        "static_status": "ready" if not warnings else "warning",
        "configs": configs,
        "warnings": warnings,
    }


def inspect_ide(
    project_root: Path,
    project: Dict[str, Any],
    source: Dict[str, Any],
) -> Dict[str, Any]:
    project_root = project_root.expanduser().resolve()
    if not project_root.is_dir():
        return {
            "applicable": False,
            "static_status": "not-applicable",
            "runtime_editor_check_required": False,
            "warnings": [],
        }

    project_files, _truncated = _walk_project(project_root)
    profiles, recommendations, collection_warnings = _collect_vscode_profiles(
        project_root, project_files
    )
    hints = set(project.get("ui_stack_hints") or [])
    python_report = _inspect_python_ide(
        "python" in hints, profiles, project_root, source
    )
    has_as_sources = any(relative.lower().endswith(".as") for relative in project_files)
    as3_report = _inspect_as3_ide(
        has_as_sources, project_root, project_files, recommendations
    )
    applicable = python_report["applicable"] or as3_report["applicable"]
    warnings = list(collection_warnings)
    warnings.extend(python_report["warnings"])
    warnings.extend(as3_report["warnings"])
    warnings = _unique(warnings)
    return {
        "applicable": applicable,
        "static_status": (
            "not-applicable"
            if not applicable
            else "warning"
            if warnings
            else "ready"
        ),
        "runtime_editor_check_required": applicable,
        "limitations": (
            "Static inspection cannot verify installed extensions, language-server "
            "Output, Problems, hover, completion, or Quick Compile."
        ),
        "extension_recommendations": recommendations,
        "python": python_report,
        "as3": as3_report,
        "warnings": warnings,
    }


def _branch_matches(expected: str, source: Dict[str, Any]) -> bool:
    git = source.get("git") or {}
    candidates = set(git.get("containing_refs") or [])
    if git.get("branch"):
        candidates.add(git["branch"])
    publication = source.get("publication") or {}
    for key in ("branch", "target"):
        value = publication.get(key)
        if isinstance(value, str) and value:
            candidates.add(value)
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
    ide = inspect_ide(project_root, project, source)
    return {
        "schema_version": 1,
        "project": project,
        "source": source,
        "game": game,
        "gate": gate,
        "ide": ide,
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
        help=(
            "Expected wotstat/wot-src data branch for the product/region "
            "(for example mt-ru or wot-eu)"
        ),
    )
    parser.add_argument(
        "--compact", action="store_true", help="Emit compact JSON"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 2 only when source code is missing or unusable",
    )
    parser.add_argument(
        "--strict-ide",
        action="store_true",
        help="Exit with status 3 when static VS Code/asconfig checks warn",
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
    if args.strict_ide and report["ide"]["static_status"] == "warning":
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
