import unittest

import manage_jobs


class ManageJobsTests(unittest.TestCase):
    def test_add_manual_job_creates_manual_record(self):
        captured = {}
        original_upsert = manage_jobs.upsert_application_record
        try:
            def fake_upsert(job, status, **extra):
                captured["job"] = job
                captured["status"] = status
                captured["extra"] = extra
                return {
                    "job_id": 123,
                    "status": status,
                    "company": job["company"],
                    "title": job["title"],
                }

            manage_jobs.upsert_application_record = fake_upsert
            record = manage_jobs.add_manual_job(
                "Embedded Software Intern",
                "AMD",
                "applied",
                location="Markham, Ontario, Canada",
                url="https://example.com/job",
                notes="Applied before bot existed",
            )
            self.assertEqual(record["job_id"], 123)
            self.assertEqual(captured["job"]["source"], "manual")
            self.assertEqual(captured["job"]["location"], "Markham, Ontario, Canada")
            self.assertTrue(captured["extra"]["manual_entry"])
            self.assertEqual(captured["extra"]["notes"], "Applied before bot existed")
        finally:
            manage_jobs.upsert_application_record = original_upsert


if __name__ == "__main__":
    unittest.main()
