"""GORDAM detailed-report import regressions."""

from pathlib import Path
import tempfile
import unittest

from gordam import GordamImportError, load_gordam_solution
from satellite_profiles import load_gordam_state_file


class GordamImportTests(unittest.TestCase):

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="opa-gordam-test-")
        self.report_path = Path(self.temporary.name) / "solution.stdout"
        self.report_path.write_text(
            """
Satellite : AZ2
Epoch: Absolute Time 2026/08/24-00:00:00.000000
Total Mass = 2429.353220 Kg
CP SCALE FACTOR = 1.166461
POSITION,VELOCITY (KM,KM/S)
POSITION EAST 0.0
POSITION NORTH 0.0
POSITION RADIAL 42164.0
VELOCITY EAST 3.074
VELOCITY NORTH 0.0
VELOCITY RADIAL 0.0
POSITION X 42164.0 0.0 0.0
POSITION Y 0.0 0.0 0.0
POSITION Z 0.0 0.0 0.0
VELOCITY X 0.0 0.0 0.0
VELOCITY Y 3.074 0.0 0.0
VELOCITY Z 0.0 0.0 0.0
KEPLERIAN ELEMENTS (KM,DEG)
LONGITUDE 45.090493 0.0 0.0
""".strip(),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_detailed_report_imports_source_derived_state(self):
        imported = load_gordam_solution(self.report_path)
        self.assertEqual(imported.satellite, "AZ2")
        self.assertEqual(imported.epoch_utc.isoformat(), "2026-08-24T00:00:00+00:00")
        self.assertAlmostEqual(imported.longitude_deg, 45.090493, places=6)
        self.assertAlmostEqual(imported.mass_kg, 2429.353220, places=6)
        self.assertEqual(len(imported.state_j2000), 6)

    def test_profile_adapter_keeps_provenance(self):
        imported = load_gordam_state_file(self.report_path)
        self.assertEqual(imported["display_name"], "AZ2")
        self.assertIn("solution.stdout", imported["source_description"])
        self.assertAlmostEqual(imported["target_longitude_deg"], 45.090493, places=6)

    def test_compact_summary_is_not_treated_as_a_state(self):
        compact = Path(self.temporary.name) / "gordam_report2.dat"
        compact.write_text("Satellite : AZ2\nEpoch: Absolute Time 2026/08/24-00:00:00.000000\n")
        with self.assertRaises(GordamImportError):
            load_gordam_solution(compact)


if __name__ == "__main__":
    unittest.main()
