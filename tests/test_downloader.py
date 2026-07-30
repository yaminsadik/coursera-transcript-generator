import io
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from rich.console import Console
from test_hierarchy import sample_materials

from coursera_transcripts.downloader import TranscriptDownloader


class FakeAPI:
    def __init__(
        self,
        missing=None,
        interrupt_on=None,
        content=None,
        excluded=None,
        fail_on=None,
    ):
        self.missing = set(missing or [])
        self.interrupt_on = interrupt_on
        self.content = content
        self.excluded = set(excluded or [])
        self.fail_on = set(fail_on or [])

    def get_course_materials(self, slug):
        materials = deepcopy(sample_materials())
        items = materials["linked"]["onDemandCourseMaterialItems.v2"]
        materials["linked"]["onDemandCourseMaterialItems.v2"] = [
            item for item in items if item["id"] not in self.excluded
        ]
        return materials

    def get_lecture_video(self, course_id, item_id):
        if item_id == self.interrupt_on:
            raise KeyboardInterrupt
        if item_id in self.fail_on:
            raise RuntimeError("simulated video API failure")
        subtitles = {} if item_id in self.missing else {"en": f"/{item_id}.txt"}
        return {
            "linked": {
                "onDemandVideos.v1": [
                    {"subtitlesTxt": subtitles, "subtitles": subtitles}
                ]
            }
        }

    def download_subtitle(self, url):
        return self.content if self.content is not None else f"Transcript from {url}\n"


class DownloaderTests(unittest.TestCase):
    def test_writes_hierarchical_transcripts_and_manifests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            console = Console(file=io.StringIO(), force_terminal=False)
            downloader = TranscriptDownloader(
                FakeAPI(), Path(temp_dir), console=console
            )

            stats = downloader.fetch_all_transcripts("test-course")

            self.assertEqual(
                stats,
                {
                    "success": 2,
                    "skipped": 1,
                    "failed": 0,
                    "interrupted": 0,
                    "stale_archived": 0,
                    "total": 3,
                },
            )
            course_dir = Path(temp_dir) / "test-course"
            first = (
                course_dir / "01-Module One" / "01-Lesson One" / "001-First--v1.en.txt"
            )
            second = (
                course_dir / "01-Module One" / "01-Lesson One" / "002-Second--v2.en.txt"
            )
            self.assertEqual(
                first.read_text(encoding="utf-8"), "Transcript from /v1.txt\n"
            )
            self.assertTrue(second.is_file())

            manifest = json.loads(
                (course_dir / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["summary"], stats)
            self.assertEqual(manifest["transcripts"][0]["module_name"], "Module One")
            self.assertEqual(manifest["transcripts"][0]["lesson_name"], "Lesson One")
            self.assertEqual(manifest["transcripts"][2]["status"], "skipped")
            self.assertTrue((course_dir / "manifest.csv").is_file())
            self.assertTrue((course_dir / "manifest.en.txt.json").is_file())

    def test_rejects_empty_or_html_transcript_content(self):
        for content in ("", "<!doctype html><html>login</html>"):
            with (
                self.subTest(content=content),
                tempfile.TemporaryDirectory() as temp_dir,
            ):
                console = Console(file=io.StringIO(), force_terminal=False)
                downloader = TranscriptDownloader(
                    FakeAPI(content=content), Path(temp_dir), console=console
                )

                stats = downloader.fetch_all_transcripts("test-course")

                self.assertEqual(stats["failed"], 2)
                self.assertEqual(stats["success"], 0)

    def test_removes_only_stale_files_from_same_language_and_format(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            console = Console(file=io.StringIO(), force_terminal=False)
            first_run = TranscriptDownloader(FakeAPI(), Path(temp_dir), console=console)
            first_run.fetch_all_transcripts("test-course")
            stale_path = (
                Path(temp_dir)
                / "test-course"
                / "01-Module One"
                / "01-Lesson One"
                / "002-Second--v2.en.txt"
            )
            self.assertTrue(stale_path.exists())

            second_run = TranscriptDownloader(
                FakeAPI(excluded={"v2"}), Path(temp_dir), console=console
            )
            stats = second_run.fetch_all_transcripts("test-course")

            self.assertFalse(stale_path.exists())
            self.assertEqual(stats["stale_archived"], 1)
            archived = list(
                (Path(temp_dir) / "test-course" / ".stale").rglob(stale_path.name)
            )
            self.assertEqual(len(archived), 1)

    def test_preserves_previous_file_when_refresh_has_no_subtitle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            console = Console(file=io.StringIO(), force_terminal=False)
            TranscriptDownloader(
                FakeAPI(), Path(temp_dir), console=console
            ).fetch_all_transcripts("test-course")
            previous_path = (
                Path(temp_dir)
                / "test-course"
                / "01-Module One"
                / "01-Lesson One"
                / "002-Second--v2.en.txt"
            )

            stats = TranscriptDownloader(
                FakeAPI(missing={"v2"}), Path(temp_dir), console=console
            ).fetch_all_transcripts("test-course")

            self.assertTrue(previous_path.exists())
            self.assertEqual(stats["stale_archived"], 0)
            manifest = json.loads(
                (Path(temp_dir) / "test-course" / "manifest.en.txt.json").read_text()
            )
            second_row = next(
                row for row in manifest["transcripts"] if row["video_id"] == "v2"
            )
            self.assertEqual(
                second_row["previous_path"],
                "01-Module One/01-Lesson One/002-Second--v2.en.txt",
            )

    def test_writes_partial_manifest_before_propagating_interrupt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            console = Console(file=io.StringIO(), force_terminal=False)
            downloader = TranscriptDownloader(
                FakeAPI(interrupt_on="v2"), Path(temp_dir), console=console
            )

            with self.assertRaises(KeyboardInterrupt):
                downloader.fetch_all_transcripts("test-course")

            manifest_path = Path(temp_dir) / "test-course" / "manifest.en.txt.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["run"]["interrupted"])
            self.assertEqual(manifest["summary"]["success"], 1)
            self.assertEqual(manifest["summary"]["interrupted"], 2)
            self.assertEqual(len(manifest["transcripts"]), 3)

    def test_validates_and_writes_srt_content(self):
        content = "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            console = Console(file=io.StringIO(), force_terminal=False)
            downloader = TranscriptDownloader(
                FakeAPI(content=content), Path(temp_dir), fmt="srt", console=console
            )

            stats = downloader.fetch_all_transcripts("test-course")

            self.assertEqual(stats["success"], 2)
            scoped_manifest = Path(temp_dir) / "test-course" / "manifest.en.srt.json"
            self.assertTrue(scoped_manifest.is_file())

    def test_txt_and_srt_outputs_coexist(self):
        srt_content = "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            console = Console(file=io.StringIO(), force_terminal=False)
            TranscriptDownloader(
                FakeAPI(), Path(temp_dir), console=console
            ).fetch_all_transcripts("test-course")
            TranscriptDownloader(
                FakeAPI(content=srt_content),
                Path(temp_dir),
                fmt="srt",
                console=console,
            ).fetch_all_transcripts("test-course")

            course_dir = Path(temp_dir) / "test-course"
            self.assertTrue(list(course_dir.rglob("*.en.txt")))
            self.assertTrue(list(course_dir.rglob("*.en.srt")))
            self.assertTrue((course_dir / "manifest.en.txt.json").is_file())
            self.assertTrue((course_dir / "manifest.en.srt.json").is_file())

    def test_empty_course_still_writes_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            console = Console(file=io.StringIO(), force_terminal=False)
            stats = TranscriptDownloader(
                FakeAPI(excluded={"v1", "v2", "v3"}),
                Path(temp_dir),
                console=console,
            ).fetch_all_transcripts("test-course")

            self.assertEqual(stats["total"], 0)
            manifest = json.loads(
                (Path(temp_dir) / "test-course" / "manifest.json").read_text()
            )
            self.assertEqual(manifest["transcripts"], [])

    def test_video_failure_is_reported_without_aborting_other_lectures(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            console = Console(file=io.StringIO(), force_terminal=False)
            stats = TranscriptDownloader(
                FakeAPI(fail_on={"v2"}), Path(temp_dir), console=console
            ).fetch_all_transcripts("test-course")

            self.assertEqual(stats["success"], 1)
            self.assertEqual(stats["failed"], 1)
            manifest = json.loads(
                (Path(temp_dir) / "test-course" / "manifest.json").read_text()
            )
            failed = next(
                row for row in manifest["transcripts"] if row["status"] == "failed"
            )
            self.assertEqual(failed["video_id"], "v2")


if __name__ == "__main__":
    unittest.main()
