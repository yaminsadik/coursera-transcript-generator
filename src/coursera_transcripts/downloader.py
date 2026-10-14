from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .api import CourseAPI
from .hierarchy import build_course_catalog
from .models import (
    DownloadRun,
    DownloadStats,
    Lecture,
    TranscriptResult,
    TranscriptStatus,
)
from .presentation import RichDownloadPresenter
from .reporting import build_manifest
from .storage import TranscriptStorage


class TranscriptDownloader:
    """Coordinate Coursera retrieval, hierarchy mapping, and persistence."""

    def __init__(
        self,
        api: CourseAPI,
        output_dir: Path,
        language: str = "en",
        fmt: str = "txt",
        console: Console | None = None,
        presenter: RichDownloadPresenter | None = None,
    ):
        self.api = api
        self.output_dir = output_dir
        self.language = language
        self.fmt = fmt
        self.presenter = presenter or RichDownloadPresenter(console)

    def _get_subtitle_url(self, video_data: dict) -> str | None:
        videos = video_data.get("linked", {}).get("onDemandVideos.v1", [])
        if not videos:
            return None
        subtitle_field = "subtitlesTxt" if self.fmt == "txt" else "subtitles"
        return videos[0].get(subtitle_field, {}).get(self.language)

    def _validate_subtitle(self, text: str) -> None:
        stripped = text.strip()
        if not stripped:
            raise ValueError("Downloaded subtitle is empty")
        lowered = stripped[:500].lower()
        if "<html" in lowered or "<!doctype html" in lowered:
            raise ValueError("Downloaded subtitle appears to be an HTML page")
        if self.fmt == "srt" and "-->" not in stripped:
            raise ValueError("Downloaded subtitle is not valid SRT content")

    def _download_lecture(
        self,
        course_id: str,
        lecture: Lecture,
        storage: TranscriptStorage,
    ) -> TranscriptResult:
        if lecture.locked:
            return TranscriptResult(
                lecture=lecture,
                status=TranscriptStatus.SKIPPED,
                error="Lecture is locked",
            )

        try:
            video_data = self.api.get_lecture_video(course_id, lecture.id)
            subtitle_url = self._get_subtitle_url(video_data)
            if not subtitle_url:
                return TranscriptResult(
                    lecture=lecture,
                    status=TranscriptStatus.SKIPPED,
                    error=f"No {self.language} {self.fmt} subtitles",
                )

            subtitle_text = self.api.download_subtitle(subtitle_url)
            self._validate_subtitle(subtitle_text)
            path = storage.transcript_path(lecture)
            storage.write_transcript(path, subtitle_text)
        # A single malformed lecture must not abort the course report.
        except Exception as exc:  # noqa: BLE001
            return TranscriptResult(
                lecture=lecture,
                status=TranscriptStatus.FAILED,
                error=str(exc),
            )

        return TranscriptResult(
            lecture=lecture,
            status=TranscriptStatus.DOWNLOADED,
            path=storage.relative_path(path),
        )

    @staticmethod
    def _interrupted_results(
        lectures: tuple[Lecture, ...], completed: list[TranscriptResult]
    ) -> list[TranscriptResult]:
        completed_ids = {result.lecture.id for result in completed}
        reason = "Download interrupted before this lecture completed"
        return [
            TranscriptResult(
                lecture=lecture,
                status=TranscriptStatus.INTERRUPTED,
                error=reason,
            )
            for lecture in lectures
            if lecture.id not in completed_ids
        ]

    def fetch_all_transcripts(self, course_slug: str) -> dict[str, int]:
        with self.presenter.fetching_materials():
            materials = self.api.get_course_materials(course_slug)

        catalog = build_course_catalog(materials, course_slug)
        storage = TranscriptStorage(
            self.output_dir, catalog.course, self.language, self.fmt
        )
        self.presenter.show_course_overview(
            catalog, storage.course_dir, self.language, self.fmt
        )

        stats = DownloadStats(total=len(catalog.lectures))
        results: list[TranscriptResult] = []
        interrupted = False

        if catalog.lectures:
            try:
                with self.presenter.progress(stats.total) as advance:
                    for lecture in catalog.lectures:
                        result = self._download_lecture(
                            catalog.course.id, lecture, storage
                        )
                        results.append(result)
                        stats.record(result.status)
                        advance()
            except KeyboardInterrupt:
                interrupted = True
                pending = self._interrupted_results(catalog.lectures, results)
                results.extend(pending)
                for result in pending:
                    stats.record(result.status)
        else:
            self.presenter.show_no_lectures()

        run = DownloadRun(
            catalog=catalog,
            language=self.language,
            fmt=self.fmt,
            course_dir=storage.course_dir,
            stats=stats,
            results=results,
            interrupted=interrupted,
        )

        if not interrupted:
            run.stale_files_archived = storage.archive_stale_files(results)
            stats.stale_archived = len(run.stale_files_archived)

        storage.write_manifests(build_manifest(run))

        if interrupted:
            self.presenter.show_partial_manifest(storage.course_dir)
            raise KeyboardInterrupt

        self.presenter.show_completed_run(run)
        return stats.as_dict()
