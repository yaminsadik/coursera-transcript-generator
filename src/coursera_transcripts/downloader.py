from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.tree import Tree

from .api import CourseAPI
from .hierarchy import build_course_catalog
from .models import Course, Lecture
from .storage import TranscriptStorage


class TranscriptDownloader:
    def __init__(
        self,
        api: CourseAPI,
        output_dir: Path,
        language: str = "en",
        fmt: str = "txt",
        console: Console | None = None,
    ):
        self.api = api
        self.output_dir = output_dir
        self.language = language
        self.fmt = fmt
        self.console = console or Console()

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

    def _manifest_row(
        self,
        lecture: Lecture,
        catalog_course: Course,
        status: str,
        path: str = "",
        error: str = "",
    ) -> dict:
        return {
            "course_name": catalog_course.name,
            "course_slug": catalog_course.slug,
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
            "language": self.language,
            "format": self.fmt,
            "path": path,
            "previous_path": "",
            "status": status,
            "error": error,
        }

    def fetch_all_transcripts(self, course_slug: str) -> dict:
        c = self.console
        with c.status(
            "[bright_cyan]  Fetching course materials…[/bright_cyan]", spinner="dots"
        ):
            materials = self.api.get_course_materials(course_slug)

        catalog = build_course_catalog(materials, course_slug)
        storage = TranscriptStorage(
            self.output_dir, catalog.course, self.language, self.fmt
        )

        info_table = Table.grid(padding=(0, 2))
        info_table.add_column(style="dim", justify="right")
        info_table.add_column(style="bold white")
        info_table.add_row("Course", escape(catalog.course.name))
        info_table.add_row("Lectures", str(len(catalog.lectures)))
        info_table.add_row("Language", escape(self.language.upper()))
        info_table.add_row("Format", self.fmt.upper())
        info_table.add_row("Output", escape(str(storage.course_dir)))
        c.print(
            Panel(
                info_table,
                title="[bold bright_cyan]📋  Course Overview[/bold bright_cyan]",
                border_style="bright_cyan",
                padding=(1, 2),
            )
        )
        c.print()

        stats = {
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "interrupted": 0,
            "stale_archived": 0,
            "total": len(catalog.lectures),
        }
        results: list[tuple[str, str, str]] = []
        manifest_rows: list[dict] = []
        interrupted = False

        if catalog.lectures:
            try:
                with Progress(
                    SpinnerColumn(style="bright_cyan"),
                    TextColumn("[bold]{task.description}[/bold]"),
                    BarColumn(
                        bar_width=30,
                        style="dim white",
                        complete_style="bright_cyan",
                        finished_style="bright_green",
                    ),
                    MofNCompleteColumn(),
                    TextColumn("•"),
                    TimeElapsedColumn(),
                    console=c,
                    transient=False,
                ) as progress:
                    task = progress.add_task(
                        "  Downloading transcripts", total=stats["total"]
                    )
                    for lecture in catalog.lectures:
                        display_name = escape(lecture.name)

                        if lecture.locked:
                            reason = "Lecture is locked"
                            stats["skipped"] += 1
                            results.append(
                                ("⊘", display_name, f"[yellow]{reason}[/yellow]")
                            )
                            manifest_rows.append(
                                self._manifest_row(
                                    lecture, catalog.course, "skipped", error=reason
                                )
                            )
                            progress.advance(task)
                            continue

                        try:
                            video_data = self.api.get_lecture_video(
                                catalog.course.id, lecture.id
                            )
                            subtitle_url = self._get_subtitle_url(video_data)
                            if not subtitle_url:
                                reason = f"No {self.language} {self.fmt} subtitles"
                                stats["skipped"] += 1
                                results.append(
                                    (
                                        "⊘",
                                        display_name,
                                        f"[yellow]{escape(reason)}[/yellow]",
                                    )
                                )
                                manifest_rows.append(
                                    self._manifest_row(
                                        lecture, catalog.course, "skipped", error=reason
                                    )
                                )
                                progress.advance(task)
                                continue

                            subtitle_text = self.api.download_subtitle(subtitle_url)
                            self._validate_subtitle(subtitle_text)
                            path = storage.transcript_path(lecture)
                            storage.write_transcript(path, subtitle_text)
                            relative_path = storage.relative_path(path)
                        # A single malformed lecture must not abort the course report.
                        except Exception as exc:  # noqa: BLE001
                            error = str(exc)
                            stats["failed"] += 1
                            results.append(
                                ("❌", display_name, f"[red]{escape(error)}[/red]")
                            )
                            manifest_rows.append(
                                self._manifest_row(
                                    lecture, catalog.course, "failed", error=error
                                )
                            )
                        else:
                            stats["success"] += 1
                            results.append(
                                (
                                    "✔",
                                    display_name,
                                    f"[dim]{escape(relative_path)}[/dim]",
                                )
                            )
                            manifest_rows.append(
                                self._manifest_row(
                                    lecture,
                                    catalog.course,
                                    "downloaded",
                                    path=relative_path,
                                )
                            )
                        progress.advance(task)
            except KeyboardInterrupt:
                interrupted = True
                processed_ids = {row["video_id"] for row in manifest_rows}
                for lecture in catalog.lectures:
                    if lecture.id in processed_ids:
                        continue
                    reason = "Download interrupted before this lecture completed"
                    stats["interrupted"] += 1
                    results.append(
                        ("⚠", escape(lecture.name), f"[yellow]{reason}[/yellow]")
                    )
                    manifest_rows.append(
                        self._manifest_row(
                            lecture, catalog.course, "interrupted", error=reason
                        )
                    )
        else:
            c.print("[yellow]  ⚠  No lecture videos found in this course.[/yellow]")

        report = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run": {
                "language": self.language,
                "format": self.fmt,
                "interrupted": interrupted,
            },
            "course": {
                "id": catalog.course.id,
                "name": catalog.course.name,
                "slug": catalog.course.slug,
            },
            "summary": stats,
            "transcripts": manifest_rows,
        }
        storage.write_manifests(report)
        if not interrupted:
            archived = storage.archive_stale_files(manifest_rows)
            stats["stale_archived"] = len(archived)
            report["stale_files_archived"] = archived
            storage.write_manifests(report)

        if interrupted:
            c.print(
                f"[yellow]  ⚠  Partial manifests saved to {escape(str(storage.course_dir))}[/yellow]"
            )
            raise KeyboardInterrupt

        c.print()
        tree = Tree("[bold bright_cyan]📂  Results[/bold bright_cyan]")
        for icon, name, detail in results:
            color = (
                "bright_green" if icon == "✔" else "yellow" if icon == "⊘" else "red"
            )
            tree.add(f"[{color}]{icon}[/{color}]  [bold]{name}[/bold]  {detail}")
        c.print(tree)

        summary_parts = []
        if stats["success"]:
            summary_parts.append(
                f"[bright_green]✔ {stats['success']} downloaded[/bright_green]"
            )
        if stats["skipped"]:
            summary_parts.append(f"[yellow]⊘ {stats['skipped']} skipped[/yellow]")
        if stats["failed"]:
            summary_parts.append(f"[red]✖ {stats['failed']} failed[/red]")
        if stats["stale_archived"]:
            summary_parts.append(
                f"[dim]♲ {stats['stale_archived']} stale files archived[/dim]"
            )
        if not summary_parts:
            summary_parts.append("[dim]No lectures found[/dim]")
        summary_text = "   ".join(summary_parts)
        summary_text += f"\n\n[dim]Files and manifests saved to [bold]{escape(str(storage.course_dir))}[/bold][/dim]"
        c.print()
        c.print(
            Panel(
                summary_text,
                title="[bold bright_cyan]✨  Summary[/bold bright_cyan]",
                border_style="bright_green" if not stats["failed"] else "yellow",
                padding=(1, 2),
            )
        )
        return stats
