import unittest

from job_sources import group_jobs_by_source, resolve_source_for_job, resolve_sources
from scraper import merge_jobs


class JobSourceTests(unittest.TestCase):
    def test_resolve_sources_defaults_to_registered_sources(self):
        sources = resolve_sources()
        self.assertTrue(any(source.source_name == "symplicity" for source in sources))
        self.assertTrue(any(source.source_name == "linkedin" for source in sources))

    def test_resolve_sources_accepts_linkedin(self):
        sources = resolve_sources(["linkedin"])
        self.assertEqual([source.source_name for source in sources], ["linkedin"])

    def test_group_jobs_by_source_defaults_missing_source_to_symplicity(self):
        grouped = group_jobs_by_source(
            [
                {"title": "A", "company": "X"},
                {"title": "B", "company": "Y", "source": "symplicity"},
            ]
        )
        self.assertEqual(len(grouped["symplicity"]), 2)

    def test_resolve_source_for_job_defaults_missing_source_to_symplicity(self):
        source = resolve_source_for_job({"title": "A", "company": "X"})
        self.assertEqual(source.source_name, "symplicity")

    def test_resolve_source_for_job_uses_linkedin_when_present(self):
        source = resolve_source_for_job({"title": "A", "company": "X", "source": "linkedin"})
        self.assertEqual(source.source_name, "linkedin")

    def test_merge_jobs_preserves_existing_entries_from_other_sources(self):
        merged = merge_jobs(
            [
                {"source": "symplicity", "url": "https://example.com/a", "title": "A"},
            ],
            [
                {"source": "linkedin", "url": "https://example.com/b", "title": "B"},
            ],
        )
        self.assertEqual(len(merged), 2)

    def test_merge_jobs_updates_existing_job_with_new_data(self):
        merged = merge_jobs(
            [
                {"source": "linkedin", "url": "https://example.com/a", "title": "Old"},
            ],
            [
                {"source": "linkedin", "url": "https://example.com/a", "title": "New"},
            ],
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["title"], "New")


if __name__ == "__main__":
    unittest.main()
