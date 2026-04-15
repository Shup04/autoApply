import unittest

from outreach import build_contact_block, compact_company_name, default_contact_role_for_job


class OutreachTests(unittest.TestCase):
    def test_compact_company_name_strips_location_suffix(self):
        self.assertEqual(
            compact_company_name("General Motors of Canada (GMC) - Markham, Ontario, Canada"),
            "General Motors of Canada",
        )

    def test_default_contact_role_prefers_technical_hiring_for_intern_roles(self):
        self.assertEqual(
            default_contact_role_for_job("Software Engineer Intern"),
            "Engineering Manager or Technical Recruiter",
        )

    def test_default_contact_role_falls_back_for_non_intern_roles(self):
        self.assertEqual(default_contact_role_for_job("Software Engineer"), "Hiring Manager")

    def test_build_contact_block_marks_placeholders_incomplete(self):
        contact = build_contact_block(contact_role="Engineering Manager")
        self.assertFalse(contact["complete"])
        self.assertEqual(contact["name"], "Unknown contact")
        self.assertEqual(contact["email"], "unknown@company.com")

    def test_build_contact_block_marks_complete_when_all_fields_present(self):
        contact = build_contact_block(
            contact_name="Jane Doe",
            contact_role="Engineering Manager",
            contact_email="jane@example.com",
        )
        self.assertTrue(contact["complete"])


if __name__ == "__main__":
    unittest.main()
