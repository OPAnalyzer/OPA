"""Focused responsive-layout and localization regression checks."""

import os
import tempfile
from pathlib import Path
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QScrollArea

from gui.main_window import (
    APP_ICON_PATH,
    APP_LOGO_PATH,
    HERO_BACKGROUND_DARK_PATH,
    MainWindow,
)


class ResponsiveLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="opa-layout-test-")
        self.window = MainWindow(
            application_config_path=Path(self.temporary.name) / "config.json"
        )
        self.window.show()
        self.application.processEvents()

    def tearDown(self):
        self.window.close()
        self.application.processEvents()
        self.temporary.cleanup()

    @staticmethod
    def _contained(child, ancestor):
        top_left = child.mapTo(ancestor, QPoint(0, 0))
        return ancestor.rect().contains(top_left) and ancestor.rect().contains(
            top_left + QPoint(max(0, child.width() - 1), max(0, child.height() - 1))
        )

    def test_major_shell_remains_contained_at_supported_sizes(self):
        for width, height in ((640, 360), (1366, 768), (1920, 1080)):
            with self.subTest(size=(width, height)):
                self.window.resize(width, height)
                self.application.processEvents()
                self.assertTrue(self._contained(self.window.module_tabs, self.window))
                self.assertGreater(self.window.module_tabs.width(), 0)
                self.assertGreater(self.window.module_tabs.height(), 0)

    def test_live_telemetry_uses_a_responsive_scroll_surface(self):
        self.window.resize(1366, 768)
        self.window.module_tabs.setCurrentIndex(0)
        self.window.tabs.setCurrentIndex(0)
        self.application.processEvents()
        self.assertTrue(self.window.monitor_page_scroll.widgetResizable())
        self.assertGreater(
            self.window.live_perturbation_box.sizeHint().height(),
            0,
        )
        self.assertGreaterEqual(
            self.window.monitor_page_scroll.widget().minimumSizeHint().height(),
            self.window.monitor_page_scroll.viewport().height(),
        )

    def test_perturbation_actions_fit_a_laptop_work_area(self):
        self.window.resize(1366, 768)
        self.window.tabs.setCurrentIndex(self.window.graph_tab_index)
        self.application.processEvents()
        self.assertTrue(self.window.graph_action_controls_host.isVisible())
        self.assertLessEqual(self.window.graph.minimumHeight(), 160)
        for button in self.window.graph_action_buttons:
            self.assertGreaterEqual(
                self.window.graph_action_controls_layout.indexOf(button), 0
            )
            self.assertTrue(self._contained(button, self.window.graph_page))
        self.assertIsNone(self.window._containing_scroll_area(self.window.graph))
        self.assertTrue(self._contained(self.window.graph, self.window.graph_page))

    def test_perturbation_graph_has_reversible_graph_only_full_screen(self):
        self.window.resize(1366, 768)
        self.window.tabs.setCurrentIndex(self.window.graph_tab_index)
        self.application.processEvents()
        self.assertTrue(
            self._contained(
                self.window.graph_fullscreen_button,
                self.window.graph,
            )
        )
        QTest.mouseClick(
            self.window.graph_fullscreen_button,
            Qt.MouseButton.LeftButton,
        )
        self.application.processEvents()
        self.assertTrue(self.window._graph_only_mode)
        self.assertTrue(self.window.isFullScreen())
        self.assertTrue(self.window.graph.isVisible())
        self.assertFalse(self.window.hero_card.isVisible())
        self.assertFalse(self.window.graph_controls_host.isVisible())

        QTest.keyClick(self.window, Qt.Key.Key_Escape)
        self.application.processEvents()
        self.assertFalse(self.window._graph_only_mode)
        self.assertTrue(self.window.hero_card.isVisible())
        self.assertTrue(self.window.graph_controls_host.isVisible())

    def test_orbital_expand_fills_the_screen_with_only_the_graph(self):
        self.window.resize(1366, 768)
        self.window.tabs.setCurrentIndex(self.window.system_view_tab_index)
        self.application.processEvents()

        self.assertTrue(self.window.hero_card.isVisible())
        self.assertTrue(self.window.tabs.tabBar().isVisible())
        self.assertTrue(self.window.system_controls_host.isVisible())
        self.assertIs(self.window.system_theater_button.parentWidget(), self.window.system_graph)

        QTest.mouseClick(
            self.window.system_theater_button,
            Qt.MouseButton.LeftButton,
        )
        self.application.processEvents()

        self.assertTrue(self.window._orbital_theater_mode)
        self.assertTrue(self.window.isFullScreen())
        self.assertFalse(self.window.hero_card.isVisible())
        self.assertFalse(self.window.tabs.tabBar().isVisible())
        self.assertFalse(self.window.module_tabs.tabBar().isVisible())
        self.assertTrue(self.window.system_graph.isVisible())
        self.assertFalse(self.window.system_controls_host.isVisible())
        self.assertFalse(self.window.system_object_box.isVisible())
        self.assertFalse(self.window.system_coordinates_box.isVisible())

        QTest.keyClick(self.window, Qt.Key.Key_Escape)
        self.application.processEvents()
        self.assertFalse(self.window._orbital_theater_mode)
        self.assertFalse(self.window.isFullScreen())
        self.assertTrue(self.window.hero_card.isVisible())
        self.assertTrue(self.window.tabs.tabBar().isVisible())
        self.assertTrue(self.window.system_controls_host.isVisible())
        self.assertTrue(self.window.system_object_box.isVisible())
        self.assertTrue(self.window.system_coordinates_box.isVisible())

    def test_geo_page_omits_redundant_analysis_only_banner(self):
        banner = (
            "ANALYSIS ONLY  ·  NO BURN IS APPLIED  ·  "
            "NO SPACECRAFT COMMAND IS GENERATED"
        )
        visible_text = "\n".join(
            label.text() for label in self.window.findChildren(QLabel)
        )
        self.assertNotIn(banner, visible_text)

    def test_settings_pages_are_scrollable_and_panel_is_not_fixed(self):
        self.window.resize(640, 360)
        self.window.settings_overlay.show_overlay()
        self.window.settings_overlay._select_page(1)
        self.application.processEvents()
        panel = self.window.settings_overlay.panel
        self.assertTrue(self._contained(panel, self.window.settings_overlay))
        self.assertLessEqual(panel.width(), self.window.settings_overlay.width())
        self.assertLessEqual(panel.height(), self.window.settings_overlay.height())
        self.assertTrue(
            all(page.widgetResizable() for page in panel.findChildren(QScrollArea))
        )
        # The panel may temporarily fill all available space, but the
        # implementation must not use Qt's fixed-size flag.
        self.window.resize(1366, 768)
        self.window.settings_overlay.show_overlay()
        self.application.processEvents()
        self.assertNotEqual(panel.minimumSize(), panel.maximumSize())

    def test_normal_retro_and_azerbaijani_admin_labels_switch_live(self):
        for selected_theme in ("normal", "retro"):
            self.window.apply_interface_theme(selected_theme)
            self.assertEqual(self.window.interface_theme, selected_theme)
        self.window.apply_language("az")
        self.window.settings_overlay.show_overlay()
        self.application.processEvents()
        self.assertEqual(
            self.window.settings_overlay.admin_nav_button.text(), "ADMİN GİRİŞİ"
        )
        self.window.apply_language("en")
        self.assertEqual(
            self.window.settings_overlay.admin_nav_button.text(), "ADMIN ACCESS"
        )

    def test_established_opa_brand_assets_load_in_the_header(self):
        for asset_path in (APP_ICON_PATH, APP_LOGO_PATH, HERO_BACKGROUND_DARK_PATH):
            with self.subTest(asset=Path(asset_path).name):
                self.assertTrue(Path(asset_path).is_file())
        self.assertFalse(self.window.hero_logo_pixmap.isNull())
        self.assertFalse(self.window.hero_card._background.isNull())


if __name__ == "__main__":
    unittest.main()
