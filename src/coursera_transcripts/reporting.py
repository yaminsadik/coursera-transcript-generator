from __future__ import annotations

from typing import Any

from .models import Course, DownloadRun, Lecture, TranscriptResult

MANIFEST_FIELDS = (
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
)


def _manifest_row(
    course: Course,
    lecture: Lecture,
    result: TranscriptResult,
    language: str,
    fmt: str,
) -> dict[str, Any]:
    return {
        "course_name": course.name,
        "course_slug": course.slug,
        "module_id": lecture.module.id if lecture.module else "",
        "module_name": lecture.module.name if lecture.module else "",
        "module_slug": lecture.module.slug if lecture.module else "",
        "module_position": lecture.module.position if lecture.module else "",
        "lesson_id": lecture.lesson.id if lecture.lesson else "",
        "lesson_name": lecture.lesson.name if lecture.lesson else "",
        "lesson_slug": lecture.lesson.slug if lecture.lesson else "",
        "lesson_position": lecture.lesson.position if lecture.lesson else "",
        "video_name": lecture.name,
        "video_id": lecture.id,
        "video_slug": lecture.slug,
        "video_position": lecture.position,
        "content_type": lecture.content_type,
        "time_commitment": lecture.time_commitment
        if lecture.time_commitment is not None
        else "",
        "optional": lecture.optional,
        "locked": lecture.locked,
        "language": language,
        "format": fmt,
        "path": result.path,
        "previous_path": result.previous_path,
        "status": result.status.value,
        "error": result.error,
    }


def build_manifest(run: DownloadRun) -> dict[str, Any]:
    course = run.catalog.course
    return {
        "schema_version": 1,
        "generated_at": run.generated_at.isoformat(),
        "run": {
            "language": run.language,
            "format": run.fmt,
            "interrupted": run.interrupted,
        },
        "course": {"id": course.id, "name": course.name, "slug": course.slug},
        "summary": run.stats.as_dict(),
        "stale_files_archived": run.stale_files_archived,
        "transcripts": [
            _manifest_row(course, result.lecture, result, run.language, run.fmt)
            for result in run.results
        ],
    }
