from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
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

from .models import CourseCatalog, DownloadRun, TranscriptResult, TranscriptStatus


class RichDownloadPresenter:
    """Own all terminal rendering for a transcript download run."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    @contextmanager
    def fetching_materials(self) -> Iterator[None]:
        with self.console.status(
            "[bright_cyan]  Fetching course materials…[/bright_cyan]", spinner="dots"
        ):
            yield

    def show_course_overview(
        self,
        catalog: CourseCatalog,
        course_dir: Path,
        language: str,
        fmt: str,
    ) -> None:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim", justify="right")
        table.add_column(style="bold white")
        table.add_row("Course", escape(catalog.course.name))
        table.add_row("Lectures", str(len(catalog.lectures)))
        table.add_row("Language", escape(language.upper()))
        table.add_row("Format", fmt.upper())
        table.add_row("Output", escape(str(course_dir)))
        self.console.print(
            Panel(
                table,
                title="[bold bright_cyan]📋  Course Overview[/bold bright_cyan]",
                border_style="bright_cyan",
                padding=(1, 2),
            )
        )
        self.console.print()

    @contextmanager
    def progress(self, total: int) -> Iterator[Callable[[], None]]:
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
            console=self.console,
            transient=False,
        ) as progress:
            task = progress.add_task("  Downloading transcripts", total=total)
            yield lambda: progress.advance(task)

    def show_no_lectures(self) -> None:
        self.console.print(
            "[yellow]  ⚠  No lecture videos found in this course.[/yellow]"
        )

    def show_partial_manifest(self, course_dir: Path) -> None:
        self.console.print(
            f"[yellow]  ⚠  Partial manifests saved to {escape(str(course_dir))}[/yellow]"
        )

    @staticmethod
    def _result_line(result: TranscriptResult) -> tuple[str, str, str]:
        name = escape(result.lecture.name)
        if result.status is TranscriptStatus.DOWNLOADED:
            return "✔", name, f"[dim]{escape(result.path)}[/dim]"
        if result.status is TranscriptStatus.SKIPPED:
            return "⊘", name, f"[yellow]{escape(result.error)}[/yellow]"
        if result.status is TranscriptStatus.INTERRUPTED:
            return "⚠", name, f"[yellow]{escape(result.error)}[/yellow]"
        return "❌", name, f"[red]{escape(result.error)}[/red]"

    def show_completed_run(self, run: DownloadRun) -> None:
        self.console.print()
        tree = Tree("[bold bright_cyan]📂  Results[/bold bright_cyan]")
        for result in run.results:
            icon, name, detail = self._result_line(result)
            color = (
                "bright_green"
                if icon == "✔"
                else "yellow"
                if icon in {"⊘", "⚠"}
                else "red"
            )
            tree.add(f"[{color}]{icon}[/{color}]  [bold]{name}[/bold]  {detail}")
        self.console.print(tree)

        stats = run.stats
        parts = []
        if stats.success:
            parts.append(f"[bright_green]✔ {stats.success} downloaded[/bright_green]")
        if stats.skipped:
            parts.append(f"[yellow]⊘ {stats.skipped} skipped[/yellow]")
        if stats.failed:
            parts.append(f"[red]✖ {stats.failed} failed[/red]")
        if stats.stale_archived:
            parts.append(f"[dim]♲ {stats.stale_archived} stale files archived[/dim]")
        if not parts:
            parts.append("[dim]No lectures found[/dim]")

        summary = "   ".join(parts)
        summary += f"\n\n[dim]Files and manifests saved to [bold]{escape(str(run.course_dir))}[/bold][/dim]"
        self.console.print()
        self.console.print(
            Panel(
                summary,
                title="[bold bright_cyan]✨  Summary[/bold bright_cyan]",
                border_style="bright_green" if not stats.failed else "yellow",
                padding=(1, 2),
            )
        )
