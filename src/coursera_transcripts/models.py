from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


@dataclass(frozen=True)
class Course:
    id: str
    name: str
    slug: str


@dataclass(frozen=True)
class Module:
    id: str
    name: str
    slug: str
    position: int


@dataclass(frozen=True)
class Lesson:
    id: str
    name: str
    slug: str
    position: int
    module: Module


@dataclass(frozen=True)
class Lecture:
    id: str
    name: str
    slug: str
    position: int
    content_type: str
    time_commitment: int | None
    optional: bool
    locked: bool
    module: Module | None = None
    lesson: Lesson | None = None


@dataclass(frozen=True)
class CourseCatalog:
    course: Course
    lectures: tuple[Lecture, ...]


class TranscriptStatus(str, Enum):
    DOWNLOADED = "downloaded"
    SKIPPED = "skipped"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass
class TranscriptResult:
    lecture: Lecture
    status: TranscriptStatus
    path: str = ""
    previous_path: str = ""
    error: str = ""


@dataclass
class DownloadStats:
    total: int
    success: int = 0
    skipped: int = 0
    failed: int = 0
    interrupted: int = 0
    stale_archived: int = 0

    def record(self, status: TranscriptStatus) -> None:
        if status is TranscriptStatus.DOWNLOADED:
            self.success += 1
        elif status is TranscriptStatus.SKIPPED:
            self.skipped += 1
        elif status is TranscriptStatus.FAILED:
            self.failed += 1
        elif status is TranscriptStatus.INTERRUPTED:
            self.interrupted += 1

    def as_dict(self) -> dict[str, int]:
        return {
            "success": self.success,
            "skipped": self.skipped,
            "failed": self.failed,
            "interrupted": self.interrupted,
            "stale_archived": self.stale_archived,
            "total": self.total,
        }


@dataclass
class DownloadRun:
    catalog: CourseCatalog
    language: str
    fmt: str
    course_dir: Path
    stats: DownloadStats
    results: list[TranscriptResult]
    interrupted: bool = False
    stale_files_archived: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
