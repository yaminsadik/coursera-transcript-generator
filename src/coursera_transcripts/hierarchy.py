from __future__ import annotations

from collections.abc import Iterable

from .models import Course, CourseCatalog, Lecture, Lesson, Module


def _linked(data: dict, resource: str) -> list[dict]:
    return data.get("linked", {}).get(resource, [])


def _ordered(resources: list[dict], ids: Iterable[str]) -> list[dict]:
    by_id = {resource["id"]: resource for resource in resources}
    ordered = [by_id[resource_id] for resource_id in ids if resource_id in by_id]
    seen = {resource["id"] for resource in ordered}
    ordered.extend(resource for resource in resources if resource["id"] not in seen)
    return ordered


def build_course_catalog(materials: dict, requested_slug: str) -> CourseCatalog:
    """Turn Coursera's linked response into an explicit course hierarchy."""
    root = materials["elements"][0]
    course = Course(
        id=root["id"],
        name=root.get("name") or requested_slug,
        slug=root.get("slug") or requested_slug,
    )

    raw_modules = _ordered(
        _linked(materials, "onDemandCourseMaterialModules.v1"),
        root.get("moduleIds", []),
    )
    modules: dict[str, Module] = {}
    for position, raw in enumerate(raw_modules, 1):
        modules[raw["id"]] = Module(
            id=raw["id"],
            name=raw.get("name") or raw.get("slug") or raw["id"],
            slug=raw.get("slug") or raw["id"],
            position=position,
        )

    raw_lessons = _linked(materials, "onDemandCourseMaterialLessons.v1")
    lessons_by_id = {lesson["id"]: lesson for lesson in raw_lessons}
    lessons: dict[str, Lesson] = {}
    item_locations: dict[str, tuple[Module, Lesson, int]] = {}

    choices = {
        choice["id"]: choice.get("itemIds", [])
        for choice in _linked(
            materials, "onDemandCourseMaterialPassableItemGroupChoices.v1"
        )
    }
    groups = {
        group["id"]: group.get("passableItemGroupChoiceIds", [])
        for group in _linked(materials, "onDemandCourseMaterialPassableItemGroups.v1")
    }

    for raw_module in raw_modules:
        module = modules[raw_module["id"]]
        for lesson_position, lesson_id in enumerate(raw_module.get("lessonIds", []), 1):
            raw_lesson = lessons_by_id.get(lesson_id)
            if raw_lesson is None:
                continue
            lesson = Lesson(
                id=lesson_id,
                name=raw_lesson.get("name") or raw_lesson.get("slug") or lesson_id,
                slug=raw_lesson.get("slug") or lesson_id,
                position=lesson_position,
                module=module,
            )
            lessons[lesson_id] = lesson

            item_ids: list[str] = []
            for element_id in raw_lesson.get("elementIds", []):
                if element_id in groups:
                    for choice_id in groups[element_id]:
                        item_ids.extend(choices.get(choice_id, []))
                elif element_id in choices:
                    item_ids.extend(choices[element_id])
                else:
                    item_ids.append(element_id)
            for item_position, item_id in enumerate(dict.fromkeys(item_ids), 1):
                item_locations.setdefault(item_id, (module, lesson, item_position))

    raw_items = _linked(materials, "onDemandCourseMaterialItems.v2")
    lectures: list[Lecture] = []
    unassigned_position = 0
    for raw_item in raw_items:
        content_type = raw_item.get("contentSummary", {}).get("typeName", "")
        if content_type.lower() != "lecture":
            continue

        location = item_locations.get(raw_item["id"])
        if location:
            module, lesson, position = location
        else:
            module = modules.get(raw_item.get("moduleId", ""))
            lesson = lessons.get(raw_item.get("lessonId", ""))
            unassigned_position += 1
            position = unassigned_position

        lectures.append(
            Lecture(
                id=raw_item["id"],
                name=raw_item.get("name")
                or raw_item.get("originalName")
                or raw_item["id"],
                slug=raw_item.get("slug") or raw_item["id"],
                position=position,
                content_type=content_type,
                time_commitment=raw_item.get("timeCommitment"),
                optional=bool(raw_item.get("optional", False)),
                locked=bool(raw_item.get("isLocked", False)),
                module=module,
                lesson=lesson,
            )
        )

    lectures.sort(
        key=lambda lecture: (
            lecture.module.position if lecture.module else 10**9,
            lecture.lesson.position if lecture.lesson else 10**9,
            lecture.position,
            lecture.name.casefold(),
        )
    )
    return CourseCatalog(course=course, lectures=tuple(lectures))
