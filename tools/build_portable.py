#!/usr/bin/env python3
"""Build a reproducible, source-first PlayAtlas portable archive.

The current build host is not assumed to have Godot or Windows.  Consequently
this script packages the Godot project, Python rule layer, tests, data, docs,
and any existing web preview, but never fabricates a native executable.  The
archive contains a manifest that records exactly what was included and what
was not verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def project_version(project_root: Path) -> str:
    project_file = project_root / "project.godot"
    if project_file.is_file():
        text = project_file.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"config/version\s*=\s*([^\s]+)", text)
        if match:
            return match.group(1).strip('"')
    return "0.1.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def should_include(path: Path, project_root: Path, out_dir: Path) -> bool:
    relative = path.relative_to(project_root)
    parts = set(relative.parts)
    if any(part in {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".godot", ".import"} for part in parts):
        return False
    # Never recursively package a previous output archive.
    try:
        path.relative_to(out_dir)
        return False
    except ValueError:
        pass
    if path.is_symlink():
        return False
    return path.is_file()


def iter_project_files(project_root: Path, out_dir: Path) -> Iterable[Path]:
    for path in sorted(project_root.rglob("*")):
        if should_include(path, project_root, out_dir):
            yield path


def make_notes(project_root: Path, archive_name: str, file_count: int) -> str:
    godot = shutil.which("godot") or shutil.which("godot4")
    return "\n".join([
        "# PlayAtlas portable build notes",
        "",
        f"Generated: {utc_now()}",
        f"Archive: `{archive_name}`",
        f"Project files included: {file_count}",
        "",
        "## What this artifact is",
        "",
        "This is a source-first portable archive. It includes the Godot project, rule engines, data, tests, tools, documentation, and any web preview present at build time.",
        "",
        "## What this artifact is not",
        "",
        "It is not a Windows installer or a claim that the game was launched and manually accepted on Windows. It is not an Android APK and no Android device verification is implied.",
        "",
        "## Build host",
        "",
        f"- OS: {platform.platform()}",
        f"- Python: {sys.version.splitlines()[0]}",
        f"- Godot executable detected: {'yes (' + godot + ')' if godot else 'no'}",
        "",
        "## First run",
        "",
        "- Linux/macOS: run `run_qa.sh` for headless rule checks, or open the project with a compatible Godot 4.x editor.",
        "- Windows: run `run_qa.bat` for headless rule checks, or open the project with a compatible Godot 4.x editor.",
        "- Review `reports/qa/qa_report.md` and `GAME_STATUS.md`; entries marked 未测试/待验证 remain unverified.",
        "",
    ])


def build(project_root: Path, out_dir: Path, include_reports: bool = True) -> Path:
    project_root = project_root.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    version = project_version(project_root)
    archive_name = f"PlayAtlas-portable-source-v{version}.zip"
    archive_path = out_dir / archive_name

    # Avoid stale output being included while walking the project.
    if archive_path.exists():
        archive_path.unlink()

    files: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="playatlas-build-") as temp_name:
        staging = Path(temp_name) / "PlayAtlas"
        staging.mkdir(parents=True)
        for source in iter_project_files(project_root, out_dir):
            relative = source.relative_to(project_root)
            # Reports are useful evidence and included by default; callers can
            # opt out when making a clean source snapshot.
            if not include_reports and relative.parts[:1] == ("reports",):
                continue
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

        notes = make_notes(project_root, archive_name, sum(1 for _ in staging.rglob("*")))
        (staging / "PORTABLE_BUILD_NOTES.md").write_text(notes, encoding="utf-8")

        for item in sorted(staging.rglob("*")):
            if item.is_file():
                relative = item.relative_to(staging).as_posix()
                files.append({
                    "path": relative,
                    "size": item.stat().st_size,
                    "sha256": sha256(item),
                })

        manifest = {
            "schema_version": 1,
            "product": "PlayAtlas",
            "version": version,
            "artifact": archive_name,
            "generated_at": utc_now(),
            "artifact_kind": "portable_source_archive",
            "contains": ["Godot project", "Python rule engines", "tests", "tools", "data", "docs", "web_preview_if_present"],
            "native_executable_included": False,
            "windows_started": False,
            "windows_interaction_tested": False,
            "android_apk_included": False,
            "android_device_tested": False,
            "files": files,
            "build_host": {
                "os": platform.platform(),
                "python": sys.version,
                "godot_detected": bool(shutil.which("godot") or shutil.which("godot4")),
            },
        }
        (staging / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        files.append({
            "path": "BUILD_MANIFEST.json",
            "size": (staging / "BUILD_MANIFEST.json").stat().st_size,
            "sha256": sha256(staging / "BUILD_MANIFEST.json"),
        })

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for item in sorted(staging.rglob("*")):
                if item.is_file():
                    archive.write(item, Path("PlayAtlas") / item.relative_to(staging))
    # Keep a copy outside the archive for CI/artifact browsers.
    (out_dir / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return archive_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, default=None, help="output directory (default: project/dist)")
    parser.add_argument("--no-reports", action="store_true", help="omit existing reports/ from the archive")
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    out_dir = (args.out or project_root / "dist").resolve()
    archive = build(project_root, out_dir, include_reports=not args.no_reports)
    print(f"Portable source archive: {archive}")
    print(f"Manifest: {out_dir / 'BUILD_MANIFEST.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
