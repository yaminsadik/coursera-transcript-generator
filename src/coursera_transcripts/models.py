from __future__ import annotations

from dataclasses import dataclass


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
