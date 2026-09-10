"""Sun-outage TXT/XLSX reference import regressions."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from sun_outage_reference import (
    SunOutageReferenceEvent,
    calculate_sun_outage_error_metrics,
    load_bundled_sun_outage_references,
    load_sun_outage_reference_files,
    sun_outage_satellite_code,
)


class SunOutageReferenceTests(unittest.TestCase):

    def test_bundled_reference_contains_both_spacecraft_and_stations(self):
        events = load_bundled_sun_outage_references()

        self.assertEqual(len(events), 32)
        self.assertEqual({event.satellite for event in events}, {"AZ1", "AZ2"})
        for satellite in ("AZ1", "AZ2"):
            satellite_events = tuple(
                event for event in events if event.satellite == satellite
            )
            self.assertEqual(len(satellite_events), 16)
            self.assertEqual(
                {event.station_code for event in satellite_events}, {"BAK", "NAX"}
            )

    def test_application_spacecraft_names_match_reference_codes(self):
        self.assertEqual(sun_outage_satellite_code("Azerspace-1"), "AZ1")
        self.assertEqual(sun_outage_satellite_code("Azerspace-2 (IS-38)"), "AZ2")
        self.assertEqual(sun_outage_satellite_code("AZ2"), "AZ2")

    def test_operator_text_schedule_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix="opa-outage-ref-") as directory:
            path = Path(directory) / "AZ2_sun_outage.txt"
            path.write_text(
                "STATCOL_Bak 2026/10/07-08:48:53.000000 "
                "2026/10/07-08:50:16.000000 Bak 1704\n",
                encoding="utf-8",
            )
            events = load_sun_outage_reference_files((path,))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].satellite, "AZ2")
        self.assertEqual(events[0].station_code, "BAK")
        self.assertEqual(events[0].start_utc.isoformat(), "2026-10-07T08:48:53+00:00")
        self.assertEqual(events[0].end_utc.isoformat(), "2026-10-07T08:50:16+00:00")

    def test_error_metrics_are_model_minus_unchanged_reference(self):
        reference_start = datetime(2026, 3, 4, 9, 11, 16, tzinfo=timezone.utc)
        start_errors = (77.527, 94.110, 103.215, 82.125, 131.857)
        end_errors = (-86.349, -103.925, -103.691, -82.924, -132.064)
        pairs = []
        for index, (start_error, end_error) in enumerate(
            zip(start_errors, end_errors)
        ):
            start = reference_start + timedelta(days=index)
            reference = SunOutageReferenceEvent(
                event_id=f"STATCOL_Bak_{index}",
                satellite="AZ2",
                station_code="BAK",
                start_utc=start,
                end_utc=start + timedelta(seconds=300),
                source_name="operator-reference.txt",
            )
            model = SimpleNamespace(
                start_utc=reference.start_utc + timedelta(seconds=start_error),
                end_utc=reference.end_utc + timedelta(seconds=end_error),
            )
            model.peak_utc = model.start_utc + (
                model.end_utc - model.start_utc
            ) / 2
            pairs.append((reference, model))

        metrics = calculate_sun_outage_error_metrics(pairs)

        self.assertEqual(metrics.matched_count, 5)
        self.assertAlmostEqual(metrics.start_bias_seconds, 97.7668, places=4)
        self.assertAlmostEqual(metrics.start_mae_seconds, 97.7668, places=4)
        self.assertAlmostEqual(metrics.end_bias_seconds, -101.7906, places=4)
        self.assertAlmostEqual(metrics.end_mae_seconds, 101.7906, places=4)
        self.assertAlmostEqual(metrics.duration_bias_seconds, -199.5574, places=4)
        self.assertAlmostEqual(metrics.duration_mae_seconds, 199.5574, places=4)
        self.assertAlmostEqual(metrics.maximum_boundary_error_seconds, 132.064)
        self.assertAlmostEqual(metrics.center_bias_seconds, -2.0119, places=4)
        self.assertAlmostEqual(metrics.center_mae_seconds, 2.0119, places=4)
        self.assertAlmostEqual(metrics.duration_mape_percent, 66.5191, places=4)

    def test_zero_matches_do_not_turn_missing_events_into_zero_error(self):
        metrics = calculate_sun_outage_error_metrics(())

        self.assertEqual(metrics.matched_count, 0)
        self.assertIsNone(metrics.start_mae_seconds)
        self.assertIsNone(metrics.end_mae_seconds)
        self.assertIsNone(metrics.duration_mae_seconds)
        self.assertIsNone(metrics.maximum_boundary_error_seconds)
        self.assertIsNone(metrics.center_mae_seconds)
        self.assertIsNone(metrics.duration_mape_percent)

    def test_unnamed_schedule_uses_identified_companion_satellite(self):
        with tempfile.TemporaryDirectory(prefix="opa-outage-ref-") as directory:
            directory = Path(directory)
            unnamed = directory / "Sun_Outage_2026_vernal.txt"
            named = directory / "AZ2_sun_outage_2026_Automnal.txt"
            unnamed.write_text(
                "STATCOL_Bak 2026/03/04-09:10:25.000000 "
                "2026/03/04-09:16:32.000000 Bak 1704\n",
                encoding="utf-8",
            )
            named.write_text(
                "STATCOL_Bak 2026/10/08-08:46:35.000000 "
                "2026/10/08-08:52:00.000000 Bak 1704\n",
                encoding="utf-8",
            )

            events = load_sun_outage_reference_files((unnamed, named))

        spring = next(event for event in events if event.source_name == unnamed.name)
        autumn = next(event for event in events if event.source_name == named.name)
        self.assertEqual(spring.satellite, "AZ2")
        self.assertTrue(spring.satellite_inferred)
        self.assertEqual(autumn.satellite, "AZ2")
        self.assertFalse(autumn.satellite_inferred)


if __name__ == "__main__":
    unittest.main()
