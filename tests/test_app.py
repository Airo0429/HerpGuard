import unittest

from app import format_output, parse_input


class HerpGuardAppTests(unittest.TestCase):
    def test_output_includes_required_sections(self):
        data = parse_input(
            """
            species: Bearded dragons
            basking_temperature: 102
            cool_side_temperature: 79
            humidity: 35
            feeding_schedule: daily
            food_intake: normal
            uvb_setup: T5 HO
            uvb_replacement_date: 2026-04-01
            weight: 320
            historical_logs: weekly logs available
            """
        )
        output = format_output(data)
        self.assertIn("Pet Analysis Summary", output)
        self.assertIn("Observations", output)
        self.assertIn("Possible Concerns", output)
        self.assertIn("Recommendations", output)
        self.assertIn("Monitoring Suggestions", output)

    def test_high_risk_terms_trigger_warning(self):
        data = parse_input(
            """
            species: Snakes
            owner_notes: severe lethargy and wheezing observed
            feeding_schedule: weekly
            food_intake: refused
            uvb_setup: none
            uvb_replacement_date: unknown
            weight: 500
            """
        )
        output = format_output(data)
        self.assertIn("- Severity: High Concern", output)
        self.assertIn("Warning", output)
        self.assertIn("exotic veterinarian", output.lower())


if __name__ == "__main__":
    unittest.main()
