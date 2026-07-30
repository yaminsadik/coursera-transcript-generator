import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from rich.console import Console

from coursera_transcripts.api import CourseAPI


class APITests(unittest.TestCase):
    def test_does_not_forward_cookie_authentication_to_external_cdn(self):
        api = CourseAPI("CAUTH=secret", Console(file=io.StringIO()))
        api._get = Mock(return_value=SimpleNamespace(text="subtitle", headers={}))

        api.download_subtitle("https://cdn.example.com/subtitle.txt")

        api._get.assert_called_once_with(
            "https://cdn.example.com/subtitle.txt", authenticated=False
        )

    def test_uses_authentication_for_relative_coursera_url(self):
        api = CourseAPI("CAUTH=secret", Console(file=io.StringIO()))
        api._get = Mock(return_value=SimpleNamespace(text="subtitle", headers={}))

        api.download_subtitle("/subtitle.txt")

        api._get.assert_called_once_with(
            "https://www.coursera.org/subtitle.txt", authenticated=True
        )

    def test_retry_after_is_bounded_and_non_negative(self):
        response = SimpleNamespace(headers={"Retry-After": "-5"})
        self.assertEqual(CourseAPI._retry_delay(response, 0), 0)

    def test_rejects_html_subtitle_response(self):
        api = CourseAPI("CAUTH=secret", Console(file=io.StringIO()))
        api._get = Mock(
            return_value=SimpleNamespace(
                text="<html>login</html>", headers={"Content-Type": "text/html"}
            )
        )

        with self.assertRaisesRegex(ValueError, "HTML"):
            api.download_subtitle("/subtitle.txt")


if __name__ == "__main__":
    unittest.main()
