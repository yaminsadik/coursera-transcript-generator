from __future__ import annotations

import time
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

import requests
from rich.console import Console

COURSERA_BASE = "https://www.coursera.org"
COURSERA_VERSION = "e184c443bbe09b70cbcebf2ba22b3b1067d7e119"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0",
    "Accept": "*/*",
    "Accept-Language": "en",
    "X-Coursera-Application": "ondemand",
    "X-Coursera-Version": COURSERA_VERSION,
    "X-Requested-With": "XMLHttpRequest",
}


def _build_headers(cookie: str | None, referer: str | None = None) -> dict:
    headers = HEADERS.copy()
    if cookie:
        headers["Cookie"] = cookie
    if referer:
        headers["Referer"] = referer
    return headers


class CourseAPI:
    def __init__(self, cookie: str, console: Console | None = None):
        self.cookie = cookie
        self.session = requests.Session()
        self.console = console or Console()

    def _get(
        self,
        url: str,
        referer: str | None = None,
        max_retries: int = 3,
        params: dict | None = None,
        authenticated: bool = True,
    ) -> requests.Response:
        headers = _build_headers(self.cookie if authenticated else None, referer)
        last_exception: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = self.session.get(
                    url, headers=headers, params=params, timeout=30
                )
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                last_exception = e
                if isinstance(e, requests.exceptions.HTTPError):
                    status = e.response.status_code if e.response is not None else None
                    if status not in {408, 429, 500, 502, 503, 504}:
                        raise
                if attempt == max_retries - 1:
                    break
                wait = self._retry_delay(getattr(e, "response", None), attempt)
                self.console.print(
                    f"  [yellow]⟳  Request failed, retrying in {wait}s…[/yellow] [dim]({e})[/dim]"
                )
                time.sleep(wait)
        raise last_exception  # type: ignore[misc]

    @staticmethod
    def _retry_delay(response: requests.Response | None, attempt: int) -> float:
        retry_after = (
            response.headers.get("Retry-After") if response is not None else None
        )
        if retry_after:
            try:
                return max(0, min(float(retry_after), 30))
            except ValueError:
                try:
                    delay = (
                        parsedate_to_datetime(retry_after)
                        - parsedate_to_datetime(response.headers["Date"])
                    ).total_seconds()
                    return max(0, min(delay, 30))
                except (KeyError, TypeError, ValueError):
                    pass
        return float(2**attempt)

    def get_course_materials(self, slug: str) -> dict:
        url = f"{COURSERA_BASE}/api/onDemandCourseMaterials.v2/"
        params = {
            "q": "slug",
            "slug": slug,
            "includes": "modules,lessons,passableItemGroups,passableItemGroupChoices,passableLessonElements,items,tracks,gradePolicy,gradingParameters,embeddedContentMapping",
            "fields": "name,slug,moduleIds,onDemandCourseMaterialModules.v1(name,slug,description,timeCommitment,lessonIds,optional,learningObjectives),onDemandCourseMaterialLessons.v1(name,slug,timeCommitment,elementIds,optional,trackId),onDemandCourseMaterialPassableItemGroups.v1(requiredPassedCount,passableItemGroupChoiceIds,trackId),onDemandCourseMaterialPassableItemGroupChoices.v1(name,description,itemIds),onDemandCourseMaterialPassableLessonElements.v1(gradingWeight,isRequiredForPassing),onDemandCourseMaterialItems.v2(name,originalName,slug,timeCommitment,contentSummary,isLocked,optional,lockableByItem,itemLockedReasonCode,trackId,lockedStatus,itemLockSummary,customDisplayTypenameOverride),onDemandCourseMaterialTracks.v1(passablesCount),onDemandGradingParameters.v1(gradedAssignmentGroups),contentAtomRelations.v1(embeddedContentSourceCourseId,subContainerId)",
            "showLockedItems": "true",
        }
        referer = f"{COURSERA_BASE}/learn/{slug}/home/module/1"
        response = self._get(url, referer, params=params)
        data = response.json()

        if not data.get("elements"):
            raise ValueError(f"Course '{slug}' not found or no data returned")

        return data

    def get_lecture_video(self, course_id: str, item_id: str) -> dict:
        url = (
            f"{COURSERA_BASE}/api/onDemandLectureVideos.v1/"
            f"{course_id}~{item_id}"
            f"?includes=video"
            f"&fields=onDemandVideos.v1(sources%2Csubtitles%2CsubtitlesTxt%2CsubtitlesAssetTags%2CdubbedSources%2CdubbedSubtitlesVtt%2CaudioDescriptionVideoSources)"
            f"%2CdisableSkippingForward%2CstartMs%2CendMs"
        )
        response = self._get(url)
        return response.json()

    def download_subtitle(self, relative_url: str) -> str:
        url = urljoin(COURSERA_BASE, relative_url)
        hostname = (urlparse(url).hostname or "").lower()
        authenticated = hostname == "coursera.org" or hostname.endswith(".coursera.org")
        response = self._get(url, authenticated=authenticated)
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" in content_type:
            raise ValueError("Subtitle request returned an HTML page")
        return response.text
