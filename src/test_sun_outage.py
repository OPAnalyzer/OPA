"""Sun-transit geometry, contact refinement and export regressions."""

from datetime import date, datetime, timezone
import csv
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from earth_orientation import j2000_to_itrs_rotation_from_datetime
from sun_outage import (
    EARTH_SIDEREAL_RATE_RAD_S,
    NOMINAL_GSO_RADIUS_KM,
    SunOutageError,
    SunOutageStation,
    geosynchronous_orbit_from_state,
    half_power_beamwidth_deg,
    predict_sun_outages,
    save_sun_outage_csv,
)


class SunOutageTests(unittest.TestCase):

    def test_below_horizon_slot_and_empty_dates_are_rejected(self):
        for station, dates, message in (
            (SunOutageStation('demo', 'SYNTHETIC', 0, 180), None, 'horizon'),
            (SunOutageStation('demo', 'SYNTHETIC', 0, 0), (), 'candidate'),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(SunOutageError, message):
                predict_sun_outages(year=2026, station=station,
                    satellite_longitude_deg=0, frequency_ghz=11,
                    antenna_diameter_m=3.7, candidate_dates=dates)

    def setUp(self):
        self.station = SunOutageStation(
            "SYNTHETIC-TEST",
            "SYNTHETIC TEST STATION",
            40.4,
            49.9,
            0.0,
        )

    def test_itu_half_power_beamwidth_equation(self):
        expected = 70.0 * 299_792_458.0 / (11.0e9 * 3.7)
        self.assertAlmostEqual(half_power_beamwidth_deg(11.0, 3.7), expected, 12)

    @staticmethod
    def _equatorial_geo_state(epoch, longitude_deg):
        longitude = math.radians(longitude_deg)
        position_ecef = NOMINAL_GSO_RADIUS_KM * np.asarray(
            (math.cos(longitude), math.sin(longitude), 0.0)
        )
        velocity_ecef_axes = np.cross(
            np.asarray((0.0, 0.0, EARTH_SIDEREAL_RATE_RAD_S)),
            position_ecef,
        )
        rotation = j2000_to_itrs_rotation_from_datetime(
            epoch, eop_enabled=False
        )
        return np.concatenate(
            (rotation.T @ position_ecef, rotation.T @ velocity_ecef_axes)
        )

    def test_state_derived_geo_is_anchored_without_reference_calibration(self):
        epoch = datetime(2026, 8, 24, tzinfo=timezone.utc)
        state = self._equatorial_geo_state(epoch, 45.0)
        model = geosynchronous_orbit_from_state(
            state,
            epoch,
            46.0,
            eop_enabled=False,
        )
        position = model.position_ecef(epoch, eop_enabled=False)
        longitude = math.degrees(math.atan2(position[1], position[0]))
        self.assertAlmostEqual(longitude, 46.0, places=9)
        self.assertAlmostEqual(
            float(np.linalg.norm(position)), NOMINAL_GSO_RADIUS_KM, places=5
        )

    def test_state_and_epoch_must_be_supplied_together(self):
        epoch = datetime(2026, 3, 4, tzinfo=timezone.utc)
        state = self._equatorial_geo_state(epoch, 46.0)
        with self.assertRaisesRegex(SunOutageError, "supplied together"):
            predict_sun_outages(
                year=2026,
                station=self.station,
                satellite_longitude_deg=46.0,
                frequency_ghz=11.0,
                antenna_diameter_m=3.7,
                satellite_state_j2000=state,
                candidate_dates=(date(2026, 3, 4),),
                eop_enabled=False,
            )

    def test_prediction_reports_state_derived_spacecraft_geometry(self):
        epoch = datetime(2026, 3, 4, tzinfo=timezone.utc)
        state = self._equatorial_geo_state(epoch, 46.0)
        prediction = predict_sun_outages(
            year=2026,
            station=self.station,
            satellite_longitude_deg=46.0,
            frequency_ghz=11.0,
            antenna_diameter_m=3.7,
            satellite_state_j2000=state,
            satellite_state_epoch_utc=epoch,
            candidate_dates=(date(2026, 3, 4),),
            eop_enabled=False,
        )
        self.assertIn("state-derived", prediction.spacecraft_geometry)
        self.assertIn("audited J2000 state", prediction.method)

    def test_tle_mode_evaluates_spacecraft_position_at_event_time(self):
        position_ecef = NOMINAL_GSO_RADIUS_KM * np.asarray(
            (math.cos(math.radians(46.0)), math.sin(math.radians(46.0)), 0.0)
        )
        epochs = []

        def position_at(_name, epoch, norad_id=None):
            self.assertEqual(norad_id, 39079)
            epochs.append(epoch)
            rotation = j2000_to_itrs_rotation_from_datetime(
                epoch,
                eop_enabled=False,
            )
            return rotation.T @ position_ecef

        tle_epoch = datetime(2026, 3, 4, tzinfo=timezone.utc)
        tle_state = self._equatorial_geo_state(tle_epoch, 46.0)
        with (
            patch("sun_outage.get_satellite_position", side_effect=position_at),
            patch("sun_outage.get_satellite_state", return_value=tle_state),
            patch(
                "sun_outage.get_tle_metadata",
                return_value={"tle_epoch": tle_epoch},
            ),
        ):
            prediction = predict_sun_outages(
                year=2026,
                station=self.station,
                satellite_longitude_deg=46.0,
                frequency_ghz=10.7,
                antenna_diameter_m=2.0,
                satellite_tle_name="AZERSPACE 1",
                satellite_norad_id=39079,
                candidate_dates=(date(2026, 3, 4),),
                eop_enabled=False,
            )
        self.assertGreater(len(epochs), 5)
        self.assertGreater(len({epoch for epoch in epochs}), 5)
        self.assertIn("event-time SGP4", prediction.spacecraft_geometry)
        self.assertIn("SGP4/TLE", prediction.method)

    def test_tle_and_isolated_state_are_mutually_exclusive(self):
        epoch = datetime(2026, 3, 4, tzinfo=timezone.utc)
        state = self._equatorial_geo_state(epoch, 46.0)
        with self.assertRaisesRegex(SunOutageError, "either an event-time TLE"):
            predict_sun_outages(
                year=2026,
                station=self.station,
                satellite_longitude_deg=46.0,
                frequency_ghz=10.7,
                antenna_diameter_m=2.0,
                satellite_state_j2000=state,
                satellite_state_epoch_utc=epoch,
                satellite_tle_name="AZERSPACE 1",
                candidate_dates=(date(2026, 3, 4),),
                eop_enabled=False,
            )

    def test_tle_drift_outside_station_box_uses_station_kept_geometry(self):
        tle_epoch = datetime(2026, 9, 10, tzinfo=timezone.utc)
        tle_state = self._equatorial_geo_state(tle_epoch, 46.0)
        drifted_ecef = NOMINAL_GSO_RADIUS_KM * np.asarray(
            (math.cos(math.radians(76.0)), math.sin(math.radians(76.0)), 0.0)
        )

        def drifted_position(_name, epoch, norad_id=None):
            rotation = j2000_to_itrs_rotation_from_datetime(
                epoch,
                eop_enabled=False,
            )
            return rotation.T @ drifted_ecef

        with (
            patch(
                "sun_outage.get_satellite_position",
                side_effect=drifted_position,
            ),
            patch("sun_outage.get_satellite_state", return_value=tle_state),
            patch(
                "sun_outage.get_tle_metadata",
                return_value={"tle_epoch": tle_epoch},
            ),
        ):
            prediction = predict_sun_outages(
                year=2026,
                station=self.station,
                satellite_longitude_deg=46.0,
                frequency_ghz=10.7,
                antenna_diameter_m=2.0,
                satellite_tle_name="AZERSPACE 1",
                satellite_station_box_half_width_deg=0.1,
                candidate_dates=(date(2026, 3, 4),),
                eop_enabled=False,
        )
        self.assertEqual(len(prediction.events), 1)
        self.assertIn("configured station box", prediction.spacecraft_geometry)

    def test_refined_contacts_enclose_peak(self):
        prediction = predict_sun_outages(
            year=2026,
            station=self.station,
            satellite_longitude_deg=46.0,
            frequency_ghz=11.0,
            antenna_diameter_m=3.7,
            candidate_dates=(date(2026, 3, 3), date(2026, 3, 4), date(2026, 3, 5)),
        )
        self.assertEqual(len(prediction.events), 3)
        closest = min(prediction.events, key=lambda event: event.minimum_separation_deg)
        self.assertEqual(closest.peak_utc.date(), date(2026, 3, 4))
        for event in prediction.events:
            self.assertLess(event.start_utc, event.peak_utc)
            self.assertLess(event.peak_utc, event.end_utc)
            self.assertLessEqual(event.minimum_separation_deg, event.threshold_deg)
            self.assertGreater(event.duration_seconds, 0.0)
            self.assertLess(event.duration_seconds, 3600.0)

    def test_csv_contains_only_prediction_fields(self):
        prediction = predict_sun_outages(
            year=2026,
            station=self.station,
            satellite_longitude_deg=46.0,
            frequency_ghz=11.0,
            antenna_diameter_m=3.7,
            candidate_dates=(date(2026, 3, 4),),
        )
        with tempfile.TemporaryDirectory(prefix="opa-sun-outage-") as directory:
            path = save_sun_outage_csv(
                prediction,
                Path(directory) / "schedule.csv",
            )
            with path.open(newline="", encoding="utf-8-sig") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Station ID"], "SYNTHETIC-TEST")
        self.assertEqual(
            rows[0]["Spacecraft geometry"],
            "fixed nominal Earth-fixed GSO slot (fallback)",
        )
        self.assertEqual(rows[0]["Peak UTC"][:10], "04/03/2026")
        self.assertIn("ITU-R S.1525-1", rows[0]["Method"])


if __name__ == "__main__":
    unittest.main()
