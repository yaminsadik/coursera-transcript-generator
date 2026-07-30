import unittest

from coursera_transcripts.hierarchy import build_course_catalog


def sample_materials():
    return {
        "elements": [
            {
                "id": "course-1",
                "name": "Test Course",
                "slug": "test-course",
                "moduleIds": ["m1"],
            }
        ],
        "linked": {
            "onDemandCourseMaterialModules.v1": [
                {
                    "id": "m1",
                    "name": "Module One",
                    "slug": "module-one",
                    "lessonIds": ["l1"],
                }
            ],
            "onDemandCourseMaterialLessons.v1": [
                {
                    "id": "l1",
                    "name": "Lesson One",
                    "slug": "lesson-one",
                    "elementIds": ["v1", "g1"],
                }
            ],
            "onDemandCourseMaterialPassableItemGroups.v1": [
                {"id": "g1", "passableItemGroupChoiceIds": ["c1"]}
            ],
            "onDemandCourseMaterialPassableItemGroupChoices.v1": [
                {"id": "c1", "itemIds": ["v2"]}
            ],
            "onDemandCourseMaterialItems.v2": [
                {
                    "id": "v2",
                    "name": "Second",
                    "contentSummary": {"typeName": "lecture"},
                    "isLocked": False,
                },
                {"id": "quiz", "name": "Quiz", "contentSummary": {"typeName": "quiz"}},
                {
                    "id": "v1",
                    "name": "First",
                    "contentSummary": {"typeName": "lecture"},
                    "isLocked": False,
                },
                {
                    "id": "v3",
                    "name": "Unassigned",
                    "contentSummary": {"typeName": "lecture"},
                    "isLocked": True,
                },
            ],
        },
    }


class HierarchyTests(unittest.TestCase):
    def test_resolves_direct_and_grouped_lesson_items_in_course_order(self):
        catalog = build_course_catalog(sample_materials(), "fallback")

        self.assertEqual(catalog.course.name, "Test Course")
        self.assertEqual(
            [lecture.id for lecture in catalog.lectures], ["v1", "v2", "v3"]
        )
        self.assertEqual(catalog.lectures[0].module.name, "Module One")
        self.assertEqual(catalog.lectures[0].lesson.name, "Lesson One")
        self.assertEqual(catalog.lectures[1].position, 2)
        self.assertIsNone(catalog.lectures[2].module)
        self.assertTrue(catalog.lectures[2].locked)


if __name__ == "__main__":
    unittest.main()
