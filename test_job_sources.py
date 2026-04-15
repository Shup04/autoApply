import os
import unittest

from job_sources import CompanyBoardsSource, LinkedInSource
from job_sources import group_jobs_by_source, resolve_source_for_job, resolve_sources
from fetch_descriptions import merge_jobs as merge_described_jobs
from scraper import merge_jobs
from utils import build_job_artifact_label, is_software_coop_role


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

    def test_merge_jobs_dedupes_cross_source_by_fingerprint(self):
        merged = merge_jobs(
            [
                {
                    "source": "symplicity",
                    "url": "https://symplicity.example/job",
                    "fingerprint": "acme:softwareengineerintern",
                    "title": "Software Engineer Intern",
                    "company": "Acme",
                },
            ],
            [
                {
                    "source": "company_boards",
                    "url": "https://company.example/careers/job",
                    "fingerprint": "acme:softwareengineerintern",
                    "title": "Software Engineer Intern",
                    "company": "Acme",
                },
            ],
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "company_boards")

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

    def test_fetch_merge_dedupes_cross_source_by_fingerprint(self):
        merged = merge_described_jobs(
            [
                {
                    "source": "symplicity",
                    "url": "https://symplicity.example/job",
                    "fingerprint": "acme:softwareengineerintern",
                    "full_description": "old",
                },
            ],
            [
                {
                    "source": "company_boards",
                    "url": "https://company.example/careers/job",
                    "fingerprint": "acme:softwareengineerintern",
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

    def test_role_filter_accepts_software_engineering_coops(self):
        self.assertTrue(is_software_coop_role("Software Engineer Intern"))
        self.assertTrue(is_software_coop_role("Backend Developer Co-op"))

    def test_role_filter_rejects_non_engineering_business_roles(self):
        self.assertFalse(is_software_coop_role("Corporate Accountant Co-op"))
        self.assertFalse(is_software_coop_role("Payroll Manager Intern"))

    def test_role_filter_uses_experience_terms(self):
        self.assertFalse(is_software_coop_role("Software Engineer"))

    def test_artifact_label_uses_company_and_title(self):
        label = build_job_artifact_label("Hootsuite", "Software Engineer Co-op")
        self.assertEqual(label, "hootsuite_software_engineer_co_op")

    def test_linkedin_source_uses_conservative_public_defaults(self):
        old_pages = os.environ.get("LINKEDIN_MAX_PAGES_PER_SEARCH")
        old_results = os.environ.get("LINKEDIN_MAX_RESULTS_PER_SEARCH")
        old_delay = os.environ.get("LINKEDIN_REQUEST_DELAY_MS")
        try:
            os.environ.pop("LINKEDIN_MAX_PAGES_PER_SEARCH", None)
            os.environ.pop("LINKEDIN_MAX_RESULTS_PER_SEARCH", None)
            os.environ.pop("LINKEDIN_REQUEST_DELAY_MS", None)
            source = LinkedInSource()
            self.assertEqual(source.max_pages_per_search, 1)
            self.assertEqual(source.max_results_per_search, 15)
            self.assertEqual(source.request_delay_ms, 4000)
        finally:
            if old_pages is None:
                os.environ.pop("LINKEDIN_MAX_PAGES_PER_SEARCH", None)
            else:
                os.environ["LINKEDIN_MAX_PAGES_PER_SEARCH"] = old_pages
            if old_results is None:
                os.environ.pop("LINKEDIN_MAX_RESULTS_PER_SEARCH", None)
            else:
                os.environ["LINKEDIN_MAX_RESULTS_PER_SEARCH"] = old_results
            if old_delay is None:
                os.environ.pop("LINKEDIN_REQUEST_DELAY_MS", None)
            else:
                os.environ["LINKEDIN_REQUEST_DELAY_MS"] = old_delay

    def test_linkedin_source_normalizes_bc_alias(self):
        source = LinkedInSource()
        self.assertEqual(source._normalize_location_or_term("bc"), "British Columbia, Canada")

    def test_linkedin_source_rejects_us_locations(self):
        source = LinkedInSource()
        self.assertFalse(source._matches_location("Durham, NC"))
        self.assertFalse(source._matches_location("Pleasanton, CA"))

    def test_linkedin_source_accepts_canadian_locations(self):
        source = LinkedInSource()
        self.assertTrue(source._matches_location("Vancouver, British Columbia, Canada"))
        self.assertTrue(source._matches_location("Remote, Canada"))

    def test_linkedin_source_allows_env_override_for_request_budget(self):
        old_pages = os.environ.get("LINKEDIN_MAX_PAGES_PER_SEARCH")
        old_results = os.environ.get("LINKEDIN_MAX_RESULTS_PER_SEARCH")
        old_delay = os.environ.get("LINKEDIN_REQUEST_DELAY_MS")
        try:
            os.environ["LINKEDIN_MAX_PAGES_PER_SEARCH"] = "2"
            os.environ["LINKEDIN_MAX_RESULTS_PER_SEARCH"] = "10"
            os.environ["LINKEDIN_REQUEST_DELAY_MS"] = "6500"
            source = LinkedInSource()
            self.assertEqual(source.max_pages_per_search, 2)
            self.assertEqual(source.max_results_per_search, 10)
            self.assertEqual(source.request_delay_ms, 6500)
        finally:
            if old_pages is None:
                os.environ.pop("LINKEDIN_MAX_PAGES_PER_SEARCH", None)
            else:
                os.environ["LINKEDIN_MAX_PAGES_PER_SEARCH"] = old_pages
            if old_results is None:
                os.environ.pop("LINKEDIN_MAX_RESULTS_PER_SEARCH", None)
            else:
                os.environ["LINKEDIN_MAX_RESULTS_PER_SEARCH"] = old_results
            if old_delay is None:
                os.environ.pop("LINKEDIN_REQUEST_DELAY_MS", None)
            else:
                os.environ["LINKEDIN_REQUEST_DELAY_MS"] = old_delay


if __name__ == "__main__":
    unittest.main()
