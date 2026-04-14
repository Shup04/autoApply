import unittest

from job_sources import CompanyBoardsSource
from job_sources import group_jobs_by_source, resolve_source_for_job, resolve_sources
from fetch_descriptions import merge_jobs as merge_described_jobs
from scraper import merge_jobs


class JobSourceTests(unittest.TestCase):
    def test_resolve_sources_defaults_to_registered_sources(self):
        sources = resolve_sources()
        self.assertTrue(any(source.source_name == "symplicity" for source in sources))
        self.assertTrue(any(source.source_name == "linkedin" for source in sources))
        self.assertTrue(any(source.source_name == "jobbank" for source in sources))
        self.assertTrue(any(source.source_name == "company_boards" for source in sources))

    def test_resolve_sources_accepts_linkedin(self):
        sources = resolve_sources(["linkedin"])
        self.assertEqual([source.source_name for source in sources], ["linkedin"])

    def test_resolve_sources_accepts_jobbank(self):
        sources = resolve_sources(["jobbank"])
        self.assertEqual([source.source_name for source in sources], ["jobbank"])

    def test_resolve_sources_accepts_company_boards(self):
        sources = resolve_sources(["company_boards"])
        self.assertEqual([source.source_name for source in sources], ["company_boards"])

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

    def test_resolve_source_for_job_uses_jobbank_when_present(self):
        source = resolve_source_for_job({"title": "A", "company": "X", "source": "jobbank"})
        self.assertEqual(source.source_name, "jobbank")

    def test_resolve_source_for_job_uses_company_boards_when_present(self):
        source = resolve_source_for_job({"title": "A", "company": "X", "source": "company_boards"})
        self.assertEqual(source.source_name, "company_boards")

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

    def test_fetch_merge_preserves_existing_entries_from_other_sources(self):
        merged = merge_described_jobs(
            [
                {"source": "symplicity", "url": "https://example.com/a", "title": "A"},
            ],
            [
                {"source": "linkedin", "url": "https://example.com/b", "title": "B"},
            ],
        )
        self.assertEqual(len(merged), 2)

    def test_fetch_merge_updates_existing_job_with_new_description(self):
        merged = merge_described_jobs(
            [
                {
                    "source": "linkedin",
                    "url": "https://example.com/a",
                    "title": "A",
                    "full_description": "old",
                },
            ],
            [
                {
                    "source": "linkedin",
                    "url": "https://example.com/a",
                    "title": "A",
                    "full_description": "new",
                },
            ],
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["full_description"], "new")

    def test_company_boards_excludes_senior_and_generic_titles(self):
        source = CompanyBoardsSource()
        self.assertTrue(source._is_excluded_title("Senior Security Engineer"))
        self.assertTrue(source._is_excluded_title("General Applications"))
        self.assertFalse(source._is_excluded_title("Software Engineer Intern"))


if __name__ == "__main__":
    unittest.main()
