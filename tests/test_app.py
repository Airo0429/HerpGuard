import unittest

from agent import generate_report


class HerpGuardLiteTests(unittest.TestCase):
    def test_report_includes_sections(self):
        output = generate_report(
            {
                "species": "Sulcata Tortoise",
                "temperature": "28",
                "humidity": "40",
                "feeding": "normal",
                "activity": "active",
                "hydration": "normal",
                "observations": "basking regularly",
            }
        )
        self.assertIn("Pet Summary", output)
        self.assertIn("Observations", output)
        self.assertIn("Concerns", output)
        self.assertIn("Recommendations", output)


if __name__ == "__main__":
    unittest.main()
