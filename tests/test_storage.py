import tempfile
import unittest
from pathlib import Path

from coursera_transcripts.models import Course, Lecture
from coursera_transcripts.storage import TranscriptStorage, safe_component


class StorageTests(unittest.TestCase):
    def test_sanitizes_unsafe_components(self):
        self.assertEqual(safe_component("../bad/name"), "badname")
        self.assertEqual(safe_component("CON"), "_CON")
        self.assertEqual(safe_component("  ", fallback="fallback"), "fallback")

    def test_disambiguates_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = TranscriptStorage(
                Path(temp_dir), Course("c", "Course", "course"), "en", "txt"
            )
            first = Lecture("id-1", "Same", "same", 1, "lecture", None, False, False)
            second = Lecture("id-2", "Same", "same", 1, "lecture", None, False, False)

            first_path = storage.transcript_path(first)
            second_path = storage.transcript_path(second)

            self.assertNotEqual(first_path, second_path)
            self.assertIn("id-2", second_path.name)

    def test_sanitizes_fallback_value_too(self):
        self.assertEqual(
            safe_component("", fallback="../fallback/name"), "fallbackname"
        )

    def test_rejects_unknown_file_format(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            self.assertRaises(ValueError),
        ):
            TranscriptStorage(
                Path(temp_dir), Course("c", "Course", "course"), "en", "../../bad"
            )


if __name__ == "__main__":
    unittest.main()
