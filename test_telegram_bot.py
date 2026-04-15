import unittest

import telegram_bot
from telegram_bot import compact_note, parse_note_argument, show_record, summary_text


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


if __name__ == "__main__":
    unittest.main()
