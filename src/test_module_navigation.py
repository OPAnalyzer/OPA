"""Regression coverage for the current two-module application shell."""

import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from app_version import APP_VERSION
from gui.main_window import MainWindow


class ModuleNavigationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="opa-nav-test-")
        self.window = MainWindow(
            application_config_path=Path(self.temporary.name) / "config.json"
        )
        self.window.timer.stop()
        self.window.localization_refresh_timer.stop()

    def tearDown(self):
        self.window.close()
        self.application.processEvents()
        self.temporary.cleanup()

    def test_top_level_modules_and_legacy_page_mapping(self):
        self.assertEqual(
            [
                self.window.module_tabs.tabBar().tabData(index)
                for index in range(self.window.module_tabs.count())
            ],
            ["PROPAGATION", "ECLIPSE"],
        )
        inner_labels = [
            self.window.tabs.tabText(index)
            for index in range(self.window.tabs.count())
        ]
        self.assertEqual(inner_labels[:3], [
            "LIVE COORDINATES", "PERTURBATION", "ORBITAL VIEW"
        ])
        self.assertIn(inner_labels[3], {"SETTINGS", "SYSTEM / VALIDATION"})
        self.assertEqual(inner_labels[4:], [
            "REFERENCE LAB", "PROPAGATION", "GEO OPERATIONS"
        ])
        self.assertIs(
            self.window.module_tabs.widget(self.window.eclipse_module_index),
            self.window.eclipse_page,
        )
        self.assertEqual(
            [
                self.window.eclipse_workspace_tabs.tabText(index)
                for index in range(self.window.eclipse_workspace_tabs.count())
            ],
            ["ECLIPSE PREDICTION", "SUN OUTAGE"],
        )
        self.assertGreaterEqual(self.window.sun_outage_station_combo.count(), 1)
        self.assertEqual(len(self.window.sun_outage_reference_events), 32)
        self.assertEqual(
            {event.satellite for event in self.window.sun_outage_reference_events},
            {"AZ1", "AZ2"},
        )

    def test_navigation_routes_nested_and_top_level_pages(self):
        self.assertTrue(self.window.select_tab_by_label("REFERENCE LAB"))
        self.assertEqual(
            self.window.module_tabs.currentIndex(),
            self.window.propagation_module_index,
        )
        self.assertEqual(
            self.window.tabs.tabText(self.window.tabs.currentIndex()),
            "REFERENCE LAB",
        )

        self.assertTrue(self.window.select_tab_by_label("ECLIPSE"))
        self.assertEqual(
            self.window.module_tabs.currentIndex(),
            self.window.eclipse_module_index,
        )
        self.assertFalse(self.window.select_tab_by_label("ORBIT DETERMINATION"))
        self.assertFalse(self.window.select_module_by_label("ORBIT DETERMINATION"))

        self.window.open_integrity_page()
        self.assertEqual(
            self.window.module_tabs.currentIndex(),
            self.window.propagation_module_index,
        )
        self.assertEqual(
            self.window.tabs.currentIndex(),
            self.window.integrity_tab_index,
        )

    def test_sun_outage_changed_input_and_late_logout_result(self):
        self.window.sun_outage_prediction = object()
        self.window.sun_outage_table.setRowCount(1)
        self.window.sun_outage_export_button.setEnabled(True)
        self.window.sun_outage_frequency.setValue(12)
        self.assertIsNone(self.window.sun_outage_prediction)
        self.assertEqual(self.window.sun_outage_table.rowCount(), 0)
        self.assertFalse(self.window.sun_outage_export_button.isEnabled())
        self.window._sun_outage_accept_result = True
        self.window.logout_admin_session()
        self.window.finish_sun_outage_prediction(object())
        self.assertIsNone(self.window.sun_outage_prediction)

    def test_sun_outage_link_preset_is_locked_until_checked(self):
        self.assertAlmostEqual(self.window.sun_outage_frequency.value(), 10.7)
        self.assertAlmostEqual(
            self.window.sun_outage_antenna_diameter.value(),
            2.0,
        )
        self.assertFalse(self.window.sun_outage_frequency.isEnabled())
        self.assertFalse(self.window.sun_outage_antenna_diameter.isEnabled())
        self.window.sun_outage_edit_link_parameters.setChecked(True)
        self.assertTrue(self.window.sun_outage_frequency.isEnabled())
        self.assertTrue(self.window.sun_outage_antenna_diameter.isEnabled())

    def test_sun_outage_profiles_with_same_target_use_distinct_references(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from unittest.mock import patch
        original = self.window.active_profile
        specs = [SimpleNamespace(satellite="DEMO ALPHA", nominal_longitude_deg=24.0),
                 SimpleNamespace(satellite="DEMO BETA", nominal_longitude_deg=75.0)]
        with patch("gui.main_window.available_eclipse_reference_specs", return_value=specs):
            for name, slot in (("DEMO ALPHA", 24.0), ("DEMO BETA", 75.0)):
                self.window.active_profile = replace(original, display_name=name,
                    profile_id=name.lower().replace(" ", "-"), target_longitude_deg=12.0)
                self.window.refresh_sun_outage_profile()
                self.assertEqual(self.window.sun_outage_satellite_longitude.value(), slot)
                self.assertTrue(self.window._sun_outage_slot_valid)
        self.window.active_profile = original
        self.window.refresh_sun_outage_profile()

    def test_sun_outage_reference_errors_use_matched_source_times(self):
        from datetime import datetime, timedelta, timezone
        from sun_outage import SunOutageEvent, SunOutagePrediction, SunOutageStation
        from sun_outage_reference import SunOutageReferenceEvent

        self.window.sun_outage_year.setValue(2026)
        selected = self.window._sun_outage_station_by_key[
            self.window.sun_outage_station_combo.currentData()
        ]
        identity = f"{selected.station_id} {selected.name}".upper()
        station_code = "BAK" if "BAK" in identity else (
            "NAX" if "NAX" in identity else "UNKNOWN"
        )
        reference_start = datetime(2026, 3, 4, 9, 10, 25, tzinfo=timezone.utc)
        reference_end = datetime(2026, 3, 4, 9, 16, 32, tzinfo=timezone.utc)
        reference = SunOutageReferenceEvent(
            event_id="STATCOL_TEST",
            satellite="",
            station_code=station_code,
            start_utc=reference_start,
            end_utc=reference_end,
            source_name="operator-reference.txt",
        )
        self.window.sun_outage_reference_events = (reference,)
        self.window.sun_outage_reference_files = (reference.source_name,)

        self.window.update_sun_outage_reference_comparison()
        self.assertEqual(
            self.window.sun_outage_reference_table.item(0, 15).text(),
            "AWAITING MODEL RUN",
        )
        self.assertEqual(
            self.window.sun_outage_error_labels["start_mae_seconds"].text(),
            "CALCULATE FIRST",
        )

        model_start = reference_start + timedelta(seconds=77.5)
        model_end = reference_end - timedelta(seconds=86.3)
        station = SunOutageStation(
            station_id=selected.station_id,
            name=selected.name,
            latitude_deg=selected.latitude_deg,
            longitude_deg=selected.longitude_deg,
            height_km=selected.height_km,
        )
        model_event = SunOutageEvent(
            start_utc=model_start,
            peak_utc=model_start + (model_end - model_start) / 2,
            end_utc=model_end,
            minimum_separation_deg=0.1,
            threshold_deg=0.4,
            sun_angular_diameter_deg=0.5,
            beamwidth_3db_deg=0.3,
        )
        self.window.sun_outage_prediction = SunOutagePrediction(
            year=2026,
            station=station,
            satellite_longitude_deg=45.0,
            frequency_ghz=11.0,
            antenna_diameter_m=6.0,
            beamwidth_3db_deg=0.3,
            events=(model_event,),
        )
        self.window.update_sun_outage_reference_comparison()

        self.assertEqual(
            self.window.sun_outage_reference_table.item(0, 10).text(),
            "-4.4 s  ·  -0.07 min",
        )
        self.assertEqual(
            self.window.sun_outage_reference_table.item(0, 11).text(),
            "+77.5 s  ·  +1.29 min",
        )
        self.assertEqual(
            self.window.sun_outage_reference_table.item(0, 12).text(),
            "-86.3 s  ·  -1.44 min",
        )
        self.assertEqual(
            self.window.sun_outage_reference_table.item(0, 13).text(),
            "-163.8 s  ·  -2.73 min",
        )
        self.assertEqual(
            self.window.sun_outage_reference_table.item(0, 14).text(), "-44.6 %"
        )
        self.assertEqual(
            self.window.sun_outage_error_labels["start_mae_seconds"].text(),
            "77.5 s  ·  1.29 min",
        )
        self.assertEqual(
            self.window.sun_outage_error_labels["center_mae_seconds"].text(),
            "4.4 s  ·  0.07 min",
        )
        self.assertEqual(
            self.window.sun_outage_error_labels["matched_count"].text(), "1"
        )

    def test_sun_outage_falls_back_to_state_longitude(self):
        from dataclasses import replace
        from datetime import datetime, timezone
        from unittest.mock import patch
        import numpy as np
        from earth_orientation import j2000_to_itrs_rotation_from_datetime
        original = self.window.active_profile
        epoch = datetime(2030, 1, 1, tzinfo=timezone.utc)
        angle = np.radians(32.0)
        rotation = j2000_to_itrs_rotation_from_datetime(epoch)
        position = rotation.T @ np.array([42164*np.cos(angle), 42164*np.sin(angle), 0])
        velocity = rotation.T @ np.array([-3.0746*np.sin(angle), 3.0746*np.cos(angle), 0])
        self.window.active_profile = replace(original, profile_id="test-state-slot",
            display_name="SYNTHETIC STATE SLOT", orbit_source="cartesian",
            state_j2000=tuple(np.r_[position, velocity]), epoch_utc=epoch.isoformat())
        with patch("gui.main_window.available_eclipse_reference_specs", return_value=[]):
            self.window.refresh_sun_outage_profile()
            self.assertTrue(self.window._sun_outage_slot_valid)
            self.assertAlmostEqual(self.window.sun_outage_satellite_longitude.value(), 32, places=5)
        self.window.active_profile = original

    def test_od_workspace_is_not_exposed_or_created(self):
        self.assertEqual(self.window.orbit_determination_module_index, -1)
        self.assertFalse(hasattr(self.window, "orbit_determination_page"))
        self.assertFalse(hasattr(self.window, "od_tabs"))
        self.window.apply_language("az")
        self.assertFalse(self.window.select_tab_by_label("ORBİT TƏYİNİ"))
        self.assertTrue(self.window.select_tab_by_label("ECLIPSE"))
        self.assertEqual(
            self.window.eclipse_workspace_tabs.tabText(1),
            "GÜNƏŞ MANEƏSİ",
        )

    def test_theme_switch_keeps_module_and_version_state(self):
        self.window.select_module_by_label("ECLIPSE")
        self.window.apply_interface_theme("retro")
        self.window.apply_interface_theme("normal")
        self.assertEqual(
            self.window.module_tabs.currentIndex(),
            self.window.eclipse_module_index,
        )
        self.assertEqual(self.window.mission_version_label.text(), f"v{APP_VERSION}")


if __name__ == "__main__":
    unittest.main()
