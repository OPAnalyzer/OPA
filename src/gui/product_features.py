"""Mission Control product features layered around the validated backend."""

from __future__ import annotations

from datetime import datetime, timezone
import os

import numpy as np
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction, QDoubleValidator, QKeySequence
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app_version import APP_VERSION
from geo_stationkeeping import StationKeepingError, analyze_geo_trajectory
from gui.localization import (
    language_for_widget,
    show_localized_message,
    translate_for_widget,
    translate_widget_tree,
)
from gui import theme
from gui.profile_dialogs import SatelliteProfileManager
from gui.scroll_canvas import ClickActivatedFigureCanvas
from initial_state import get_tle_initial_state
from opa_project import (
    ProjectValidationError,
    load_project,
    new_project,
    save_project,
    validate_project,
)
from reference_comparison import earth_fixed_longitude_degrees
from satellite_profiles import (
    BUILTIN_DEMO_GEO_ID,
    BUILTIN_PROFILES,
    ProfileValidationError,
    SatelliteProfileStore,
    validate_profile,
)


class GeoOperationsChart(ClickActivatedFigureCanvas):
    """Compact, theme-aware GEO operations plot independent of model code."""

    def __init__(self, parent=None):
        self.figure = Figure(figsize=(10, 7), dpi=100)
        super().__init__(self.figure)
        self.setParent(parent)
        self.setMinimumHeight(560)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.axes = self.figure.subplots(3, 1, sharex=True)
        self._date_numbers = np.asarray([], dtype=float)
        self._hover_series = {}
        self._annotations = []
        self.mpl_connect("motion_notify_event", self._on_hover)
        self.apply_theme()
        self.show_empty()

    def apply_theme(self):
        self.figure.patch.set_facecolor(theme.PLOT_FIGURE)
        for axis in self.axes:
            axis.set_facecolor(theme.PLOT_BACKGROUND)
            axis.tick_params(colors=theme.TEXT_MUTED, labelsize=8)
            axis.grid(True, color=theme.PLOT_GRID, linewidth=0.6, alpha=0.65)
            for spine in axis.spines.values():
                spine.set_color(theme.BORDER)
            axis.xaxis.label.set_color(theme.TEXT_SECONDARY)
            axis.yaxis.label.set_color(theme.TEXT_SECONDARY)
            axis.title.set_color(theme.TEXT_PRIMARY)

    def show_empty(self, message="Run a propagation, then analyze the GEO trajectory"):
        self._date_numbers = np.asarray([], dtype=float)
        self._hover_series = {}
        self._annotations = []
        for axis in self.axes:
            axis.clear()
        self.apply_theme()
        self.axes[1].text(
            0.5,
            0.5,
            message,
            ha="center",
            va="center",
            transform=self.axes[1].transAxes,
            color=theme.TEXT_MUTED,
        )
        self.figure.tight_layout(pad=1.2)
        self.draw_idle()

    def _on_hover(self, event):
        if (
            event.inaxes not in self.axes
            or event.xdata is None
            or self._date_numbers.size == 0
        ):
            changed = False
            for annotation in self._annotations:
                if annotation.get_visible():
                    annotation.set_visible(False)
                    changed = True
            if changed:
                self.draw_idle()
            return
        axis = event.inaxes
        index = int(np.argmin(np.abs(self._date_numbers - float(event.xdata))))
        series, unit = self._hover_series[axis]
        value = float(series[index])
        stamp = mdates.num2date(
            self._date_numbers[index], tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC")
        for annotation in self._annotations:
            annotation.set_visible(False)
        annotation = self._annotations[self.axes.tolist().index(axis)]
        annotation.xy = (self._date_numbers[index], value)
        annotation.set_text(f"{stamp}\n{value:.8g} {unit}")
        annotation.set_visible(True)
        self.draw_idle()

    def update_result(self, result, target=None, half_width=None):
        timeline = tuple(result["timeline_utc"])
        self._date_numbers = np.asarray(mdates.date2num(timeline), dtype=float)
        longitude_error = np.asarray(result["longitude_errors_deg"], dtype=float)
        inclination = np.asarray(result["inclination_series_deg"], dtype=float)
        eccentricity = np.asarray(result["eccentricity_series"], dtype=float)
        target = float(result["target_longitude_deg"] if target is None else target)
        half_width = float(
            result["station_box_half_width_deg"] if half_width is None else half_width
        )

        for axis in self.axes:
            axis.clear()
        self.apply_theme()
        first, second, third = self.axes
        first.plot(timeline, longitude_error, color=theme.ACCENT, linewidth=1.35)
        first.axhspan(-half_width, half_width, color=theme.STATUS_OK, alpha=0.10)
        first.axhline(half_width, color=theme.STATUS_WARNING, linewidth=0.8)
        first.axhline(-half_width, color=theme.STATUS_WARNING, linewidth=0.8)
        first.set_ylabel("Longitude error [deg]")
        first.set_title(f"Earth-fixed longitude · target {target:.4f}°")

        second.plot(timeline, inclination, color=theme.STATUS_WARNING, linewidth=1.25)
        second.axhline(
            result["inclination_warning_deg"],
            color=theme.STATUS_WARNING,
            linewidth=0.75,
            linestyle="--",
        )
        second.axhline(
            result["inclination_limit_deg"],
            color=theme.STATUS_ERROR,
            linewidth=0.8,
            linestyle="--",
        )
        second.ticklabel_format(axis="y", style="plain", useOffset=False)
        second.set_ylabel("Inclination [deg]")
        second.set_title("Inclination evolution")

        third.plot(timeline, eccentricity, color=theme.ACCENT_INFO, linewidth=1.25)
        third.axhline(
            result["eccentricity_warning"],
            color=theme.STATUS_WARNING,
            linewidth=0.75,
            linestyle="--",
        )
        third.axhline(
            result["eccentricity_limit"],
            color=theme.STATUS_ERROR,
            linewidth=0.8,
            linestyle="--",
        )
        third.ticklabel_format(axis="y", style="plain", useOffset=False)
        third.set_ylabel("Eccentricity [-]")
        third.set_xlabel("UTC")
        third.set_title("Eccentricity evolution")
        locator = mdates.AutoDateLocator(minticks=3, maxticks=8, tz=timezone.utc)
        third.xaxis.set_major_locator(locator)
        third.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator, tz=timezone.utc))
        self._hover_series = {
            first: (longitude_error, "deg"),
            second: (inclination, "deg"),
            third: (eccentricity, ""),
        }
        self._annotations = []
        for axis in self.axes:
            annotation = axis.annotate(
                "",
                xy=(0.0, 0.0),
                xytext=(12, 12),
                textcoords="offset points",
                color=theme.TEXT_PRIMARY,
                fontsize=8,
                bbox={
                    "boxstyle": "round,pad=0.4",
                    "facecolor": theme.PLOT_BACKGROUND,
                    "edgecolor": theme.ACCENT,
                    "alpha": 0.96,
                },
            )
            annotation.set_visible(False)
            self._annotations.append(annotation)
        self.figure.tight_layout(pad=1.25)
        self.draw_idle()


class ProjectDetailsDialog(QDialog):
    """Small document-metadata editor opened from the command-bar status."""

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Project details")
        self.setModal(True)
        self.resize(620, 520)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(str(project.get("name") or "Untitled Mission"))
        self.description_edit = QTextEdit()
        self.description_edit.setPlainText(str(project.get("description") or ""))
        self.description_edit.setMinimumHeight(120)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(str(project.get("notes") or ""))
        self.notes_edit.setMinimumHeight(180)
        form.addRow("Project name", self.name_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Mission notes", self.notes_edit)
        layout.addLayout(form)
        explanation = QLabel(
            "These fields are stored only in the .opa mission document. "
            "They do not change global application preferences."
        )
        explanation.setWordWrap(True)
        explanation.setObjectName("metricDetail")
        layout.addWidget(explanation)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        translate_widget_tree(self, language_for_widget(self))

    def _accept_if_valid(self):
        if not self.name_edit.text().strip():
            show_localized_message(
                self,
                QMessageBox.Icon.Warning,
                "Project details",
                "Project name is required.",
            )
            return
        self.accept()

    def values(self):
        return {
            "name": self.name_edit.text().strip(),
            "description": self.description_edit.toPlainText(),
            "notes": self.notes_edit.toPlainText(),
        }


class ProductFeatureMixin:
    """Satellite, project and GEO operations UI for Mission Control mode."""

    def initialize_product_features(self):
        self.profile_store = SatelliteProfileStore()
        requested = self.application_config.get(
            "active_profile_id", BUILTIN_DEMO_GEO_ID
        )
        try:
            self.active_profile = self.profile_store.get(requested)
        except ProfileValidationError:
            self.active_profile = self.profile_store.get(BUILTIN_DEMO_GEO_ID)
        self.active_profile_id = self.active_profile.profile_id
        self.current_project = None
        self.current_project_path = None
        self.project_dirty = False
        self._applying_product_state = False
        self._profile_snapshot_active = False
        self._project_snapshot_notice = ""
        self.latest_geo_analysis = None
        self.spacecraft_selectors = []

    def create_file_menu(self):
        """Create the conventional project menu without changing .opa logic."""

        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(False)
        file_menu = menu_bar.addMenu("File")
        actions = (
            ("New", self.new_project_action, QKeySequence.StandardKey.New),
            ("Open", self.open_project_action, QKeySequence.StandardKey.Open),
            ("Save", self.save_project_action, QKeySequence.StandardKey.Save),
            ("Save As", self.save_project_as_action, QKeySequence.StandardKey.SaveAs),
        )
        self.file_actions = {}
        for text, slot, shortcut in actions:
            action = QAction(text, self)
            action.setShortcut(shortcut)
            action.triggered.connect(slot)
            file_menu.addAction(action)
            self.file_actions[text] = action
        file_menu.addSeparator()
        # The header button is the only other route to this command, and it
        # is hidden in the Retro theme and on narrow windows.  The menu keeps
        # the command reachable in every presentation.
        refresh_action = QAction("Refresh Application", self)
        refresh_action.triggered.connect(self.refresh_application)
        file_menu.addAction(refresh_action)
        self.file_actions["Refresh Application"] = refresh_action
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        self.file_actions["Exit"] = exit_action
        self.file_menu = file_menu

    def create_product_command_bar(self, parent_layout):
        if not hasattr(self, "file_menu"):
            self.create_file_menu()
        bar = QFrame()
        self.product_command_bar = bar
        bar.setObjectName("productCommandBar")
        layout = QHBoxLayout(bar)
        self.product_command_layout = layout
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        label = QLabel("ACTIVE SPACECRAFT")
        label.setObjectName("missionEyebrow")
        layout.addWidget(label)
        self.profile_selector = QComboBox()
        self.profile_selector.setMinimumWidth(230)
        self.profile_selector.setMinimumHeight(34)
        self.profile_selector.setToolTip(
            "The active spacecraft is shared immediately by Telemetry, "
            "Perturbation, Propagation, Orbital View, Reference Lab and GEO Operations."
        )
        self.refresh_profile_selector()
        self.profile_selector.currentIndexChanged.connect(
            self._profile_selector_changed
        )
        layout.addWidget(self.profile_selector)
        profiles = QPushButton("PROFILES")
        profiles.setObjectName("ghostAction")
        profiles.clicked.connect(self.open_profile_manager)
        layout.addWidget(profiles)
        layout.addStretch(1)
        self.project_status_label = QPushButton("NO PROJECT · UNSAVED WORKSPACE")
        self.project_status_label.setObjectName("projectStatusButton")
        self.project_status_label.setFlat(True)
        self.project_status_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.project_status_label.clicked.connect(self.edit_project_details)
        layout.addWidget(self.project_status_label)
        parent_layout.addWidget(bar)

    def edit_project_details(self):
        if self.current_project is None and not self.new_project_action():
            return False
        dialog = ProjectDetailsDialog(self.current_project, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        self.current_project.update(dialog.values())
        self.mark_project_dirty()
        self.update_project_status()
        return True

    def rebuild_recent_projects_menu(self):
        menu = getattr(self, "recent_projects_menu", None)
        if menu is None:
            return
        menu.clear()
        paths = list(self.application_config.get("recent_projects", []))
        if not paths:
            empty = menu.addAction("NO RECENT PROJECTS")
            empty.setEnabled(False)
            return
        for path in paths:
            label = os.path.basename(path) or path
            action = menu.addAction(label)
            action.setToolTip(path)
            action.triggered.connect(
                lambda _checked=False, selected=path: self.open_recent_project(
                    selected
                )
            )
        menu.addSeparator()
        menu.addAction("CLEAR RECENT PROJECTS", self.clear_recent_projects)

    def _record_recent_project(self, path):
        absolute_path = os.path.abspath(path)
        existing = list(self.application_config.get("recent_projects", []))
        key = os.path.normcase(absolute_path)
        recent = [
            item for item in existing
            if os.path.normcase(os.path.abspath(item)) != key
        ]
        recent.insert(0, absolute_path)
        self.application_config["recent_projects"] = recent[:8]
        self.persist_recent_project_preferences()
        self.rebuild_recent_projects_menu()

    def _remove_recent_project(self, path):
        key = os.path.normcase(os.path.abspath(path))
        self.application_config["recent_projects"] = [
            item
            for item in self.application_config.get("recent_projects", [])
            if os.path.normcase(os.path.abspath(item)) != key
        ]
        self.persist_recent_project_preferences()
        self.rebuild_recent_projects_menu()

    def clear_recent_projects(self):
        self.application_config["recent_projects"] = []
        self.persist_recent_project_preferences()
        self.rebuild_recent_projects_menu()

    def refresh_profile_selector(self):
        selector = getattr(self, "profile_selector", None)
        if selector is None:
            return
        selected_id = self.active_profile_id
        selector.blockSignals(True)
        selector.clear()
        for profile in self.profile_store.all():
            suffix = " · BUILT-IN" if profile.built_in else ""
            selector.addItem(profile.display_name + suffix, profile.profile_id)
        if self._profile_snapshot_active:
            snapshot_label = self.active_profile.display_name + " · PROJECT SNAPSHOT"
            snapshot_index = selector.findData(selected_id)
            if snapshot_index < 0:
                selector.addItem(snapshot_label, selected_id)
            else:
                selector.setItemText(snapshot_index, snapshot_label)
        index = selector.findData(selected_id)
        selector.setCurrentIndex(max(0, index))
        selector.blockSignals(False)
        self.refresh_spacecraft_selectors()

    def register_spacecraft_selector(self, selector):
        """Bind one module selector to the central spacecraft registry."""

        if selector not in self.spacecraft_selectors:
            self.spacecraft_selectors.append(selector)
            selector.currentIndexChanged.connect(
                lambda _index, bound=selector: self._module_spacecraft_changed(bound)
            )
        self._populate_spacecraft_selector(selector)
        return selector

    def _populate_spacecraft_selector(self, selector):
        if selector is None:
            return
        selected_id = self.active_profile_id
        selector.blockSignals(True)
        selector.clear()
        for profile in self.profile_store.all():
            selector.addItem(profile.display_name, profile.profile_id)
        if self._profile_snapshot_active and selector.findData(selected_id) < 0:
            selector.addItem(
                self.active_profile.display_name + " · PROJECT SNAPSHOT",
                selected_id,
            )
        selector.setCurrentIndex(max(0, selector.findData(selected_id)))
        selector.blockSignals(False)

    def refresh_spacecraft_selectors(self):
        for selector in tuple(getattr(self, "spacecraft_selectors", ())):
            self._populate_spacecraft_selector(selector)

    def _module_spacecraft_changed(self, selector):
        profile_id = selector.currentData()
        if profile_id and profile_id != self.active_profile_id:
            self.activate_profile(profile_id)

    def _profile_selector_changed(self, _index):
        profile_id = self.profile_selector.currentData()
        if profile_id:
            self.activate_profile(profile_id)

    def open_profile_manager(self):
        manager = SatelliteProfileManager(
            self.profile_store, self.active_profile_id, self
        )
        manager.profile_activated.connect(self.activate_profile)
        manager.profiles_changed.connect(self._profiles_changed)
        manager.exec()
        self.profile_store.reload()
        self._profiles_changed()

    def _profiles_changed(self):
        self.profile_store.reload()
        self.refresh_profile_selector()

    def activate_profile(
        self,
        profile_id,
        *,
        profile_snapshot=None,
        load_state=True,
        apply_eop_default=True,
        update_application_preference=True,
    ):
        previous_profile_id = getattr(self, "active_profile_id", None)
        try:
            if profile_snapshot is not None:
                profile = validate_profile(profile_snapshot)
                self._profile_snapshot_active = profile_id not in {
                    item.profile_id for item in self.profile_store.all()
                }
            else:
                profile = self.profile_store.get(profile_id)
                self._profile_snapshot_active = False
        except ProfileValidationError as error:
            show_localized_message(
                self,
                QMessageBox.Icon.Warning,
                "Profile activation failed",
                str(error),
            )
            return False
        self.active_profile = profile
        self.active_profile_id = profile.profile_id
        if update_application_preference and profile.profile_id in BUILTIN_PROFILES:
            self.application_config["active_profile_id"] = profile.profile_id
        self.refresh_profile_selector()
        subtitle = getattr(self, "main_subtitle", None)
        if subtitle is not None:
            # The workspace names used to be spelled out here as well, which
            # only repeated the tab bar two rows below and forced the
            # subtitle onto a second line.
            subtitle.setText(
                "MULTI-BODY DYNAMICS CONSOLE  //  "
                f"{profile.display_name.upper()}"
            )
        live_box = getattr(self, "live_satellite_box", None)
        if live_box is not None:
            live_box.setTitle(
                f"{profile.display_name.upper()} — ACTIVE STATE"
            )
        if hasattr(self, "update_reference_srp_controls"):
            self.update_reference_srp_controls()
        if hasattr(self, "live_force_srp"):
            if profile.is_demo_geo_baseline:
                self.live_force_srp.setText("SRP — BOX-WING")
                self.live_force_srp.setToolTip(
                    "Validated SYNTHETIC GEO DEMO physical box-wing SRP with the "
                    "explicit public-mode CP=1.0 coefficient."
                )
            else:
                self.live_force_srp.setText("SRP — EFFECTIVE AREA")
                self.live_force_srp.setToolTip(
                    f"Active profile SRP · area {profile.generic_srp_area_m2:g} m² · "
                    f"mass {profile.mass_kg:g} kg · CP {profile.srp_coefficient:g}."
                )
        if hasattr(self, "prop_srp"):
            self._apply_profile_force_defaults(
                apply_eop_default=apply_eop_default
            )
            if load_state:
                self.load_active_profile_into_propagation(
                    apply_force_defaults=False
                )
        if hasattr(self, "geo_target_longitude"):
            self._apply_profile_geo_defaults()
        if hasattr(self, "refresh_sun_outage_profile"):
            self.refresh_sun_outage_profile()
        if self.current_project is not None and not self._applying_product_state:
            self.mark_project_dirty()
        if previous_profile_id != profile.profile_id:
            self.clear_product_results()
            if hasattr(self, "clear_active_spacecraft_history"):
                self.clear_active_spacecraft_history()
            if hasattr(self, "sync_active_profile_orbital_object"):
                self.sync_active_profile_orbital_object()
            if hasattr(self, "update_data"):
                QTimer.singleShot(0, self.update_data)
        return True

    def active_spacecraft_state(self, requested_epoch=None):
        """Resolve the active registry profile to one J2000 state and UTC epoch."""

        profile = self.active_profile
        if profile.orbit_source in {"cartesian", "ephemeris"}:
            return np.asarray(profile.state_j2000, dtype=float), profile.parsed_epoch
        epoch = requested_epoch or self.get_analysis_utc()
        if not profile.tle_name:
            raise ProfileValidationError(
                "This TLE profile needs a satellite name supported by the local TLE file."
            )
        return np.asarray(
            get_tle_initial_state(epoch, profile.tle_name), dtype=float
        ), epoch

    def _apply_profile_force_defaults(self, *, apply_eop_default=True):
        profile = self.active_profile
        if hasattr(self, "prop_srp_model"):
            index = self.prop_srp_model.findData("active_profile")
            if index >= 0:
                self.prop_srp_model.setCurrentIndex(index)
        for control, value in (
            (self.prop_j2, profile.include_j2),
            (self.prop_moon, profile.include_moon),
            (self.prop_sun, profile.include_sun),
            (self.prop_srp, profile.include_srp),
        ):
            control.setChecked(value)
        if self.prop_egm_degree is not None:
            index = self.prop_egm_degree.findData(profile.egm96_degree)
            if index >= 0:
                self.prop_egm_degree.setCurrentIndex(index)
        if apply_eop_default and hasattr(self, "eop_enabled_checkbox"):
            self.eop_enabled_checkbox.setChecked(profile.eop_enabled)
        if profile.is_demo_geo_baseline:
            self.prop_srp.setToolTip(
                "Validated SYNTHETIC GEO DEMO physical box-wing SRP model with "
                "the explicit public-mode CP=1.0 coefficient."
            )
        else:
            self.prop_srp.setToolTip(
                f"Generic cannonball SRP adapter · mass {profile.mass_kg:g} kg · "
                f"equivalent area {profile.generic_srp_area_m2:g} m² · "
                f"coefficient {profile.srp_coefficient:g}."
            )
        if hasattr(self, "update_propagation_srp_model_details"):
            self.update_propagation_srp_model_details()

    def load_active_profile_into_propagation(self, *, apply_force_defaults=True):
        profile = self.active_profile
        try:
            state, epoch = self.active_spacecraft_state(self.get_analysis_utc())
            self.prop_epoch.setText(epoch.astimezone(timezone.utc).isoformat())
            for control, value in zip(
                (
                    self.prop_x,
                    self.prop_y,
                    self.prop_z,
                    self.prop_vx,
                    self.prop_vy,
                    self.prop_vz,
                ),
                state,
            ):
                control.setText(f"{float(value):.15g}")
            if apply_force_defaults:
                self._apply_profile_force_defaults()
            self.statusBar().showMessage(
                f"Loaded profile into propagation: {profile.display_name}", 5000
            )
            return True
        except Exception as error:
            self.statusBar().showMessage(
                f"Profile state could not be loaded: {error}", 9000
            )
            return False

    def profile_srp_adapter(self):
        """Return only optional propagator inputs; SYNTHETIC GEO DEMO stays untouched."""

        profile = self.active_profile
        if profile.is_demo_geo_baseline:
            return {}, None
        area = profile.generic_srp_area_m2
        if area <= 0.0:
            raise ProfileValidationError(
                "The active profile needs a positive effective area when SRP is enabled."
            )
        return {
            "srp_area_m2": area,
            "srp_mass_kg": profile.mass_kg,
        }, profile.srp_coefficient

    def _confirm_discard_project_changes(self):
        if not self.project_dirty:
            return True
        answer = show_localized_message(
            self,
            QMessageBox.Icon.Warning,
            "Unsaved project changes",
            "The current project has unsaved changes. Save before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self.save_project_action()
        return True

    def new_project_action(self):
        if not self._confirm_discard_project_changes():
            return False
        self.current_project = new_project(self.active_profile, APP_VERSION)
        self.current_project_path = None
        # The active TLE profile has no frozen Cartesian state of its own.
        # Preserve the valid state currently shown in Propagation when starting
        # a new workspace instead of replacing it with blank profile fields.
        self.current_project = self.capture_project_from_ui()
        self.clear_product_results()
        self.project_dirty = True
        self.update_project_status()
        return True

    def close_project_action(self):
        if not self._confirm_discard_project_changes():
            return False
        if self._profile_snapshot_active:
            preferred_profile_id = self.application_config.get(
                "active_profile_id", BUILTIN_DEMO_GEO_ID
            )
            restored = self.activate_profile(
                    preferred_profile_id,
                    load_state=False,
                    apply_eop_default=False,
                    update_application_preference=False,
                )
            if not restored:
                self.activate_profile(
                    BUILTIN_DEMO_GEO_ID,
                    load_state=False,
                    apply_eop_default=False,
                    update_application_preference=False,
                )
        self._project_snapshot_notice = ""
        self.current_project = None
        self.current_project_path = None
        self.project_dirty = False
        self.clear_product_results()
        self.update_project_status()
        return True

    def open_project_action(self):
        if not self._confirm_discard_project_changes():
            return False
        path, _ = QFileDialog.getOpenFileName(
            self,
            translate_for_widget(self, "Open OPA project"),
            "",
            "OPA Project (*.opa)",
            options=theme.file_dialog_options(),
        )
        if not path:
            return False
        return self._open_project_path(path)

    def open_recent_project(self, path):
        if not self._confirm_discard_project_changes():
            return False
        if not os.path.isfile(path):
            self._remove_recent_project(path)
            show_localized_message(
                self,
                QMessageBox.Icon.Warning,
                "Recent project unavailable",
                f"The project no longer exists at:\n{path}",
            )
            return False
        return self._open_project_path(path)

    def _open_project_path(self, path):
        try:
            project = load_project(path)
            self.apply_project_to_ui(project)
        except (OSError, ProjectValidationError, ProfileValidationError) as error:
            show_localized_message(
                self,
                QMessageBox.Icon.Warning,
                "Project open failed",
                str(error),
            )
            return False
        self.current_project = project
        self.current_project_path = os.path.abspath(path)
        self.project_dirty = False
        self.update_project_status()
        try:
            self._record_recent_project(path)
        except OSError as error:
            self.statusBar().showMessage(
                f"Project opened; recent list could not be saved: {error}", 9000
            )
        if self._project_snapshot_notice:
            show_localized_message(
                self,
                QMessageBox.Icon.Information,
                "Project profile snapshot",
                self._project_snapshot_notice,
            )
        return True

    def save_project_action(self):
        if self.current_project is None:
            self.current_project = new_project(self.active_profile, APP_VERSION)
        if not self.current_project_path:
            return self.save_project_as_action()
        return self._write_project(self.current_project_path)

    def save_project_as_action(self):
        if self.current_project is None:
            self.current_project = new_project(self.active_profile, APP_VERSION)
        path, _ = QFileDialog.getSaveFileName(
            self,
            translate_for_widget(self, "Save OPA project"),
            f"{self.current_project.get('name', 'Untitled Mission')}.opa",
            "OPA Project (*.opa)",
            options=theme.file_dialog_options(),
        )
        if not path:
            return False
        if not path.lower().endswith(".opa"):
            path += ".opa"
        if self.current_project.get("name") == "Untitled Mission":
            self.current_project["name"] = os.path.splitext(
                os.path.basename(path)
            )[0]
        return self._write_project(path)

    def _write_project(self, path):
        try:
            project = self.capture_project_from_ui()
            self.current_project = save_project(project, path)
        except (OSError, ValueError, ProjectValidationError) as error:
            show_localized_message(
                self,
                QMessageBox.Icon.Warning,
                "Project save failed",
                str(error),
            )
            return False
        self.current_project_path = os.path.abspath(path)
        self.project_dirty = False
        self.update_project_status()
        try:
            self._record_recent_project(path)
        except OSError as error:
            self.statusBar().showMessage(
                f"Project saved; recent list could not be saved: {error}", 9000
            )
            return True
        self.statusBar().showMessage(f"Saved project: {path}", 7000)
        return True

    def capture_project_from_ui(self):
        project = dict(
            self.current_project
            if self.current_project is not None
            else new_project(self.active_profile, APP_VERSION)
        )
        step_seconds = self.step_minutes.value() * 60 + self.step_seconds.value()
        epoch_utc = self.parse_propagation_epoch(
            self.prop_epoch.text()
        ).isoformat()
        state = [
            float(control.text())
            for control in (
                self.prop_x,
                self.prop_y,
                self.prop_z,
                self.prop_vx,
                self.prop_vy,
                self.prop_vz,
            )
        ]
        geo_operations = self.geo_controls_payload()
        eclipse_text = [control.text().strip() for control in self.eclipse_state_inputs]
        if any(eclipse_text):
            if not all(eclipse_text):
                raise ProjectValidationError(
                    "All six Eclipse J2000 state components are required together."
                )
            eclipse_state = [float(value) for value in eclipse_text]
            eclipse_epoch = self.parse_propagation_epoch(
                self.eclipse_epoch.text()
            ).isoformat()
        else:
            eclipse_state = []
            eclipse_epoch = ""
        visible_objects = [
            object_id
            for object_id, checkbox in self.system_object_checks.items()
            if checkbox.isChecked()
        ]
        project.update(
            {
                "application_version": APP_VERSION,
                "satellite_profile_id": self.active_profile.profile_id,
                "satellite_profile_snapshot": self.active_profile.to_dict(),
                "initial_state": {
                    "source": self.active_profile.orbit_source,
                    "epoch_utc": epoch_utc,
                    "reference_frame": "J2000",
                    "state_j2000": state,
                    "provenance": self.active_profile.source_description,
                },
                "propagation": {
                    "start_utc": epoch_utc,
                    "epoch_utc": epoch_utc,
                    "state_j2000": state,
                    "duration_days": float(self.prop_days.text()),
                    "output_step_seconds": step_seconds,
                    "earth_gravity_enabled": True,
                    "include_j2": self.prop_j2.isChecked(),
                    "egm96_degree": (
                        int(self.prop_egm_degree.currentData())
                        if self.prop_egm_degree is not None
                        else 4
                    ),
                    "egm96_order": (
                        int(self.prop_egm_degree.currentData())
                        if self.prop_egm_degree is not None
                        else 4
                    ),
                    "include_moon": self.prop_moon.isChecked(),
                    "include_sun": self.prop_sun.isChecked(),
                    "include_srp": self.prop_srp.isChecked(),
                    "srp_model": str(
                        self.prop_srp_model.currentData() or "active_profile"
                    ),
                    "manual_srp_mode": str(
                        "panel_body"
                        if self.prop_manual_srp_separate_panels.isChecked()
                        else "combined"
                    ),
                    "manual_srp_mass_kg": self.prop_manual_srp_mass.value(),
                    "manual_srp_total_area_m2": (
                        self.prop_manual_srp_total_area.value()
                    ),
                    "manual_srp_coefficient": (
                        self.prop_manual_srp_coefficient.value()
                    ),
                    "manual_srp_panel_area_m2": (
                        self.prop_manual_srp_panel_area.value()
                    ),
                    "manual_srp_panel_coefficient": (
                        self.prop_manual_srp_panel_coefficient.value()
                    ),
                    "manual_srp_body_area_m2": (
                        self.prop_manual_srp_body_area.value()
                    ),
                    "manual_srp_body_coefficient": (
                        self.prop_manual_srp_body_coefficient.value()
                    ),
                },
                "numerical": {
                    "rtol": self.integrator_rtol.text().strip(),
                    "atol": self.integrator_atol.text().strip(),
                    "max_step_seconds": self.integrator_max_step.value(),
                    "eop_enabled": self.eop_enabled_checkbox.isChecked(),
                },
                "eclipse": {
                    "epoch_utc": eclipse_epoch,
                    "state_j2000": eclipse_state,
                    "duration_days": self.eclipse_days.value(),
                    "output_step_seconds": (
                        self.eclipse_step_value.value()
                        * int(self.eclipse_step_unit.currentData())
                    ),
                    "include_j2": self.eclipse_include_j2.isChecked(),
                    "include_moon": self.eclipse_include_moon.isChecked(),
                    "include_sun": self.eclipse_include_sun.isChecked(),
                    "include_srp": self.eclipse_include_srp.isChecked(),
                    "oblate_earth_shadow": self.eclipse_oblate_earth.isChecked(),
                    "light_time_moon": self.eclipse_light_time_moon.isChecked(),
                    "yearly_search_year": self.eclipse_year.value(),
                    "reference_dataset_id": (
                        self.eclipse_reference_selector.currentData() or ""
                    ),
                    "reference_tolerance_seconds": (
                        self.eclipse_reference_tolerance_seconds.value()
                    ),
                },
                "geo_operations": geo_operations,
                "view": {
                    "active_tab": self.tabs.currentIndex(),
                    "manual_chart": self.manual_chart_component.currentData(),
                    "perturbation_parameter": self.parameter.currentText(),
                    "perturbation_time_range": self.time_range.currentText(),
                    "reference_chart": (
                        self.reference_chart_mode.currentData()
                        or self.reference_chart_mode.currentText()
                    ),
                    "reference_dataset_id": (
                        self.reference_dataset_combo.currentData() or ""
                    ),
                    "system_projection": self.system_plane.currentText(),
                    "system_scale": self.system_scale.currentText(),
                    "system_focus": self.system_focus.currentData() or "earth",
                    "system_visible_objects": visible_objects,
                },
            }
        )
        return validate_project(project)

    @staticmethod
    def _select_project_combo_value(combo, value):
        index = combo.findData(value)
        if index < 0 and value is not None:
            index = combo.findText(str(value))
        if index >= 0:
            combo.setCurrentIndex(index)

    def _apply_project_eclipse_settings(self, values):
        self.eclipse_epoch.setText(values["epoch_utc"])
        state = values["state_j2000"]
        for index, control in enumerate(self.eclipse_state_inputs):
            control.setText(f"{float(state[index]):.15g}" if state else "")
        self.eclipse_days.setValue(values["duration_days"])
        step_seconds = int(values["output_step_seconds"])
        for unit_seconds in (86400, 3600, 60, 1):
            if step_seconds % unit_seconds:
                continue
            amount = step_seconds // unit_seconds
            if 1 <= amount <= 60:
                self._select_project_combo_value(
                    self.eclipse_step_unit, unit_seconds
                )
                self.eclipse_step_value.setValue(amount)
                break
        for control, key in (
            (self.eclipse_include_j2, "include_j2"),
            (self.eclipse_include_moon, "include_moon"),
            (self.eclipse_include_sun, "include_sun"),
            (self.eclipse_include_srp, "include_srp"),
            (self.eclipse_oblate_earth, "oblate_earth_shadow"),
            (self.eclipse_light_time_moon, "light_time_moon"),
        ):
            control.setChecked(values[key])
        self.eclipse_year.setValue(values["yearly_search_year"])
        self._select_project_combo_value(
            self.eclipse_reference_selector,
            values["reference_dataset_id"],
        )
        self.eclipse_reference_tolerance_seconds.setValue(
            values["reference_tolerance_seconds"]
        )

    def apply_project_to_ui(self, project):
        project = validate_project(project)
        self._applying_product_state = True
        self._project_snapshot_notice = ""
        try:
            profile_id = project["satellite_profile_id"]
            snapshot = project["satellite_profile_snapshot"]
            snapshot_profile = validate_profile(snapshot)
            try:
                installed_profile = self.profile_store.get(profile_id)
                if installed_profile.to_dict() == snapshot_profile.to_dict():
                    self.activate_profile(
                        profile_id,
                        load_state=False,
                        apply_eop_default=False,
                        update_application_preference=False,
                    )
                else:
                    self.activate_profile(
                        profile_id,
                        profile_snapshot=snapshot,
                        load_state=False,
                        apply_eop_default=False,
                        update_application_preference=False,
                    )
                    self._profile_snapshot_active = True
                    self._project_snapshot_notice = (
                        "This project contains a satellite-profile snapshot that "
                        "differs from the currently installed profile. OPA is using "
                        "the project snapshot so the scenario remains reproducible."
                    )
                    self.refresh_profile_selector()
            except ProfileValidationError:
                self.activate_profile(
                    profile_id,
                    profile_snapshot=snapshot,
                    load_state=False,
                    apply_eop_default=False,
                    update_application_preference=False,
                )
                self._profile_snapshot_active = True
                self._project_snapshot_notice = (
                    "The satellite profile referenced by this project is not "
                    "installed. OPA is using the embedded project snapshot so the "
                    "scenario remains reproducible."
                )
                self.refresh_profile_selector()
            propagation = project["propagation"]
            self.prop_epoch.setText(propagation["epoch_utc"])
            for control, value in zip(
                (
                    self.prop_x,
                    self.prop_y,
                    self.prop_z,
                    self.prop_vx,
                    self.prop_vy,
                    self.prop_vz,
                ),
                propagation["state_j2000"],
            ):
                control.setText(f"{float(value):.15g}")
            self.prop_days.setText(f"{propagation['duration_days']:g}")
            output_step = int(propagation["output_step_seconds"])
            self.step_minutes.setValue(output_step // 60)
            self.step_seconds.setValue(output_step % 60)
            for control, key in (
                (self.prop_j2, "include_j2"),
                (self.prop_moon, "include_moon"),
                (self.prop_sun, "include_sun"),
                (self.prop_srp, "include_srp"),
            ):
                control.setChecked(propagation[key])
            self.prop_manual_srp_separate_panels.setChecked(
                propagation.get("manual_srp_mode", "combined")
                == "panel_body"
            )
            for control, key in (
                (self.prop_manual_srp_mass, "manual_srp_mass_kg"),
                (
                    self.prop_manual_srp_total_area,
                    "manual_srp_total_area_m2",
                ),
                (
                    self.prop_manual_srp_coefficient,
                    "manual_srp_coefficient",
                ),
                (
                    self.prop_manual_srp_panel_area,
                    "manual_srp_panel_area_m2",
                ),
                (
                    self.prop_manual_srp_panel_coefficient,
                    "manual_srp_panel_coefficient",
                ),
                (
                    self.prop_manual_srp_body_coefficient,
                    "manual_srp_body_coefficient",
                ),
            ):
                control.setValue(float(propagation[key]))
            srp_model_index = self.prop_srp_model.findData(
                propagation.get("srp_model", "active_profile")
            )
            self.prop_srp_model.setCurrentIndex(max(0, srp_model_index))
            self.update_propagation_srp_model_details()
            if self.prop_egm_degree is not None:
                degree_index = self.prop_egm_degree.findData(
                    propagation["egm96_degree"]
                )
                if degree_index >= 0:
                    self.prop_egm_degree.setCurrentIndex(degree_index)
            numerical = project["numerical"]
            self.integrator_rtol.setText(numerical["rtol"])
            self.integrator_atol.setText(numerical["atol"])
            self.integrator_max_step.setValue(numerical["max_step_seconds"])
            self.eop_enabled_checkbox.setChecked(numerical["eop_enabled"])
            self._apply_project_eclipse_settings(project["eclipse"])
            self.apply_geo_controls(project["geo_operations"])
            chart_index = self.manual_chart_component.findData(
                project["view"].get("manual_chart")
            )
            if chart_index >= 0:
                self.manual_chart_component.setCurrentIndex(chart_index)
            view = project["view"]
            for combo, key in (
                (self.parameter, "perturbation_parameter"),
                (self.time_range, "perturbation_time_range"),
                (self.reference_chart_mode, "reference_chart"),
                (self.reference_dataset_combo, "reference_dataset_id"),
                (self.system_plane, "system_projection"),
                (self.system_scale, "system_scale"),
                (self.system_focus, "system_focus"),
            ):
                self._select_project_combo_value(combo, view.get(key))
            selected_objects = set(view.get("system_visible_objects", []))
            for object_id, checkbox in self.system_object_checks.items():
                checkbox.setChecked(object_id in selected_objects)
            tab_index = int(project["view"].get("active_tab", 0))
            if 0 <= tab_index < self.tabs.count():
                self.tabs.setCurrentIndex(tab_index)
        finally:
            self._applying_product_state = False
        self.current_project = project
        self.clear_product_results()
        self.project_dirty = False
        self.update_project_status()

    def clear_product_results(self):
        """Prevent a trajectory from being attributed to another profile/project."""

        if not hasattr(self, "last_prop_times"):
            return
        self.last_prop_times = None
        self.last_prop_states = None
        self.last_prop_epoch = None
        self.last_prop_force_profile_cache = None
        self.latest_geo_analysis = None
        if hasattr(self, "save_csv_button"):
            self.save_csv_button.setEnabled(False)
        if hasattr(self, "propagation_kepler_widget"):
            self.propagation_kepler_widget.clear()
        if hasattr(self, "manual_graph") and self.isVisible():
            self.update_manual_propagation_chart()
        if hasattr(self, "geo_output"):
            self.geo_output.clear()
            self.geo_status_value.setText("READY")
            self.geo_status_value.setStyleSheet("")
            self.geo_orbit_value.setText("—")
            self.geo_boundary_value.setText("—")
            self.geo_ew_value.setText("—")
            self.geo_ns_value.setText("—")
            self.geo_advisory_value.setText("—")
            if self.isVisible():
                self.geo_chart.show_empty()

    def bind_project_editors(self):
        controls = (
            self.prop_epoch,
            self.prop_x,
            self.prop_y,
            self.prop_z,
            self.prop_vx,
            self.prop_vy,
            self.prop_vz,
            self.prop_days,
            self.geo_target_longitude,
            self.geo_station_box,
            self.geo_inc_warning,
            self.geo_inc_limit,
            self.geo_ecc_warning,
            self.geo_ecc_limit,
            self.geo_annual_budget,
            self.geo_annual_used,
            self.integrator_rtol,
            self.integrator_atol,
            self.eclipse_epoch,
            *self.eclipse_state_inputs,
        )
        for control in controls:
            control.textEdited.connect(self.mark_project_dirty)
        for control in (
            self.step_minutes,
            self.step_seconds,
            self.integrator_max_step,
            self.eclipse_days,
            self.eclipse_step_value,
            self.eclipse_year,
            self.eclipse_reference_tolerance_seconds,
            self.prop_manual_srp_mass,
            self.prop_manual_srp_total_area,
            self.prop_manual_srp_coefficient,
            self.prop_manual_srp_panel_area,
            self.prop_manual_srp_panel_coefficient,
            self.prop_manual_srp_body_area,
            self.prop_manual_srp_body_coefficient,
        ):
            control.valueChanged.connect(self.mark_project_dirty)
        for control in (
            self.prop_egm_degree,
            self.prop_srp_model,
            self.manual_chart_component,
            self.parameter,
            self.time_range,
            self.reference_chart_mode,
            self.reference_dataset_combo,
            self.system_plane,
            self.system_scale,
            self.system_focus,
            self.eclipse_step_unit,
            self.eclipse_reference_selector,
        ):
            if control is not None:
                control.currentIndexChanged.connect(self.mark_project_dirty)
        for control in (
            self.prop_j2,
            self.prop_moon,
            self.prop_sun,
            self.prop_srp,
            self.prop_manual_srp_separate_panels,
            self.eop_enabled_checkbox,
            self.eclipse_include_j2,
            self.eclipse_include_moon,
            self.eclipse_include_sun,
            self.eclipse_include_srp,
            self.eclipse_oblate_earth,
            self.eclipse_light_time_moon,
            *self.system_object_checks.values(),
        ):
            control.toggled.connect(self.mark_project_dirty)
        self.tabs.currentChanged.connect(self.mark_project_dirty)

    def mark_project_dirty(self, *_args):
        if self._applying_product_state or self.current_project is None:
            return
        self.project_dirty = True
        self.update_project_status()

    def update_project_status(self):
        label = getattr(self, "project_status_label", None)
        if label is None:
            return
        if self.current_project is None:
            text = "NO PROJECT · UNSAVED WORKSPACE"
        else:
            name = self.current_project.get("name", "Untitled Mission")
            suffix = " · MODIFIED" if self.project_dirty else " · SAVED"
            if self._profile_snapshot_active:
                suffix += " · PROFILE SNAPSHOT"
            text = name.upper() + suffix
        label.setText(text)
        label.setToolTip(
            self._project_snapshot_notice
            or (self.current_project_path or "Project has not been saved yet.")
        )

    def create_geo_operations_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        self.geo_operations_scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 10, 12, 16)
        layout.setSpacing(14)
        heading = QLabel("GEO STATION-KEEPING ANALYSIS")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        description = QLabel(
            "Analyze the latest propagated trajectory against an operator-defined "
            "longitude box and GEO element limits. Advisory estimates never alter "
            "the propagated state and are not flight-certified maneuver commands."
        )
        description.setWordWrap(True)
        description.setObjectName("metricDetail")
        layout.addWidget(description)

        controls_box = QGroupBox("ACTIVE PROJECT CONSTRAINTS")
        form = QGridLayout(controls_box)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        self.geo_target_longitude = QLineEdit()
        self.geo_station_box = QLineEdit()
        self.geo_inc_warning = QLineEdit()
        self.geo_inc_limit = QLineEdit()
        self.geo_ecc_warning = QLineEdit()
        self.geo_ecc_limit = QLineEdit()
        self.geo_annual_budget = QLineEdit()
        self.geo_annual_used = QLineEdit()
        controls = (
            ("Target longitude [deg]", self.geo_target_longitude),
            ("Station-box ± half-width [deg]", self.geo_station_box),
            ("Inclination warning [deg]", self.geo_inc_warning),
            ("Inclination limit [deg]", self.geo_inc_limit),
            ("Eccentricity warning [-]", self.geo_ecc_warning),
            ("Eccentricity limit [-]", self.geo_ecc_limit),
            ("Annual ΔV budget [m/s]", self.geo_annual_budget),
            ("Annual ΔV already used [m/s]", self.geo_annual_used),
        )
        validator = QDoubleValidator(-1.0e12, 1.0e12, 12, self)
        validator.setNotation(QDoubleValidator.Notation.ScientificNotation)
        for index, (label_text, control) in enumerate(controls):
            row = index // 2
            column = (index % 2) * 2
            label = QLabel(label_text)
            label.setObjectName("metricDetail")
            control.setValidator(validator)
            control.setMinimumWidth(150)
            form.addWidget(label, row, column)
            form.addWidget(control, row, column + 1)
        self.geo_annual_budget.setPlaceholderText("Not configured")
        self.geo_annual_used.setPlaceholderText("0")
        self._apply_profile_geo_defaults()
        layout.addWidget(controls_box)

        action_row = QHBoxLayout()
        analyze = QPushButton("ANALYZE LATEST PROPAGATION")
        analyze.setObjectName("primaryAction")
        analyze.setMinimumHeight(42)
        analyze.clicked.connect(self.run_geo_stationkeeping_analysis)
        action_row.addWidget(analyze)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        cards = QGridLayout()
        cards.setSpacing(10)
        self.geo_status_value = QLabel("READY")
        self.geo_status_value.setObjectName("geoMetricValue")
        self.geo_orbit_value = QLabel("—")
        self.geo_orbit_value.setObjectName("geoMetricValue")
        self.geo_boundary_value = QLabel("—")
        self.geo_boundary_value.setObjectName("geoMetricValue")
        for column, (title, value) in enumerate(
            (
                ("STATION BOX / LIMIT STATUS", self.geo_status_value),
                ("CURRENT GEO STATE", self.geo_orbit_value),
                ("BOUNDARY FORECAST", self.geo_boundary_value),
            )
        ):
            card = QGroupBox(title)
            card_layout = QVBoxLayout(card)
            value.setWordWrap(True)
            card_layout.addWidget(value)
            cards.addWidget(card, 0, column)
        layout.addLayout(cards)

        advisory_cards = QGridLayout()
        advisory_cards.setSpacing(10)
        self.geo_ew_value = QLabel("—")
        self.geo_ew_value.setObjectName("geoMetricValue")
        self.geo_ns_value = QLabel("—")
        self.geo_ns_value.setObjectName("geoMetricValue")
        self.geo_advisory_value = QLabel("—")
        self.geo_advisory_value.setObjectName("geoMetricValue")
        for column, (title, value) in enumerate(
            (
                ("EAST-WEST ADVISORY", self.geo_ew_value),
                ("NORTH-SOUTH ADVISORY", self.geo_ns_value),
                ("RESOURCE / BUDGET CHECK", self.geo_advisory_value),
            )
        ):
            card = QGroupBox(title)
            card_layout = QVBoxLayout(card)
            value.setWordWrap(True)
            card_layout.addWidget(value)
            advisory_cards.addWidget(card, 0, column)
        layout.addLayout(advisory_cards)

        chart_box = QGroupBox("GEO OPERATIONS TREND")
        chart_layout = QVBoxLayout(chart_box)
        self.geo_chart = GeoOperationsChart()
        chart_layout.addWidget(self.geo_chart)
        layout.addWidget(chart_box)
        self.geo_output = QTextEdit()
        self.geo_output.setReadOnly(True)
        self.geo_output.setMinimumHeight(300)
        self.geo_output.setPlaceholderText("GEO analysis report will appear here.")
        layout.addWidget(self.geo_output)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.geo_tab_index = self.tabs.addTab(page, "GEO OPERATIONS")

    def _apply_profile_geo_defaults(self):
        profile = self.active_profile
        for control_name, value in (
            ("geo_target_longitude", profile.target_longitude_deg),
            ("geo_station_box", profile.station_box_half_width_deg),
            ("geo_inc_warning", profile.inclination_warning_deg),
            ("geo_inc_limit", profile.inclination_limit_deg),
            ("geo_ecc_warning", profile.eccentricity_warning),
            ("geo_ecc_limit", profile.eccentricity_limit),
            ("geo_annual_budget", profile.annual_delta_v_budget_m_s),
            ("geo_annual_used", 0.0),
        ):
            control = getattr(self, control_name, None)
            if control is not None:
                control.setText("" if value is None else f"{value:g}")

    def geo_controls_payload(self):
        def optional_value(control):
            text = control.text().strip()
            return None if not text else float(text)

        return {
            "target_longitude_deg": float(self.geo_target_longitude.text()),
            "station_box_half_width_deg": float(self.geo_station_box.text()),
            "inclination_warning_deg": float(self.geo_inc_warning.text()),
            "inclination_limit_deg": float(self.geo_inc_limit.text()),
            "eccentricity_warning": float(self.geo_ecc_warning.text()),
            "eccentricity_limit": float(self.geo_ecc_limit.text()),
            "annual_delta_v_budget_m_s": optional_value(self.geo_annual_budget),
            "annual_delta_v_used_m_s": optional_value(self.geo_annual_used) or 0.0,
        }

    def apply_geo_controls(self, values):
        for key, control in (
            ("target_longitude_deg", self.geo_target_longitude),
            ("station_box_half_width_deg", self.geo_station_box),
            ("inclination_warning_deg", self.geo_inc_warning),
            ("inclination_limit_deg", self.geo_inc_limit),
            ("eccentricity_warning", self.geo_ecc_warning),
            ("eccentricity_limit", self.geo_ecc_limit),
            ("annual_delta_v_budget_m_s", self.geo_annual_budget),
            ("annual_delta_v_used_m_s", self.geo_annual_used),
        ):
            value = values.get(key)
            control.setText("" if value is None else f"{float(value):g}")

    @staticmethod
    def _format_geo_duration(seconds):
        if seconds is None:
            return "—"
        total = max(0, int(round(float(seconds))))
        days, remainder = divmod(total, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days} d {hours:02d} h {minutes:02d} m {seconds:02d} s"

    def _show_geo_insufficient_data(self, detail):
        self.latest_geo_analysis = None
        self.geo_status_value.setText("INSUFFICIENT DATA")
        self.geo_status_value.setStyleSheet(theme.status_style("warning", padding=6))
        self.geo_orbit_value.setText("—")
        self.geo_boundary_value.setText("—")
        self.geo_ew_value.setText("—")
        self.geo_ns_value.setText("—")
        self.geo_advisory_value.setText("—")
        self.geo_output.setPlainText(f"INSUFFICIENT DATA\n\n{detail}")
        self.geo_chart.show_empty("INSUFFICIENT DATA · RUN PROPAGATION")

    def run_geo_stationkeeping_analysis(self):
        if (
            self.last_prop_times is None
            or self.last_prop_states is None
            or self.last_prop_epoch is None
        ):
            self._show_geo_insufficient_data(
                "Run Propagation first. GEO Operations uses the latest completed "
                "result and never launches a hidden propagation."
            )
            return False
        try:
            controls = self.geo_controls_payload()
            longitudes = earth_fixed_longitude_degrees(
                self.last_prop_states, self.last_prop_epoch, self.last_prop_times
            )
            profile = self.active_profile
            result = analyze_geo_trajectory(
                self.last_prop_times,
                self.last_prop_states,
                longitudes,
                self.last_prop_epoch,
                **controls,
                mass_kg=profile.mass_kg,
                isp_s=profile.thruster_isp_s,
                available_propellant_mass_kg=profile.propellant_mass_kg,
            )
        except (ValueError, StationKeepingError) as error:
            self._show_geo_insufficient_data(str(error))
            return False
        self.latest_geo_analysis = result
        status = result["status"]
        self.geo_status_value.setText(
            f"BOX {result['station_box_status']}  ·  OVERALL {status}\n"
            f"Δλ {result['longitude_error_deg']:+.6f}°  ·  "
            f"drift {result['drift_rate_deg_day']:+.6f}°/day\n"
            f"W {result['west_limit_longitude_deg']:+.6f}°  ·  "
            f"E {result['east_limit_longitude_deg']:+.6f}°"
        )
        self.geo_status_value.setStyleSheet(
            theme.status_style(
                "ok" if status == "NOMINAL" else "warning" if status == "WARNING" else "error",
                padding=6,
            )
        )
        self.geo_orbit_value.setText(
            f"λ {result['current_longitude_deg']:+.7f}°\n"
            f"a−aGEO {result['semimajor_offset_km']:+.3f} km  ·  "
            f"i {result['inclination_deg']:.6f}°\n"
            f"e {result['eccentricity']:.8f}  ·  "
            f"i⃗ [{result['inclination_vector_rad'][0]:+.3e}, "
            f"{result['inclination_vector_rad'][1]:+.3e}] rad"
        )
        if result["boundary_utc"] is not None:
            boundary_time = result["boundary_utc"].strftime("%Y-%m-%d %H:%M:%S UTC")
            boundary_remaining = self._format_geo_duration(
                result["time_to_boundary_seconds"]
            )
            boundary_detail = (
                f"{result['boundary_prediction_kind']}  ·  {result['boundary_side']} LIMIT\n"
                f"{boundary_time}\nT− {boundary_remaining}"
            )
        elif result["linear_boundary_utc"] is not None:
            boundary_time = result["linear_boundary_utc"].strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
            boundary_remaining = self._format_geo_duration(
                result["linear_time_to_boundary_seconds"]
            )
            boundary_detail = (
                "NO CROSSING IN PROPAGATED ARC\n"
                f"LINEAR ESTIMATE · {result['linear_boundary_side']} LIMIT\n"
                f"{boundary_time}  ·  T− {boundary_remaining}"
            )
        else:
            boundary_time = "No crossing in propagated interval"
            boundary_remaining = "—"
            boundary_detail = "NO CROSSING IN PROPAGATED ARC\nZERO-DRIFT LINEAR ESTIMATE"
        self.geo_boundary_value.setText(boundary_detail)

        ew_propellant = result["east_west_propellant_estimate_kg"]
        ns_propellant = result["north_south_propellant_estimate_kg"]
        self.geo_ew_value.setText(
            f"{result['east_west_direction']}  ·  {result['east_west_delta_v_m_s']:.6f} m/s\n"
            f"{result['east_west_correction_direction']}\n"
            + (
                f"Ideal propellant {ew_propellant:.4f} kg"
                if ew_propellant is not None
                else result["propellant_status"]
            )
        )
        self.geo_ns_value.setText(
            f"{result['north_south_delta_v_m_s']:.6f} m/s\n"
            f"{result['north_south_direction']}\n"
            + (
                f"Ideal propellant {ns_propellant:.4f} kg"
                if ns_propellant is not None
                else result["propellant_status"]
            )
        )
        propellant_text = (
            f"{result['propellant_estimate_kg']:.4f} kg"
            if result["propellant_estimate_kg"] is not None
            else "INSUFFICIENT DATA"
        )
        budget_text = (
            f"{result['annual_budget_remaining_m_s']:+.4f} m/s after advisory"
            if result["annual_budget_remaining_m_s"] is not None
            else "NOT CONFIGURED"
        )
        self.geo_advisory_value.setText(
            f"TOTAL ADVISORY {result['total_advisory_delta_v_m_s']:.6f} m/s\n"
            f"Ideal propellant {propellant_text}\n"
            f"Annual budget {budget_text}\n{result['annual_budget_status']}"
        )
        reasons = ", ".join(result["status_reasons"]) or "all configured limits nominal"
        inclination_vector = result["inclination_vector_rad"]
        eccentricity_vector = result["eccentricity_vector_xy"]
        propagated_boundary = (
            f"{result['boundary_utc'].isoformat()} · {result['boundary_side']} · "
            f"{self._format_geo_duration(result['time_to_boundary_seconds'])}"
            if result["boundary_utc"] is not None
            else "none in propagated interval"
        )
        linear_boundary = (
            f"{result['linear_boundary_utc'].isoformat()} · "
            f"{result['linear_boundary_side']} · "
            f"{self._format_geo_duration(result['linear_time_to_boundary_seconds'])}"
            if result["linear_boundary_utc"] is not None
            else "not used"
        )
        report = [
            "GEO STATION-KEEPING ENGINEERING ADVISORY",
            "=" * 78,
            f"Profile                : {profile.display_name}",
            f"Analysis epoch         : {result['analysis_epoch_utc'].isoformat()}",
            f"Station box / overall  : {result['station_box_status']} / {status} · {reasons}",
            f"Current longitude      : {result['current_longitude_deg']:.8f} deg geocentric Earth-fixed",
            f"Target / station box   : {controls['target_longitude_deg']:.6f} ± {controls['station_box_half_width_deg']:.6f} deg",
            f"Longitude drift        : {result['drift_rate_deg_day']:+.8f} deg/day",
            f"Semi-major-axis offset : {result['semimajor_offset_km']:+.6f} km from nominal GEO",
            f"Inclination            : {result['inclination_deg']:.8f} deg",
            f"Inclination vector     : [{inclination_vector[0]:+.10e}, {inclination_vector[1]:+.10e}] rad · i[cos Ω, sin Ω]",
            f"Eccentricity           : {result['eccentricity']:.10f}",
            f"Eccentricity vector    : [{eccentricity_vector[0]:+.10e}, {eccentricity_vector[1]:+.10e}] · J2000 XY projection",
            f"Propagated violation   : {propagated_boundary}",
            f"Linear estimate        : {linear_boundary}",
            "",
            "EAST-WEST DRIFT-ARREST ESTIMATE",
            f"Observed drift         : {result['east_west_direction']}",
            f"Correction direction   : {result['east_west_correction_direction']}",
            f"EW advisory delta-v    : {result['east_west_delta_v_m_s']:.6f} m/s",
            "",
            "NORTH-SOUTH IDEAL PLANE-CHANGE ESTIMATE",
            f"Correction direction   : {result['north_south_direction']}",
            f"NS advisory delta-v    : {result['north_south_delta_v_m_s']:.6f} m/s",
            f"Combined planning value: {result['total_advisory_delta_v_m_s']:.6f} m/s",
            f"Propellant status      : {result['propellant_status']}",
            f"Annual budget status   : {result['annual_budget_status']}",
            "",
            "ASSUMPTIONS / LIMITATIONS",
            *(f"- {line}" for line in result["assumptions"]),
            "",
            "SCIENTIFIC PROVENANCE",
            *(
                f"- {item['source']} · {item['use']} · {item['url']}"
                for item in result["scientific_provenance"]
            ),
        ]
        self.geo_output.setPlainText("\n".join(report))
        self.geo_chart.update_result(result)
        return True

    def refresh_geo_theme(self):
        if not hasattr(self, "geo_chart"):
            return
        if self.latest_geo_analysis is None:
            if self.geo_status_value.text() == "INSUFFICIENT DATA":
                self.geo_status_value.setStyleSheet(
                    theme.status_style("warning", padding=6)
                )
            self.geo_chart.apply_theme()
            self.geo_chart.draw_idle()
            return
        status = self.latest_geo_analysis["status"]
        self.geo_status_value.setStyleSheet(
            theme.status_style(
                "ok"
                if status == "NOMINAL"
                else "warning"
                if status == "WARNING"
                else "error",
                padding=6,
            )
        )
        self.geo_chart.update_result(self.latest_geo_analysis)

    def prepare_product_close(self):
        return self._confirm_discard_project_changes()
