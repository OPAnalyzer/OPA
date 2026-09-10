"""Mission-Control dialogs for validated satellite-profile management."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.localization import (
    language_for_widget,
    show_localized_message,
    translate_for_widget,
    translate_widget_tree,
)
from gui import theme
from satellite_profiles import (
    ProfileValidationError,
    SatelliteProfile,
    SatelliteProfileStore,
    load_gordam_state_file,
    load_ephemeris_state_file,
    new_basic_profile_template,
    validate_profile,
)


def _number_text(value):
    return "" if value in (None, "") else f"{float(value):.12g}"


class SatelliteProfileEditor(QDialog):
    """Validated editor for one user-owned satellite profile."""

    def __init__(self, profile: SatelliteProfile, parent=None):
        super().__init__(parent)
        self._source_profile = profile
        self._result_profile = None
        self.setWindowTitle("Satellite Profile Editor")
        self.setMinimumSize(760, 720)

        outer = QVBoxLayout(self)
        heading = QLabel("SATELLITE PROFILE")
        heading.setObjectName("settingsTitle")
        outer.addWidget(heading)
        note = QLabel(
            "Profiles provide validated spacecraft and mission inputs. "
            "They do not replace propagation or force-model equations."
        )
        note.setWordWrap(True)
        note.setObjectName("metricDetail")
        outer.addWidget(note)

        self.mode_tabs = QTabWidget()

        def scrollable_mode_page():
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_scroll = QScrollArea()
            page_scroll.setWidgetResizable(True)
            page_content = QWidget()
            page_content_layout = QVBoxLayout(page_content)
            page_content_layout.setSpacing(12)
            page_scroll.setWidget(page_content)
            page_layout.addWidget(page_scroll)
            return page, page_content_layout

        basic_page, basic_layout = scrollable_mode_page()
        advanced_page, advanced_layout = scrollable_mode_page()
        self.mode_tabs.addTab(basic_page, "BASIC")
        self.mode_tabs.addTab(advanced_page, "ADVANCED")

        identity = QGroupBox("IDENTITY / ORBIT SOURCE")
        identity_form = QFormLayout(identity)
        self.display_name = QLineEdit(profile.display_name)
        self.operator = QLineEdit(profile.operator)
        self.notes = QTextEdit(profile.notes)
        self.notes.setMaximumHeight(72)
        self.orbit_source = QComboBox()
        self.orbit_source.addItem("TLE catalogue", "tle")
        self.orbit_source.addItem("Cartesian J2000 state", "cartesian")
        self.orbit_source.addItem("Imported ephemeris state", "ephemeris")
        self.orbit_source.setCurrentIndex(
            max(0, self.orbit_source.findData(profile.orbit_source))
        )
        self.tle_name = QLineEdit(profile.tle_name)
        self.norad_id = QLineEdit("" if profile.norad_id is None else str(profile.norad_id))
        self.epoch_utc = QLineEdit(profile.epoch_utc or "")
        self.epoch_utc.setPlaceholderText("2030-01-01T00:00:00+00:00")
        self.reference_frame = QComboBox()
        self.reference_frame.addItem("J2000 / ICRF", "J2000")
        self.reference_frame.setToolTip(
            "The current propagation backend accepts Earth-centred J2000/ICRF states."
        )
        self.source_description = QTextEdit(profile.source_description)
        self.source_description.setMaximumHeight(72)
        self.source_description.setPlaceholderText(
            "Catalogue/file source, generation method or operator provenance note"
        )
        self.import_ephemeris_button = QPushButton("IMPORT EPHEMERIS STATE JSON")
        self.import_ephemeris_button.clicked.connect(self._import_ephemeris_state)
        self.import_gordam_button = QPushButton("IMPORT GORDAM OD REPORT")
        self.import_gordam_button.clicked.connect(self._import_gordam_state)
        state = profile.state_j2000 or ("",) * 6
        self.state_fields = [QLineEdit(_number_text(value)) for value in state]
        identity_form.addRow("Display name", self.display_name)
        identity_form.addRow("Operator", self.operator)
        identity_form.addRow("Notes", self.notes)
        identity_form.addRow("Orbit source", self.orbit_source)
        identity_form.addRow("TLE name", self.tle_name)
        identity_form.addRow("NORAD ID", self.norad_id)
        identity_form.addRow("Cartesian epoch UTC", self.epoch_utc)
        identity_form.addRow("Reference frame", self.reference_frame)
        identity_form.addRow("Source / provenance", self.source_description)
        identity_form.addRow("Ephemeris import", self.import_ephemeris_button)
        identity_form.addRow("GORDAM import", self.import_gordam_button)
        for label, field in zip(("X [km]", "Y [km]", "Z [km]", "Vx [km/s]", "Vy [km/s]", "Vz [km/s]"), self.state_fields):
            identity_form.addRow(label, field)
        self.orbit_source.currentIndexChanged.connect(
            self._sync_orbit_source_controls
        )
        self._sync_orbit_source_controls()
        basic_layout.addWidget(identity)

        basic_physical = QGroupBox("BASIC SPACECRAFT MODEL")
        basic_physical_form = QFormLayout(basic_physical)
        self.mass = QLineEdit(_number_text(profile.mass_kg))
        self.effective_area = QLineEdit(
            _number_text(profile.generic_srp_area_m2)
        )
        self.srp_coefficient = QLineEdit(
            _number_text(profile.srp_coefficient)
        )
        self._display_name_source_row = identity_form.takeRow(self.display_name)
        if self._display_name_source_row.labelItem is not None:
            source_label = self._display_name_source_row.labelItem.widget()
            if source_label is not None:
                source_label.hide()
        basic_physical_form.addRow("Spacecraft name", self.display_name)
        basic_physical_form.addRow("Total mass [kg]", self.mass)
        basic_physical_form.addRow(
            "Cross-sectional / effective area [m²]",
            self.effective_area,
        )
        basic_physical_form.addRow(
            "SRP coefficient / CP",
            self.srp_coefficient,
        )
        basic_note = QLabel(
            "These fields, together with the orbit source below, are enough "
            "to create and use a spacecraft. Propulsion and detailed surface "
            "properties are optional and remain under Advanced."
        )
        basic_note.setObjectName("metricDetail")
        basic_note.setWordWrap(True)
        basic_physical_form.addRow(basic_note)
        basic_layout.insertWidget(0, basic_physical)
        basic_layout.addStretch()

        physical = QGroupBox("DETAILED SPACECRAFT / PROPULSION MODEL")
        physical_grid = QGridLayout(physical)
        self.dry_mass = QLineEdit(_number_text(profile.dry_mass_kg))
        self.propellant_mass = QLineEdit(_number_text(profile.propellant_mass_kg))
        self.body_x = QLineEdit(_number_text(profile.body_x_m))
        self.body_y = QLineEdit(_number_text(profile.body_y_m))
        self.body_z = QLineEdit(_number_text(profile.body_z_m))
        self.body_specular = QLineEdit(_number_text(profile.body_specular))
        self.body_diffuse = QLineEdit(_number_text(profile.body_diffuse))
        self.body_absorption = QLineEdit(_number_text(profile.body_absorption))
        self.array_count = QSpinBox()
        self.array_count.setRange(0, 32)
        self.array_count.setValue(profile.solar_array_count)
        self.array_tracking = QComboBox()
        self.array_tracking.addItem("TrueSun tracking", "TrueSun")
        self.array_tracking.addItem(
            "Equivalent Sun-normal area", "EquivalentSunNormalArea"
        )
        self.array_tracking.setCurrentIndex(
            max(
                0,
                self.array_tracking.findData(profile.solar_array_tracking_mode),
            )
        )
        self.array_width = QLineEdit(_number_text(profile.solar_array_width_m))
        self.array_height = QLineEdit(_number_text(profile.solar_array_height_m))
        self.array_specular = QLineEdit(_number_text(profile.solar_array_specular))
        self.array_diffuse = QLineEdit(_number_text(profile.solar_array_diffuse))
        self.array_absorption = QLineEdit(_number_text(profile.solar_array_absorption))
        self.isp = QLineEdit(_number_text(profile.thruster_isp_s))
        rows = (
            ("Dry mass [kg]", self.dry_mass, "Propellant [kg]", self.propellant_mass),
            ("Thruster Isp [s]", self.isp, "", QLabel("")),
            ("Body X [m]", self.body_x, "Body Y [m]", self.body_y),
            ("Body Z [m]", self.body_z, "Array count", self.array_count),
            ("Array orientation", self.array_tracking, "", QLabel("")),
            ("Array width [m]", self.array_width, "Array height [m]", self.array_height),
            ("Body specular", self.body_specular, "Body diffuse", self.body_diffuse),
            ("Body absorption", self.body_absorption, "", QLabel("")),
            ("Array specular", self.array_specular, "Array diffuse", self.array_diffuse),
            ("Array absorption", self.array_absorption, "", QLabel("")),
        )
        for row, (left_label, left, right_label, right) in enumerate(rows):
            physical_grid.addWidget(QLabel(left_label), row, 0)
            physical_grid.addWidget(left, row, 1)
            if right_label:
                physical_grid.addWidget(QLabel(right_label), row, 2)
                physical_grid.addWidget(right, row, 3)
        optical_note = QLabel(
            "OPTICAL CONVENTION · For each surface: specular + diffuse + "
            "absorption = 1.0. Every coefficient must be dimensionless and in "
            "the inclusive range [0, 1]. Generic propagation uses the profile's "
            "equivalent area, mass and SRP coefficient; these surface shares "
            "remain explicit engineering metadata."
        )
        optical_note.setObjectName("metricDetail")
        optical_note.setWordWrap(True)
        physical_grid.addWidget(optical_note, len(rows), 0, 1, 4)
        advanced_layout.addWidget(physical)

        defaults = QGroupBox("FORCE MODEL / GEO DEFAULTS")
        defaults_grid = QGridLayout(defaults)
        self.earth_gravity = QCheckBox("Earth central gravity — required")
        self.earth_gravity.setChecked(True)
        self.earth_gravity.setEnabled(False)
        self.include_j2 = QCheckBox("Earth EGM96 harmonics")
        self.egm96_degree = QComboBox()
        for degree in (2, 3, 4):
            self.egm96_degree.addItem(f"Degree/order {degree}×{degree}", degree)
        self.egm96_degree.setCurrentIndex(
            max(0, self.egm96_degree.findData(profile.egm96_degree))
        )
        self.include_moon = QCheckBox("Moon third-body")
        self.include_sun = QCheckBox("Sun third-body")
        self.include_srp = QCheckBox("Solar radiation pressure")
        self.eop_enabled = QCheckBox("IERS EOP default")
        for control, checked in (
            (self.include_j2, profile.include_j2),
            (self.include_moon, profile.include_moon),
            (self.include_sun, profile.include_sun),
            (self.include_srp, profile.include_srp),
            (self.eop_enabled, profile.eop_enabled),
        ):
            control.setChecked(checked)
        defaults_grid.addWidget(self.earth_gravity, 0, 0)
        defaults_grid.addWidget(self.include_j2, 0, 1)
        defaults_grid.addWidget(self.egm96_degree, 0, 2)
        defaults_grid.addWidget(self.eop_enabled, 0, 3)
        defaults_grid.addWidget(self.include_moon, 1, 0)
        defaults_grid.addWidget(self.include_sun, 1, 1)
        defaults_grid.addWidget(self.include_srp, 1, 2)
        self.target_longitude = QLineEdit(_number_text(profile.target_longitude_deg))
        self.station_box = QLineEdit(_number_text(profile.station_box_half_width_deg))
        self.inc_warning = QLineEdit(_number_text(profile.inclination_warning_deg))
        self.inc_limit = QLineEdit(_number_text(profile.inclination_limit_deg))
        self.ecc_warning = QLineEdit(_number_text(profile.eccentricity_warning))
        self.ecc_limit = QLineEdit(_number_text(profile.eccentricity_limit))
        self.annual_budget = QLineEdit(_number_text(profile.annual_delta_v_budget_m_s))
        geo_rows = (
            ("Target longitude [deg E]", self.target_longitude, "Station half-width [deg]", self.station_box),
            ("Inclination warning [deg]", self.inc_warning, "Inclination limit [deg]", self.inc_limit),
            ("Eccentricity warning", self.ecc_warning, "Eccentricity limit", self.ecc_limit),
            ("Annual ΔV budget [m/s]", self.annual_budget, "", QLabel("")),
        )
        for offset, (left_label, left, right_label, right) in enumerate(geo_rows, start=2):
            defaults_grid.addWidget(QLabel(left_label), offset, 0)
            defaults_grid.addWidget(left, offset, 1)
            if right_label:
                defaults_grid.addWidget(QLabel(right_label), offset, 2)
                defaults_grid.addWidget(right, offset, 3)
        advanced_layout.addWidget(defaults)
        advanced_layout.addStretch()
        outer.addWidget(self.mode_tabs, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        translate_widget_tree(self, language_for_widget(self))

    def _payload(self):
        state_values = [field.text().strip() for field in self.state_fields]
        state = None if not any(state_values) else state_values
        return {
            **self._source_profile.to_dict(),
            "display_name": self.display_name.text().strip(),
            "operator": self.operator.text().strip(),
            "notes": self.notes.toPlainText().strip(),
            "built_in": False,
            "orbit_source": self.orbit_source.currentData(),
            "tle_name": self.tle_name.text().strip(),
            "norad_id": self.norad_id.text().strip() or None,
            "epoch_utc": self.epoch_utc.text().strip() or None,
            "state_j2000": state,
            "reference_frame": self.reference_frame.currentData(),
            "source_description": self.source_description.toPlainText().strip(),
            "mass_kg": self.mass.text().strip(),
            "effective_area_m2": self.effective_area.text().strip(),
            "dry_mass_kg": self.dry_mass.text().strip() or None,
            "propellant_mass_kg": self.propellant_mass.text().strip() or None,
            "body_x_m": self.body_x.text().strip(),
            "body_y_m": self.body_y.text().strip(),
            "body_z_m": self.body_z.text().strip(),
            "body_specular": self.body_specular.text().strip(),
            "body_diffuse": self.body_diffuse.text().strip(),
            "body_absorption": self.body_absorption.text().strip(),
            "solar_array_count": self.array_count.value(),
            "solar_array_tracking_mode": self.array_tracking.currentData(),
            "solar_array_width_m": self.array_width.text().strip(),
            "solar_array_height_m": self.array_height.text().strip(),
            "solar_array_specular": self.array_specular.text().strip(),
            "solar_array_diffuse": self.array_diffuse.text().strip(),
            "solar_array_absorption": self.array_absorption.text().strip(),
            "srp_coefficient": self.srp_coefficient.text().strip(),
            "thruster_isp_s": self.isp.text().strip() or None,
            "earth_gravity_enabled": True,
            "include_j2": self.include_j2.isChecked(),
            "egm96_degree": self.egm96_degree.currentData(),
            "egm96_order": self.egm96_degree.currentData(),
            "include_moon": self.include_moon.isChecked(),
            "include_sun": self.include_sun.isChecked(),
            "include_srp": self.include_srp.isChecked(),
            "eop_enabled": self.eop_enabled.isChecked(),
            "target_longitude_deg": self.target_longitude.text().strip(),
            "station_box_half_width_deg": self.station_box.text().strip(),
            "inclination_warning_deg": self.inc_warning.text().strip(),
            "inclination_limit_deg": self.inc_limit.text().strip(),
            "eccentricity_warning": self.ecc_warning.text().strip(),
            "eccentricity_limit": self.ecc_limit.text().strip(),
            "annual_delta_v_budget_m_s": self.annual_budget.text().strip() or None,
        }

    def _sync_orbit_source_controls(self, *_args):
        source = self.orbit_source.currentData()
        tle_mode = source == "tle"
        self.tle_name.setEnabled(tle_mode)
        self.norad_id.setEnabled(tle_mode)
        self.epoch_utc.setEnabled(not tle_mode)
        self.reference_frame.setEnabled(not tle_mode)
        for field in self.state_fields:
            field.setEnabled(not tle_mode)

    def _validate_and_accept(self):
        try:
            self._result_profile = validate_profile(self._payload())
        except (ProfileValidationError, ValueError) as error:
            show_localized_message(
                self,
                QMessageBox.Icon.Warning,
                "Invalid satellite profile",
                str(error),
            )
            return
        self.accept()

    def _import_ephemeris_state(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            translate_for_widget(self, "Import J2000 ephemeris state"),
            "",
            "OPA Ephemeris State (*.json);;JSON (*.json)",
            options=theme.file_dialog_options(),
        )
        if not path:
            return
        try:
            imported = load_ephemeris_state_file(path)
        except (OSError, ProfileValidationError, ValueError) as error:
            show_localized_message(
                self,
                QMessageBox.Icon.Warning,
                "Ephemeris import failed",
                str(error),
            )
            return
        self.orbit_source.setCurrentIndex(
            self.orbit_source.findData("ephemeris")
        )
        self.epoch_utc.setText(imported["epoch_utc"])
        self.reference_frame.setCurrentIndex(0)
        self.source_description.setPlainText(imported["source_description"])
        for field, value in zip(self.state_fields, imported["state_j2000"]):
            field.setText(_number_text(value))

    def _import_gordam_state(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            translate_for_widget(self, "Import GORDAM orbit-determination report"),
            "",
            "GORDAM detailed report (*.stdout *.txt);;All Files (*)",
            options=theme.file_dialog_options(),
        )
        if not path:
            return
        try:
            imported = load_gordam_state_file(path)
        except (OSError, ProfileValidationError, ValueError) as error:
            show_localized_message(
                self,
                QMessageBox.Icon.Warning,
                "GORDAM import failed",
                str(error),
            )
            return
        self.orbit_source.setCurrentIndex(self.orbit_source.findData("ephemeris"))
        self.display_name.setText(imported["display_name"])
        self.epoch_utc.setText(imported["epoch_utc"])
        self.reference_frame.setCurrentIndex(0)
        self.source_description.setPlainText(imported["source_description"])
        self.target_longitude.setText(_number_text(imported["target_longitude_deg"]))
        if imported["mass_kg"] is not None:
            self.mass.setText(_number_text(imported["mass_kg"]))
        cp_scale = imported["cp_scale_factor"]
        if cp_scale is not None:
            note = "GORDAM CP scale factor: " + _number_text(cp_scale)
            existing = self.notes.toPlainText().strip()
            self.notes.setPlainText(f"{existing}\n{note}".strip())
        for field, value in zip(self.state_fields, imported["state_j2000"]):
            field.setText(_number_text(value))

    def result_profile(self):
        return self._result_profile


class SatelliteProfileManager(QDialog):
    """Create, import, export and activate satellite profiles."""

    profile_activated = pyqtSignal(str)
    profiles_changed = pyqtSignal()

    def __init__(self, store: SatelliteProfileStore, active_profile_id: str, parent=None):
        super().__init__(parent)
        self.store = store
        self.active_profile_id = active_profile_id
        self.setWindowTitle("Satellite Profile Manager")
        self.setMinimumSize(880, 560)
        layout = QVBoxLayout(self)
        title = QLabel("SATELLITE PROFILE MANAGER")
        title.setObjectName("settingsTitle")
        layout.addWidget(title)
        subtitle = QLabel(
            "Built-in profiles are read-only. Duplicate one to create a validated "
            "operator-owned spacecraft configuration."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("metricDetail")
        layout.addWidget(subtitle)

        body = QHBoxLayout()
        self.profile_list = QListWidget()
        self.profile_list.currentRowChanged.connect(self._show_selected)
        self.profile_list.itemDoubleClicked.connect(lambda _item: self._activate())
        body.addWidget(self.profile_list, 2)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        body.addWidget(self.details, 3)
        layout.addLayout(body, 1)

        actions = QHBoxLayout()
        for label, slot in (
            ("NEW", self._new),
            ("DUPLICATE", self._duplicate),
            ("EDIT", self._edit),
            ("DELETE", self._delete),
            ("IMPORT", self._import),
            ("EXPORT", self._export),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            actions.addWidget(button)
        actions.addStretch()
        activate = QPushButton("USE PROFILE")
        activate.setObjectName("primaryAction")
        activate.clicked.connect(self._activate)
        actions.addWidget(activate)
        close = QPushButton("CLOSE")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)
        self._refresh()
        translate_widget_tree(self, language_for_widget(self))

    def _refresh(self, select_id=None):
        selected_id = select_id or self._selected_id() or self.active_profile_id
        self.store.reload()
        self.profile_list.clear()
        selected_row = 0
        for row, profile in enumerate(self.store.all()):
            suffix = "  ·  BUILT-IN" if profile.built_in else "  ·  USER"
            if profile.profile_id == self.active_profile_id:
                suffix += "  ·  ACTIVE"
            self.profile_list.addItem(profile.display_name + suffix)
            self.profile_list.item(row).setData(256, profile.profile_id)
            if profile.profile_id == selected_id:
                selected_row = row
        self.profile_list.setCurrentRow(selected_row)
        self.profiles_changed.emit()

    def _selected_id(self):
        item = self.profile_list.currentItem()
        return None if item is None else item.data(256)

    def _selected(self):
        identifier = self._selected_id()
        return None if identifier is None else self.store.get(identifier)

    def _show_selected(self, _row=None):
        profile = self._selected()
        if profile is None:
            self.details.clear()
            return
        if profile.orbit_source == "tle":
            state_source = (
                f"TLE · {profile.tle_name or 'NORAD'} · {profile.norad_id or '—'}"
            )
        elif profile.orbit_source == "ephemeris":
            state_source = f"Imported ephemeris · J2000 · {profile.epoch_utc}"
        else:
            state_source = f"Manual Cartesian · J2000 · {profile.epoch_utc}"
        self.details.setPlainText(
            f"{profile.display_name}\n"
            f"{'=' * 58}\n"
            f"Profile ID       : {profile.profile_id}\n"
            f"Ownership        : {'BUILT-IN / READ-ONLY' if profile.built_in else 'USER'}\n"
            f"Operator         : {profile.operator or '—'}\n"
            f"Orbit source     : {state_source}\n"
            f"Provenance       : {profile.source_description or '—'}\n"
            f"Mass             : {profile.mass_kg:.3f} kg\n"
            f"Effective SRP area: {profile.generic_srp_area_m2:.6f} m²\n"
            f"Array mode       : {profile.solar_array_tracking_mode}\n"
            f"Earth gravity    : REQUIRED · EGM96 "
            f"{profile.egm96_degree}×{profile.egm96_order} "
            f"{'ON' if profile.include_j2 else 'OFF'}\n"
            f"Force defaults   : "
            f"Moon {'ON' if profile.include_moon else 'OFF'} · "
            f"Sun {'ON' if profile.include_sun else 'OFF'} · "
            f"SRP {'ON' if profile.include_srp else 'OFF'} · "
            f"EOP {'ON' if profile.eop_enabled else 'OFF'}\n"
            f"GEO target       : {profile.target_longitude_deg:.4f}°E "
            f"± {profile.station_box_half_width_deg:.4f}°\n\n"
            f"{profile.notes or 'No profile notes.'}"
        )

    def _edit_profile(self, profile):
        editor = SatelliteProfileEditor(profile, self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return None
        result = editor.result_profile()
        try:
            saved = self.store.save(result)
        except (OSError, ProfileValidationError) as error:
            show_localized_message(
                self,
                QMessageBox.Icon.Warning,
                "Profile save failed",
                str(error),
            )
            return None
        self._refresh(saved.profile_id)
        return saved

    def _new(self):
        saved = self._edit_profile(new_basic_profile_template())
        if saved is not None:
            self.active_profile_id = saved.profile_id
            self.profile_activated.emit(saved.profile_id)
            self._refresh(saved.profile_id)

    def _duplicate(self):
        profile = self._selected()
        if profile is not None:
            self._edit_profile(profile.editable_copy())

    def _edit(self):
        profile = self._selected()
        if profile is None:
            return
        if profile.built_in:
            show_localized_message(
                self,
                QMessageBox.Icon.Information,
                "Built-in profile",
                "Duplicate this profile before editing it.",
            )
            return
        self._edit_profile(profile)

    def _delete(self):
        profile = self._selected()
        if profile is None:
            return
        if profile.built_in:
            show_localized_message(
                self,
                QMessageBox.Icon.Information,
                "Built-in profile",
                "Built-in profiles cannot be deleted.",
            )
            return
        answer = show_localized_message(
            self,
            QMessageBox.Icon.Question,
            "Delete satellite profile",
            f"Delete '{profile.display_name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.delete(profile.profile_id)
        except (OSError, ProfileValidationError) as error:
            show_localized_message(
                self,
                QMessageBox.Icon.Warning,
                "Profile delete failed",
                str(error),
            )
            return
        self._refresh()

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            translate_for_widget(self, "Import satellite profile"),
            "",
            "OPA Profile (*.json);;JSON (*.json)",
            options=theme.file_dialog_options(),
        )
        if not path:
            return
        try:
            profile = self.store.import_file(path)
        except (OSError, ProfileValidationError) as error:
            show_localized_message(
                self,
                QMessageBox.Icon.Warning,
                "Profile import failed",
                str(error),
            )
            return
        self._refresh(profile.profile_id)

    def _export(self):
        profile = self._selected()
        if profile is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            translate_for_widget(self, "Export satellite profile"),
            f"{profile.profile_id}.json",
            "OPA Profile (*.json)",
            options=theme.file_dialog_options(),
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            self.store.export_file(profile.profile_id, path)
        except (OSError, ProfileValidationError) as error:
            show_localized_message(
                self,
                QMessageBox.Icon.Warning,
                "Profile export failed",
                str(error),
            )

    def _activate(self):
        profile = self._selected()
        if profile is None:
            return
        self.active_profile_id = profile.profile_id
        self.profile_activated.emit(profile.profile_id)
        self._refresh(profile.profile_id)
