import unittest

from job_sources import group_jobs_by_source, resolve_source_for_job, resolve_sources


class JobSourceTests(unittest.TestCase):
    def test_resolve_sources_defaults_to_registered_sources(self):
        sources = resolve_sources()
        self.assertTrue(any(source.source_name == "symplicity" for source in sources))

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


if __name__ == "__main__":
    unittest.main()
