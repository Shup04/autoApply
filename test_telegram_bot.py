import unittest

import telegram_bot
from telegram_bot import compact_note, flow_text, parse_note_argument, show_record, sort_records_for_user, summary_text, title_fit_score


class TelegramBotTests(unittest.TestCase):
    def test_parse_note_argument_reads_id_and_text(self):
        self.assertEqual(parse_note_argument("12 OA completed"), (12, "OA completed"))

    def test_parse_note_argument_rejects_missing_id(self):
        self.assertEqual(parse_note_argument("OA completed"), (None, None))

    def test_compact_note_truncates_long_text(self):
        note = "x" * 120
        self.assertTrue(compact_note(note).endswith("…"))

    def test_show_record_includes_note(self):
        rendered = show_record(
            {
                "job_id": 7,
                "company": "Hootsuite",
                "title": "Data Engineering Intern",
                "status": "prepared",
                "location": "Vancouver, BC",
                "notes": "Waiting on referral",
                "resume_path": "/tmp/resume.pdf",
                "cover_letter_path": "/tmp/cover.pdf",
                "url": "https://example.com/job",
            }
        )
        self.assertIn("Note: Waiting on referral", rendered)

    def test_summary_text_formats_counts_and_recent_updates(self):
        original_loader = telegram_bot.load_application_statuses
        try:
            telegram_bot.load_application_statuses = lambda: {
                "a": {
                    "job_id": 1,
                    "company": "Hootsuite",
                    "title": "Data Engineering Intern",
                    "status": "prepared",
                    "location": "Vancouver, BC, Canada",
                    "updated_at": "2026-04-15T10:00:00+00:00",
                },
                "b": {
                    "job_id": 2,
                    "company": "IBM",
                    "title": "Software Engineer Intern",
                    "status": "archived",
                    "location": "Durham, NC",
                    "updated_at": "2026-04-15T09:00:00+00:00",
                },
            }
            rendered = summary_text()
            self.assertIn("Status Summary (2 total)", rendered)
            self.assertIn("prepared: 1", rendered)
            self.assertIn("archived: 1", rendered)
            self.assertIn("active: 1", rendered)
            self.assertIn("bc: 1", rendered)
            self.assertIn("us: 0", rendered)
        finally:
            telegram_bot.load_application_statuses = original_loader

    def test_flow_text_formats_funnel_counts(self):
        original_loader = telegram_bot.load_application_statuses
        try:
            telegram_bot.load_application_statuses = lambda: {
                "a": {"status": "prepared", "updated_at": "2026-04-15T10:00:00+00:00"},
                "b": {"status": "applied", "updated_at": "2026-04-15T09:00:00+00:00"},
                "c": {"status": "archived", "updated_at": "2026-04-15T08:00:00+00:00"},
            }
            rendered = flow_text()
            self.assertIn("Job Flow", rendered)
            self.assertIn("all jobs: 3", rendered)
            self.assertIn("active: 2", rendered)
            self.assertIn("prepared: 1", rendered)
            self.assertIn("applied: 1", rendered)
            self.assertIn("archived: 1", rendered)
        finally:
            telegram_bot.load_application_statuses = original_loader

    def test_sort_records_for_user_prefers_bc_then_ab_then_rest(self):
        records = [
            {"job_id": 3, "title": "Software Engineer Intern", "company": "OntarioCo", "location": "Toronto, Ontario, Canada", "updated_at": "2026-04-15T08:00:00+00:00"},
            {"job_id": 2, "title": "Software Engineer Intern", "company": "AlbertaCo", "location": "Calgary, Alberta, Canada", "updated_at": "2026-04-15T08:00:00+00:00"},
            {"job_id": 1, "title": "Software Engineer Intern", "company": "BCCo", "location": "Vancouver, BC, Canada", "updated_at": "2026-04-15T08:00:00+00:00"},
        ]
        ordered = sort_records_for_user(records)
        self.assertEqual([record["job_id"] for record in ordered], [1, 2, 3])

    def test_title_fit_score_prefers_embedded_over_business_analyst(self):
        embedded = title_fit_score({"title": "Embedded Firmware Engineer Intern"})
        analyst = title_fit_score({"title": "Business Analyst Intern"})
        self.assertGreater(embedded, analyst)

    def test_sort_records_for_user_prefers_embedded_within_same_region(self):
        records = [
            {
                "job_id": 1,
                "title": "Software Engineer Intern",
                "company": "GenericCo",
                "location": "Vancouver, BC, Canada",
                "updated_at": "2026-04-15T08:00:00+00:00",
            },
            {
                "job_id": 2,
                "title": "Embedded Firmware Engineer Intern",
                "company": "DeviceCo",
                "location": "Burnaby, BC, Canada",
                "updated_at": "2026-04-15T07:00:00+00:00",
            },
        ]
        ordered = sort_records_for_user(records)
        self.assertEqual([record["job_id"] for record in ordered], [2, 1])


if __name__ == "__main__":
    unittest.main()
