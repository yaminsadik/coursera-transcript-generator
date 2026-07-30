from __future__ import annotations

import csv
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Course, Lecture

_INVALID_COMPONENT = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_component(value: str, fallback: str = "unnamed", max_length: int = 120) -> str:
    def clean(candidate: str) -> str:
        candidate = unicodedata.normalize("NFC", candidate)
        candidate = _INVALID_COMPONENT.sub("", candidate)
        candidate = " ".join(candidate.split()).strip(" .")
        return candidate[:max_length].rstrip(" .")

    value = clean(value) or clean(fallback) or "unnamed"
    if value.upper() in _WINDOWS_RESERVED:
        value = f"_{value}"
    return value


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.part")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class TranscriptStorage:
    def __init__(self, output_dir: Path, course: Course, language: str, fmt: str):
        if fmt not in {"txt", "srt"}:
            raise ValueError(f"Unsupported transcript format: {fmt}")
        self.output_dir = output_dir.resolve()
        self.course = course
        self.language = safe_component(language, "unknown", 12)
        self.fmt = fmt
        self.course_dir = self.output_dir / safe_component(course.slug, "course", 32)
        self.course_dir.mkdir(parents=True, exist_ok=True)
        self._assert_contained(self.course_dir)
        self._allocated: set[Path] = set()
        self._manifest_stem = f"manifest.{self.language}.{self.fmt}"
        self._previous_rows = self._load_previous_rows()

    def _assert_contained(self, path: Path) -> None:
        if not path.resolve().is_relative_to(self.output_dir):
            raise ValueError(f"Refusing to write outside output directory: {path}")

    def transcript_path(self, lecture: Lecture) -> Path:
        if lecture.module:
            module_name = safe_component(lecture.module.name, lecture.module.slug, 32)
            module_dir = f"{lecture.module.position:02d}-{module_name}"
        else:
            module_dir = "00-Unassigned module"

        if lecture.lesson:
            lesson_name = safe_component(lecture.lesson.name, lecture.lesson.slug, 32)
            lesson_dir = f"{lecture.lesson.position:02d}-{lesson_name}"
        else:
            lesson_dir = "00-Unassigned lesson"

        video_name = safe_component(lecture.name, lecture.id, 48)
        item_id = safe_component(lecture.id, "item", 16)
        filename = (
            f"{lecture.position:03d}-{video_name}--{item_id}.{self.language}.{self.fmt}"
        )
        path = self.course_dir / module_dir / lesson_dir / filename
        if path in self._allocated:
            item_id = safe_component(lecture.id, "item", 32)
            filename = f"{lecture.position:03d}-{video_name}--{item_id}.{self.language}.{self.fmt}"
            path = path.with_name(filename)
        self._allocated.add(path)
        self._assert_contained(path)
        return path

    def write_transcript(self, path: Path, text: str) -> None:
        self._assert_contained(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, text)

    def relative_path(self, path: Path) -> str:
        return path.relative_to(self.course_dir).as_posix()

    def _load_previous_rows(self) -> list[dict[str, Any]]:
        candidates = [
            self.course_dir / f"{self._manifest_stem}.json",
            self.course_dir / "manifest.json",
        ]
        for path in candidates:
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                continue
            rows = report.get("transcripts", [])
            if rows and (
                rows[0].get("language") != self.language
                or rows[0].get("format") != self.fmt
            ):
                continue
            return [row for row in rows if row.get("path")]
        return []

    def archive_stale_files(self, current_rows: list[dict[str, Any]]) -> list[str]:
        current_by_id = {row["video_id"]: row for row in current_rows}
        stale_paths: set[str] = set()
        for previous in self._previous_rows:
            video_id = previous.get("video_id")
            current = current_by_id.get(video_id)
            if current is None:
                if video_id:
                    stale_paths.add(previous["path"])
            elif (
                current["status"] == "downloaded"
                and current["path"] != previous["path"]
            ):
                stale_paths.add(previous["path"])
            elif current["status"] != "downloaded":
                current["previous_path"] = previous["path"]

        archived: list[str] = []
        archive_root = (
            self.course_dir
            / ".stale"
            / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        )
        for relative_path in sorted(stale_paths):
            path = self.course_dir / relative_path
            self._assert_contained(path)
            if path.is_file() and path.suffix == f".{self.fmt}":
                archive_path = archive_root / relative_path
                self._assert_contained(archive_path)
                archive_path.parent.mkdir(parents=True, exist_ok=True)
                path.replace(archive_path)
                archived.append(relative_path)
        return archived

    def write_manifests(self, report: dict[str, Any]) -> None:
        json_content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        _atomic_write(self.course_dir / f"{self._manifest_stem}.json", json_content)
        _atomic_write(self.course_dir / "manifest.json", json_content)

        rows = report["transcripts"]
        fields = (
            list(rows[0])
            if rows
            else [
                "course_name",
                "course_slug",
                "module_id",
                "module_name",
                "module_slug",
                "module_position",
                "lesson_id",
                "lesson_name",
                "lesson_slug",
                "lesson_position",
                "video_name",
                "video_id",
                "video_slug",
                "video_position",
                "content_type",
                "time_commitment",
                "optional",
                "locked",
                "language",
                "format",
                "path",
                "previous_path",
                "status",
                "error",
            ]
        )
        for csv_path in (
            self.course_dir / f"{self._manifest_stem}.csv",
            self.course_dir / "manifest.csv",
        ):
            temporary = csv_path.with_name(f".{csv_path.name}.{os.getpid()}.part")
            try:
                with temporary.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)
                temporary.replace(csv_path)
            finally:
                temporary.unlink(missing_ok=True)
