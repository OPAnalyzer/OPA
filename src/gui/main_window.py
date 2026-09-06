import sys
import os
import csv
import json
import re
import time
from collections import deque
from datetime import datetime, timezone, timedelta

import numpy as np

from PyQt6.QtCore import (
    QDate,
    QEasingCurve,
    QEvent,
    QLocale,
    QPropertyAnimation,
    QTime,
    QTimer,
    Qt,
    QObject,
    QProcess,
    QThread,
    QRectF,
    QSize,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QDesktopServices,
    QFontDatabase,
    QFontMetrics,
    QIcon,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QHBoxLayout,
    QBoxLayout,
    QLabel,
    QComboBox,
    QTabWidget,
    QStackedWidget,
    QGroupBox,
    QGridLayout,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QFormLayout,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QDoubleSpinBox,
    QSpinBox,
    QFileDialog,
    QFrame,
    QScrollArea,
    QCalendarWidget,
    QTimeEdit,
    QGraphicsOpacityEffect,
    QSizePolicy,
    QProgressBar,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractSpinBox,
    QToolBar,
    QStyle,
)

from matplotlib.backend_bases import MouseButton
from matplotlib.figure import Figure
from matplotlib import get_data_path as get_matplotlib_data_path
from matplotlib import dates as mdates
from matplotlib import ticker as mticker
from matplotlib.colors import to_hex as matplotlib_to_hex
from matplotlib import patheffects as mpatheffects
from matplotlib.patches import Circle
from matplotlib.path import Path as MplPath
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from gui.scroll_canvas import ClickActivatedFigureCanvas
from gui.runtime_diagnostics import (
    install_runtime_diagnostics,
    record_runtime_event,
)
from gui.localization import (
    LocalizedStatusBar,
    SUPPORTED_LANGUAGES,
    normalise_language,
    translate_text,
    translate_widget_tree,
)
from admin_security import (
    AdminSecurityError,
    AdminSessionManager,
    default_admin_package_path,
    enroll_device,
    load_verification_key_file,
)
from application_config import (
    DEFAULT_APPLICATION_CONFIG,
    default_application_config_path,
    get_last_config_warning,
    load_application_config,
    normalise_application_config,
    save_application_config,
)


# ============================================================
# PATH
# ============================================================

CURRENT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

SRC_DIR = os.path.dirname(
    CURRENT_DIR
)

PROJECT_DIR = os.path.dirname(
    SRC_DIR
)

ASSETS_DIR = os.path.join(
    PROJECT_DIR,
    "assets",
)

APPLICATION_CONFIG_PATH = str(default_application_config_path())
APPLICATION_DATA_DIR = str(default_application_config_path().parent)
PROPAGATION_SRP_ACTIVE_PROFILE = "active_profile"
PROPAGATION_SRP_DEMO_EQUIVALENT = "demo_equivalent"
PROPAGATION_SRP_MANUAL = "manual"
# The OD engine remains available for future work, but its unfinished desktop
# workspace is intentionally not exposed in the current product shell.
ORBIT_DETERMINATION_UI_ENABLED = False


APP_ICON_PATH = os.path.join(
    ASSETS_DIR,
    "opa_orbit_emblem_windows_v2.ico",
)

APP_LOGO_PATH = os.path.join(
    ASSETS_DIR,
    "opa_orbit_emblem_windows_v2.png",
)

DROPDOWN_ARROW_PATH = os.path.join(
    ASSETS_DIR,
    "dropdown_arrow.svg",
)

HERO_BACKGROUND_PATH = os.path.join(
    ASSETS_DIR,
    "orbital_mission_banner_dark_v2.png",
)
HERO_BACKGROUND_DARK_PATH = HERO_BACKGROUND_PATH

if SRC_DIR not in sys.path:
    sys.path.insert(
        0,
        SRC_DIR
    )


# ============================================================
# PROJECT IMPORTS
# ============================================================

from spice_loader import (
    get_kernel_status,
    load_kernels,
)
from app_version import APP_VERSION

WINDOWS_APP_USER_MODEL_ID = "OPA.OrbitalPerturbationAnalyzer.v4"
RESTART_APPLICATION_EXIT_CODE = 773
WINDOWS_ICON_REFRESH_DELAYS_MS = (0, 250, 1500)


def apply_windows_taskbar_icon(window, icon_path):
    """Attach stable small/large native icons to an existing Windows HWND."""

    if sys.platform != "win32" or not os.path.isfile(icon_path):
        return False

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        user32.GetSystemMetrics.restype = ctypes.c_int
        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.SendMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        ]
        user32.SendMessageW.restype = ctypes.c_ssize_t

        native_icons = getattr(window, "_windows_native_icon_handles", None)
        if native_icons is None:
            image_icon = 1
            load_from_file = 0x0010
            big_icon = user32.LoadImageW(
                None,
                icon_path,
                image_icon,
                user32.GetSystemMetrics(11),
                user32.GetSystemMetrics(12),
                load_from_file,
            )
            small_icon = user32.LoadImageW(
                None,
                icon_path,
                image_icon,
                user32.GetSystemMetrics(49),
                user32.GetSystemMetrics(50),
                load_from_file,
            )
            if not big_icon or not small_icon:
                return False
            native_icons = (big_icon, small_icon)
            # Keep the HICON handles alive for the complete HWND lifetime.
            window._windows_native_icon_handles = native_icons

        window_handle = int(window.winId())
        wm_seticon = 0x0080
        icon_small = 0
        icon_big = 1
        user32.SendMessageW(
            window_handle,
            wm_seticon,
            icon_big,
            int(native_icons[0]),
        )
        user32.SendMessageW(
            window_handle,
            wm_seticon,
            icon_small,
            int(native_icons[1]),
        )
        return True
    except (AttributeError, OSError, TypeError, ValueError):
        return False

# User-specified station-keeping display limits. These are presentation/QC
# bounds only; they do not alter the propagation or reference trajectories.
TARGET_LONGITUDE_DEG = 12.0
LONGITUDE_TOLERANCE_DEG = 0.05
DEFAULT_KEPLER_HISTORY_BOUNDS = {
    "e": (None, 300.0e-6),
    # Classical inclination is non-negative; ±0.05° about the equator is
    # therefore displayed as the physically meaningful 0.00–0.05° band.
    "i_deg": (0.0, 0.05),
}

from time_utils import (
    format_csv_date,
    format_csv_time,
    format_csv_utc,
    get_current_utc,
    utc_to_et,
)

from satellite import (
    TARGET_SATELLITE_DISPLAY_NAME,
    TARGET_SATELLITE_NAME,
    TARGET_SATELLITE_NORAD_ID,
    get_satellite_orbital_period_seconds,
    get_satellite_position,
    get_satellite_position_and_altitude,
    get_satellite_positions_and_altitudes,
    get_tle_metadata,
    update_local_tle,
)

from moon import (
    get_moon_position,
    get_sun_position,
)

from moon_perturbation import (
    moon_perturbation,
)

from sun_perturbation import (
    sun_perturbation,
)
from solar_radiation_pressure import (
    resolve_effective_area_srp_inputs,
    resolved_solar_pressure_coefficient,
    solar_radiation_pressure,
    sunlight_fraction,
)
from gui import theme
from gui.product_features import ProductFeatureMixin
from eclipse_prediction import (
    EclipseGeometryOptions,
    EclipsePrediction,
    EclipsePredictionCancelled,
    build_yearly_eclipse_schedule,
    predict_eclipses,
    save_eclipse_prediction_csv,
    save_yearly_eclipse_schedule_csv,
)
from eclipse_references import (
    available_eclipse_reference_specs,
    clear_session_eclipse_reference_datasets,
    compare_eclipse_events,
    load_eclipse_reference_dataset,
    register_session_eclipse_reference_datasets,
    save_eclipse_reference_comparison_csv,
    save_eclipse_reference_side_by_side_csv,
)
from perturbation_analysis import (
    PERTURBATION_PARAMETERS,
    acceleration_components,
)
from graph_prediction import compute_perturbation_prediction
from orbital_elements import cartesian_to_keplerian
from orbit_determination import (
    OrbitDeterminationCancelled,
    OrbitDeterminationError,
    available_ground_stations,
    clear_session_orbit_determination_datasets,
    fit_weighted_least_squares,
    load_dataset as load_orbit_determination_dataset,
    register_session_orbit_determination_datasets,
)
from sun_outage import (
    SunOutageCancelled,
    SunOutageStation,
    predict_sun_outages,
    save_sun_outage_csv,
)
from constants import MU_EARTH
from earth_orientation import (
    EarthOrientationError,
    eop_values_at,
    get_eop_status,
    is_eop_enabled,
    j2000_to_itrs_rotation_from_datetime,
    set_eop_enabled,
)

from initial_state import (
    get_nominal_geostationary_state,
    get_tle_initial_state,
    nominal_geostationary_trajectory,
)

from propagator import (
    PropagationCancelled,
    propagate_state,
    propagate_trajectory,
)

from reference_comparison import (
    DEMO_EARTH_MOON_SUN_SRP_DATASET_ID,
    DEFAULT_REFERENCE_DATASET_ID,
    EARTH_MOON_SUN_REFERENCE_DATASET_ID,
    EARTH_SUN_REFERENCE_DATASET_ID,
    REFERENCE_DIR,
    SECOND_REFERENCE_DATASET_ID,
    SUN_MOON_COMPARISON_DATASET_ID,
    combine_reference_scenarios,
    clear_session_reference_datasets,
    earth_fixed_longitude_degrees,
    get_reference_dataset,
    list_reference_datasets,
    load_reference_scenario,
    reference_dataset_has_scenario,
    register_session_reference_datasets,
    reload_user_reference_datasets,
    rotate_j2000_states_to_tod_fk5,
    run_reference_scenario,
    save_scenario_csv,
)


# Reference Lab və Propagation eyni ssenari kataloqundan istifadə edir. Bu
# rollar QComboBox sətrində dataset ID-sinə əlavə olaraq Ay və SRP açarlarını
# saxlayır; Günəş açarı datasetin required_force_model məlumatından alınır.
REFERENCE_SCENARIO_MOON_ROLE = int(Qt.ItemDataRole.UserRole) + 1
REFERENCE_SCENARIO_SRP_ROLE = int(Qt.ItemDataRole.UserRole) + 2


def reference_scenario_groups():
    """Return public synthetic and user-provided reference scenarios."""

    bundled_groups = (
        (
            "SYNTHETIC/DEMO — 2030-01-01 00:00 UTC",
            (
                ("EARTH", DEFAULT_REFERENCE_DATASET_ID, False, False),
                ("EARTH + MOON", DEFAULT_REFERENCE_DATASET_ID, True, False),
                (
                    "EARTH + SUN",
                    EARTH_SUN_REFERENCE_DATASET_ID,
                    False,
                    False,
                ),
                (
                    "EARTH + MOON + SUN",
                    EARTH_MOON_SUN_REFERENCE_DATASET_ID,
                    True,
                    False,
                ),
                ("──── SYNTHETIC SRP REFERENCES ────", None, None, None),
                (
                    "EARTH + SRP (CP)",
                    DEFAULT_REFERENCE_DATASET_ID,
                    False,
                    True,
                ),
                (
                    "EARTH + MOON + SRP (CP)",
                    DEFAULT_REFERENCE_DATASET_ID,
                    True,
                    True,
                ),
                (
                    "EARTH + SUN + SRP (CP)",
                    EARTH_SUN_REFERENCE_DATASET_ID,
                    False,
                    True,
                ),
                (
                    "EARTH + MOON + SUN + SRP (CP)",
                    EARTH_MOON_SUN_REFERENCE_DATASET_ID,
                    True,
                    True,
                ),
                (
                    "SYNTHETIC FULL FORCE MODEL",
                    DEMO_EARTH_MOON_SUN_SRP_DATASET_ID,
                    True,
                    True,
                ),
            ),
        ),
    )
    user_groups = []
    for metadata in list_reference_datasets():
        if not (
            metadata.get("user_supplied") or metadata.get("admin_session")
        ):
            continue
        dataset = get_reference_dataset(metadata["id"])
        entries = []
        for include_srp, scenario_group in (
            (False, dataset.get("scenarios", {})),
            (True, dataset.get("srp_scenarios", {})),
        ):
            for include_moon, scenario in scenario_group.items():
                entries.append(
                    (
                        scenario["name"],
                        dataset["id"],
                        bool(include_moon),
                        include_srp,
                    )
                )
        if entries:
            user_groups.append(
                (
                    (
                        "ADMIN SESSION — "
                        if dataset.get("admin_session")
                        else "USER REFERENCE — "
                    )
                    + dataset.get("short_label", dataset["label"]),
                    tuple(entries),
                )
            )
    return bundled_groups + tuple(user_groups)


def populate_reference_scenario_combo(combo, default_index=2):
    """Referans ssenarilərini başlıqlar və fiziki açarlarla combo-ya yaz."""

    combo.clear()
    for group_label, entries in reference_scenario_groups():
        combo.addItem(group_label, None)
        header_item = combo.model().item(combo.count() - 1)
        if header_item is not None:
            header_item.setEnabled(False)

        for model_label, dataset_id, include_moon, include_srp in entries:
            combo.addItem(f"    {model_label}", dataset_id)
            item_index = combo.count() - 1
            item = combo.model().item(item_index)
            if dataset_id is None:
                if item is not None:
                    item.setEnabled(False)
                continue
            combo.setItemData(
                item_index,
                bool(include_moon),
                REFERENCE_SCENARIO_MOON_ROLE,
            )
            combo.setItemData(
                item_index,
                bool(include_srp),
                REFERENCE_SCENARIO_SRP_ROLE,
            )

    if 0 <= default_index < combo.count():
        combo.setCurrentIndex(default_index)


EARTH_EQUATORIAL_RADIUS_KM = 6378.137
EARTH_POLAR_RADIUS_KM = 6356.752314245
WGS84_FLATTENING = 1.0 / 298.257223563
MOON_MEAN_RADIUS_KM = 1737.4

# Lightweight offline land geometry. It is intentionally simplified for the
# small globe shown in the operations plot, while retaining recognisable
# coastlines without adding a heavy GIS dependency or a network requirement.
EARTH_LAND_POLYGONS = (
    # North America
    ((-168, 72), (-150, 70), (-138, 58), (-126, 50), (-124, 39),
     (-117, 31), (-106, 23), (-97, 18), (-88, 20), (-81, 27),
     (-80, 34), (-73, 42), (-61, 47), (-55, 55), (-64, 62),
     (-82, 66), (-105, 73), (-135, 74)),
    # South America
    ((-81, 12), (-70, 11), (-59, 7), (-48, 1), (-35, -7),
     (-39, -20), (-47, -29), (-54, -39), (-67, -55),
     (-74, -44), (-76, -26), (-81, -10)),
    # Greenland
    ((-73, 60), (-58, 59), (-42, 65), (-20, 75), (-27, 83),
     (-50, 84), (-66, 76)),
    # Europe and Asia
    ((-11, 36), (-10, 58), (6, 70), (31, 72), (58, 76),
     (88, 76), (116, 71), (143, 61), (161, 51), (151, 42),
     (133, 33), (122, 23), (109, 10), (97, 7), (80, 8),
     (69, 21), (56, 25), (45, 36), (31, 41), (20, 35),
     (10, 45), (1, 43)),
    # Africa
    ((-17, 37), (10, 37), (31, 31), (43, 12), (51, 2),
     (42, -13), (33, -27), (20, -35), (5, -35), (-8, -20),
     (-17, 5), (-10, 21)),
    # India and south-east Asia
    ((66, 24), (78, 29), (89, 23), (96, 17), (105, 8),
     (103, 1), (94, 6), (83, 8), (77, 6), (72, 17)),
    # Australia
    ((112, -11), (130, -11), (145, -17), (153, -28),
     (146, -39), (130, -43), (115, -35), (111, -23)),
    # Japan
    ((129, 31), (136, 34), (142, 43), (146, 45), (142, 36)),
    # British Isles
    ((-10, 50), (-6, 58), (1, 59), (2, 51)),
    # Madagascar
    ((47, -13), (51, -17), (49, -26), (44, -24)),
    # Indonesia
    ((95, 5), (108, 5), (119, -3), (131, -4), (141, -8),
     (128, -10), (113, -8), (101, -4)),
)

# Build the coastline paths once.  Reconstructing them for every camera frame
# is surprisingly expensive and was one of the largest sources of drag-view
# stutter in Orbital View.
EARTH_LAND_PATHS = tuple(
    MplPath(np.asarray(polygon, dtype=float))
    for polygon in EARTH_LAND_POLYGONS
)


def wgs84_geodetic_altitude_km(positions):
    """Calculate geodetic height above the WGS-84 ellipsoid."""

    vectors = np.asarray(
        positions,
        dtype=float,
    )
    scalar_input = vectors.ndim == 1
    vectors = np.atleast_2d(
        vectors
    )

    x = vectors[:, 0]
    y = vectors[:, 1]
    z = vectors[:, 2]
    semi_major = EARTH_EQUATORIAL_RADIUS_KM
    semi_minor = EARTH_POLAR_RADIUS_KM
    eccentricity_squared = 1.0 - (
        semi_minor * semi_minor
        / (semi_major * semi_major)
    )
    second_eccentricity_squared = (
        semi_major * semi_major
        / (semi_minor * semi_minor)
        - 1.0
    )
    cylindrical_radius = np.hypot(
        x,
        y,
    )
    bowring_angle = np.arctan2(
        z * semi_major,
        cylindrical_radius * semi_minor,
    )
    latitude = np.arctan2(
        z
        + second_eccentricity_squared
        * semi_minor
        * np.sin(bowring_angle) ** 3,
        cylindrical_radius
        - eccentricity_squared
        * semi_major
        * np.cos(bowring_angle) ** 3,
    )
    prime_vertical_radius = semi_major / np.sqrt(
        1.0
        - eccentricity_squared
        * np.sin(latitude) ** 2
    )
    cosine_latitude = np.cos(
        latitude
    )
    altitude = np.where(
        np.abs(cosine_latitude) > 1.0e-12,
        cylindrical_radius / cosine_latitude - prime_vertical_radius,
        np.abs(z) - semi_minor,
    )

    if scalar_input:
        return float(altitude[0])
    return altitude

# NORAD identifiers make every optional object deterministic even when a TLE
# catalogue contains similarly named spacecraft.
ORBITAL_OBJECTS = {
    "earth": {
        "display": "Earth",
        "short": "EARTH",
        "kind": "earth",
        "color": "#2563EB",
        "edge": "#93C5FD",
        "default": True,
        "label_offset": (8, 8),
    },
    "moon": {
        "display": "Moon",
        "short": "MOON",
        "kind": "moon",
        "color": "#CBD5E1",
        "edge": "#F8FAFC",
        "default": True,
        "label_offset": (8, 8),
    },
    "active_profile": {
        "display": "Active spacecraft",
        "short": "ACTIVE SPACECRAFT",
        "kind": "satellite",
        "orbit_source": "cartesian",
        "tle_name": "",
        "norad": None,
        "color": "#34D399",
        "edge": "#D1FAE5",
        "marker": "o",
        "default": True,
        "label_offset": (8, 8),
    },
    "iss": {
        "display": "ISS (ZARYA)",
        "short": "ISS",
        "kind": "satellite",
        "tle_name": "ISS (ZARYA)",
        "norad": 25544,
        "color": "#F59E0B",
        "edge": "#FEF3C7",
        "marker": "^",
        "default": False,
        "label_offset": (8, 8),
    },
    "hubble": {
        "display": "Hubble Space Telescope",
        "short": "HUBBLE",
        "kind": "satellite",
        "tle_name": "HST",
        "norad": 20580,
        "color": "#FB7185",
        "edge": "#FFE4E6",
        "marker": "P",
        "default": False,
        "label_offset": (-8, -14),
        "label_align": "right",
    },
}


def load_application_fonts():
    """Register bundled Matplotlib fonts for consistent Qt rendering."""

    font_directory = os.path.join(
        get_matplotlib_data_path(),
        "fonts",
        "ttf",
    )
    for file_name in (
        "DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf",
    ):
        font_path = os.path.join(font_directory, file_name)
        if os.path.isfile(font_path):
            QFontDatabase.addApplicationFont(font_path)


# ============================================================
# BACKGROUND WORKERS
# ============================================================

def interface_animations_enabled():
    """Report whether short interface transitions should actually run.

    Offscreen rendering is used by the headless smoke test, the visual-QA
    capture and the unit suite.  Those callers show a surface and grab it in
    the same event-loop turn, so a running fade would be captured half
    finished.  Animation is presentation only: it is skipped there and the
    final state is applied immediately.
    """

    application = QApplication.instance()
    if application is None:
        return False
    return application.platformName() != "offscreen"


def _set_status_role(widget, role):
    """Apply a semantic status role and immediately refresh Qt styling."""

    widget.setProperty("statusRole", str(role))
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


class TLEUpdateWorker(QObject):

    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def run(self):
        try:
            metadata = update_local_tle()
            self.completed.emit(
                metadata
            )
        except Exception as error:
            self.failed.emit(
                f"{type(error).__name__}: {error}"
            )


class PropagationWorker(QObject):

    completed = pyqtSignal(object, object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(self, parameters):
        super().__init__()
        self.parameters = parameters

    def run(self):
        try:
            times, states = propagate_trajectory(
                **self.parameters,
                cancel_check=(
                    self.thread().isInterruptionRequested
                ),
                progress_callback=self.progress.emit,
            )
            self.completed.emit(
                times,
                states,
            )
        except PropagationCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(
                f"{type(error).__name__}: {error}"
            )


class GraphPredictionWorker(QObject):

    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(self, parameters):
        super().__init__()
        self.parameters = parameters
        self._last_progress = -1

    def _emit_progress(self, value):
        value = int(value)
        if value != self._last_progress:
            self._last_progress = value
            self.progress.emit(value)

    def run(self):
        try:
            result = compute_perturbation_prediction(
                **self.parameters,
                cancel_check=self.thread().isInterruptionRequested,
                progress_callback=self._emit_progress,
            )
            self.completed.emit(result)
        except PropagationCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(f"{type(error).__name__}: {error}")


class OrbitDeterminationWorker(QObject):

    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    progress = pyqtSignal(int)
    stage = pyqtSignal(str)

    def __init__(self, parameters):
        super().__init__()
        self.parameters = parameters

    def run(self):
        try:
            result = fit_weighted_least_squares(
                **self.parameters,
                cancel_check=self.thread().isInterruptionRequested,
                progress_callback=lambda value, stage: (
                    self.progress.emit(int(value)),
                    self.stage.emit(str(stage)),
                ),
            )
            self.completed.emit(result)
        except OrbitDeterminationCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(f"{type(error).__name__}: {error}")


class EclipsePredictionWorker(QObject):

    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(self, parameters, initial_epoch, geometry=None):
        super().__init__()
        self.parameters = parameters
        self.initial_epoch = initial_epoch
        self.geometry = geometry or EclipseGeometryOptions()

    def run(self):
        try:
            times, states = propagate_trajectory(
                **self.parameters,
                cancel_check=self.thread().isInterruptionRequested,
                progress_callback=lambda value: self.progress.emit(
                    int(80 * int(value) / 100)
                ),
            )
            if self.thread().isInterruptionRequested():
                self.cancelled.emit()
                return
            # Force switches above affect only the propagated trajectory.
            # Detection below is a separate geometric pass over that state
            # history and therefore has no SRP/J2/Moon-gravity prerequisite.
            prediction = predict_eclipses(
                times,
                states,
                self.initial_epoch,
                geometry=self.geometry,
                cancel_check=self.thread().isInterruptionRequested,
                progress_callback=lambda value: self.progress.emit(
                    80 + int(20 * int(value) / 100)
                ),
            )
            self.completed.emit(prediction)
        except (PropagationCancelled, EclipsePredictionCancelled):
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(
                f"{type(error).__name__}: {error}"
            )


class SunOutageWorker(QObject):

    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(self, parameters):
        super().__init__()
        self.parameters = dict(parameters)

    def run(self):
        try:
            prediction = predict_sun_outages(
                **self.parameters,
                cancel_check=self.thread().isInterruptionRequested,
                progress_callback=lambda value: self.progress.emit(int(value)),
            )
            self.completed.emit(prediction)
        except SunOutageCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(f"{type(error).__name__}: {error}")


class YearlyEclipseWorker(QObject):

    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    progress = pyqtSignal(int)
    stage = pyqtSignal(str)
    date_changed = pyqtSignal(str)

    def __init__(
        self,
        parameters,
        selected_year=None,
        *,
        interval_start_utc=None,
        interval_end_utc=None,
        return_schedule=True,
        shadow_bodies=("EARTH",),
        seed_candidate_epochs=(),
        geometry=None,
    ):
        super().__init__()
        self.parameters = dict(parameters)
        self.geometry = geometry or EclipseGeometryOptions()
        self.return_schedule = bool(return_schedule)
        self.shadow_bodies = tuple(
            dict.fromkeys(str(body).strip().upper() for body in shadow_bodies)
        )
        if not self.shadow_bodies or any(
            body not in {"EARTH", "MOON"} for body in self.shadow_bodies
        ):
            raise ValueError("shadow_bodies must contain EARTH and/or MOON.")
        self.seed_candidate_epochs = tuple(
            epoch.astimezone(timezone.utc)
            for epoch in seed_candidate_epochs
        )
        if interval_start_utc is None or interval_end_utc is None:
            if selected_year is None:
                raise ValueError(
                    "selected_year or an explicit UTC interval is required."
                )
            self.selected_year = int(selected_year)
            self.interval_start_utc = datetime(
                self.selected_year,
                1,
                1,
                tzinfo=timezone.utc,
            )
            self.interval_end_utc = datetime(
                self.selected_year + 1,
                1,
                1,
                tzinfo=timezone.utc,
            )
        else:
            if interval_start_utc.tzinfo is None or interval_end_utc.tzinfo is None:
                raise ValueError("Reference interval must be timezone-aware.")
            self.interval_start_utc = interval_start_utc.astimezone(
                timezone.utc
            )
            self.interval_end_utc = interval_end_utc.astimezone(
                timezone.utc
            )
            if self.interval_end_utc <= self.interval_start_utc:
                raise ValueError("Reference interval end must be after start.")
            self.selected_year = self.interval_start_utc.year

    @staticmethod
    def _scaled_progress(callback, start, end):
        span = int(end) - int(start)
        return lambda value: callback(
            int(start) + int(span * int(value) / 100)
        )

    def run(self):
        try:
            search_start = self.interval_start_utc
            search_end = self.interval_end_utc
            self.date_changed.emit(
                f"{search_start:%Y-%m-%d} → "
                f"{(search_end - timedelta(microseconds=1)):%Y-%m-%d} UTC"
            )
            initial_epoch = self.parameters.pop("initial_epoch")
            initial_state = self.parameters.pop("initial_state")
            nominal_longitude_deg = self.parameters.pop(
                "nominal_geostationary_longitude_deg",
                None,
            )
            alignment_seconds = (search_start - initial_epoch).total_seconds()

            if nominal_longitude_deg is not None:
                initial_epoch = search_start
                initial_state = get_nominal_geostationary_state(
                    search_start,
                    nominal_longitude_deg,
                )
                self.stage.emit(
                    f"NOMINAL GEO {float(nominal_longitude_deg):.1f}°E"
                )
                self.progress.emit(20)
            elif alignment_seconds:
                self.stage.emit("ALIGNING STATE")
                self.date_changed.emit(
                    f"Aligning state to {search_start:%Y-%m-%d %H:%M} UTC"
                )
                self.progress.emit(1)
                _times, aligned_states = propagate_trajectory(
                    initial_state=initial_state,
                    initial_epoch=initial_epoch,
                    duration_seconds=alignment_seconds,
                    output_step=abs(alignment_seconds),
                    max_step=1800.0,
                    cancel_check=self.thread().isInterruptionRequested,
                    progress_callback=self._scaled_progress(
                        self.progress.emit,
                        1,
                        20,
                    ),
                    **self.parameters,
                )
                initial_state = aligned_states[-1]
            else:
                self.progress.emit(20)

            # Fast first pass: one-hour samples locate the eclipse seasons.
            # The smooth GEO orbit is still integrated continuously; only the
            # expensive output/occultation classification is coarse here.
            self.stage.emit(
                "HOURLY YEAR SCAN"
                if self.return_schedule
                else "HOURLY REFERENCE SCAN"
            )
            self.date_changed.emit(
                f"Hourly scan: {search_start:%Y-%m-%d} → "
                f"{(search_end - timedelta(microseconds=1)):%Y-%m-%d} UTC"
            )
            if nominal_longitude_deg is None:
                coarse_times, coarse_states = propagate_trajectory(
                    initial_state=initial_state,
                    initial_epoch=search_start,
                    duration_seconds=(search_end - search_start).total_seconds(),
                    output_step=3600.0,
                    max_step=1800.0,
                    cancel_check=self.thread().isInterruptionRequested,
                    progress_callback=self._scaled_progress(
                        self.progress.emit,
                        20,
                        70,
                    ),
                    **self.parameters,
                )
            else:
                coarse_times, coarse_states = nominal_geostationary_trajectory(
                    search_start,
                    (search_end - search_start).total_seconds(),
                    output_step=3600.0,
                    longitude_deg=nominal_longitude_deg,
                    cancel_check=self.thread().isInterruptionRequested,
                    progress_callback=self._scaled_progress(
                        self.progress.emit,
                        20,
                        70,
                    ),
                )
            self.stage.emit("FINDING CANDIDATE DAYS")
            detected_epochs = [
                epoch
                for epoch in self.seed_candidate_epochs
                if search_start <= epoch < search_end
            ]
            body_count = len(self.shadow_bodies)
            for body_index, shadow_body in enumerate(self.shadow_bodies):
                progress_start = 70 + int(10 * body_index / body_count)
                progress_end = 70 + int(10 * (body_index + 1) / body_count)
                coarse_prediction = predict_eclipses(
                    coarse_times,
                    coarse_states,
                    search_start,
                    shadow_body=shadow_body,
                    geometry=self.geometry,
                    cancel_check=self.thread().isInterruptionRequested,
                    progress_callback=self._scaled_progress(
                        self.progress.emit,
                        progress_start,
                        progress_end,
                    ),
                )
                detected_epochs.extend(
                    search_start + timedelta(seconds=float(seconds))
                    for seconds, state in zip(
                        coarse_prediction.elapsed_seconds,
                        coarse_prediction.states,
                    )
                    if state != "FULL SUN"
                )
            candidate_dates = set()
            for detected_epoch in detected_epochs:
                for day_offset in range(-4, 5):
                    candidate_date = (
                        detected_epoch + timedelta(days=day_offset)
                    ).date()
                    if search_start.date() <= candidate_date < search_end.date():
                        candidate_dates.add(candidate_date)

            refined_events = {}
            sorted_dates = sorted(candidate_dates)
            if sorted_dates:
                self.stage.emit("1-MINUTE REFINEMENT")
            for candidate_index, candidate_date in enumerate(sorted_dates):
                if self.thread().isInterruptionRequested():
                    raise EclipsePredictionCancelled(
                        "Yearly eclipse search cancelled by user."
                    )

                self.date_changed.emit(
                    f"1-minute refinement: {candidate_date.isoformat()} UTC"
                )

                # Use the nearest coarse eclipse hour as the expected daily
                # center, then inspect a generous +/-3-hour local window at
                # the requested one-minute resolution.
                nearest_detection = min(
                    detected_epochs,
                    key=lambda value: abs(
                        (value.date() - candidate_date).days
                    ),
                )
                expected_center = datetime(
                    candidate_date.year,
                    candidate_date.month,
                    candidate_date.day,
                    nearest_detection.hour,
                    nearest_detection.minute,
                    tzinfo=timezone.utc,
                )
                window_start = max(
                    search_start,
                    expected_center - timedelta(hours=3),
                )
                window_end = min(
                    search_end,
                    expected_center + timedelta(hours=3),
                )
                start_seconds = (window_start - search_start).total_seconds()
                start_index = max(
                    0,
                    int(np.searchsorted(
                        coarse_times,
                        start_seconds,
                        side="right",
                    )) - 1,
                )
                local_epoch = search_start + timedelta(
                    seconds=float(coarse_times[start_index])
                )
                local_duration = (window_end - local_epoch).total_seconds()
                if nominal_longitude_deg is None:
                    local_times, local_states = propagate_trajectory(
                        initial_state=coarse_states[start_index],
                        initial_epoch=local_epoch,
                        duration_seconds=local_duration,
                        output_step=60.0,
                        cancel_check=self.thread().isInterruptionRequested,
                        **self.parameters,
                    )
                else:
                    local_times, local_states = nominal_geostationary_trajectory(
                        local_epoch,
                        local_duration,
                        output_step=60.0,
                        longitude_deg=nominal_longitude_deg,
                        cancel_check=self.thread().isInterruptionRequested,
                    )
                for shadow_body in self.shadow_bodies:
                    local_prediction = predict_eclipses(
                        local_times,
                        local_states,
                        local_epoch,
                        shadow_body=shadow_body,
                        geometry=self.geometry,
                        cancel_check=self.thread().isInterruptionRequested,
                    )
                    for event in local_prediction.events:
                        reference_epoch = next(
                            (
                                value
                                for value in (
                                    event.penumbra_entry_utc,
                                    event.umbra_entry_utc,
                                    event.umbra_exit_utc,
                                    event.penumbra_exit_utc,
                                )
                                if value is not None
                            ),
                            None,
                        )
                        if reference_epoch is not None:
                            reference_epoch = reference_epoch.astimezone(
                                timezone.utc
                            )
                            if search_start <= reference_epoch < search_end:
                                refined_events[
                                    f"{shadow_body}:{reference_epoch.isoformat()}"
                                ] = event

                if sorted_dates:
                    self.progress.emit(
                        80 + int(
                            20 * (candidate_index + 1) / len(sorted_dates)
                        )
                    )

            ordered_events = sorted(
                refined_events.values(),
                key=lambda event: next(
                    value
                    for value in (
                        event.penumbra_entry_utc,
                        event.umbra_entry_utc,
                        event.umbra_exit_utc,
                        event.penumbra_exit_utc,
                    )
                    if value is not None
                )
            )
            prediction = EclipsePrediction(
                elapsed_seconds=np.array([0.0, 60.0]),
                illumination_fraction=np.ones(2),
                states=("FULL SUN", "FULL SUN"),
                events=tuple(ordered_events),
                source_step_seconds=60.0,
            )
            self.progress.emit(100)
            if self.return_schedule:
                schedule = build_yearly_eclipse_schedule(
                    prediction,
                    self.selected_year,
                )
                self.completed.emit(schedule)
            else:
                self.completed.emit(prediction)
        except (PropagationCancelled, EclipsePredictionCancelled):
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(f"{type(error).__name__}: {error}")


class ReferenceComparisonWorker(QObject):

    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(
        self,
        numerical_settings,
        include_moon,
        include_sun,
        include_srp,
        calibration_enabled,
        dataset_id,
        srp_overrides=None,
    ):
        super().__init__()
        self.numerical_settings = numerical_settings
        self.include_moon = bool(include_moon)
        self.include_sun = bool(include_sun)
        self.include_srp = bool(include_srp)
        self.calibration_enabled = bool(calibration_enabled)
        self.dataset_id = str(dataset_id)
        self.srp_overrides = dict(srp_overrides or {})

    def run(self):
        try:
            result = run_reference_scenario(
                include_moon=self.include_moon,
                include_sun=self.include_sun,
                include_srp=self.include_srp,
                calibration_enabled=self.calibration_enabled,
                dataset_id=self.dataset_id,
                srp_overrides=self.srp_overrides,
                **self.numerical_settings,
                cancel_check=(
                    self.thread().isInterruptionRequested
                ),
                progress_callback=self.progress.emit,
            )
            self.completed.emit(result)
        except PropagationCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(
                f"{type(error).__name__}: {error}"
            )


# ============================================================
# MISSION-CONTROL BACKGROUND
# ============================================================

class MissionControlSurface(QWidget):
    """Low-contrast orbital HUD backdrop for the mission theme."""

    @staticmethod
    def _with_alpha(colour, alpha):
        value = QColor(colour)
        value.setAlpha(int(alpha))
        return value

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(theme.BACKGROUND))
        if theme.is_retro():
            painter.end()
            super().paintEvent(event)
            return

        width = float(self.width())
        height = float(self.height())

        horizon_glow = QLinearGradient(0.0, 0.0, width, height * 0.72)
        horizon_glow.setColorAt(
            0.0,
            self._with_alpha(theme.ACCENT_INFO, 15 if theme.is_normal() else 12),
        )
        horizon_glow.setColorAt(
            0.42,
            self._with_alpha(theme.ACCENT, 7 if theme.is_normal() else 5),
        )
        horizon_glow.setColorAt(
            1.0,
            self._with_alpha(theme.BACKGROUND, 0),
        )
        painter.fillRect(self.rect(), horizon_glow)

        grid_pen = QPen(
            self._with_alpha(theme.BORDER_STRONG, 20 if theme.is_normal() else 28),
            1.0,
        )
        painter.setPen(grid_pen)
        grid_step = 56
        for x in range(0, self.width(), grid_step):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), grid_step):
            painter.drawLine(0, y, self.width(), y)

        orbital_glow = QRadialGradient(
            width * 0.88,
            height * 0.12,
            max(width, height) * 0.46,
        )
        orbital_glow.setColorAt(
            0.0,
            self._with_alpha(theme.ACCENT, 18 if theme.is_normal() else 12),
        )
        orbital_glow.setColorAt(
            0.55,
            self._with_alpha(theme.ACCENT_INFO, 6),
        )
        orbital_glow.setColorAt(1.0, self._with_alpha(theme.BACKGROUND, 0))
        painter.fillRect(self.rect(), orbital_glow)

        painter.setPen(
            QPen(self._with_alpha(theme.ACCENT_INFO, 32), 1.0)
        )
        orbit_bounds = QRectF(
            width * 0.67,
            -height * 0.24,
            width * 0.48,
            height * 0.67,
        )
        painter.drawArc(orbit_bounds, 205 * 16, 225 * 16)
        painter.setPen(
            QPen(self._with_alpha(theme.STATUS_ERROR, 68), 2.0)
        )
        painter.drawArc(orbit_bounds, 314 * 16, 13 * 16)

        painter.end()
        super().paintEvent(event)


class HeroBannerFrame(QFrame):
    """Mission header with Normal artwork and a compact Retro title band."""

    def __init__(self, image_path, parent=None, interface_theme="normal"):
        super().__init__(parent)
        self._background = QPixmap(image_path)
        self._interface_theme = interface_theme

    def set_theme(self, interface_theme, image_path):
        self._interface_theme = str(interface_theme or "normal").lower()
        background = QPixmap(image_path)
        if not background.isNull():
            self._background = background
        self.setStyleSheet("")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if theme.is_retro():
            return
        if self._background.isNull() or self.width() <= 0 or self.height() <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(self.rect()), 8.0, 8.0)
        painter.setClipPath(clip_path)

        target = QRectF(self.rect())
        image_width = float(self._background.width())
        image_height = float(self._background.height())
        target_ratio = target.width() / target.height()
        image_ratio = image_width / image_height
        if image_ratio > target_ratio:
            source_width = image_height * target_ratio
            source = QRectF(
                image_width - source_width,
                0.0,
                source_width,
                image_height,
            )
        else:
            source_height = image_width / target_ratio
            source = QRectF(
                0.0,
                (image_height - source_height) / 2.0,
                image_width,
                source_height,
            )
        painter.drawPixmap(target, self._background, source)

        # Text sits at both ends of the banner, so the scrim is dark under
        # the title and dark again under the status controls, leaving one
        # bright window of artwork between them.  A single left-to-right
        # ramp used to leave the right-hand controls sitting on open sky.
        readability = QLinearGradient(0.0, 0.0, target.width(), 0.0)
        readability.setColorAt(0.0, QColor(5, 9, 14, 244))
        readability.setColorAt(0.40, QColor(5, 9, 14, 214))
        readability.setColorAt(0.60, QColor(5, 9, 14, 132))
        readability.setColorAt(0.78, QColor(5, 9, 14, 196))
        readability.setColorAt(1.0, QColor(5, 9, 14, 228))
        painter.fillRect(target, readability)

        painter.setClipping(False)
        painter.setPen(QPen(QColor(theme.BORDER_STRONG), 1.0))
        painter.drawRoundedRect(
            target.adjusted(0.5, 0.5, -0.5, -0.5), 8.0, 8.0
        )
        painter.setPen(QPen(QColor(theme.ACCENT), 2.0))
        painter.drawLine(8, 1, max(8, self.width() - 8), 1)


class SettingsOverlay(QWidget):
    """Compact in-window settings surface with two clear destinations."""

    def __init__(self, owner, parent):
        super().__init__(parent)
        self.owner = owner
        self.setObjectName("settingsOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._panel_opacity = None
        self._panel_fade = None
        parent.installEventFilter(self)

        overlay_layout = QVBoxLayout(self)
        overlay_layout.setContentsMargins(24, 24, 24, 24)
        overlay_layout.addStretch()

        center_row = QHBoxLayout()
        center_row.addStretch()
        panel = QFrame()
        self.panel = panel
        panel.setObjectName("settingsPanel")
        panel.setMinimumSize(520, 320)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("settingsHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 14, 14, 14)
        header_title = QLabel("SETTINGS")
        header_title.setObjectName("settingsTitle")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        close_button = QPushButton("×")
        close_button.setObjectName("settingsCloseButton")
        close_button.setFixedSize(34, 34)
        close_button.setToolTip("Close settings")
        close_button.clicked.connect(self.hide)
        header_layout.addWidget(close_button)
        panel_layout.addWidget(header)

        body = QFrame()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        navigation = QFrame()
        navigation.setObjectName("settingsNavigation")
        navigation.setMinimumWidth(168)
        navigation.setMaximumWidth(208)
        navigation_layout = QVBoxLayout(navigation)
        navigation_layout.setContentsMargins(12, 16, 12, 16)
        navigation_layout.setSpacing(8)

        self.program_nav_button = QPushButton("PROGRAM &\nCONFIGURATION")
        self.program_nav_button.setObjectName("settingsNavButton")
        self.program_nav_button.setCheckable(True)
        self.program_nav_button.setChecked(True)
        self.program_nav_button.setMinimumHeight(52)
        navigation_layout.addWidget(self.program_nav_button)
        self.admin_nav_button = QPushButton("ADMIN ACCESS")
        self.admin_nav_button.setObjectName("settingsNavButton")
        self.admin_nav_button.setCheckable(True)
        self.admin_nav_button.setMinimumHeight(42)
        navigation_layout.addWidget(self.admin_nav_button)
        self.credits_nav_button = QPushButton("CREDITS")
        self.credits_nav_button.setObjectName("settingsNavButton")
        self.credits_nav_button.setCheckable(True)
        self.credits_nav_button.setMinimumHeight(42)
        navigation_layout.addWidget(self.credits_nav_button)
        # The three destinations read as one contiguous group; the free
        # space belongs below them, not wedged between the first and the
        # second entry.
        navigation_layout.addStretch(1)
        body_layout.addWidget(navigation)

        self.pages = QStackedWidget()
        self.pages.setObjectName("settingsPages")
        self.pages.addWidget(self._create_program_page())
        self.pages.addWidget(self._create_admin_page())
        self.pages.addWidget(self._create_credits_page())
        body_layout.addWidget(self.pages, 1)
        panel_layout.addWidget(body, 1)

        center_row.addWidget(panel)
        center_row.addStretch()
        overlay_layout.addLayout(center_row)
        overlay_layout.addStretch()

        self.program_nav_button.clicked.connect(
            lambda: self._select_page(0)
        )
        self.admin_nav_button.clicked.connect(
            lambda: self._select_page(1)
        )
        self.credits_nav_button.clicked.connect(
            lambda: self._select_page(2)
        )
        self.apply_theme()
        self._fit_panel_to_overlay()
        self.hide()

    def _create_program_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        heading = QLabel("Program & Configuration")
        heading.setObjectName("settingsPageTitle")
        layout.addWidget(heading)
        description = QLabel(
            "Application identity, active flight-dynamics models and "
            "numerical precision."
        )
        description.setObjectName("settingsPageDescription")
        layout.addWidget(description)

        appearance_card = QFrame()
        appearance_card.setObjectName("settingsCard")
        appearance_card.setProperty("surfaceRole", "sand")
        appearance_card.setMinimumHeight(190)
        appearance_layout = QGridLayout(appearance_card)
        appearance_layout.setContentsMargins(16, 11, 16, 11)
        appearance_layout.setHorizontalSpacing(14)
        appearance_layout.setVerticalSpacing(5)
        appearance_title = QLabel("INTERFACE APPEARANCE")
        appearance_title.setObjectName("settingsCaption")
        appearance_layout.addWidget(appearance_title, 0, 0, 1, 2)
        appearance_layout.addWidget(QLabel("Theme"), 1, 0)
        theme_choices = QHBoxLayout()
        self.settings_normal_theme = QRadioButton("Normal")
        self.settings_retro_theme = QRadioButton("Retro")
        self.settings_theme_group = QButtonGroup(self)
        self.settings_theme_group.addButton(self.settings_normal_theme)
        self.settings_theme_group.addButton(self.settings_retro_theme)
        self.settings_normal_theme.setToolTip(
            "Use the established modern mission-control interface."
        )
        self.settings_retro_theme.setToolTip(
            "Use the Windows XP-inspired engineering interface."
        )
        self.settings_normal_theme.toggled.connect(self.preview_theme)
        self.settings_retro_theme.toggled.connect(self.preview_theme)
        theme_choices.addWidget(self.settings_normal_theme)
        theme_choices.addWidget(self.settings_retro_theme)
        theme_choices.addStretch(1)
        appearance_layout.addLayout(theme_choices, 1, 1)
        appearance_layout.addWidget(QLabel("Language"), 2, 0)
        self.settings_language = QComboBox()
        self.settings_language.setObjectName("settingsLanguageSelector")
        self.settings_language.addItem("Azerbaijani", "az")
        self.settings_language.addItem("English", "en")
        language_index = self.settings_language.findData(self.owner.language)
        if language_index >= 0:
            self.settings_language.setCurrentIndex(language_index)
        self.settings_language.setToolTip(
            "Azerbaijani and English update the active interface immediately."
        )
        self.settings_language.currentIndexChanged.connect(
            self.preview_language
        )
        appearance_layout.addWidget(self.settings_language, 2, 1)
        appearance_note = QLabel(
            "Normal and Retro update the complete interface immediately. Save "
            "Configuration to restore the selected theme on the next launch. "
            "Calculations are unchanged."
        )
        appearance_note.setObjectName("settingsPageDescription")
        appearance_note.setWordWrap(True)
        appearance_note.setMinimumHeight(34)
        appearance_layout.addWidget(appearance_note, 3, 0, 1, 2)
        appearance_layout.setColumnStretch(1, 1)
        layout.addWidget(appearance_card)

        identity_card = QFrame()
        identity_card.setObjectName("settingsCard")
        identity_card.setProperty("surfaceRole", "blue")
        identity_layout = QGridLayout(identity_card)
        identity_layout.setContentsMargins(16, 13, 16, 13)
        identity_layout.setHorizontalSpacing(18)
        identity_layout.setVerticalSpacing(8)
        identity_rows = (
            ("APPLICATION", "Orbital Perturbation Analyzer"),
            ("VERSION", f"v{APP_VERSION}"),
            ("DATA MODE", "PUBLIC SYNTHETIC / DEMO"),
            ("REFERENCE FRAME", "Earth-centred J2000"),
        )
        for row, (caption, value) in enumerate(identity_rows):
            caption_label = QLabel(caption)
            caption_label.setObjectName("settingsCaption")
            value_label = QLabel(value)
            value_label.setObjectName("settingsValue")
            identity_layout.addWidget(caption_label, row, 0)
            identity_layout.addWidget(value_label, row, 1)
        identity_layout.setColumnStretch(1, 1)
        layout.addWidget(identity_card)

        model_card = QFrame()
        model_card.setObjectName("settingsCard")
        model_card.setProperty("surfaceRole", "lavender")
        model_layout = QGridLayout(model_card)
        model_layout.setContentsMargins(16, 12, 16, 12)
        model_layout.setHorizontalSpacing(12)
        model_layout.setVerticalSpacing(8)
        model_items = (
            ("EARTH GRAVITY", "EGM96 4×4"),
            ("EPHEMERIS", "DE440"),
            ("PERTURBATIONS", "Moon · Sun · SRP"),
        )
        for column, (caption, value) in enumerate(model_items):
            caption_label = QLabel(caption)
            caption_label.setObjectName("settingsCaption")
            value_label = QLabel(value)
            value_label.setObjectName("settingsValue")
            model_layout.addWidget(caption_label, 0, column)
            model_layout.addWidget(value_label, 1, column)
            model_layout.setColumnStretch(column, 1)
        layout.addWidget(model_card)

        precision_card = QFrame()
        precision_card.setObjectName("settingsCard")
        precision_card.setProperty("surfaceRole", "sage")
        precision_layout = QGridLayout(precision_card)
        precision_layout.setContentsMargins(16, 12, 16, 12)
        precision_layout.setHorizontalSpacing(10)
        precision_layout.setVerticalSpacing(8)
        precision_title = QLabel("NUMERICAL PRECISION")
        precision_title.setObjectName("settingsCaption")
        precision_layout.addWidget(precision_title, 0, 0, 1, 4)
        self.settings_rtol = QLineEdit()
        self.settings_atol = QLineEdit()
        self.settings_max_step = QSpinBox()
        self.settings_max_step.setRange(1, 3600)
        precision_layout.addWidget(QLabel("Relative tol."), 1, 0)
        precision_layout.addWidget(self.settings_rtol, 1, 1)
        precision_layout.addWidget(QLabel("Absolute tol."), 1, 2)
        precision_layout.addWidget(self.settings_atol, 1, 3)
        precision_layout.addWidget(QLabel("Maximum step [s]"), 2, 0)
        precision_layout.addWidget(self.settings_max_step, 2, 1)
        self.settings_eop = QCheckBox("IERS EOP correction")
        self.settings_eop.setToolTip(
            "Use bundled UT1−UTC and polar-motion Earth orientation data."
        )
        precision_layout.addWidget(self.settings_eop, 2, 2, 1, 2)
        layout.addWidget(precision_card)

        footer = QHBoxLayout()
        self.settings_apply_status = QLabel("")
        self.settings_apply_status.setObjectName("settingsApplyStatus")
        footer.addWidget(self.settings_apply_status, 1)
        self.apply_configuration_button = QPushButton("APPLY TO SESSION")
        self.apply_configuration_button.setObjectName("settingsPrimaryButton")
        self.apply_configuration_button.clicked.connect(self.apply_configuration)
        footer.addWidget(self.apply_configuration_button)
        self.save_configuration_button = QPushButton("SAVE CONFIGURATION")
        self.save_configuration_button.setObjectName("settingsPrimaryButton")
        self.save_configuration_button.clicked.connect(self.save_configuration)
        footer.addWidget(self.save_configuration_button)
        layout.addLayout(footer)
        # The declared minimum application height is smaller than the complete
        # Settings form. Keep every control reachable instead of compressing
        # and clipping the language row on shorter displays.
        page.setMinimumHeight(650)
        scroll = QScrollArea()
        scroll.setObjectName("settingsProgramScroll")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        return scroll

    def _create_admin_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        heading = QLabel("ADMIN ACCESS")
        heading.setObjectName("settingsPageTitle")
        layout.addWidget(heading)
        description = QLabel(
            "Public Mode is always the startup state. Admin content is loaded "
            "only from a signed, encrypted package authorized for this "
            "Windows user/device. Private files stay outside the application "
            "folder, so sharing a ZIP of the program does not include them. "
            "Passwords, private paths and unlock state are never saved."
        )
        description.setObjectName("settingsPageDescription")
        description.setWordWrap(True)
        layout.addWidget(description)

        storage_group = QGroupBox("LOCAL ADMIN STORAGE")
        storage_layout = QGridLayout(storage_group)
        storage_layout.addWidget(QLabel("Device"), 0, 0)
        self.admin_device_storage_status = QLabel()
        self.admin_device_storage_status.setObjectName("settingsValue")
        self.admin_device_storage_status.setWordWrap(True)
        storage_layout.addWidget(self.admin_device_storage_status, 0, 1)
        storage_layout.addWidget(QLabel("Encrypted package"), 1, 0)
        self.admin_package_storage_status = QLabel()
        self.admin_package_storage_status.setObjectName("settingsValue")
        self.admin_package_storage_status.setWordWrap(True)
        storage_layout.addWidget(self.admin_package_storage_status, 1, 1)
        storage_note = QLabel(
            "Only readiness is shown here. External private locations are "
            "never displayed, copied into the project, or written to normal settings."
        )
        storage_note.setWordWrap(True)
        storage_note.setObjectName("settingsPageDescription")
        storage_layout.addWidget(storage_note, 2, 0, 1, 2)
        storage_layout.setColumnStretch(1, 1)
        layout.addWidget(storage_group)

        enrollment_group = QGroupBox("DEVICE SETUP")
        self.admin_enrollment_group = enrollment_group
        enrollment_layout = QGridLayout(enrollment_group)
        enrollment_layout.addWidget(QLabel("Verification key"), 0, 0)
        self.admin_verification_key = QLineEdit()
        self.admin_verification_key.setPlaceholderText(
            "Select the provisioned Ed25519 public key"
        )
        enrollment_layout.addWidget(self.admin_verification_key, 0, 1)
        browse_key = QPushButton("BROWSE…")
        browse_key.clicked.connect(self._browse_admin_verification_key)
        enrollment_layout.addWidget(browse_key, 0, 2)
        self.admin_enroll_button = QPushButton("ENROLL THIS DEVICE")
        self.admin_enroll_button.clicked.connect(self._enroll_admin_device)
        enrollment_layout.addWidget(self.admin_enroll_button, 1, 1, 1, 2)
        enrollment_note = QLabel(
            "Enrollment generates a unique random device key protected by "
            "Windows DPAPI. Re-enrollment invalidates packages made for the "
            "previous device identity."
        )
        enrollment_note.setWordWrap(True)
        enrollment_note.setObjectName("settingsPageDescription")
        enrollment_layout.addWidget(enrollment_note, 2, 0, 1, 3)
        enrollment_layout.setColumnStretch(1, 1)
        layout.addWidget(enrollment_group)

        unlock_group = QGroupBox("SIGNED ADMIN PACKAGE")
        self.admin_unlock_group = unlock_group
        unlock_layout = QGridLayout(unlock_group)
        self.admin_package_picker = QWidget()
        package_picker_layout = QHBoxLayout(self.admin_package_picker)
        package_picker_layout.setContentsMargins(0, 0, 0, 0)
        package_picker_layout.addWidget(QLabel("Package"))
        self.admin_package_path = QLineEdit()
        self.admin_package_path.setPlaceholderText("Select a local .opa-admin package")
        self.admin_package_path.textChanged.connect(self.sync_admin_status)
        package_picker_layout.addWidget(self.admin_package_path, 1)
        self.admin_browse_package_button = QPushButton("BROWSE…")
        self.admin_browse_package_button.clicked.connect(self._browse_admin_package)
        package_picker_layout.addWidget(self.admin_browse_package_button)
        unlock_layout.addWidget(self.admin_package_picker, 0, 0, 1, 3)
        unlock_layout.addWidget(QLabel("Admin password"), 1, 0)
        self.admin_password = QLineEdit()
        self.admin_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.admin_password.setPlaceholderText("Password is used in memory only")
        self.admin_password.returnPressed.connect(self._unlock_admin_package)
        unlock_layout.addWidget(self.admin_password, 1, 1, 1, 2)
        button_row = QHBoxLayout()
        self.admin_unlock_button = QPushButton("UNLOCK")
        self.admin_unlock_button.setObjectName("settingsPrimaryButton")
        self.admin_unlock_button.clicked.connect(self._unlock_admin_package)
        button_row.addWidget(self.admin_unlock_button)
        self.admin_logout_button = QPushButton("LOG OUT")
        self.admin_logout_button.clicked.connect(self._logout_admin)
        button_row.addWidget(self.admin_logout_button)
        button_row.addStretch()
        unlock_layout.addLayout(button_row, 2, 1, 1, 2)
        unlock_layout.setColumnStretch(1, 1)
        layout.addWidget(unlock_group)

        self.admin_status = QLabel()
        self.admin_status.setObjectName("settingsApplyStatus")
        self.admin_status.setWordWrap(True)
        layout.addWidget(self.admin_status)
        self.admin_loaded_content = QLabel()
        self.admin_loaded_content.setObjectName("settingsPageDescription")
        self.admin_loaded_content.setWordWrap(True)
        layout.addWidget(self.admin_loaded_content)
        layout.addStretch()
        self.sync_admin_status()

        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        return scroll

    def _browse_admin_verification_key(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Admin Verification Key",
            "",
            "Public keys (*.pub *.pem);;All Files (*)",
            options=theme.file_dialog_options(),
        )
        if path:
            self.admin_verification_key.setText(path)

    def _browse_admin_package(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Admin Package",
            "",
            "OPA Admin Packages (*.opa-admin);;All Files (*)",
            options=theme.file_dialog_options(),
        )
        if path:
            self.admin_package_path.setText(path)

    def _set_admin_status(self, text, state):
        self.admin_status.setText(text)
        self.admin_status.setProperty("state", state)
        self.admin_status.style().unpolish(self.admin_status)
        self.admin_status.style().polish(self.admin_status)

    def _enroll_admin_device(self):
        try:
            self.owner.enroll_admin_device(self.admin_verification_key.text())
        except AdminSecurityError as error:
            self._set_admin_status(str(error), "error")
            return False
        self.admin_verification_key.clear()
        self._set_admin_status("Device enrollment completed.", "success")
        self.sync_admin_status()
        return True

    def _unlock_admin_package(self):
        password = self.admin_password.text()
        self.admin_password.clear()
        installed_package = default_admin_package_path()
        selected_package = self.admin_package_path.text().strip()
        package_path = (
            selected_package
            if selected_package
            else str(installed_package)
        )
        try:
            self.owner.unlock_admin_package(package_path, password)
        except AdminSecurityError as error:
            self._set_admin_status(str(error), "error")
            return False
        self._set_admin_status("Admin package unlocked for this session.", "success")
        self.sync_admin_status()
        return True

    def _logout_admin(self):
        self.owner.logout_admin_session()
        self.admin_password.clear()
        self.admin_package_path.clear()
        self._set_admin_status("Admin session cleared; Public Mode is active.", "success")
        self.sync_admin_status()

    def sync_admin_status(self):
        manager = getattr(self.owner, "admin_session", None)
        unlocked = bool(manager and manager.unlocked)
        installed_package = default_admin_package_path()
        enrollment_ready = bool(
            manager is not None and manager.enrollment_path.is_file()
        )
        installed_package_ready = installed_package.is_file()
        selected_package_ready = os.path.isfile(
            self.admin_package_path.text().strip()
        )
        package_ready = installed_package_ready or selected_package_ready

        self.admin_device_storage_status.setText(
            self.owner.tr("PROVISIONED FOR THIS WINDOWS USER/DEVICE")
            if enrollment_ready
            else self.owner.tr("SETUP REQUIRED")
        )
        self.admin_package_storage_status.setText(
            self.owner.tr("ENCRYPTED PACKAGE READY OUTSIDE APPLICATION FOLDER")
            if installed_package_ready
            else self.owner.tr("EXTERNAL PACKAGE NOT INSTALLED")
        )
        self.admin_enrollment_group.setVisible(
            not enrollment_ready and not unlocked
        )
        self.admin_package_picker.setVisible(
            not installed_package_ready and not unlocked
        )
        self.admin_unlock_group.setTitle(
            self.owner.tr("ADMIN PASSWORD")
            if enrollment_ready and package_ready
            else self.owner.tr("SIGNED ADMIN PACKAGE")
        )
        self.admin_unlock_button.setEnabled(
            not unlocked and enrollment_ready and package_ready
        )
        self.admin_logout_button.setEnabled(unlocked)
        if unlocked and manager.content is not None:
            content = manager.content
            self.admin_loaded_content.setText(self.owner.tr(
                "SESSION CONTENT — "
                f"{len(content.profiles)} profiles · "
                f"{len(content.reference_datasets)} references · "
                f"{len(content.eclipse_reference_datasets)} Eclipse sets · "
                f"{len(content.admin_modules)} data-only modules"
            ))
        else:
            self.admin_loaded_content.setText(
                self.owner.tr("PUBLIC MODE — LOCKED")
            )

    def _create_credits_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(34, 26, 34, 30)
        layout.setSpacing(12)

        heading = QLabel("Credits")
        heading.setObjectName("settingsPageTitle")
        layout.addWidget(heading)
        description = QLabel(
            "Orbital Perturbation Analyzer public edition. Personal contact "
            "records are not embedded in the distributable application."
        )
        description.setObjectName("settingsPageDescription")
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addSpacing(12)

        self._credit_email_labels = []
        layout.addStretch()
        version_label = QLabel(
            f"ORBITAL PERTURBATION ANALYZER  ·  VERSION {APP_VERSION}"
        )
        version_label.setObjectName("creditsVersion")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)
        return page

    def _select_page(self, index):
        self.pages.setCurrentIndex(index)
        self.program_nav_button.setChecked(index == 0)
        self.admin_nav_button.setChecked(index == 1)
        self.credits_nav_button.setChecked(index == 2)

    def sync_configuration(self):
        self.settings_rtol.setText(self.owner.integrator_rtol.text())
        self.settings_atol.setText(self.owner.integrator_atol.text())
        self.settings_max_step.setValue(self.owner.integrator_max_step.value())
        self.settings_eop.setChecked(is_eop_enabled())
        self.settings_normal_theme.blockSignals(True)
        self.settings_retro_theme.blockSignals(True)
        self.settings_normal_theme.setChecked(
            self.owner.interface_theme == "normal"
        )
        self.settings_retro_theme.setChecked(
            self.owner.interface_theme == "retro"
        )
        self.settings_normal_theme.blockSignals(False)
        self.settings_retro_theme.blockSignals(False)
        self.settings_language.blockSignals(True)
        language_index = self.settings_language.findData(
            self.owner.language
        )
        if language_index >= 0:
            self.settings_language.setCurrentIndex(language_index)
        self.settings_language.blockSignals(False)
        self.settings_apply_status.clear()
        self.sync_admin_status()

    def selected_theme(self):
        return "retro" if self.settings_retro_theme.isChecked() else "normal"

    def preview_theme(self, checked=False):
        if checked:
            self.owner.apply_interface_theme(self.selected_theme())

    def preview_language(self, _index=None):
        self.owner.apply_language(self.settings_language.currentData())

    def apply_configuration(self):
        try:
            rtol = float(self.settings_rtol.text())
            atol = float(self.settings_atol.text())
            if rtol <= 0.0 or atol <= 0.0:
                raise ValueError("Tolerances must be positive.")
        except ValueError as error:
            self.settings_apply_status.setText(str(error))
            self.settings_apply_status.setProperty("state", "error")
            self.settings_apply_status.style().unpolish(self.settings_apply_status)
            self.settings_apply_status.style().polish(self.settings_apply_status)
            return False

        self.owner.integrator_rtol.setText(self.settings_rtol.text().strip())
        self.owner.integrator_atol.setText(self.settings_atol.text().strip())
        self.owner.integrator_max_step.setValue(self.settings_max_step.value())
        self.owner.eop_enabled_checkbox.setChecked(self.settings_eop.isChecked())
        self.settings_eop.setChecked(is_eop_enabled())
        self.owner.apply_interface_theme(self.selected_theme())
        self.owner.apply_language(self.settings_language.currentData())
        self.settings_apply_status.setProperty("state", "success")
        self.settings_apply_status.setText("✓ Configuration updated")
        self.settings_apply_status.style().unpolish(self.settings_apply_status)
        self.settings_apply_status.style().polish(self.settings_apply_status)
        self.owner.refresh_localized_text()
        return True

    def save_configuration(self):
        """Apply the visible values and persist them through an explicit action."""

        if not self.apply_configuration():
            return
        try:
            self.owner.persist_configuration(
                self.selected_theme(),
                self.settings_language.currentData(),
            )
        except (OSError, ValueError) as error:
            self.settings_apply_status.setProperty("state", "error")
            self.settings_apply_status.setText(f"Save failed: {error}")
            self.settings_apply_status.style().unpolish(self.settings_apply_status)
            self.settings_apply_status.style().polish(self.settings_apply_status)
            return

        self.settings_apply_status.setProperty("state", "success")
        self.settings_apply_status.setText("Configuration saved")
        self.settings_apply_status.style().unpolish(self.settings_apply_status)
        self.settings_apply_status.style().polish(self.settings_apply_status)
        self.owner.refresh_localized_text()

    def show_overlay(self):
        self.sync_configuration()
        self._select_page(0)
        self.setGeometry(self.parentWidget().rect())
        self._fit_panel_to_overlay()
        self.raise_()
        self.show()
        self.setFocus(Qt.FocusReason.PopupFocusReason)
        self._run_entrance_fade()

    def _run_entrance_fade(self):
        """Fade the panel in without moving it.

        Opacity is the only animated property, so the panel never changes
        size or position while it appears and nothing around it reflows.
        """

        if not interface_animations_enabled():
            if self._panel_opacity is not None:
                self._panel_opacity.setOpacity(1.0)
            return
        if self._panel_opacity is None:
            self._panel_opacity = QGraphicsOpacityEffect(self.panel)
            self.panel.setGraphicsEffect(self._panel_opacity)
        if self._panel_fade is not None:
            self._panel_fade.stop()
        self._panel_opacity.setOpacity(0.0)
        fade = QPropertyAnimation(self._panel_opacity, b"opacity", self)
        fade.setDuration(130)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._panel_fade = fade
        fade.start()

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
            self._fit_panel_to_overlay()
        return super().eventFilter(watched, event)

    def _fit_panel_to_overlay(self):
        """Keep Settings responsive without locking it to one pixel size."""

        available_width = max(320, self.width() - 48)
        available_height = max(240, self.height() - 48)
        target_width = min(920, available_width)
        target_height = min(820, available_height)
        self.panel.setMinimumSize(
            min(700, target_width),
            min(600, target_height),
        )
        self.panel.setMaximumSize(target_width, target_height)
        self.panel.resize(target_width, target_height)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def apply_theme(self):
        self.setStyleSheet(theme.settings_stylesheet())
        for label in getattr(self, "_credit_email_labels", ()):
            email = label.property("emailAddress")
            label.setText(
                f'<a href="mailto:{email}" style="color:{theme.ACCENT}; '
                f'text-decoration:none;">{email}</a>'
            )

    @staticmethod
    def _style_sheet():
        return theme.settings_stylesheet()


# ============================================================
# GRAPH WIDGET
# ============================================================

class GraphWidget(ClickActivatedFigureCanvas):

    def __init__(self, parent=None, figsize=(10, 6)):

        self.figure = Figure(
            figsize=figsize,
            dpi=100
        )

        self.figure.patch.set_facecolor(
            theme.PLOT_FIGURE
        )

        self.ax = self.figure.add_subplot(
            111
        )

        super().__init__(
            self.figure
        )

        self.setParent(
            parent
        )

        self.style_axes()

        # Every chart uses the same scientific inspection behaviour: a
        # crosshair pointer and a parameter-aware readout next to the pointer.
        # The readout derives names and units from each axis instead of showing
        # ambiguous generic X/Y values.
        # The annotation is created lazily because several charts clear and
        # rebuild their axes while the application is running.
        self.setCursor(
            Qt.CursorShape.CrossCursor
        )
        self._coordinate_annotations = {}
        self.mpl_connect(
            "motion_notify_event",
            self._show_pointer_coordinates,
        )
        self.mpl_connect(
            "figure_leave_event",
            self._hide_pointer_coordinates,
        )

    @staticmethod
    def _format_pointer_value(value):

        value = float(value)
        magnitude = abs(value)
        if magnitude != 0.0 and (
            magnitude >= 1.0e6
            or magnitude < 1.0e-4
        ):
            return f"{value:.6e}"
        return f"{value:.6f}".rstrip("0").rstrip(".")

    @staticmethod
    def _clean_pointer_title(title):

        title = str(title or "").strip()
        # Plot titles sometimes append display-policy notes which are useful in
        # the heading but are not part of the physical parameter name.
        for separator in (" · ", " Â· "):
            if separator in title:
                title = title.split(separator, 1)[0].strip()
        return title

    @classmethod
    def _pointer_axis_descriptor(cls, axis_label, title, fallback):

        raw_label = str(axis_label or "").strip()
        clean_title = cls._clean_pointer_title(title)

        # Standard labels used throughout the application, for example
        # ``Longitude [deg E]`` and ``Elapsed time [days]``.
        bracket_match = re.fullmatch(r"(.+?)\s*\[([^\]]+)\]", raw_label)
        if bracket_match:
            return (
                bracket_match.group(1).strip(),
                bracket_match.group(2).strip(),
            )

        # Live graphs use ``Time (minutes, 0 = now)``.  Keep the zero-origin
        # information in the semantic name while treating minutes/hours as the
        # unit displayed beside the value.
        relative_time_match = re.fullmatch(
            r"Time\s*\((minutes|hours|seconds|days),\s*0\s*=\s*now\)",
            raw_label,
            flags=re.IGNORECASE,
        )
        if relative_time_match:
            return "Time from now", relative_time_match.group(1).lower()

        # A few graphs use parentheses for a scaled physical unit.
        parenthesis_match = re.fullmatch(r"(.+?)\s*\(([^()]+)\)", raw_label)
        if parenthesis_match:
            possible_unit = parenthesis_match.group(2).strip()
            if any(
                token in possible_unit.lower()
                for token in ("km", "m/s", "deg", "minute", "hour", "day")
            ):
                return parenthesis_match.group(1).strip(), possible_unit

        unit_only = {
            "km": "km",
            "km/s": "km/s",
            "deg": "deg",
            "degree": "deg",
            "degrees": "deg",
            "dimensionless": "",
            "state": "",
        }
        normalized_label = raw_label.lower()
        if normalized_label in unit_only:
            return clean_title or fallback, unit_only[normalized_label]

        if raw_label:
            return raw_label, ""
        return fallback, ""

    @staticmethod
    def _shared_axis_label(axis, coordinate):

        getter_name = "get_xlabel" if coordinate == "x" else "get_ylabel"
        label = getattr(axis, getter_name)().strip()
        if label:
            return label

        # Shared-axis subplot grids normally print the time label only on the
        # bottom row.  Reuse that semantic label for the upper-row tooltip.
        grouper = (
            axis.get_shared_x_axes()
            if coordinate == "x"
            else axis.get_shared_y_axes()
        )
        for sibling in grouper.get_siblings(axis):
            sibling_label = getattr(sibling, getter_name)().strip()
            if sibling_label:
                return sibling_label
        return ""

    @classmethod
    def _format_pointer_axis_value(
        cls,
        axis,
        coordinate,
        value,
    ):

        axis_label = cls._shared_axis_label(axis, coordinate)
        title = axis.get_title() if coordinate == "y" else ""
        fallback = (
            "Horizontal coordinate"
            if coordinate == "x"
            else cls._clean_pointer_title(axis.get_title()) or "Value"
        )
        parameter, unit = cls._pointer_axis_descriptor(
            axis_label,
            title,
            fallback,
        )

        # Matplotlib date axes store time as a floating-point day number.  Show
        # the actual timestamp rather than leaking that internal number.
        if coordinate == "x" and "utc" in parameter.lower():
            try:
                timestamp = mdates.num2date(
                    float(value),
                    tz=timezone.utc,
                )
            except (OverflowError, TypeError, ValueError):
                pass
            else:
                return (
                    f"{parameter}: "
                    f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC"
                )

        number = cls._format_pointer_value(value)
        normalized_unit = unit.lower().replace("°", "deg").strip()
        if normalized_unit in {"deg e", "degree e", "degrees e"}:
            suffix = "°E"
        elif normalized_unit in {"deg w", "degree w", "degrees w"}:
            suffix = "°W"
        elif normalized_unit in {"deg", "degree", "degrees"}:
            suffix = "°"
        else:
            suffix = unit
        return f"{parameter}: {number}" + (f" {suffix}" if suffix else "")

    def _pointer_annotation(self, axis):

        annotation = self._coordinate_annotations.get(axis)
        if annotation is not None and annotation in axis.texts:
            return annotation

        annotation = axis.annotate(
            "",
            xy=(0.0, 0.0),
            xytext=(12, 12),
            textcoords="offset points",
            color=theme.TEXT_PRIMARY,
            fontsize=8,
            linespacing=1.25,
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": theme.SURFACE_RAISED,
                "edgecolor": theme.ACCENT,
                "alpha": 0.94,
            },
            zorder=1000,
        )
        annotation.set_visible(False)
        self._coordinate_annotations[axis] = annotation
        return annotation

    def _show_pointer_coordinates(self, event):

        # Camera dragging has its own high-frequency render loop.  Updating the
        # crosshair annotation at the same time schedules a second full canvas
        # redraw and defeats blitting, so it is paused until drag release.
        if getattr(self, "_suspend_pointer_coordinates", False):
            return

        active_axis = event.inaxes
        changed = False

        for axis, annotation in tuple(
            self._coordinate_annotations.items()
        ):
            if axis is not active_axis and annotation.get_visible():
                annotation.set_visible(False)
                changed = True

        if (
            active_axis is not None
            and event.xdata is not None
            and event.ydata is not None
            and getattr(active_axis, "name", "") != "3d"
            and active_axis.axison
            and not getattr(
                active_axis,
                "_opa_disable_pointer_coordinates",
                False,
            )
        ):
            annotation = self._pointer_annotation(active_axis)
            annotation.xy = (
                float(event.xdata),
                float(event.ydata),
            )
            annotation.set_text(
                self._format_pointer_axis_value(
                    active_axis,
                    "x",
                    event.xdata,
                )
                + "\n"
                + self._format_pointer_axis_value(
                    active_axis,
                    "y",
                    event.ydata,
                )
            )
            annotation.set_visible(True)
            changed = True

        if changed:
            self.draw_idle()

    def _hide_pointer_coordinates(self, _event=None):

        changed = False
        for annotation in getattr(self, "_coordinate_annotations", {}).values():
            if annotation.get_visible():
                annotation.set_visible(False)
                changed = True
        if changed:
            self.draw_idle()

    def style_axes(self):

        self.style_axis(self.ax)

    @staticmethod
    def _semantic_text_colour(colour):
        try:
            value = matplotlib_to_hex(colour).upper()
        except (TypeError, ValueError):
            return colour
        roles = (
            "TEXT_PRIMARY",
            "TEXT_SECONDARY",
            "TEXT_MUTED",
            "TEXT_FAINT",
            "TEXT_NOTE",
            "PLOT_NEUTRAL",
        )
        for role in roles:
            if any(
                value == palette.get(role, "").upper()
                for palette in theme.PALETTES.values()
            ):
                return getattr(theme, role)
        legacy_neutrals = {
            "#F8FAFC": theme.TEXT_PRIMARY,
            "#F4F9FF": theme.TEXT_PRIMARY,
            "#E2E8F0": theme.TEXT_SECONDARY,
            "#CBD5E1": theme.TEXT_SECONDARY,
            "#94A3B8": theme.TEXT_MUTED,
            "#64748B": theme.TEXT_FAINT,
        }
        return legacy_neutrals.get(value, colour)

    @classmethod
    def _semantic_artist_colour(cls, colour):
        """Resolve plot-series and neutral colours for the active palette."""

        try:
            value = matplotlib_to_hex(colour).upper()
        except (TypeError, ValueError):
            return colour
        series_colour = theme.plot_colour(value)
        if str(series_colour).upper() != value:
            return series_colour
        return cls._semantic_text_colour(value)

    def apply_theme(self):
        """Restyle every current axis without altering any plotted data."""

        self.figure.patch.set_facecolor(theme.PLOT_FIGURE)
        for figure_text in self.figure.texts:
            figure_text.set_color(
                self._semantic_text_colour(figure_text.get_color())
            )
        for axis in self.figure.axes:
            self.style_axis(axis)
            for line in axis.lines:
                line.set_color(self._semantic_artist_colour(line.get_color()))
                marker_face = line.get_markerfacecolor()
                marker_edge = line.get_markeredgecolor()
                if str(marker_face).lower() not in {"auto", "none"}:
                    try:
                        mapped_face = self._semantic_artist_colour(marker_face)
                    except (TypeError, ValueError):
                        pass
                    else:
                        line.set_markerfacecolor(mapped_face)
                if str(marker_edge).lower() not in {"auto", "none"}:
                    try:
                        mapped_edge = self._semantic_artist_colour(marker_edge)
                    except (TypeError, ValueError):
                        pass
                    else:
                        line.set_markeredgecolor(mapped_edge)
            for text in axis.texts:
                text.set_color(self._semantic_artist_colour(text.get_color()))
                text_box = text.get_bbox_patch()
                if text_box is not None:
                    text_box.set_facecolor(theme.SURFACE_RAISED)
                    text_box.set_edgecolor(theme.BORDER_STRONG)
            legend = axis.get_legend()
            if legend is not None:
                frame = legend.get_frame()
                frame.set_facecolor(theme.SURFACE)
                frame.set_edgecolor(theme.BORDER_STRONG)
                frame.set_alpha(0.96)
                for text in legend.get_texts():
                    text.set_color(theme.TEXT_SECONDARY)
            for axis_dimension in (
                axis.xaxis,
                axis.yaxis,
                getattr(axis, "zaxis", None),
            ):
                if axis_dimension is None:
                    continue
                pane = getattr(axis_dimension, "pane", None)
                if pane is not None:
                    pane.set_facecolor(theme.PLOT_BACKGROUND)
                    pane.set_edgecolor(theme.BORDER)
        for annotation in self._coordinate_annotations.values():
            annotation.set_color(theme.TEXT_PRIMARY)
            patch = annotation.get_bbox_patch()
            if patch is not None:
                patch.set_facecolor(theme.SURFACE_RAISED)
                patch.set_edgecolor(theme.ACCENT)
        return self

    def draw(self, *args, **kwargs):
        self.apply_theme()
        return super().draw(*args, **kwargs)

    @staticmethod
    def style_axis(axis):

        axis.set_facecolor(
            theme.PLOT_BACKGROUND
        )

        for spine in axis.spines.values():
            spine.set_color(
                theme.BORDER_STRONG
            )
            spine.set_linewidth(
                1.0
            )

        axis.tick_params(
            colors=theme.TEXT_SECONDARY,
            labelsize=10,
        )

        axis.xaxis.label.set_color(
            theme.TEXT_SECONDARY
        )

        axis.yaxis.label.set_color(
            theme.TEXT_SECONDARY
        )

        axis.title.set_color(
            theme.TEXT_PRIMARY
        )

        axis.grid(
            True,
            color=theme.PLOT_GRID,
            alpha=0.55 if theme.is_normal() else 0.75,
            linestyle="-",
            linewidth=0.65,
        )


# ============================================================
# OSCULATING KEPLER ELEMENT COMPARISON
# ============================================================

class KeplerComparisonWidget(QWidget):
    """Initial/final Kepler elements with an explicit inertial-frame label."""

    ELEMENT_ROWS = (
        ("a", "Semi-major axis", "a_km", "km", False),
        ("e", "Eccentricity", "e", "", False),
        ("i", "Inclination", "i_deg", "deg", True),
        ("Ω", "RAAN", "raan_deg", "deg", True),
        ("ω", "Argument of periapsis", "argp_deg", "deg", True),
        ("ν", "True anomaly", "nu_deg", "deg", True),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)

        self._visual_scales = {
            key: 1 for _symbol, _name, key, _unit, _angular in self.ELEMENT_ROWS
        }
        self._initial_elements = None
        self._final_elements = None
        self._initial_state = None
        self._final_state = None
        self._initial_epoch = None
        self._final_epoch = None
        self._frame_label = "J2000"
        self._trajectory_states = None
        self._trajectory_elapsed_days = None
        self._trajectory_elements = None
        self._history_bounds = dict(DEFAULT_KEPLER_HISTORY_BOUNDS)

        display_controls = QHBoxLayout()
        display_controls.setSpacing(10)
        display_controls.addWidget(QLabel("View:"))
        self.kepler_view_combo = QComboBox()
        self.kepler_view_combo.addItem("30-DAY ELEMENT HISTORY", "history")
        self.kepler_view_combo.addItem("ORBIT GEOMETRY", "geometry")
        self.kepler_view_combo.setMinimumHeight(34)
        self.kepler_view_combo.setToolTip(
            "History plots a, e, i, Ω, ω and ν at every propagation output "
            "epoch. Geometry keeps the initial/final 3D construction."
        )
        display_controls.addWidget(self.kepler_view_combo)
        display_controls.addWidget(QLabel("GM basis:"))
        self.gm_basis_combo = QComboBox()
        self.gm_basis_combo.addItem(
            "WEB CHECK — 398600.0",
            398600.0,
        )
        self.gm_basis_combo.addItem(
            "EGM96 PHYSICAL — 398600.4418",
            MU_EARTH,
        )
        self.gm_basis_combo.setToolTip(
            "WEB CHECK reproduces the rounded Earth GM used by the cited "
            "online calculator. EGM96 PHYSICAL uses the propagation model's "
            "GM. This selection changes only the displayed Kepler elements."
        )
        self.gm_basis_combo.setMinimumHeight(34)
        self.gm_basis_combo.setCurrentIndex(1)
        display_controls.addWidget(self.gm_basis_combo)
        display_controls.addStretch(1)
        root_layout.addLayout(display_controls)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(QLabel("Visual emphasis:"))
        self.visual_element_combo = QComboBox()
        for symbol, name, key, _unit, _angular in self.ELEMENT_ROWS:
            self.visual_element_combo.addItem(f"{symbol} — {name}", key)
        self.visual_element_combo.setCurrentIndex(2)
        self.visual_element_combo.setMinimumHeight(34)
        controls.addWidget(self.visual_element_combo)

        self.visual_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.visual_scale_slider.setRange(1, 100)
        self.visual_scale_slider.setValue(1)
        self.visual_scale_slider.setTickInterval(10)
        self.visual_scale_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        # A 260px floor stopped the row compressing on a 1024px window and
        # the slider grew over the "100x" end label instead.
        self.visual_scale_slider.setMinimumWidth(150)
        controls.addWidget(QLabel("1×"))
        controls.addWidget(self.visual_scale_slider, 1)
        controls.addWidget(QLabel("100×"))

        self.visual_scale_spin = QSpinBox()
        self.visual_scale_spin.setRange(1, 100)
        self.visual_scale_spin.setValue(1)
        self.visual_scale_spin.setSuffix("×")
        self.visual_scale_spin.setMinimumHeight(34)
        controls.addWidget(self.visual_scale_spin)
        self.visual_scale_status = QLabel("i ×1")
        controls.addWidget(self.visual_scale_status)
        reset_button = QPushButton("RESET ALL 1×")
        reset_button.setMinimumHeight(34)
        controls.addWidget(reset_button)
        root_layout.addLayout(controls)

        explanation = QLabel(
            "Visual-only scale: a amplifies initial/final size separation; "
            "e and i amplify both geometries; Ω, ω and ν amplify final change "
            "from the initial orbit. Visual scaling never changes the table. "
            "GM basis changes only displayed elements; propagation remains EGM96."
        )
        explanation.setWordWrap(True)
        explanation.setObjectName("metricDetail")
        root_layout.addWidget(explanation)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        root_layout.addLayout(layout)

        self.graph = GraphWidget(figsize=(8.2, 5.0))
        self.graph.setMinimumHeight(500)
        self.graph.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self.graph, 3)

        table_column = QVBoxLayout()
        table_column.setSpacing(8)
        self.epoch_summary = QLabel(
            "Run a calculation to compare the initial and final epochs."
        )
        self.epoch_summary.setWordWrap(True)
        table_column.addWidget(self.epoch_summary)

        self.table = QTableWidget(6, 4)
        self.table.setHorizontalHeaderLabels(
            ("Element", "Initial", "Final", "Change")
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.NoSelection
        )
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumWidth(420)
        self.table.setMinimumHeight(260)
        self.table.setMaximumHeight(300)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        for row, (symbol, name, _key, unit, _angular) in enumerate(
            self.ELEMENT_ROWS
        ):
            label = f"{symbol}  {name}"
            if unit:
                label += f" [{unit}]"
            self.table.setItem(row, 0, QTableWidgetItem(label))
            for column in range(1, 4):
                self.table.setItem(row, column, QTableWidgetItem("—"))
        self.table.resizeRowsToContents()
        table_column.addWidget(self.table)

        self.frame_note = QLabel(
            "Earth-centred J2000 osculating elements · EGM96 GM = "
            "398600.4418 km³/s² · angular changes use the shortest signed arc"
        )
        self.frame_note.setWordWrap(True)
        self.frame_note.setObjectName("metricDetail")
        table_column.addWidget(self.frame_note)
        table_column.addStretch(1)
        layout.addLayout(table_column, 2)

        self.visual_element_combo.currentIndexChanged.connect(
            self._selected_visual_element_changed
        )
        self.kepler_view_combo.currentIndexChanged.connect(
            self._kepler_view_changed
        )
        self.gm_basis_combo.currentIndexChanged.connect(
            self._gm_basis_changed
        )
        self.visual_scale_slider.valueChanged.connect(
            self._visual_scale_slider_changed
        )
        self.visual_scale_spin.valueChanged.connect(
            self._visual_scale_spin_changed
        )
        reset_button.clicked.connect(self._reset_visual_scales)

        self.apply_theme()
        self.clear()

    def apply_theme(self):
        self.visual_scale_status.setStyleSheet(
            theme.monospace_readout_style()
            + " min-width: 74px;"
        )
        self.epoch_summary.setStyleSheet(
            theme.note_style() + " padding: 2px 4px;"
        )
        self.table.setStyleSheet(theme.table_style())
        self.graph.apply_theme()
        self.graph.draw_idle()

    def _selected_visual_element_changed(self, _index=None):
        key = self.visual_element_combo.currentData()
        factor = int(self._visual_scales[key])
        self.visual_scale_slider.blockSignals(True)
        self.visual_scale_spin.blockSignals(True)
        self.visual_scale_slider.setValue(factor)
        self.visual_scale_spin.setValue(factor)
        self.visual_scale_slider.blockSignals(False)
        self.visual_scale_spin.blockSignals(False)
        self._update_visual_scale_status()

    def _kepler_view_changed(self, _index=None):
        self._render_current_view()

    def _gm_basis_changed(self, _index=None):
        if self._initial_state is None or self._final_state is None:
            return
        self.update_states(
            self._initial_state,
            self._final_state,
            self._initial_epoch,
            self._final_epoch,
            frame_label=self._frame_label,
        )

    def _visual_scale_slider_changed(self, value):
        self.visual_scale_spin.blockSignals(True)
        self.visual_scale_spin.setValue(int(value))
        self.visual_scale_spin.blockSignals(False)
        self._store_visual_scale(value)

    def _visual_scale_spin_changed(self, value):
        self.visual_scale_slider.blockSignals(True)
        self.visual_scale_slider.setValue(int(value))
        self.visual_scale_slider.blockSignals(False)
        self._store_visual_scale(value)

    def _store_visual_scale(self, value):
        key = self.visual_element_combo.currentData()
        self._visual_scales[key] = int(value)
        self._update_visual_scale_status()
        self._render_current_view()

    def _update_visual_scale_status(self):
        key = self.visual_element_combo.currentData()
        symbol = next(
            row[0] for row in self.ELEMENT_ROWS if row[2] == key
        )
        self.visual_scale_status.setText(
            f"{symbol} ×{self._visual_scales[key]}"
        )

    def _reset_visual_scales(self, _checked=False):
        for key in self._visual_scales:
            self._visual_scales[key] = 1
        self._selected_visual_element_changed()
        self._render_current_view()

    @staticmethod
    def _format_value(value, unit, delta=False):
        if value is None or not np.isfinite(value):
            return "undefined"
        sign = "+" if delta and value >= 0.0 else ""
        if unit == "km":
            return f"{sign}{value:.9f}"
        if unit == "deg":
            return f"{sign}{value:.9f}°"
        return f"{sign}{value:.12f}"

    @staticmethod
    def _difference(initial, final, angular):
        if initial is None or final is None:
            return None
        difference = float(final) - float(initial)
        if angular:
            difference = (difference + 180.0) % 360.0 - 180.0
        return difference

    def clear(self):
        self._initial_elements = None
        self._final_elements = None
        self._initial_state = None
        self._final_state = None
        self._initial_epoch = None
        self._final_epoch = None
        self._trajectory_states = None
        self._trajectory_elapsed_days = None
        self._trajectory_elements = None
        for row in range(6):
            for column in range(1, 4):
                self.table.item(row, column).setText("—")
        self.epoch_summary.setText(
            "Run a calculation to compare the initial and final epochs."
        )
        figure = self.graph.figure
        figure.clear()
        axis = figure.add_subplot(111)
        self.graph.ax = axis
        GraphWidget.style_axis(axis)
        axis.set_axis_off()
        axis.text(
            0.5,
            0.5,
            "Osculating orbit geometry will appear after calculation",
            transform=axis.transAxes,
            ha="center",
            va="center",
            color="#64748B",
            fontsize=11,
        )
        self.graph.draw_idle()

    def set_history_bounds(self, bounds=None):
        """Set optional {element_key: (minimum, maximum)} plot limits.

        Either side may be ``None`` when only one limit should be drawn.
        """

        self._history_bounds = dict(bounds or {})
        self._render_current_view()

    @staticmethod
    def _rotation_matrix(elements):
        raan = np.radians(elements["raan_deg"] or 0.0)
        inclination = np.radians(elements["i_deg"])
        argp = np.radians(elements["argp_deg"] or 0.0)
        co, so = np.cos(raan), np.sin(raan)
        ci, si = np.cos(inclination), np.sin(inclination)
        cw, sw = np.cos(argp), np.sin(argp)
        return np.array(
            [
                [co * cw - so * sw * ci, -co * sw - so * cw * ci, so * si],
                [so * cw + co * sw * ci, -so * sw + co * cw * ci, -co * si],
                [sw * si, cw * si, ci],
            ],
            dtype=float,
        )

    @staticmethod
    def _signed_angle_delta(initial, final):
        return (float(final) - float(initial) + 180.0) % 360.0 - 180.0

    def _visual_elements(self):
        if self._initial_elements is None or self._final_elements is None:
            return None, None

        initial = dict(self._initial_elements)
        final = dict(self._final_elements)

        # a: exaggerate only the relative size difference around the common
        # mean; geometry remains bounded by the viewport's normalized scale.
        a_scale = self._visual_scales["a_km"]
        a_mean = 0.5 * (initial["a_km"] + final["a_km"])
        initial["a_km"] = a_mean + (initial["a_km"] - a_mean) * a_scale
        final["a_km"] = a_mean + (final["a_km"] - a_mean) * a_scale

        # e/i are absolute geometric features, so both before/after values are
        # magnified. Angles Ω/ω/ν retain the initial orientation and magnify
        # only the physical final-minus-initial change.
        e_scale = self._visual_scales["e"]
        i_scale = self._visual_scales["i_deg"]
        initial["e"] = min(max(initial["e"] * e_scale, 0.0), 0.92)
        final["e"] = min(max(final["e"] * e_scale, 0.0), 0.92)
        initial["i_deg"] = min(initial["i_deg"] * i_scale, 89.0)
        final["i_deg"] = min(final["i_deg"] * i_scale, 89.0)

        for key in ("raan_deg", "argp_deg", "nu_deg"):
            if initial[key] is None or final[key] is None:
                continue
            delta = self._signed_angle_delta(initial[key], final[key])
            final[key] = (
                initial[key] + delta * self._visual_scales[key]
            ) % 360.0
        return initial, final

    def _draw_geometry(
        self,
        axis,
        elements,
        title,
        accent,
        orbit_normalization,
    ):
        axis.set_facecolor("#08111F")
        axis.computed_zorder = False
        axis.set_axis_off()
        axis.set_box_aspect((1.0, 1.0, 0.82))
        axis.view_init(elev=24.0, azim=-52.0)
        axis.set_xlim(-1.55, 1.55)
        axis.set_ylim(-1.55, 1.55)
        axis.set_zlim(-1.25, 1.25)

        # Earth sphere.
        u = np.linspace(0.0, 2.0 * np.pi, 40)
        v = np.linspace(0.0, np.pi, 22)
        earth_radius = 0.27
        earth_x = earth_radius * np.outer(np.cos(u), np.sin(v))
        earth_y = earth_radius * np.outer(np.sin(u), np.sin(v))
        earth_z = earth_radius * np.outer(np.ones_like(u), np.cos(v))
        axis.plot_surface(
            earth_x,
            earth_y,
            earth_z,
            color="#2563EB",
            alpha=0.82,
            linewidth=0.0,
            shade=True,
        )
        earth_artists = list(axis.collections)

        # Equatorial plane and equator.
        plane = np.linspace(-1.15, 1.15, 2)
        px, py = np.meshgrid(plane, plane)
        axis.plot_surface(
            px,
            py,
            np.zeros_like(px),
            color="#0891B2",
            alpha=0.10,
            linewidth=0.0,
        )
        theta = np.linspace(0.0, 2.0 * np.pi, 241)
        axis.plot(
            1.13 * np.cos(theta),
            1.13 * np.sin(theta),
            np.zeros_like(theta),
            color="#22D3EE",
            linewidth=1.0,
            alpha=0.75,
            label="Equatorial plane",
        )

        rotation = self._rotation_matrix(elements)
        eccentricity = min(max(float(elements["e"]), 0.0), 0.98)
        p = max(1.0 - eccentricity * eccentricity, 1.0e-6)
        orbit_size = max(float(elements["a_km"]), 1.0) / orbit_normalization
        radius = (
            1.36
            * orbit_size
            * p
            / (1.0 + eccentricity * np.cos(theta))
        )
        orbit_pf = np.vstack(
            (radius * np.cos(theta), radius * np.sin(theta), np.zeros_like(theta))
        )
        orbit = rotation @ orbit_pf
        axis.plot(
            orbit[0],
            orbit[1],
            orbit[2],
            color=accent,
            linewidth=2.0,
            label="Osculating orbit",
        )

        # Orbital plane disk, node line and line of apsides.
        disk_pf = np.vstack(
            (1.05 * np.cos(theta), 1.05 * np.sin(theta), np.zeros_like(theta))
        )
        disk = rotation @ disk_pf
        axis.add_collection3d(
            Poly3DCollection(
                [disk.T],
                facecolor=accent,
                edgecolor="none",
                alpha=0.045,
            )
        )
        raan = np.radians(elements["raan_deg"] or 0.0)
        node_direction = np.array([np.cos(raan), np.sin(raan), 0.0])
        axis.plot(
            [-1.42 * node_direction[0], 1.42 * node_direction[0]],
            [-1.42 * node_direction[1], 1.42 * node_direction[1]],
            [0.0, 0.0],
            color="#FACC15",
            linestyle="--",
            linewidth=1.25,
            label="Line of nodes",
        )
        peri_direction = rotation[:, 0]
        axis.plot(
            [-1.42 * peri_direction[0], 1.42 * peri_direction[0]],
            [-1.42 * peri_direction[1], 1.42 * peri_direction[1]],
            [-1.42 * peri_direction[2], 1.42 * peri_direction[2]],
            color="#FB7185",
            linestyle=":",
            linewidth=1.4,
            label="Line of apsides",
        )

        # Direct geometric arcs for Ω, i and ω, matching their definitions.
        if elements["raan_deg"] is not None:
            raan_arc = np.linspace(0.0, raan, 80)
            axis.plot(
                0.72 * np.cos(raan_arc),
                0.72 * np.sin(raan_arc),
                np.zeros_like(raan_arc),
                color="#FACC15",
                linewidth=1.8,
            )
            raan_mid = 0.5 * raan
            axis.text(
                0.79 * np.cos(raan_mid),
                0.79 * np.sin(raan_mid),
                0.02,
                "Ω",
                color="#FACC15",
                fontsize=10,
            )

        inclination = np.radians(elements["i_deg"])
        inclination_arc = np.linspace(0.0, inclination, 64)
        axis.plot(
            -0.62 * np.sin(raan) * np.cos(inclination_arc),
            0.62 * np.cos(raan) * np.cos(inclination_arc),
            0.62 * np.sin(inclination_arc),
            color="#4ADE80",
            linewidth=1.8,
        )
        inclination_mid = 0.5 * inclination
        axis.text(
            -0.70 * np.sin(raan) * np.cos(inclination_mid),
            0.70 * np.cos(raan) * np.cos(inclination_mid),
            0.70 * np.sin(inclination_mid),
            "i",
            color="#4ADE80",
            fontsize=10,
        )

        if elements["argp_deg"] is not None and not elements["equatorial"]:
            argp = np.radians(elements["argp_deg"])
            argp_arc = np.linspace(0.0, argp, 80)
            node_hat = np.array([np.cos(raan), np.sin(raan), 0.0])
            orbital_transverse = np.array(
                [
                    -np.sin(raan) * np.cos(inclination),
                    np.cos(raan) * np.cos(inclination),
                    np.sin(inclination),
                ]
            )
            omega_points = 0.86 * (
                node_hat[:, None] * np.cos(argp_arc)[None, :]
                + orbital_transverse[:, None] * np.sin(argp_arc)[None, :]
            )
            axis.plot(
                omega_points[0], omega_points[1], omega_points[2],
                color="#FB7185", linewidth=1.8,
            )
            omega_mid = 0.5 * argp
            omega_label = 0.94 * (
                node_hat * np.cos(omega_mid)
                + orbital_transverse * np.sin(omega_mid)
            )
            axis.text(
                omega_label[0], omega_label[1], omega_label[2],
                "ω", color="#FB7185", fontsize=10,
            )

        anomaly = np.radians(elements["nu_deg"] or 0.0)
        anomaly_radius = (
            1.36
            * orbit_size
            * p
            / (1.0 + eccentricity * np.cos(anomaly))
        )
        point = rotation @ np.array(
            [anomaly_radius * np.cos(anomaly), anomaly_radius * np.sin(anomaly), 0.0]
        )
        axis.plot(
            [0.0, point[0]],
            [0.0, point[1]],
            [0.0, point[2]],
            color="#F8FAFC",
            linewidth=0.9,
            alpha=0.75,
        )
        axis.scatter(
            [point[0]], [point[1]], [point[2]],
            s=42, color="#F8FAFC", edgecolor=accent, depthshade=False,
        )
        axis.text(
            point[0], point[1], point[2] + 0.10, "SAT / ν",
            color="#F8FAFC", fontsize=8
        )
        axis.set_title(
            title
            + f"\ni={elements['i_deg']:.6f}°  ·  "
            + (
                f"Ω={elements['raan_deg']:.6f}°"
                if elements["raan_deg"] is not None
                else "Ω=undefined"
            ),
            color="#F8FAFC",
            fontsize=10,
            pad=4,
        )

        # mplot3d normally sorts the globe in front of the orbit. This diagram
        # intentionally keeps all orbital construction lines readable as an
        # engineering overlay, including the segment geometrically behind Earth.
        overlay_artists = [
            artist
            for artist in (*axis.lines, *axis.collections, *axis.texts)
            if artist not in earth_artists
        ]
        for artist in earth_artists:
            if hasattr(artist, "set_sort_zpos"):
                artist.set_sort_zpos(-1000.0)
            artist.set_zorder(1)
        for artist in overlay_artists:
            if hasattr(artist, "set_sort_zpos"):
                artist.set_sort_zpos(1000.0)
            artist.set_zorder(100)

    def _render_geometry(self):
        visual_initial, visual_final = self._visual_elements()
        if visual_initial is None or visual_final is None:
            return
        figure = self.graph.figure
        figure.clear()
        initial_axis = figure.add_subplot(121, projection="3d")
        final_axis = figure.add_subplot(122, projection="3d")
        self.graph.ax = initial_axis
        orbit_normalization = max(
            max(float(visual_initial["a_km"]), 1.0)
            * (1.0 + float(visual_initial["e"])),
            max(float(visual_final["a_km"]), 1.0)
            * (1.0 + float(visual_final["e"])),
        )
        self._draw_geometry(
            initial_axis,
            visual_initial,
            "INITIAL OSCULATING ORBIT",
            "#38BDF8",
            orbit_normalization,
        )
        self._draw_geometry(
            final_axis,
            visual_final,
            "FINAL OSCULATING ORBIT",
            "#F59E0B",
            orbit_normalization,
        )
        active_scales = [
            f"{symbol}×{self._visual_scales[key]}"
            for symbol, _name, key, _unit, _angular in self.ELEMENT_ROWS
            if self._visual_scales[key] != 1
        ]
        scale_caption = (
            "  ·  visual emphasis: " + ", ".join(active_scales)
            if active_scales
            else "  ·  true geometry (all 1×)"
        )
        figure.suptitle(
            f"{self._frame_label} classical Keplerian geometry" + scale_caption,
            color="#F8FAFC",
            fontsize=12,
        )
        figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.95), pad=0.5)
        self.graph.draw_idle()

    def _calculate_trajectory_elements(self):
        if self._trajectory_states is None:
            self._trajectory_elements = None
            return
        selected_mu = float(self.gm_basis_combo.currentData())
        rows = [
            cartesian_to_keplerian(state, mu=selected_mu)
            for state in self._trajectory_states
        ]
        history = {}
        for _symbol, _name, key, _unit, _angular in self.ELEMENT_ROWS:
            values = np.asarray(
                [
                    np.nan if row[key] is None else float(row[key])
                    for row in rows
                ],
                dtype=float,
            )
            finite = np.isfinite(values)
            if (
                key in {"raan_deg", "argp_deg"}
                and np.count_nonzero(finite) >= 2
            ):
                values[finite] = np.degrees(
                    np.unwrap(np.radians(values[finite]))
                )
            history[key] = values
        self._trajectory_elements = history

    def _render_history(self):
        figure = self.graph.figure
        figure.clear()
        axes = tuple(figure.subplots(2, 3, sharex=True).ravel())
        self.graph.ax = axes[0]
        if (
            self._trajectory_elements is None
            or self._trajectory_elapsed_days is None
        ):
            for axis in axes:
                GraphWidget.style_axis(axis)
                axis.set_axis_off()
            axes[1].text(
                0.5,
                0.5,
                "Run a propagation to build the Kepler element history",
                transform=axes[1].transAxes,
                ha="center",
                va="center",
                color="#64748B",
                fontsize=11,
            )
            self.graph.draw_idle()
            return

        for index, (symbol, name, key, unit, angular) in enumerate(
            self.ELEMENT_ROWS
        ):
            axis = axes[index]
            GraphWidget.style_axis(axis)
            values = self._trajectory_elements[key]
            axis.plot(
                self._trajectory_elapsed_days,
                values,
                color="#38BDF8",
                linewidth=1.2,
            )
            if key in {"raan_deg", "argp_deg"}:
                title_suffix = " · continuous"
            elif key == "nu_deg":
                title_suffix = " · 0–360°"
            else:
                title_suffix = ""
            axis.set_title(
                f"{symbol} — {name}{title_suffix}",
                pad=8,
                fontsize=9.5,
            )
            axis.set_ylabel(unit or "dimensionless")
            if index >= 3:
                axis.set_xlabel("Elapsed time [days]")
            axis.margins(x=0.01)
            bounds = self._history_bounds.get(key)
            if bounds is not None:
                lower, upper = bounds
                for value, label in ((lower, "MIN"), (upper, "MAX")):
                    if value is None:
                        continue
                    axis.axhline(
                        float(value),
                        color="#EF4444",
                        linestyle="--",
                        linewidth=1.15,
                        label=label,
                    )
                axis.legend(
                    facecolor="#0F172A",
                    edgecolor="#334155",
                    labelcolor="#FCA5A5",
                    loc="best",
                    fontsize=8,
                )
        figure.suptitle(
            f"{self._frame_label} osculating Kepler elements vs time",
            color="#F8FAFC",
            fontsize=12,
        )
        figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.95), pad=1.0)
        self.graph.draw_idle()

    def _render_current_view(self):
        if self.kepler_view_combo.currentData() == "history":
            self._render_history()
        else:
            self._render_geometry()

    def update_trajectory(
        self,
        j2000_states,
        elapsed_seconds,
        initial_epoch,
        frame_label="TOD/FK5 (matches CSV export)",
        rotate_to_tod_fk5=True,
    ):
        """Populate initial/final elements and the full time history."""

        states = np.asarray(j2000_states, dtype=float)
        elapsed = np.asarray(elapsed_seconds, dtype=float)
        if states.ndim != 2 or states.shape[1] != 6:
            raise ValueError("trajectory states must have shape (N, 6).")
        if elapsed.shape != (states.shape[0],):
            raise ValueError("elapsed_seconds must contain one value per state.")
        epochs = tuple(
            initial_epoch + timedelta(seconds=float(seconds))
            for seconds in elapsed
        )
        self._trajectory_states = (
            rotate_j2000_states_to_tod_fk5(epochs, states)
            if rotate_to_tod_fk5
            else states.copy()
        )
        self._trajectory_elapsed_days = elapsed / 86400.0
        final_epoch = epochs[-1]
        self.update_states(
            self._trajectory_states[0],
            self._trajectory_states[-1],
            initial_epoch,
            final_epoch,
            frame_label=frame_label,
        )

    def update_states(
        self,
        initial_state,
        final_state,
        initial_epoch,
        final_epoch,
        frame_label="J2000",
    ):
        self._initial_state = np.asarray(initial_state, dtype=float).copy()
        self._final_state = np.asarray(final_state, dtype=float).copy()
        selected_mu = float(self.gm_basis_combo.currentData())
        initial = cartesian_to_keplerian(self._initial_state, mu=selected_mu)
        final = cartesian_to_keplerian(self._final_state, mu=selected_mu)
        self._initial_elements = initial
        self._final_elements = final
        self._initial_epoch = initial_epoch
        self._final_epoch = final_epoch
        self._frame_label = str(frame_label)
        self._calculate_trajectory_elements()
        duration_days = (
            final_epoch - initial_epoch
        ).total_seconds() / 86400.0
        near_circular = max(initial["e"], final["e"]) < 1.0e-3
        sensitivity_note = (
            "\nNear-circular orbit: ω and ν are individually sensitive; "
            "their sum (argument of latitude) is stable."
            if near_circular
            else ""
        )
        self.epoch_summary.setText(
            f"Initial: {initial_epoch.isoformat()}\n"
            f"Final (+{duration_days:.9f} d): {final_epoch.isoformat()}\n"
            f"Element frame: {self._frame_label}"
            f"{sensitivity_note}"
        )
        self.frame_note.setText(
            f"Earth-centred {self._frame_label} osculating elements · "
            f"display GM = {selected_mu:.4f} km³/s² · angular changes use the "
            "shortest signed arc. "
            + (
                "WEB CHECK reproduces the cited calculator exactly; the "
                "propagator itself remains on EGM96 GM = 398600.4418."
                if selected_mu == 398600.0
                else "EGM96 PHYSICAL matches the force model; calculators "
                "using GM = 398600.0 differ slightly in a/e and, for a "
                "near-circular orbit, in ω/ν."
            )
        )
        self.table.setHorizontalHeaderLabels(
            ("Element", "Initial", f"Final (+{duration_days:.3f} d)", "Change")
        )
        for row, (_symbol, _name, key, unit, angular) in enumerate(
            self.ELEMENT_ROWS
        ):
            initial_value = initial[key]
            final_value = final[key]
            difference = self._difference(initial_value, final_value, angular)
            self.table.item(row, 1).setText(
                self._format_value(initial_value, unit)
            )
            self.table.item(row, 2).setText(
                self._format_value(final_value, unit)
            )
            self.table.item(row, 3).setText(
                self._format_value(difference, unit, delta=True)
            )
            for column, elements in ((1, initial), (2, final)):
                if key == "argp_deg":
                    definition = elements["periapsis_kind"]
                elif key == "nu_deg":
                    definition = elements["anomaly_kind"]
                else:
                    definition = "classical_osculating_element"
                self.table.item(row, column).setToolTip(
                    definition.replace("_", " ")
                )
        self.table.resizeRowsToContents()

        self._render_current_view()


# ============================================================
# MAIN WINDOW
# ============================================================


class UtcEpochPickerDialog(QDialog):
    """Mouse-friendly UTC calendar and time selector."""

    def __init__(self, initial_epoch, parent=None):
        super().__init__(parent)
        initial_epoch = initial_epoch.astimezone(timezone.utc)
        self.setWindowTitle("Select Epoch UTC")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Date (UTC)"))
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setSelectedDate(
            QDate(initial_epoch.year, initial_epoch.month, initial_epoch.day)
        )
        layout.addWidget(self.calendar)

        layout.addWidget(QLabel("Time (UTC)"))
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm:ss")
        self.time_edit.setTime(
            QTime(initial_epoch.hour, initial_epoch.minute, initial_epoch.second)
        )
        self.time_edit.setMinimumHeight(38)
        layout.addWidget(self.time_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_epoch(self):
        selected_date = self.calendar.selectedDate()
        selected_time = self.time_edit.time()
        return datetime(
            selected_date.year(),
            selected_date.month(),
            selected_date.day(),
            selected_time.hour(),
            selected_time.minute(),
            selected_time.second(),
            tzinfo=timezone.utc,
        )

class OperatorDoubleSpinBox(QDoubleSpinBox):
    """Stable engineering input accepting either decimal separator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLocale(QLocale.c())

    @staticmethod
    def _normalise_decimal_text(text):
        return str(text).replace(",", ".")

    def validate(self, text, position):
        return super().validate(
            self._normalise_decimal_text(text),
            position,
        )

    def valueFromText(self, text):
        return super().valueFromText(self._normalise_decimal_text(text))

    def fixup(self, text):
        return super().fixup(self._normalise_decimal_text(text))


class MainWindow(ProductFeatureMixin, QMainWindow):

    def __init__(self, *, application_config_path=None):

        super().__init__()

        self.application_config_path = str(
            application_config_path or APPLICATION_CONFIG_PATH
        )
        self.application_config = load_application_config(
            self.application_config_path
        )
        self.interface_theme = self.application_config["theme"]
        self.language = self.application_config["language"]
        self.admin_session = AdminSessionManager()
        self._admin_module_pages = []
        theme.set_theme(self.interface_theme)
        application = QApplication.instance()
        if application is not None:
            application.setStyleSheet(
                theme.application_stylesheet(DROPDOWN_ARROW_PATH)
                if theme.is_retro()
                else ""
            )
        self.initialize_product_features()
        self.setStatusBar(LocalizedStatusBar(lambda: self.language, self))

        # ----------------------------------------------------
        # WINDOW
        # ----------------------------------------------------

        self.setWindowTitle(
            "Orbital Perturbation Analyzer"
        )

        if os.path.isfile(APP_ICON_PATH):
            self.setWindowIcon(
                QIcon(APP_ICON_PATH)
            )

        saved_geometry = self.application_config.get("window_geometry")
        if saved_geometry:
            self.setGeometry(*saved_geometry)
        else:
            self.resize(1280, 820)

        # 640×360 logical pixels remains usable at 200% scaling on a
        # 1366×768 display; page-level scroll areas keep actions reachable.
        self.setMinimumSize(640, 360)

        # ----------------------------------------------------
        # HISTORY
        # ----------------------------------------------------

        self.history_time = deque()
        self.force_histories = {
            source: {
                parameter: deque()
                for parameter in PERTURBATION_PARAMETERS
            }
            for source in ("Moon", "Sun β", "SRP", "Combined")
        }

        # Compatibility aliases for the established inertial histories.
        combined_history = self.force_histories["Combined"]
        moon_history = self.force_histories["Moon"]
        sun_history = self.force_histories["Sun β"]
        self.history_ax = combined_history["ax"]
        self.history_ay = combined_history["ay"]
        self.history_az = combined_history["az"]
        self.history_magnitude = combined_history["Magnitude"]
        self.history_moon_ax = moon_history["ax"]
        self.history_moon_ay = moon_history["ay"]
        self.history_moon_az = moon_history["az"]
        self.history_moon_magnitude = moon_history["Magnitude"]
        self.history_sun_ax = sun_history["ax"]
        self.history_sun_ay = sun_history["ay"]
        self.history_sun_az = sun_history["az"]
        self.history_sun_magnitude = sun_history["Magnitude"]

        # Propagation overlay and horizontal chart navigation.
        self.graph_prediction_epoch = None
        self.graph_prediction_times = None
        self.graph_prediction_values = None
        self.graph_prediction_uncertainty = None
        self.graph_view_offset = 0.0

        # Latest 3D states shared by the live monitor and the 2D system
        # view. Trails are bounded so memory and rendering stay stable.
        self.current_satellite_position = None
        self.current_satellite_altitude_km = None
        self.current_moon_position = None
        self.current_sun_position = None
        self.satellite_position_history = deque(
            maxlen=1800
        )
        self.moon_position_history = deque(
            maxlen=1800
        )
        self.current_system_epoch = None
        self.system_reference_orbits = {}
        self.system_live_positions = {}
        self.system_live_altitudes = {}
        self.system_object_errors = {}
        self._system_live_cache_key = None
        self._system_live_position_errors = {}
        self._earth_texture_cache_key = None
        self._earth_texture_cache = None
        self._earth_texture_geometry_cache = {}
        self._last_system_drag_draw_time = 0.0
        self._system_drag_background = None
        self._system_drag_animated_artists = ()
        self._system_drag_frame_pending = False
        self._system_drag_last_frame_time = 0.0
        self._system_drag_frame_times = deque(maxlen=45)
        self._system_last_view_limit = None
        self._system_last_horizontal_limit = None
        self._system_last_vertical_limit = None
        self.system_view_yaw = 35.0
        self.system_view_pitch = 25.0
        self.system_view_zoom = 1.0
        self._orbital_theater_mode = False
        self._graph_only_mode = False
        self._graph_fullscreen_restore = None
        self._window_restore_maximized = False

        self.analysis_fixed_epoch = None
        self.live_log_file = None
        self.live_log_writer = None
        self.live_log_path = None
        self.propagation_thread = None
        self.propagation_worker = None
        self.graph_prediction_thread = None
        self.graph_prediction_worker = None
        self._graph_prediction_timer_was_active = False
        self.eclipse_thread = None
        self.eclipse_worker = None
        self.sun_outage_thread = None
        self.sun_outage_worker = None
        self.sun_outage_prediction = None
        self.eclipse_prediction_result = None
        self.eclipse_initial_epoch = None
        self.yearly_eclipse_schedule = None
        self.eclipse_reference_comparison = None
        self.eclipse_reference_interval_prediction = None
        self._pending_eclipse_reference_spec = None
        self._pending_eclipse_reference_state_source = None
        self._pending_eclipse_reference_state_warning = None
        self._last_eclipse_output_kind = None
        self._eclipse_run_mode = None
        self._eclipse_progress_started_at = None
        self._eclipse_progress_percent = 0
        self._eclipse_eta_deadline = None
        self.reference_comparison_thread = None
        self.reference_comparison_worker = None
        self.orbit_determination_thread = None
        self.orbit_determination_worker = None
        self.latest_orbit_determination = None
        self.latest_reference_comparison = None
        # CSV ixracı həmişə son hesablanan konkret ssenarini saxlayır.
        # Müqayisə üçün iki nəticə yaddaşda olsa belə avtomatik cüt fayl
        # yaradılmır.
        self.latest_reference_scenario = None
        self.reference_scenario_results = {
            True: None,
            False: None,
        }
        self.reference_validation_settings = None
        self._reference_selection_sun_mode = None
        self._reference_selected_dataset_id = None
        self.reference_active_scenario = None
        self.tle_update_thread = None
        self.tle_update_worker = None

        # ----------------------------------------------------
        # BUILD GUI
        # ----------------------------------------------------

        load_kernels()

        load_application_fonts()


        self.create_ui()
        self.apply_minimum_window_size()
        self.install_wheel_value_guards()

        # Mouse events can arrive much faster than the GUI can paint.  A
        # precise single-shot timer coalesces them into at most one frame per
        # refresh interval and keeps input responsive under load.
        self._system_drag_frame_timer = QTimer(self)
        self._system_drag_frame_timer.setSingleShot(True)
        self._system_drag_frame_timer.setTimerType(
            Qt.TimerType.PreciseTimer
        )
        self._system_drag_frame_timer.timeout.connect(
            self._render_pending_system_drag_frame
        )

        self.fullscreen_shortcut = QShortcut(
            QKeySequence("F11"),
            self,
        )
        self.fullscreen_shortcut.activated.connect(
            self.toggle_full_screen
        )

        self.apply_interface_theme(self.interface_theme)

        # ----------------------------------------------------
        # TIMER
        # ----------------------------------------------------

        self.timer = QTimer(
            self
        )

        self.timer.timeout.connect(
            self.update_data
        )

        # 1 second
        self.timer.start(
            1000
        )

        # First update immediately
        self.update_data()



    # ========================================================
    # INTERFACE THEMES
    # ========================================================

    def install_wheel_value_guards(self):
        """Keep page scrolling from changing values under the pointer."""

        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)
        for control in self.findChildren(QAbstractSpinBox):
            control.installEventFilter(self)
        for control in self.findChildren(QComboBox):
            control.installEventFilter(self)

    @staticmethod
    def _containing_scroll_area(widget):

        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                return parent
            parent = parent.parentWidget()
        return None

    def eventFilter(self, watched, event):

        if (
            watched is getattr(self, "graph", None)
            and event.type() == QEvent.Type.Resize
        ):
            QTimer.singleShot(0, self.position_graph_fullscreen_button)

        if event.type() == QEvent.Type.MouseButtonPress:
            clicked_canvas = None
            target = watched if isinstance(watched, QWidget) else None
            while target is not None:
                if isinstance(target, ClickActivatedFigureCanvas):
                    clicked_canvas = target
                    break
                target = target.parentWidget()
            for canvas in self.findChildren(ClickActivatedFigureCanvas):
                if canvas is not clicked_canvas:
                    canvas.deactivate_wheel_interaction()
        if (
            event.type() == QEvent.Type.Wheel
            and isinstance(watched, (QAbstractSpinBox, QComboBox))
        ):
            scroll_area = self._containing_scroll_area(watched)
            if scroll_area is not None:
                scroll_bar = scroll_area.verticalScrollBar()
                pixel_delta = event.pixelDelta().y()
                if pixel_delta:
                    scroll_delta = int(pixel_delta)
                else:
                    wheel_steps = event.angleDelta().y() / 120.0
                    scroll_delta = int(
                        wheel_steps
                        * max(scroll_bar.singleStep(), 20)
                        * 3
                    )
                scroll_bar.setValue(
                    scroll_bar.value() - scroll_delta
                )
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def apply_application_theme(self):
        self.setStyleSheet(
            theme.application_stylesheet(DROPDOWN_ARROW_PATH)
        )

    # ========================================================
    # CREATE UI
    # ========================================================

    def create_ui(self):
        central = MissionControlSurface()
        central.setObjectName("commandSurface")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        self.main_layout = main_layout
        main_layout.setContentsMargins(16, 12, 16, 14)
        main_layout.setSpacing(11)

        # ----------------------------------------------------
        # HERO HEADER
        # ----------------------------------------------------

        hero = HeroBannerFrame(
            HERO_BACKGROUND_DARK_PATH,
            interface_theme=self.interface_theme,
        )
        self.hero_card = hero
        hero.setMinimumHeight(116)
        hero.setMaximumHeight(132)
        hero.setObjectName(
            "heroCard"
        )
        hero.set_theme(self.interface_theme, "")

        hero_layout = QHBoxLayout(hero)
        self.hero_layout = hero_layout
        hero_layout.setContentsMargins(20, 12, 20, 12)
        hero_layout.setSpacing(18)

        logo = QLabel()
        logo.setObjectName(
            "heroLogo"
        )
        logo.setStyleSheet(
            "background: transparent; border: none;"
        )
        self.hero_logo = logo
        logo_size = 72
        logo.setFixedSize(logo_size, logo_size)
        logo.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.hero_logo_pixmap = QPixmap(APP_LOGO_PATH)
        if not self.hero_logo_pixmap.isNull():
            logo.setPixmap(
                self.hero_logo_pixmap.scaled(
                    logo_size - 6,
                    logo_size - 6,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        heading_layout = QVBoxLayout()
        heading_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        heading_layout.setSpacing(
            6
        )

        mission_eyebrow = QLabel(
            "ORBITAL DYNAMICS"
        )
        mission_eyebrow.setObjectName("missionEyebrow")
        self.mission_eyebrow = mission_eyebrow

        title = QLabel("ORBITAL PERTURBATION ANALYZER")
        self.main_title = title
        title.setObjectName(
            "mainTitle"
        )

        title.setAlignment(Qt.AlignmentFlag.AlignLeft)

        subtitle = QLabel(
            "MULTI-BODY DYNAMICS CONSOLE  //  SYNTHETIC GEO DEMO  //  OPA"
        )
        subtitle.setObjectName(
            "mainSubtitle"
        )
        self.main_subtitle = subtitle

        subtitle.setAlignment(Qt.AlignmentFlag.AlignLeft)
        subtitle.setWordWrap(
            True
        )

        heading_layout.addWidget(mission_eyebrow)
        heading_layout.addWidget(title)
        heading_layout.addWidget(
            subtitle
        )

        hero_layout.addWidget(
            logo
        )
        hero_layout.addLayout(
            heading_layout,
            1,
        )
        divider = QFrame()
        divider.setObjectName("missionDivider")
        divider.setFixedHeight(62)
        hero_layout.addWidget(divider)

        mission_status_layout = QVBoxLayout()
        self.mission_status_layout = mission_status_layout
        mission_status_layout.setContentsMargins(5, 4, 0, 4)
        mission_status_layout.setSpacing(8)
        mission_status_layout.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.hero_status = QLabel("LIVE UPDATE  ·  1 s")
        self.hero_status.setObjectName("heroStatus")
        self.hero_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero_model = QLabel(
            "EGM96 4×4  ·  DE440  ·  J2000  ·  MOON / SUN / SRP"
        )
        self.hero_model.setObjectName("heroModel")
        self.hero_model.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.hero_utc = QLabel("UTC  —")
        self.hero_utc.setObjectName("heroUtc")
        self.hero_utc.setAlignment(Qt.AlignmentFlag.AlignRight)
        mission_version = QLabel(f"v{APP_VERSION}")
        self.mission_version_label = mission_version
        mission_version.setObjectName("heroVersion")
        mission_version.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.refresh_app_button = QPushButton("REFRESH APPLICATION")
        self.refresh_app_button.setObjectName("ghostAction")
        self.refresh_app_button.setMinimumHeight(28)
        self.refresh_app_button.setToolTip(
            "Restart the application cleanly without closing it manually."
        )
        self.refresh_app_button.clicked.connect(self.refresh_application)
        self.settings_button = QPushButton("SETTINGS")
        self.settings_button.setObjectName("ghostAction")
        self.settings_button.setMinimumHeight(28)
        self.settings_button.setToolTip(
            "Open appearance, configuration and credits."
        )
        self.settings_button.clicked.connect(self.open_settings_overlay)
        # One action row, then one meta row.  Keeping every control on a
        # single line stops the header from growing a fourth stacked row and
        # leaves the artwork a clear area to breathe on the left.
        top_status_layout = QHBoxLayout()
        top_status_layout.setContentsMargins(0, 0, 0, 0)
        top_status_layout.setSpacing(8)
        top_status_layout.addStretch(1)
        top_status_layout.addWidget(self.hero_status)
        top_status_layout.addWidget(self.settings_button)
        top_status_layout.addWidget(self.refresh_app_button)
        mission_status_layout.addLayout(top_status_layout)
        mission_status_layout.addWidget(self.hero_model)
        details_layout = QHBoxLayout()
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(10)
        details_layout.addStretch(1)
        details_layout.addWidget(self.hero_utc)
        details_layout.addWidget(mission_version)
        mission_status_layout.addLayout(details_layout)
        hero_layout.addLayout(mission_status_layout)

        main_layout.addWidget(
            hero
        )

        self.create_product_command_bar(main_layout)

        # ----------------------------------------------------
        # TABS
        # ----------------------------------------------------

        self.module_tabs = QTabWidget()
        self.module_tabs.setObjectName("moduleTabs")

        self.propagation_module_page = QWidget()
        propagation_module_layout = QVBoxLayout(
            self.propagation_module_page
        )
        propagation_module_layout.setContentsMargins(0, 0, 0, 0)
        propagation_module_layout.setSpacing(0)

        # Keep this long-standing tab widget as the Propagation workspace.
        # A number of safe lazy-update routes intentionally depend on its
        # stable page indexes.
        self.tabs = QTabWidget()
        self.tabs.setObjectName("propagationWorkspaceTabs")
        propagation_module_layout.addWidget(self.tabs)

        self.propagation_module_index = self.module_tabs.addTab(
            self.propagation_module_page,
            "PROPAGATION",
        )
        self.module_tabs.tabBar().setTabData(
            self.propagation_module_index,
            "PROPAGATION",
        )
        main_layout.addWidget(self.module_tabs)

        # ----------------------------------------------------
        # PAGES
        # ----------------------------------------------------

        self.create_monitor_page()

        self.create_graph_page()

        self.create_system_view_page()

        self.create_integrity_page()

        self.create_reference_validation_page()

        self.create_propagation_page()

        self.create_geo_operations_page()

        self.create_eclipse_page()
        self.eclipse_module_index = self.module_tabs.addTab(
            self.eclipse_page,
            "ECLIPSE",
        )
        self.module_tabs.tabBar().setTabData(
            self.eclipse_module_index,
            "ECLIPSE",
        )

        self.orbit_determination_module_index = -1
        if ORBIT_DETERMINATION_UI_ENABLED:
            self.orbit_determination_page = (
                self.create_orbit_determination_workspace()
            )
            self.orbit_determination_module_index = self.module_tabs.addTab(
                self.orbit_determination_page,
                "ORBIT DETERMINATION",
            )
            self.module_tabs.tabBar().setTabData(
                self.orbit_determination_module_index,
                "ORBIT DETERMINATION",
            )

        self.tabs.tabBar().setTabVisible(
            self.integrity_tab_index,
            False,
        )

        self.create_retro_navigation()

        self.settings_overlay = SettingsOverlay(self, central)
        self.settings_overlay.setGeometry(central.rect())

        self.tabs.currentChanged.connect(
            self.handle_tab_changed
        )
        self.module_tabs.currentChanged.connect(
            self.handle_module_changed
        )
        saved_module = max(
            0, int(self.application_config.get("active_module", 0))
        )
        if saved_module >= self.module_tabs.count():
            saved_module = self.propagation_module_index
        saved_tab = min(
            self.tabs.count() - 1,
            max(0, int(self.application_config.get("active_tab", 0))),
        )
        self.module_tabs.setCurrentIndex(saved_module)
        self.tabs.setCurrentIndex(saved_tab)
        self.activate_profile(
            self.active_profile_id,
            apply_eop_default=False,
        )
        self.bind_project_editors()

        self.apply_language(self.language)
        self.localization_refresh_timer = QTimer(self)
        self.localization_refresh_timer.setInterval(5000)
        self.localization_refresh_timer.timeout.connect(
            self.safe_refresh_localized_text
        )
        self.localization_refresh_timer.start()
        if self.application_config.get("window_maximized"):
            QTimer.singleShot(0, self.showMaximized)
        config_warning = get_last_config_warning()
        if config_warning:
            QTimer.singleShot(
                0,
                lambda message=config_warning: self.statusBar().showMessage(
                    message, 15000
                ),
            )


    def create_retro_navigation(self):
        """Create real menu/toolbar routes, shown only while Retro is active."""

        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(False)

        self.retro_view_menu = menu_bar.addMenu("View")
        for label in (
            "LIVE TELEMETRY",
            "PERTURBATION",
            "ORBITAL VIEW",
            "REFERENCE LAB",
            "PROPAGATION",
            "GEO OPERATIONS",
            "ECLIPSE",
        ):
            action = self.retro_view_menu.addAction(label.title())
            action.triggered.connect(
                lambda _checked=False, page_label=label: self.select_tab_by_label(
                    page_label
                )
            )
        self.retro_view_menu.addSeparator()
        fullscreen_action = self.retro_view_menu.addAction("Full Screen")
        fullscreen_action.setShortcut(QKeySequence("F11"))
        fullscreen_action.triggered.connect(self.toggle_full_screen)

        self.retro_spacecraft_menu = menu_bar.addMenu("Spacecraft")
        profiles_action = self.retro_spacecraft_menu.addAction(
            "Spacecraft Profiles..."
        )
        profiles_action.triggered.connect(self.open_profile_manager)

        self.retro_simulation_menu = menu_bar.addMenu("Simulation")
        run_action = self.retro_simulation_menu.addAction("Run Propagation")
        run_action.triggered.connect(self.run_manual_propagation)
        stop_action = self.retro_simulation_menu.addAction("Stop Propagation")
        stop_action.triggered.connect(self.cancel_manual_propagation)
        self.retro_simulation_menu.addSeparator()
        eclipse_action = self.retro_simulation_menu.addAction(
            "Calculate Eclipse"
        )
        eclipse_action.triggered.connect(self.run_eclipse_prediction)

        self.retro_tools_menu = menu_bar.addMenu("Tools")
        validation_action = self.retro_tools_menu.addAction(
            "System / Validation"
        )
        validation_action.triggered.connect(self.open_integrity_page)
        settings_action = self.retro_tools_menu.addAction("Settings...")
        settings_action.triggered.connect(self.open_settings_overlay)
        self.retro_tools_menu.addSeparator()
        refresh_action = self.retro_tools_menu.addAction("Refresh Application")
        refresh_action.triggered.connect(self.refresh_application)

        self.retro_help_menu = menu_bar.addMenu("Help")
        credits_action = self.retro_help_menu.addAction("Credits")
        credits_action.triggered.connect(self.open_credits_overlay)

        self.retro_menus = (
            self.retro_view_menu,
            self.retro_spacecraft_menu,
            self.retro_simulation_menu,
            self.retro_tools_menu,
            self.retro_help_menu,
        )

        toolbar = QToolBar("Main")
        toolbar.setObjectName("retroToolBar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        self.retro_toolbar = toolbar

        def toolbar_action(label, icon_name, slot):
            icon = self.style().standardIcon(
                getattr(QStyle.StandardPixmap, icon_name)
            )
            action = toolbar.addAction(icon, label)
            action.triggered.connect(slot)
            return action

        toolbar_action("New", "SP_FileIcon", self.new_project_action)
        toolbar_action("Open", "SP_DialogOpenButton", self.open_project_action)
        toolbar_action("Save", "SP_DialogSaveButton", self.save_project_action)
        toolbar.addSeparator()
        toolbar_action("Run", "SP_MediaPlay", self.run_manual_propagation)
        toolbar_action("Stop", "SP_MediaStop", self.cancel_manual_propagation)
        toolbar.addSeparator()
        toolbar_action("Refresh", "SP_BrowserReload", self.refresh_application)
        toolbar_action("Settings", "SP_FileDialogInfoView", self.open_settings_overlay)

        self.retro_ready_status = QLabel(" Ready ")
        self.retro_spacecraft_status = QLabel("")
        self.statusBar().addPermanentWidget(self.retro_ready_status)
        self.statusBar().addPermanentWidget(self.retro_spacecraft_status)


    def select_tab_by_label(self, label):
        target = str(label).strip().upper()
        if target in {"ECLIPSE", self.tr("ECLIPSE").upper()}:
            return self.select_module_by_label("ECLIPSE")
        localized_target = self.tr(target).strip().upper()
        for index in range(self.tabs.count()):
            visible_label = self.tabs.tabText(index).strip().upper()
            if visible_label in {target, localized_target}:
                self.module_tabs.setCurrentIndex(
                    self.propagation_module_index
                )
                self.tabs.setCurrentIndex(index)
                return True
        return False


    def select_module_by_label(self, label):
        """Select a top-level module using English or localized text."""

        target = str(label).strip().upper()
        localized_target = self.tr(target).strip().upper()
        for index in range(self.module_tabs.count()):
            canonical = str(
                self.module_tabs.tabBar().tabData(index) or ""
            ).strip().upper()
            visible_label = self.module_tabs.tabText(index).strip().upper()
            if target in {canonical, visible_label} or visible_label == localized_target:
                self.module_tabs.setCurrentIndex(index)
                return True
        return False


    def open_integrity_page(self):
        self.module_tabs.setCurrentIndex(self.propagation_module_index)
        self.tabs.tabBar().setTabVisible(self.integrity_tab_index, True)
        self.tabs.setCurrentIndex(self.integrity_tab_index)


    def open_credits_overlay(self):
        self.settings_overlay.show_overlay()
        self.settings_overlay._select_page(2)


    def open_settings_overlay(self):

        self.settings_overlay.show_overlay()


    def tr(self, text):
        """Translate a user-facing string into the active UI language."""

        return translate_text(text, self.language)


    def refresh_localized_text(self):
        """Keep dynamic labels, tables and chart annotations in one language."""

        translate_widget_tree(self, self.language)


    def safe_refresh_localized_text(self):
        """Refresh dynamic text without interrupting active data entry."""

        focus_widget = QApplication.focusWidget()
        focus_target = focus_widget
        while focus_target is not None:
            if isinstance(focus_target, (QLineEdit, QAbstractSpinBox)):
                return False
            focus_target = focus_target.parentWidget()
        if getattr(self, "_localization_refresh_in_progress", False):
            return False
        self._localization_refresh_in_progress = True
        try:
            # Periodic refresh is for dynamic widget text only. Matplotlib is
            # translated on explicit language changes, avoiding queued redraws
            # racing widget teardown or scientific input events.
            translate_widget_tree(
                self,
                self.language,
                include_matplotlib=False,
                include_table_cells=False,
            )
            return True
        except Exception as error:
            print("LOCALIZATION REFRESH ERROR:", error)
            return False
        finally:
            self._localization_refresh_in_progress = False


    def apply_language(self, language):
        """Switch Azerbaijani/English live without touching scientific state."""

        selected_language = normalise_language(language, self.language)
        if selected_language not in SUPPORTED_LANGUAGES:
            raise ValueError("Unknown language selection.")
        self.language = selected_language
        self.application_config["language"] = selected_language
        application = QApplication.instance()
        if application is not None:
            application.setApplicationDisplayName(
                translate_text("Orbital Perturbation Analyzer", selected_language)
            )
        self.refresh_localized_text()
        status_bar = self.statusBar()
        if isinstance(status_bar, LocalizedStatusBar):
            status_bar.retranslate_current_message()
        return self.language


    def apply_interface_theme(self, interface_theme):
        """Switch Normal/Retro presentation without touching model state."""

        selected = str(interface_theme or "normal").strip().lower()
        if selected not in {"normal", "retro"}:
            raise ValueError("Unknown interface theme selection.")
        self.interface_theme = theme.set_theme(selected)
        self.application_config["theme"] = self.interface_theme
        application = QApplication.instance()
        if application is not None:
            application.setStyleSheet(
                theme.application_stylesheet(DROPDOWN_ARROW_PATH)
                if theme.is_retro()
                else ""
            )
        self.apply_application_theme()
        self.apply_theme_presentation()
        if hasattr(self, "hero_card"):
            self.hero_card.set_theme(
                self.interface_theme,
                HERO_BACKGROUND_DARK_PATH,
            )
        if hasattr(self, "settings_overlay"):
            self.settings_overlay.apply_theme()
        if hasattr(self, "geo_chart"):
            self.refresh_geo_theme()
        for graph in self.findChildren(GraphWidget):
            graph.apply_theme()
            graph.draw_idle()
        for widget in self.findChildren(KeplerComparisonWidget):
            widget.apply_theme()
        central = self.centralWidget()
        if central is not None:
            central.update()
        return self.interface_theme


    # The workspace is dense enough that below roughly 1024x600 captions
    # start to clip and the command bar controls begin to overlap.  Refusing
    # to shrink past that is what keeps the layout correct rather than
    # patching each panel for a size no display actually uses.
    MINIMUM_WINDOW_SIZE = (1024, 600)

    def apply_minimum_window_size(self):
        """Stop the window shrinking into a size the layout cannot hold.

        The floor is clamped to the screen so a high-DPI desktop, where the
        logical work area can itself be smaller than the floor, never ends up
        with a window it cannot fit.
        """

        minimum_width, minimum_height = self.MINIMUM_WINDOW_SIZE
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            minimum_width = min(minimum_width, max(320, available.width() - 40))
            minimum_height = min(minimum_height, max(240, available.height() - 80))
        self.setMinimumSize(minimum_width, minimum_height)

    # Widths at which the header sheds its least important text.  The title
    # is set at a fixed 24px, which needs 514px of the header row; below
    # roughly 1280px that no longer fits beside the status controls and both
    # the title and the buttons were being clipped.
    HERO_TITLE_STEPS = ((1400, 24), (1200, 20), (1040, 17), (0, 15))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.apply_responsive_hero()

    def apply_responsive_hero(self):
        """Scale the header to the window so no header text is ever clipped."""

        if not hasattr(self, "main_title"):
            return
        width = self.width()
        for threshold, size in self.HERO_TITLE_STEPS:
            if width >= threshold:
                title_size = size
                break
        # A stylesheet font-size outranks setFont(), so the step has to be
        # written as a widget stylesheet too.  It is only reapplied when the
        # step actually changes, otherwise every resize event would trigger a
        # full restyle of the header.
        if getattr(self, "_hero_title_size", None) != title_size:
            self._hero_title_size = title_size
            self.main_title.setStyleSheet(f"font-size: {title_size}px;")

        retro = theme.is_retro()
        # The model chain also appears in Settings, so dropping it on a
        # narrow window loses no information.
        self.hero_model.setVisible(not retro and width >= 1200)
        self.mission_eyebrow.setVisible(not retro and width >= 900)
        self.main_subtitle.setVisible(width >= 820)
        # Azerbaijani labels are noticeably longer than the English ones, so
        # the three header controls stop fitting before the window gets
        # narrow.  The restart command stays available from the File menu.
        self.refresh_app_button.setVisible(not retro and width >= 1200)

    def apply_theme_presentation(self):
        """Apply theme-specific density and desktop-shell presentation."""

        if not hasattr(self, "main_layout"):
            return
        retro = theme.is_retro()
        if retro:
            self.main_layout.setContentsMargins(6, 5, 6, 6)
            self.main_layout.setSpacing(5)
            self.hero_layout.setContentsMargins(8, 5, 8, 5)
            self.hero_layout.setSpacing(8)
            self.hero_card.setMinimumHeight(72)
            self.hero_card.setMaximumHeight(82)
            logo_size = 48
            self.mission_status_layout.setSpacing(2)
        else:
            self.main_layout.setContentsMargins(16, 12, 16, 14)
            self.main_layout.setSpacing(11)
            self.hero_layout.setContentsMargins(20, 12, 20, 12)
            self.hero_layout.setSpacing(18)
            self.hero_card.setMinimumHeight(116)
            self.hero_card.setMaximumHeight(132)
            logo_size = 72
            self.mission_status_layout.setSpacing(7)

        self.hero_logo.setFixedSize(logo_size, logo_size)
        if not self.hero_logo_pixmap.isNull():
            self.hero_logo.setPixmap(
                self.hero_logo_pixmap.scaled(
                    logo_size - 6,
                    logo_size - 6,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self.hero_model.setVisible(not retro)
        self.apply_responsive_hero()
        self.refresh_app_button.setVisible(not retro)
        self.settings_button.setVisible(not retro)

        if hasattr(self, "product_command_layout"):
            self.product_command_layout.setContentsMargins(
                6 if retro else 12,
                3 if retro else 8,
                6 if retro else 12,
                3 if retro else 8,
            )
            self.product_command_layout.setSpacing(4 if retro else 8)
        if hasattr(self, "profile_selector"):
            self.profile_selector.setMinimumHeight(22 if retro else 34)
        if hasattr(self, "telemetry_top_layout"):
            self.telemetry_top_layout.setDirection(
                QBoxLayout.Direction.TopToBottom
                if retro
                else QBoxLayout.Direction.LeftToRight
            )

        if hasattr(self, "graph_action_buttons"):
            # Keep filters and actions on separate compact rows in both
            # themes.  A single row overflowed laptop-width work areas and
            # made prediction/navigation buttons unreachable.
            for button in self.graph_action_buttons:
                if self.graph_primary_controls_layout.indexOf(button) >= 0:
                    self.graph_primary_controls_layout.removeWidget(button)
                    self.graph_action_controls_layout.addWidget(button)
            self.graph_action_controls_host.show()
        if hasattr(self, "system_fullscreen_button"):
            self.system_fullscreen_button.setText(
                "FULL SCREEN" if retro else "FULL SCREEN  [F11]"
            )

        if hasattr(self, "retro_toolbar"):
            self.retro_toolbar.setVisible(retro)
        for menu in getattr(self, "retro_menus", ()):
            menu.menuAction().setVisible(retro)
        if hasattr(self, "retro_ready_status"):
            self.retro_ready_status.setVisible(retro)
            self.retro_spacecraft_status.setVisible(retro)
            self.retro_spacecraft_status.setText(
                f" Spacecraft: {self.active_profile.display_name} "
            )

        if hasattr(self, "integrity_tab_index"):
            self.tabs.tabBar().setTabVisible(self.integrity_tab_index, retro)
            self.tabs.setTabText(
                self.integrity_tab_index,
                "SYSTEM / VALIDATION" if retro else "SETTINGS",
            )
        for widget in self.findChildren(QWidget):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.updateGeometry()


    def persist_configuration(
        self,
        interface_theme,
        language=None,
    ):
        """Save public UI preferences without changing scientific algorithms."""

        selected_theme = str(interface_theme or "normal").strip().lower()
        if selected_theme not in {"normal", "retro"}:
            raise ValueError("Unknown interface theme selection.")
        selected_language = normalise_language(language, self.language)
        if selected_language not in SUPPORTED_LANGUAGES:
            raise ValueError("Unknown language selection.")
        saved = save_application_config(
            {
                "theme": selected_theme,
                "language": selected_language,
                "integrator_rtol": self.integrator_rtol.text().strip(),
                "integrator_atol": self.integrator_atol.text().strip(),
                "integrator_max_step": self.integrator_max_step.value(),
                "validation_minutes": self.validation_minutes.value(),
                "eop_enabled": is_eop_enabled(),
                "active_profile_id": self.active_profile_id,
                "window_geometry": [
                    self.normalGeometry().x(),
                    self.normalGeometry().y(),
                    self.normalGeometry().width(),
                    self.normalGeometry().height(),
                ],
                "window_maximized": self.isMaximized(),
                "active_module": self.module_tabs.currentIndex(),
                "active_tab": self.tabs.currentIndex(),
            },
            self.application_config_path,
        )
        self.application_config = saved
        self.interface_theme = saved["theme"]
        self.language = selected_language
        self.refresh_localized_text()
        return self.interface_theme


    def persist_recent_project_preferences(self):
        """Keep recent file paths session-only so private paths never persist."""

        return list(self.application_config.get("recent_projects", []))


    def enroll_admin_device(self, verification_key_path):
        """Provision this Windows user/device without retaining the key path."""

        path = str(verification_key_path or "").strip()
        if not path:
            raise AdminSecurityError("Select a provisioned verification key first.")
        self.logout_admin_session()
        verification_key = load_verification_key_file(path)
        enroll_device(
            verification_key,
            enrollment_path=self.admin_session.enrollment_path,
            protector=self.admin_session.protector,
        )
        self.admin_session = AdminSessionManager(
            enrollment_path=self.admin_session.enrollment_path,
            protector=self.admin_session.protector,
        )
        return True


    def _clear_admin_module_pages(self):
        if not hasattr(self, "module_tabs"):
            self._admin_module_pages.clear()
            return
        for page in tuple(self._admin_module_pages):
            index = self.module_tabs.indexOf(page)
            if index >= 0:
                self.module_tabs.removeTab(index)
            page.deleteLater()
        self._admin_module_pages.clear()


    def _install_admin_content(self, content):
        """Install validated session data without importing executable code."""

        self.profile_store.set_session_profiles(content.profiles)
        register_session_reference_datasets(content.reference_datasets)
        register_session_eclipse_reference_datasets(
            content.eclipse_reference_datasets
        )
        # The OD workspace can remain hidden while its validated, data-only
        # station catalogue supplies the Sun-outage tool.  Coordinates stay
        # memory-only and are cleared on logout below.
        register_session_orbit_determination_datasets(
            content.orbit_determination_datasets
        )
        self.refresh_profile_selector()
        if hasattr(self, "reference_dataset_combo"):
            populate_reference_scenario_combo(
                self.reference_dataset_combo,
                default_index=2,
            )
            self._reference_selected_dataset_id = None
            self.reference_dataset_changed()
        self._refresh_eclipse_reference_selector()
        self.refresh_sun_outage_stations()
        if hasattr(self, "od_dataset_summary"):
            self.reload_orbit_determination_dataset(reset_arc=True)
        self._clear_admin_module_pages()
        for descriptor in content.admin_modules:
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(28, 28, 28, 28)
            title = QLabel(descriptor.label)
            title.setObjectName("pageTitle")
            layout.addWidget(title)
            notice = QLabel(
                descriptor.description
                + "\n\nThis page was created from a validated data-only "
                "descriptor. No package code was executed."
            )
            notice.setWordWrap(True)
            notice.setObjectName("sectionDescription")
            layout.addWidget(notice)
            layout.addStretch()
            index = self.module_tabs.addTab(page, descriptor.label)
            self.module_tabs.tabBar().setTabData(
                index, f"ADMIN:{descriptor.module_id}"
            )
            self._admin_module_pages.append(page)
        self.refresh_localized_text()


    def _refresh_eclipse_reference_selector(self):
        selector = getattr(self, "eclipse_reference_selector", None)
        if selector is None:
            return
        selected = selector.currentData()
        selector.blockSignals(True)
        selector.clear()
        for spec in available_eclipse_reference_specs():
            selector.addItem(spec.label, spec.dataset_id)
        index = selector.findData(selected)
        if index < 0:
            index = selector.findData("synthetic_geo_2030_equinox")
        selector.setCurrentIndex(max(0, index))
        selector.blockSignals(False)


    def unlock_admin_package(self, package_path, password):
        package_path = str(package_path or "").strip()
        if not package_path:
            raise AdminSecurityError("Select a signed admin package first.")
        try:
            content = self.admin_session.unlock(package_path, password)
            self._install_admin_content(content)
        except Exception:
            self.logout_admin_session()
            raise
        self.statusBar().showMessage(
            "ADMIN SESSION UNLOCKED — encrypted content is memory-only",
            10000,
        )
        return content


    def logout_admin_session(self):
        """Remove private session UI/data and return to the public profile."""

        manager = getattr(self, "admin_session", None)
        if manager is None:
            return
        # A worker may hold a session profile/reference after the UI changes.
        # Stop those workers before dropping the last managed session objects.
        for thread in (
            getattr(self, "propagation_thread", None),
            getattr(self, "eclipse_thread", None),
            getattr(self, "sun_outage_thread", None),
            getattr(self, "reference_comparison_thread", None),
            getattr(self, "orbit_determination_thread", None),
        ):
            if thread is not None and thread.isRunning():
                thread.requestInterruption()
                thread.quit()
                thread.wait(3000)
        self.stop_live_logging()
        session_profile_active = (
            hasattr(self, "profile_store")
            and self.profile_store.is_session_profile(
                getattr(self, "active_profile_id", "")
            )
        )
        if session_profile_active:
            public_profile = self.application_config.get(
                "active_profile_id", "synthetic_geo_demo"
            )
            self.activate_profile(
                public_profile,
                load_state=True,
                apply_eop_default=False,
                update_application_preference=False,
            )
        clear_session_reference_datasets()
        clear_session_eclipse_reference_datasets()
        clear_session_orbit_determination_datasets()
        if hasattr(self, "profile_store"):
            self.profile_store.clear_session_profiles()
            self.refresh_profile_selector()
        self._clear_admin_module_pages()
        manager.logout()
        self.latest_reference_comparison = None
        self.latest_reference_scenario = None
        self.reference_scenario_results = {True: None, False: None}
        self.latest_orbit_determination = None
        self.orbit_determination_dataset = None
        self.eclipse_reference_comparison = None
        self.eclipse_prediction_result = None
        self.eclipse_reference_interval_prediction = None
        self.yearly_eclipse_schedule = None
        self.sun_outage_prediction = None
        if hasattr(self, "sun_outage_table"):
            self.sun_outage_table.setRowCount(0)
            self.sun_outage_export_button.setEnabled(False)
            self.sun_outage_summary.setText(
                "Choose the receiving link parameters and calculate the yearly schedule."
            )
        if hasattr(self, "reference_dataset_combo"):
            populate_reference_scenario_combo(
                self.reference_dataset_combo,
                default_index=2,
            )
            self._reference_selected_dataset_id = None
            self.reference_dataset_changed()
        self._refresh_eclipse_reference_selector()
        self.refresh_sun_outage_stations()
        if hasattr(self, "od_dataset_summary"):
            self.reload_orbit_determination_dataset(reset_arc=True)
        if hasattr(self, "clear_product_results"):
            self.clear_product_results()
        settings = getattr(self, "settings_overlay", None)
        if settings is not None and hasattr(settings, "sync_admin_status"):
            settings.sync_admin_status()
        return True


    # ========================================================
    # MONITOR PAGE
    # ========================================================

    @staticmethod
    def _reserve_readout_width(labels, widest_reading):
        """Hold a fixed width for labels that are rewritten continuously."""

        for label in labels:
            metrics = QFontMetrics(label.font())
            label.setMinimumWidth(metrics.horizontalAdvance(widest_reading) + 6)

    def create_monitor_page(self):

        page = QWidget()
        outer_layout = QVBoxLayout(page)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.monitor_page_scroll = QScrollArea()
        self.monitor_page_scroll.setWidgetResizable(True)
        self.monitor_page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.monitor_page_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        monitor_content = QWidget()
        layout = QVBoxLayout(monitor_content)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # The active spacecraft is chosen once in the command bar above the
        # workspace; every module reads that same selection, so no page
        # repeats the control.

        # ----------------------------------------------------
        # SATELLITE + CELESTIAL EPHEMERIDES
        # ----------------------------------------------------

        top_layout = QHBoxLayout()
        self.telemetry_top_layout = top_layout

        # Satellite
        satellite_box = QGroupBox(
            f"{TARGET_SATELLITE_DISPLAY_NAME} — SATELLITE"
        )
        self.live_satellite_box = satellite_box
        satellite_box.setProperty("surfaceRole", "blue")

        satellite_layout = QGridLayout(
            satellite_box
        )
        satellite_layout.setContentsMargins(16, 16, 16, 12)
        satellite_layout.setHorizontalSpacing(14)
        satellite_layout.setVerticalSpacing(7)
        # Only columns 0 and 1 carry content here; column 2 is the trailing
        # spacer that keeps the caption/readout pair together on the left.
        satellite_layout.setColumnStretch(0, 0)
        satellite_layout.setColumnStretch(1, 0)
        satellite_layout.setColumnStretch(2, 1)

        self.sat_x = QLabel(
            "0.000 km"
        )

        self.sat_y = QLabel(
            "0.000 km"
        )

        self.sat_z = QLabel(
            "0.000 km"
        )

        self.sat_distance = QLabel(
            "0.000 km"
        )
        for value_label in (
            self.sat_x,
            self.sat_y,
            self.sat_z,
            self.sat_distance,
        ):
            value_label.setObjectName("telemetryValue")

        satellite_layout.addWidget(
            QLabel("X:"),
            0,
            0
        )

        satellite_layout.addWidget(
            self.sat_x,
            0,
            1
        )

        satellite_layout.addWidget(
            QLabel("Y:"),
            1,
            0
        )

        satellite_layout.addWidget(
            self.sat_y,
            1,
            1
        )

        satellite_layout.addWidget(
            QLabel("Z:"),
            2,
            0
        )

        satellite_layout.addWidget(
            self.sat_z,
            2,
            1
        )

        satellite_layout.addWidget(
            QLabel("Distance:"),
            3,
            0
        )

        satellite_layout.addWidget(
            self.sat_distance,
            3,
            1
        )

        # Celestial ephemerides
        moon_box = QGroupBox(
            "CELESTIAL EPHEMERIDES — DE440 / J2000"
        )
        moon_box.setProperty("surfaceRole", "lavender")

        moon_layout = QGridLayout(
            moon_box
        )
        moon_layout.setContentsMargins(16, 16, 16, 12)
        moon_layout.setHorizontalSpacing(14)
        moon_layout.setVerticalSpacing(7)
        # Columns 0 and 2 carry captions, 1 and 3 carry readouts.  The
        # stretch belongs on the readout columns so each value stays beside
        # its own caption instead of being pushed to the panel edge.
        moon_layout.setColumnStretch(0, 0)
        moon_layout.setColumnStretch(1, 1)
        moon_layout.setColumnStretch(2, 0)
        moon_layout.setColumnStretch(3, 1)

        self.moon_x = QLabel(
            "0.000 km"
        )

        self.moon_y = QLabel(
            "0.000 km"
        )

        self.moon_z = QLabel(
            "0.000 km"
        )

        self.moon_distance = QLabel(
            "0.000 km"
        )
        for value_label in (
            self.moon_x,
            self.moon_y,
            self.moon_z,
            self.moon_distance,
        ):
            value_label.setObjectName("telemetryValue")

        moon_layout.addWidget(
            QLabel("X:"),
            0,
            0
        )

        moon_layout.addWidget(
            self.moon_x,
            0,
            1
        )

        moon_layout.addWidget(
            QLabel("Y:"),
            1,
            0
        )

        moon_layout.addWidget(
            self.moon_y,
            1,
            1
        )

        moon_layout.addWidget(
            QLabel("Z:"),
            2,
            0
        )

        moon_layout.addWidget(
            self.moon_z,
            2,
            1
        )

        moon_layout.addWidget(
            QLabel("Earth-Moon Distance:"),
            3,
            0
        )

        moon_layout.addWidget(
            self.moon_distance,
            3,
            1
        )

        self.sun_x = QLabel("0.000 km")
        self.sun_y = QLabel("0.000 km")
        self.sun_z = QLabel("0.000 km")
        self.sun_distance = QLabel("0.000 km")
        for value_label in (
            self.sun_x,
            self.sun_y,
            self.sun_z,
            self.sun_distance,
        ):
            value_label.setObjectName("telemetryValue")

        moon_layout.addWidget(QLabel("Sun X:"), 0, 2)
        moon_layout.addWidget(self.sun_x, 0, 3)
        moon_layout.addWidget(QLabel("Sun Y:"), 1, 2)
        moon_layout.addWidget(self.sun_y, 1, 3)
        moon_layout.addWidget(QLabel("Sun Z:"), 2, 2)
        moon_layout.addWidget(self.sun_z, 2, 3)
        moon_layout.addWidget(QLabel("Earth-Sun Distance:"), 3, 2)
        moon_layout.addWidget(self.sun_distance, 3, 3)

        # The ephemerides panel carries twice as many caption/readout pairs
        # as the state panel, so it is given twice the width instead of an
        # even split that left one panel half empty on wide screens.
        top_layout.setSpacing(10)
        top_layout.addWidget(
            satellite_box,
            1,
        )

        top_layout.addWidget(
            moon_box,
            2,
        )

        layout.addLayout(
            top_layout
        )

        # ----------------------------------------------------
        # PERTURBATION
        # ----------------------------------------------------

        perturbation_box = QGroupBox(
            "PERTURBATION ACCELERATION — THIRD-BODY + SRP"
        )
        self.live_perturbation_box = perturbation_box
        perturbation_box.setProperty("surfaceRole", "blush")

        perturbation_layout = QGridLayout(
            perturbation_box
        )
        perturbation_layout.setContentsMargins(16, 16, 16, 12)
        perturbation_layout.setHorizontalSpacing(14)
        perturbation_layout.setVerticalSpacing(7)
        # Same caption/readout pairing as the ephemerides panel above.
        perturbation_layout.setColumnStretch(0, 0)
        perturbation_layout.setColumnStretch(1, 1)
        perturbation_layout.setColumnStretch(2, 0)
        perturbation_layout.setColumnStretch(3, 1)

        self.live_force_moon = QCheckBox("Moon — DE440")
        self.live_force_moon.setChecked(True)
        self.live_force_sun = QCheckBox("Sun — DE440")
        self.live_force_sun.setChecked(True)
        self.live_force_srp = QCheckBox("SRP — BOX-WING")
        self.live_force_srp.setChecked(True)
        self.live_force_srp.setToolTip(
            "Physical box-wing SRP uses the transparent public coefficient "
            "CP=1.0. No spacecraft calibration is bundled."
        )
        self.live_force_moon.toggled.connect(
            lambda _checked=False: self.update_data()
        )
        self.live_force_sun.toggled.connect(
            lambda _checked=False: self.update_data()
        )
        self.live_force_srp.toggled.connect(
            lambda _checked=False: self.update_data()
        )
        force_selector = QHBoxLayout()
        # Without explicit spacing each label ran straight into the next
        # check indicator, so the three switches read as one long string.
        force_selector.setSpacing(20)
        force_selector.setContentsMargins(0, 0, 0, 4)
        force_selector.addWidget(QLabel("Active force modules:"))
        force_selector.addWidget(self.live_force_moon)
        force_selector.addWidget(self.live_force_sun)
        force_selector.addWidget(self.live_force_srp)
        force_selector.addStretch(1)
        perturbation_layout.addLayout(force_selector, 0, 0, 1, 4)

        self.ax_value = QLabel(
            "0.0000e+00 km/s²"
        )

        self.ay_value = QLabel(
            "0.0000e+00 km/s²"
        )

        self.az_value = QLabel(
            "0.0000e+00 km/s²"
        )

        self.magnitude_value = QLabel(
            "0.0000e+00 km/s²"
        )
        for value_label in (
            self.ax_value,
            self.ay_value,
            self.az_value,
        ):
            value_label.setObjectName("telemetryValue")
        self.magnitude_value.setObjectName("telemetryPrimary")

        magnitude_font = (
            self.magnitude_value.font()
        )

        magnitude_font.setBold(
            True
        )

        magnitude_font.setPointSize(
            13
        )

        self.magnitude_value.setFont(
            magnitude_font
        )

        perturbation_layout.addWidget(
            QLabel("ax:"),
            1,
            0
        )

        perturbation_layout.addWidget(
            self.ax_value,
            1,
            1
        )

        perturbation_layout.addWidget(
            QLabel("ay:"),
            2,
            0
        )

        perturbation_layout.addWidget(
            self.ay_value,
            2,
            1
        )

        perturbation_layout.addWidget(
            QLabel("az:"),
            3,
            0
        )

        perturbation_layout.addWidget(
            self.az_value,
            3,
            1
        )

        perturbation_layout.addWidget(
            QLabel("Magnitude:"),
            4,
            0
        )

        perturbation_layout.addWidget(
            self.magnitude_value,
            4,
            1
        )

        self.live_moon_magnitude = QLabel("0.0000e+00 km/s²")
        self.live_sun_magnitude = QLabel("0.0000e+00 km/s²")
        self.live_srp_magnitude = QLabel("Waiting for live state...")
        self.live_srp_illumination = QLabel("N/A")
        self.live_force_mode = QLabel("MOON + SUN + SRP")
        for value_label in (
            self.live_moon_magnitude,
            self.live_sun_magnitude,
            self.live_srp_magnitude,
            self.live_srp_illumination,
            self.live_force_mode,
        ):
            value_label.setObjectName("telemetryValue")
        perturbation_layout.addWidget(QLabel("Moon |a|:"), 1, 2)
        perturbation_layout.addWidget(self.live_moon_magnitude, 1, 3)
        perturbation_layout.addWidget(QLabel("Sun β |a|:"), 2, 2)
        perturbation_layout.addWidget(self.live_sun_magnitude, 2, 3)
        perturbation_layout.addWidget(QLabel("SRP |a|:"), 3, 2)
        perturbation_layout.addWidget(self.live_srp_magnitude, 3, 3)
        perturbation_layout.addWidget(QLabel("Sunlight / CP:"), 4, 2)
        perturbation_layout.addWidget(self.live_srp_illumination, 4, 3)
        perturbation_layout.addWidget(QLabel("Displayed sum:"), 5, 2)
        perturbation_layout.addWidget(self.live_force_mode, 5, 3)

        for telemetry_panel in (satellite_box, moon_box, perturbation_box):
            for caption_label in telemetry_panel.findChildren(QLabel):
                if not caption_label.objectName():
                    caption_label.setObjectName("telemetryLabel")

        # Live readouts are rewritten once a second and every value has a
        # different width.  Reserving the width of the widest reading each
        # field can produce keeps the grid columns still, so the panel never
        # twitches while the numbers change.
        self._reserve_readout_width(
            (
                self.sat_x, self.sat_y, self.sat_z, self.sat_distance,
                self.moon_x, self.moon_y, self.moon_z, self.moon_distance,
                self.sun_x, self.sun_y, self.sun_z, self.sun_distance,
            ),
            "-000000000.000 km",
        )
        self._reserve_readout_width(
            (
                self.ax_value, self.ay_value, self.az_value,
                self.live_moon_magnitude, self.live_sun_magnitude,
                self.live_srp_magnitude,
            ),
            "-0.0000e+00 km/s²",
        )
        self._reserve_readout_width(
            (self.magnitude_value,),
            "-0.0000e+00 km/s²",
        )

        layout.addWidget(
            perturbation_box
        )

        # ----------------------------------------------------
        # SYSTEM STATUS
        # ----------------------------------------------------

        status_box = QGroupBox(
            "SYSTEM STATUS"
        )
        status_box.setProperty("surfaceRole", "sage")

        status_layout = QHBoxLayout(
            status_box
        )

        self.spice_status = QLabel(
            "SPICE: ✓ Loaded"
        )

        self.tle_status = QLabel(
            "TLE: ✓ Loaded"
        )

        self.utc_status = QLabel(
            "UTC: Waiting..."
        )
        _set_status_role(self.spice_status, "ok")
        _set_status_role(self.tle_status, "ok")
        _set_status_role(self.utc_status, "info")

        # Read the three indicators left to right, then act: the single
        # action sits on the right edge instead of between two readouts.
        status_layout.setContentsMargins(16, 14, 16, 8)
        status_layout.setSpacing(18)
        status_layout.addWidget(
            self.spice_status
        )

        status_layout.addWidget(
            self.tle_status
        )

        status_layout.addWidget(
            self.utc_status
        )

        status_layout.addStretch(1)

        self.live_tle_update_button = QPushButton(
            "UPDATE TLE"
        )
        self.live_tle_update_button.setObjectName("primaryAction")
        self.live_tle_update_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.live_tle_update_button.setToolTip(
            "UPDATE TLE FROM CELESTRAK"
        )
        self.live_tle_update_button.clicked.connect(
            self.start_tle_update
        )
        status_layout.addWidget(
            self.live_tle_update_button
        )

        layout.addWidget(
            status_box
        )

        layout.addStretch()

        self.monitor_page_scroll.setWidget(monitor_content)
        outer_layout.addWidget(self.monitor_page_scroll)

        self.tabs.addTab(
            page,
            "LIVE TELEMETRY"
        )


    # ========================================================
    # GRAPH PAGE
    # ========================================================

    def create_graph_page(self):

        page = QWidget()
        self.graph_page = page

        # Controls stay fixed above the graph.  The previous whole-page scroll
        # surface let normal mouse-wheel use push every control off-screen and
        # made a standard desktop viewport look clipped.
        layout = QVBoxLayout(page)
        self.graph_page_layout = layout
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(5)

        # ----------------------------------------------------
        # CONTROLS
        # ----------------------------------------------------

        controls_host = QWidget()
        self.graph_controls_host = controls_host
        controls_host_layout = QVBoxLayout(controls_host)
        controls_host_layout.setContentsMargins(0, 0, 0, 0)
        controls_host_layout.setSpacing(3)
        controls = QHBoxLayout()
        self.graph_primary_controls_layout = controls

        controls.addWidget(
            QLabel("Time range:")
        )

        self.time_range = QComboBox()

        self.time_range.addItems(
            [
                "1 Hour",
                "6 Hours",
                "24 Hours",
            ]
        )

        self.time_range.currentIndexChanged.connect(
            self.handle_graph_range_changed
        )

        controls.addWidget(
            self.time_range
        )

        controls.addSpacing(
            20
        )

        controls.addWidget(
            QLabel("Parameter:")
        )

        self.parameter = QComboBox()

        self.parameter.addItems(list(PERTURBATION_PARAMETERS))
        self.parameter.setToolTip(
            "ax/ay/az are J2000 inertial components; aR/aT/aN are radial, "
            "along-track, and orbit-normal RTN components."
        )

        self.parameter.currentIndexChanged.connect(
            self.safe_update_graph
        )

        controls.addWidget(
            self.parameter
        )

        controls.addSpacing(14)
        controls.addWidget(QLabel("Force sources:"))
        self.graph_force_moon = QCheckBox("Moon")
        self.graph_force_sun = QCheckBox("Sun β")
        self.graph_force_srp = QCheckBox("SRP")
        self.graph_force_total = QCheckBox("Combined")
        self.graph_force_moon.setChecked(True)
        self.graph_force_sun.setChecked(True)
        self.graph_force_srp.setChecked(True)
        self.graph_force_total.setChecked(True)
        for source_checkbox in (
            self.graph_force_moon,
            self.graph_force_sun,
            self.graph_force_srp,
            self.graph_force_total,
        ):
            source_checkbox.toggled.connect(self.handle_graph_source_changed)
            controls.addWidget(source_checkbox)

        controls.addSpacing(14)

        self.predict_graph_button = QPushButton(
            "PREDICT PAST + FUTURE"
        )
        self.predict_graph_button.setObjectName("primaryAction")
        self.predict_graph_button.clicked.connect(
            self.run_graph_prediction
        )
        controls.addWidget(
            self.predict_graph_button
        )

        self.graph_past_button = QPushButton(
            "< PAST"
        )
        self.graph_past_button.clicked.connect(
            lambda: self.shift_graph_view(-1)
        )
        controls.addWidget(
            self.graph_past_button
        )

        self.graph_now_button = QPushButton(
            "CENTER NOW"
        )
        self.graph_now_button.clicked.connect(
            self.center_graph_view
        )
        controls.addWidget(
            self.graph_now_button
        )

        self.graph_future_button = QPushButton(
            "FUTURE >"
        )
        self.graph_future_button.clicked.connect(
            lambda: self.shift_graph_view(1)
        )
        controls.addWidget(
            self.graph_future_button
        )

        controls.addStretch()
        controls_host_layout.addLayout(controls)
        self.graph_action_controls_host = QWidget()
        self.graph_action_controls_layout = QHBoxLayout(
            self.graph_action_controls_host
        )
        self.graph_action_controls_layout.setContentsMargins(0, 0, 0, 0)
        self.graph_action_controls_layout.setSpacing(5)
        self.graph_action_controls_layout.addStretch(1)
        controls_host_layout.addWidget(self.graph_action_controls_host)
        self.graph_action_controls_host.hide()
        self.graph_action_buttons = (
            self.predict_graph_button,
            self.graph_past_button,
            self.graph_now_button,
            self.graph_future_button,
        )

        layout.addWidget(controls_host)

        self.graph_prediction_status = QLabel(
            "Moon, Sun β and physical SRP are independent; Combined is the "
            "vector sum. Public-mode SRP uses the explicit neutral CP=1.0 "
            "coefficient."
        )
        self.graph_prediction_status.setObjectName("metricDetail")
        self.graph_prediction_status.setWordWrap(True)
        self.graph_prediction_status.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(
            self.graph_prediction_status
        )

        # ----------------------------------------------------
        # GRAPH
        # ----------------------------------------------------

        self.graph = GraphWidget()
        # A 520 px hard minimum forced the controls off-screen on common
        # 768/1080 px desktop work areas.  The canvas remains expandable but
        # can now share the available viewport with its controls.
        # The control block above the plot needs about 120px, so a 160px
        # floor pushed the canvas past the bottom of the page on a 600px
        # tall window.  132px still leaves a usable plot and fits.
        self.graph.setMinimumHeight(132)
        self.graph.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.graph.setToolTip("")

        self.graph_fullscreen_button = QPushButton(
            "FULL SCREEN",
            self.graph,
        )
        self.graph_fullscreen_button.setObjectName("graphOverlayAction")
        self.graph_fullscreen_button.setToolTip(
            "Show only this graph. Press Esc to return."
        )
        self.graph_fullscreen_button.clicked.connect(
            self.toggle_graph_full_screen
        )
        self.graph_fullscreen_button.adjustSize()
        self.graph.installEventFilter(self)
        QTimer.singleShot(0, self.position_graph_fullscreen_button)

        self.graph.mpl_connect(
            "scroll_event",
            self.on_graph_scroll,
        )
        self.graph.mpl_connect(
            "button_press_event",
            self.on_graph_pan_start,
        )
        self.graph.mpl_connect(
            "motion_notify_event",
            self.on_graph_pan_move,
        )
        self.graph.mpl_connect(
            "button_release_event",
            self.on_graph_pan_end,
        )

        layout.addWidget(
            self.graph
        )

        self.graph_tab_index = self.tabs.addTab(
            page,
            "PERTURBATION"
        )


    # ========================================================
    # 2D EARTH / MOON / SATELLITE VIEW
    # ========================================================

    def create_system_view_page(self):

        page = QWidget()
        self.system_view_page = page

        outer_layout = QVBoxLayout(page)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.system_view_scroll = QScrollArea()
        self.system_view_scroll.setWidgetResizable(True)
        self.system_view_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.system_view_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        system_content = QWidget()
        layout = QVBoxLayout(system_content)
        layout.setContentsMargins(12, 10, 12, 16)

        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.sync_active_profile_orbital_object()

        controls.addWidget(
            QLabel("Projection:")
        )

        self.system_plane = QComboBox()
        self.system_plane.addItems(
            [
                "XY Plane",
                "XZ Plane",
                "YZ Plane",
                "3D Interactive",
            ]
        )
        self.system_plane.currentIndexChanged.connect(
            self.safe_update_system_view
        )
        controls.addWidget(
            self.system_plane
        )

        controls.addWidget(
            QLabel("Scale:")
        )

        self.system_scale = QComboBox()
        self.system_scale.addItems(
            [
                "Auto Fit Selected",
                "Focused Object Orbit",
                "Satellite Close-up (1,000 km)",
                "Satellite Detail (100 km)",
                "Low Earth Orbit (12,000 km)",
                "Geostationary Belt (55,000 km)",
                "Earth-Moon System",
            ]
        )
        self.system_scale.currentIndexChanged.connect(
            self.handle_system_scale_changed
        )
        controls.addWidget(
            self.system_scale
        )

        controls.addWidget(
            QLabel("Focus:")
        )

        self.system_focus = QComboBox()
        for object_id, config in ORBITAL_OBJECTS.items():
            self.system_focus.addItem(
                config["display"],
                object_id,
            )
        active_focus_index = self.system_focus.findData("active_profile")
        if active_focus_index >= 0:
            self.system_focus.setCurrentIndex(active_focus_index)
        self.system_focus.currentIndexChanged.connect(
            self.handle_system_focus_changed
        )
        controls.addWidget(
            self.system_focus
        )

        self.system_reset_view_button = QPushButton(
            "RESET VIEW"
        )
        self.system_reset_view_button.clicked.connect(
            self.reset_system_view
        )
        controls.addWidget(
            self.system_reset_view_button
        )

        self.system_zoom_in_button = QPushButton(
            "+"
        )
        # The stylesheet's 14px horizontal padding makes the natural width
        # 40px; a 38px fixed width clipped the glyph.
        self.system_zoom_in_button.setFixedWidth(
            40
        )
        self.system_zoom_in_button.setToolTip(
            "Zoom in deeply toward the focused object."
        )
        self.system_zoom_in_button.clicked.connect(
            lambda: self.adjust_system_view_zoom(0.50)
        )
        controls.addWidget(
            self.system_zoom_in_button
        )

        self.system_zoom_out_button = QPushButton(
            "−"
        )
        self.system_zoom_out_button.setFixedWidth(
            40
        )
        self.system_zoom_out_button.setToolTip(
            "Zoom out from the focused object."
        )
        self.system_zoom_out_button.clicked.connect(
            lambda: self.adjust_system_view_zoom(2.0)
        )
        controls.addWidget(
            self.system_zoom_out_button
        )

        self.system_fullscreen_button = QPushButton(
            "FULL SCREEN  [F11]"
        )
        self.system_fullscreen_button.setToolTip(
            "Toggle application full screen. Press Esc to exit."
        )
        self.system_fullscreen_button.clicked.connect(
            self.toggle_full_screen
        )
        controls.addWidget(
            self.system_fullscreen_button
        )

        controls.addStretch()

        self.system_live_status = QLabel(
            "LIVE - waiting for coordinates"
        )
        _set_status_role(self.system_live_status, "info")
        layout.addLayout(
            controls
        )
        live_status_row = QHBoxLayout()
        live_status_row.addStretch(1)
        live_status_row.addWidget(self.system_live_status)
        layout.addLayout(live_status_row)

        object_box = QGroupBox(
            "VISIBLE OBJECTS — TLE / GCRS J2000"
        )
        self.system_object_box = object_box
        object_box_layout = QVBoxLayout(object_box)
        object_layout = QHBoxLayout()
        object_actions_layout = QHBoxLayout()
        object_box_layout.addLayout(object_layout)
        object_layout.setContentsMargins(
            10,
            7,
            10,
            7,
        )
        object_layout.setSpacing(14)

        earth_badge = QLabel(
            "● EARTH (origin)"
        )
        _set_status_role(earth_badge, "info")
        object_layout.addWidget(
            earth_badge
        )

        self.system_object_checks = {}
        for object_id in (
            "moon",
            "iss",
            "hubble",
        ):
            config = ORBITAL_OBJECTS[object_id]
            checkbox = QCheckBox(
                config["short"]
            )
            checkbox.setChecked(
                bool(config["default"])
            )
            if config["kind"] == "satellite":
                checkbox.setToolTip(
                    f"{config['display']} — NORAD {config['norad']}"
                )
            checkbox.toggled.connect(
                lambda checked, key=object_id: (
                    self.handle_system_object_toggle(
                        key,
                        checked,
                    )
                )
            )
            self.system_object_checks[object_id] = checkbox
            object_layout.addWidget(
                checkbox
            )

        object_layout.addStretch()

        self.system_theater_button = QPushButton(
            "EXPAND ORBIT"
        )
        self.system_theater_button.setToolTip(
            "Hide the header and telemetry cards to enlarge the orbit canvas."
        )
        self.system_theater_button.clicked.connect(
            self.toggle_orbital_theater_mode
        )
        object_action_target = object_actions_layout
        object_action_target.addStretch(1)
        object_action_target.addWidget(
            self.system_theater_button
        )

        self.system_precision_badge = QLabel(
            "1:1 AXES  •  REAL DISTANCES"
        )
        _set_status_role(self.system_precision_badge, "ok")
        object_action_target.addWidget(
            self.system_precision_badge
        )
        object_box_layout.addLayout(object_actions_layout)
        layout.addWidget(
            object_box
        )

        self.system_graph = GraphWidget()
        self.system_graph.setMinimumHeight(
            410
        )
        self.system_graph.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.system_graph.mpl_connect(
            "button_press_event",
            self.on_system_view_press,
        )
        self.system_graph.mpl_connect(
            "motion_notify_event",
            self.on_system_view_move,
        )
        self.system_graph.mpl_connect(
            "button_release_event",
            self.on_system_view_release,
        )
        self.system_graph.mpl_connect(
            "scroll_event",
            self.on_system_view_scroll,
        )
        layout.addWidget(
            self.system_graph,
            stretch=1,
        )

        self.system_interaction_hint = QLabel(
            "Click graph: enable wheel zoom  •  Click outside: page scroll  •  "
            "Double-click: deep focus zoom  •  3D: drag orbit camera  •  "
            "Crosshair: focused-frame horizontal / vertical coordinates"
        )
        self.system_interaction_hint.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.system_interaction_hint.setObjectName("metricDetail")
        layout.addWidget(
            self.system_interaction_hint
        )

        coordinates_box = QGroupBox(
            "LIVE TELEMETRY — ABSOLUTE GCRS J2000 [km]"
        )
        self.system_coordinates_box = coordinates_box
        coordinates_box.setMaximumHeight(
            126
        )
        coordinates_layout = QHBoxLayout(
            coordinates_box
        )

        self.system_earth_coordinates = QLabel(
            "EARTH\nX: 0.000\nY: 0.000\nZ: 0.000"
        )
        self.system_satellite_coordinates = QLabel(
            "FOCUS: EARTH\nX: 0.000  •  Y: 0.000  •  Z: 0.000"
        )
        self.system_moon_coordinates = QLabel(
            "VIEW METRICS\nSelected: --  •  Span: --"
        )

        for coordinate_label in (
            self.system_earth_coordinates,
            self.system_satellite_coordinates,
            self.system_moon_coordinates,
        ):
            coordinate_label.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            coordinate_label.setObjectName("telemetryValue")
            coordinates_layout.addWidget(
                coordinate_label,
                stretch=1,
            )

        layout.addWidget(
            coordinates_box
        )

        self.system_view_scroll.setWidget(system_content)
        outer_layout.addWidget(self.system_view_scroll)

        self.system_view_tab_index = self.tabs.addTab(
            page,
            "ORBITAL VIEW"
        )


    def sync_active_profile_orbital_object(self):
        """Expose the active registry entry to Orbital View without hard-coding it."""

        profile = self.active_profile
        config = ORBITAL_OBJECTS["active_profile"]
        config.update(
            {
                "display": profile.display_name,
                "short": profile.display_name.upper(),
                "orbit_source": profile.orbit_source,
                "tle_name": profile.tle_name,
                "norad": profile.norad_id,
            }
        )
        self.system_reference_orbits.pop("active_profile", None)
        self._system_live_cache_key = None
        focus = getattr(self, "system_focus", None)
        if focus is not None:
            index = focus.findData("active_profile")
            if index >= 0:
                focus.setItemText(index, profile.display_name)
                focus.setCurrentIndex(index)
        if hasattr(self, "system_graph"):
            self._system_view_signature = None
            self.safe_update_system_view()


    def selected_system_object_ids(self):

        selected = [
            "earth",
            "active_profile",
        ]
        for object_id, checkbox in self.system_object_checks.items():
            if checkbox.isChecked():
                selected.append(
                    object_id
                )

        return selected


    def handle_system_object_toggle(self, object_id, checked):

        if (
            not checked
            and self.system_focus.currentData() == object_id
        ):
            earth_index = self.system_focus.findData(
                "earth"
            )
            self.system_focus.setCurrentIndex(
                earth_index
            )

        self._system_view_signature = None
        self.system_view_zoom = 1.0
        self.safe_update_system_view()


    def handle_system_focus_changed(self, *args):

        object_id = self.system_focus.currentData()
        checkbox = self.system_object_checks.get(
            object_id
        )
        if checkbox is not None and not checkbox.isChecked():
            checkbox.setChecked(
                True
            )

        self.system_view_zoom = 1.0
        self.safe_update_system_view()


    def handle_system_scale_changed(self, *args):

        self.system_view_zoom = 1.0
        self.safe_update_system_view()


    def adjust_system_view_zoom(self, multiplier):

        self.system_view_zoom = float(
            np.clip(
                self.system_view_zoom * float(multiplier),
                0.0025,
                20.0,
            )
        )
        self.safe_update_system_view()


    def toggle_full_screen(self):

        if self.isFullScreen():
            if self._window_restore_maximized:
                self.showMaximized()
            else:
                self.showNormal()
            self.system_fullscreen_button.setText(
                "FULL SCREEN  [F11]"
            )
        else:
            self._window_restore_maximized = self.isMaximized()
            self.showFullScreen()
            self.system_fullscreen_button.setText(
                "EXIT FULL SCREEN  [F11]"
            )

        QTimer.singleShot(
            0,
            self.safe_update_system_view,
        )


    def position_graph_fullscreen_button(self):

        button = getattr(self, "graph_fullscreen_button", None)
        graph = getattr(self, "graph", None)
        if button is None or graph is None:
            return
        button.setMinimumSize(104, 28)
        button.adjustSize()
        button.move(10, 10)
        button.raise_()


    def refresh_graph_layout_after_view_change(self):

        graph = getattr(self, "graph", None)
        if graph is None:
            return
        try:
            graph.figure.tight_layout(pad=1.0)
        except (RuntimeError, ValueError):
            # A transient zero-sized canvas during a native window-state
            # transition is harmless; the next graph update will lay it out.
            pass
        graph.draw_idle()
        self.position_graph_fullscreen_button()


    def toggle_graph_full_screen(self):
        """Show only the active Perturbation graph and restore it safely."""

        if self._graph_only_mode:
            restore = self._graph_fullscreen_restore or {}
            self._graph_only_mode = False
            for widget, was_visible in restore.get("widgets", ()):
                widget.setVisible(was_visible)
            self.main_layout.setContentsMargins(
                *restore.get("main_margins", (18, 14, 18, 18))
            )
            self.main_layout.setSpacing(restore.get("main_spacing", 14))
            self.graph_page_layout.setContentsMargins(
                *restore.get("graph_margins", (12, 8, 12, 8))
            )
            self.graph_page_layout.setSpacing(
                restore.get("graph_spacing", 5)
            )
            if restore.get("was_fullscreen", False):
                self.showFullScreen()
            elif restore.get("was_maximized", False):
                self.showMaximized()
            else:
                self.showNormal()
            self.graph_fullscreen_button.setText("FULL SCREEN")
            self.graph_fullscreen_button.setToolTip(
                "Show only this graph. Press Esc to return."
            )
            self._graph_fullscreen_restore = None
        else:
            widgets = (
                self.menuBar(),
                self.hero_card,
                self.product_command_bar,
                self.module_tabs.tabBar(),
                self.tabs.tabBar(),
                self.graph_controls_host,
                self.graph_prediction_status,
                self.statusBar(),
            )
            self._graph_fullscreen_restore = {
                "widgets": tuple(
                    (widget, widget.isVisible()) for widget in widgets
                ),
                "main_margins": self.main_layout.getContentsMargins(),
                "main_spacing": self.main_layout.spacing(),
                "graph_margins": self.graph_page_layout.getContentsMargins(),
                "graph_spacing": self.graph_page_layout.spacing(),
                "was_fullscreen": self.isFullScreen(),
                "was_maximized": self.isMaximized(),
            }
            self._graph_only_mode = True
            for widget in widgets:
                widget.hide()
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setSpacing(0)
            self.graph_page_layout.setContentsMargins(0, 0, 0, 0)
            self.graph_page_layout.setSpacing(0)
            self.graph_fullscreen_button.setText("EXIT  [ESC]")
            self.graph_fullscreen_button.setToolTip(
                "Return to the complete application."
            )
            self.showFullScreen()

        QTimer.singleShot(0, self.safe_update_graph)
        QTimer.singleShot(0, self.refresh_graph_layout_after_view_change)


    def toggle_orbital_theater_mode(self):

        self._orbital_theater_mode = not self._orbital_theater_mode
        regular_view = not self._orbital_theater_mode
        self.hero_card.setVisible(
            regular_view
        )
        self.tabs.tabBar().setVisible(
            regular_view
        )
        self.module_tabs.tabBar().setVisible(
            regular_view
        )
        self.system_coordinates_box.setVisible(
            regular_view
        )
        self.system_interaction_hint.setVisible(
            regular_view
        )
        self.system_theater_button.setText(
            "EXIT EXPANDED"
            if self._orbital_theater_mode
            else "EXPAND ORBIT"
        )
        QTimer.singleShot(
            0,
            self.safe_update_system_view,
        )


    def keyPressEvent(self, event):

        if event.key() == Qt.Key.Key_Escape:
            if self._graph_only_mode:
                self.toggle_graph_full_screen()
                event.accept()
                return
            if self._orbital_theater_mode:
                self.toggle_orbital_theater_mode()
                event.accept()
                return
            if self.isFullScreen():
                self.toggle_full_screen()
                event.accept()
                return

        super().keyPressEvent(
            event
        )


    # ========================================================
    # SYSTEM / VALIDATION PAGE
    # ========================================================

    def create_integrity_page(self):

        page = QWidget()
        self.integrity_page = page
        page_layout = QVBoxLayout(
            page
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )
        page_layout.addWidget(
            scroll
        )

        content = QWidget()
        layout = QVBoxLayout(
            content
        )
        layout.setSpacing(
            14
        )

        source_box = QGroupBox(
            "DATA SOURCE AND REFERENCE FRAMES"
        )
        source_layout = QVBoxLayout(
            source_box
        )

        self.tle_integrity_status = QLabel(
            "Loading local TLE metadata..."
        )
        self.tle_integrity_status.setWordWrap(
            True
        )
        source_layout.addWidget(
            self.tle_integrity_status
        )

        frame_text = QLabel(
            "Satellite: Skyfield/SGP4 GCRS (Earth-centred inertial, "
            "J2000-aligned)\n"
            "Moon: SPICE DE440, Earth-centred J2000, geometric (NONE)\n"
            "Numerical propagator: Earth-centred J2000, km / s"
        )
        frame_text.setWordWrap(
            True
        )
        frame_text.setObjectName("metricDetail")
        source_layout.addWidget(
            frame_text
        )

        source_buttons = QHBoxLayout()
        self.refresh_tle_status_button = QPushButton(
            "REFRESH STATUS"
        )
        self.refresh_tle_status_button.clicked.connect(
            self.refresh_integrity_status
        )
        source_buttons.addWidget(
            self.refresh_tle_status_button
        )

        self.update_tle_button = QPushButton(
            "UPDATE TLE FROM CELESTRAK"
        )
        self.update_tle_button.setObjectName("primaryAction")
        self.update_tle_button.clicked.connect(
            self.start_tle_update
        )
        source_buttons.addWidget(
            self.update_tle_button
        )
        source_buttons.addStretch()
        source_layout.addLayout(
            source_buttons
        )
        layout.addWidget(
            source_box
        )

        time_box = QGroupBox(
            "REPRODUCIBLE TIME MODE"
        )
        time_layout = QHBoxLayout(
            time_box
        )
        time_layout.addWidget(
            QLabel("Mode:")
        )
        self.analysis_time_mode = QComboBox()
        self.analysis_time_mode.addItems(
            [
                "Live UTC",
                "Fixed Epoch",
            ]
        )
        time_layout.addWidget(
            self.analysis_time_mode
        )
        time_layout.addWidget(
            QLabel("Epoch:")
        )
        self.analysis_fixed_epoch_input = QLineEdit(
            datetime.now(
                timezone.utc
            ).isoformat(
                timespec="seconds"
            )
        )
        time_layout.addWidget(
            self.analysis_fixed_epoch_input,
            stretch=1,
        )
        self.analysis_epoch_picker_button = QPushButton("SELECT DATE / TIME")
        self.analysis_epoch_picker_button.setObjectName("ghostAction")
        self.analysis_epoch_picker_button.clicked.connect(
            self.open_analysis_epoch_picker
        )
        time_layout.addWidget(self.analysis_epoch_picker_button)
        apply_time_button = QPushButton(
            "APPLY TIME MODE"
        )
        apply_time_button.clicked.connect(
            self.apply_analysis_time_mode
        )
        time_layout.addWidget(
            apply_time_button
        )
        self.analysis_time_status = QLabel(
            "LIVE"
        )
        _set_status_role(self.analysis_time_status, "info")
        time_layout.addWidget(
            self.analysis_time_status
        )
        layout.addWidget(
            time_box
        )

        eop_box = QGroupBox(
            "EARTH ORIENTATION PARAMETERS — IERS"
        )
        eop_layout = QVBoxLayout(eop_box)
        self.eop_enabled_checkbox = QCheckBox(
            "Use bundled IERS EOP (UT1−UTC + polar motion xp/yp)"
        )
        self.eop_enabled_checkbox.setChecked(False)
        self.eop_enabled_checkbox.setToolTip(
            "Applies the bundled finals2000A series to J2000↔ITRS, "
            "EGM96 Earth harmonics, GEO longitude and WGS-84 products."
        )
        self.eop_enabled_checkbox.toggled.connect(
            self.apply_eop_setting
        )
        self.eop_enabled_checkbox.blockSignals(True)
        self.eop_enabled_checkbox.setChecked(
            self.application_config["eop_enabled"]
        )
        self.eop_enabled_checkbox.blockSignals(False)
        eop_layout.addWidget(self.eop_enabled_checkbox)
        self.eop_status_label = QLabel()
        self.eop_status_label.setWordWrap(True)
        eop_layout.addWidget(self.eop_status_label)
        layout.addWidget(eop_box)
        try:
            set_eop_enabled(self.eop_enabled_checkbox.isChecked())
        except EarthOrientationError:
            self.eop_enabled_checkbox.blockSignals(True)
            self.eop_enabled_checkbox.setChecked(False)
            self.eop_enabled_checkbox.blockSignals(False)
            set_eop_enabled(False)
        self.refresh_eop_status_label()

        settings_box = QGroupBox(
            "NUMERICAL SETTINGS"
        )
        settings_layout = QGridLayout(
            settings_box
        )

        self.integrator_rtol = QLineEdit(
            self.application_config["integrator_rtol"]
        )
        self.integrator_atol = QLineEdit(
            self.application_config["integrator_atol"]
        )
        self.integrator_max_step = QSpinBox()
        self.integrator_max_step.setRange(
            1,
            3600,
        )
        self.integrator_max_step.setValue(
            self.application_config["integrator_max_step"]
        )
        self.validation_minutes = QSpinBox()
        self.validation_minutes.setRange(
            1,
            1440,
        )
        self.validation_minutes.setValue(
            self.application_config["validation_minutes"]
        )

        settings_layout.addWidget(
            QLabel("Relative tolerance:"),
            0,
            0,
        )
        settings_layout.addWidget(
            self.integrator_rtol,
            0,
            1,
        )
        settings_layout.addWidget(
            QLabel("Absolute tolerance:"),
            0,
            2,
        )
        settings_layout.addWidget(
            self.integrator_atol,
            0,
            3,
        )
        settings_layout.addWidget(
            QLabel("Maximum step [s]:"),
            1,
            0,
        )
        settings_layout.addWidget(
            self.integrator_max_step,
            1,
            1,
        )
        settings_layout.addWidget(
            QLabel("Validation horizon [min]:"),
            1,
            2,
        )
        settings_layout.addWidget(
            self.validation_minutes,
            1,
            3,
        )
        layout.addWidget(
            settings_box
        )

        action_box = QGroupBox(
            "VALIDATION, ERROR BUDGET, AND LOGGING"
        )
        action_layout = QVBoxLayout(
            action_box
        )
        action_buttons = QHBoxLayout()

        run_validation_button = QPushButton(
            "RUN VALIDATION + ERROR BUDGET"
        )
        run_validation_button.setObjectName("primaryAction")
        run_validation_button.clicked.connect(
            self.run_integrity_validation
        )
        action_buttons.addWidget(
            run_validation_button
        )

        self.start_log_button = QPushButton(
            "START LIVE CSV/JSON LOG"
        )
        self.start_log_button.clicked.connect(
            self.start_live_logging
        )
        action_buttons.addWidget(
            self.start_log_button
        )

        self.stop_log_button = QPushButton(
            "STOP LOGGING"
        )
        self.stop_log_button.setEnabled(
            False
        )
        self.stop_log_button.clicked.connect(
            self.stop_live_logging
        )
        action_buttons.addWidget(
            self.stop_log_button
        )
        action_buttons.addStretch()
        action_layout.addLayout(
            action_buttons
        )

        self.logging_status = QLabel(
            "Logging is stopped."
        )
        self.logging_status.setWordWrap(
            True
        )
        _set_status_role(self.logging_status, "muted")
        action_layout.addWidget(
            self.logging_status
        )

        self.integrity_output = QTextEdit()
        self.integrity_output.setReadOnly(
            True
        )
        self.integrity_output.setMinimumHeight(
            330
        )
        self.integrity_output.setPlainText(
            "Run validation to compare numerical propagation with the "
            "local TLE/SGP4 reference and estimate model sensitivities."
        )
        action_layout.addWidget(
            self.integrity_output
        )
        layout.addWidget(
            action_box
        )

        layout.addStretch()
        scroll.setWidget(
            content
        )

        self.integrity_tab_index = self.tabs.addTab(
            page,
            "SETTINGS"
        )

        self.refresh_integrity_status()


    def get_numerical_settings(self):

        rtol = float(
            self.integrator_rtol.text()
        )
        atol = float(
            self.integrator_atol.text()
        )
        max_step = float(
            self.integrator_max_step.value()
        )

        if rtol <= 0.0 or atol <= 0.0:
            raise ValueError(
                "Integrator tolerances must be positive."
            )

        return {
            "rtol": rtol,
            "atol": atol,
            "max_step": max_step,
        }


    def model_provenance_rows(self):
        """Return every model choice with its value and where it comes from.

        Read from the imported modules rather than from a written-down copy, so
        a change in ``constants.py`` cannot leave this panel stating something
        the model no longer does.
        """

        import constants
        import eclipse_prediction

        geometry = self.eclipse_geometry_options()
        rows = [
            ("GRAVITY", "Earth GM", f"{constants.MU_EARTH} km³/s²",
             "EGM96 / WGS84(G873), NGA f477.f"),
            ("GRAVITY", "Earth equatorial radius",
             f"{constants.R_EARTH} km", "EGM96 / WGS84(G873)"),
            ("GRAVITY", "Spherical-harmonic truncation",
             f"degree/order {constants.EARTH_GRAVITY_DEGREE}",
             "Chosen on a 30-day GEO regression against the supplied reference"),
            ("GRAVITY", "Moon GM", f"{constants.MU_MOON} km³/s²", "JPL DE440"),
            ("GRAVITY", "Sun GM", f"{constants.MU_SUN} km³/s²",
             "JPL DE440 compatible"),
            ("SHAPE", "Earth polar radius",
             f"{constants.EARTH_POLAR_RADIUS_KM} km", "WGS-84"),
            ("SHAPE", "Moon radius", f"{constants.R_MOON} km",
             "IAU mean radius, used for the apparent lunar disc"),
            ("SHAPE", "Sun radius", f"{constants.SUN_MEAN_RADIUS_KM} km",
             "IAU nominal solar radius"),
            ("EPHEMERIS", "Planetary ephemeris", "DE440",
             "kernels/de440s.bsp"),
            ("EPHEMERIS", "Leap seconds", "naif0012.tls",
             "kernels/naif0012.tls"),
            ("EPHEMERIS", "Aberration, gravity",
             "geometric", "Correct for force models"),
            ("EPHEMERIS", "Aberration, occultation",
             "light-time" if geometry.light_time_moon else "geometric",
             "Switchable on the Eclipse page; off reproduces the references"),
            ("ECLIPSE", "Earth shadow silhouette",
             "oblate (WGS-84)" if geometry.oblate_earth_shadow
             else "sphere at equatorial radius",
             "Switchable on the Eclipse page; sphere reproduces the references"),
            ("ECLIPSE", "Contact root tolerance",
             f"{eclipse_prediction.ECLIPSE_CONTACT_TOLERANCE_SECONDS * 1000:.0f} ms",
             "Bisection on the limb margin after cubic Hermite interpolation"),
            ("ECLIPSE", "Grazing threshold",
             f"{eclipse_prediction.GRAZING_CONTACT_SECONDS_PER_MILLIDEGREE} s/mdeg",
             "Public numerical contact-conditioning threshold"),
            ("INTEGRATION", "Method", "DOP853 adaptive",
             f"rtol {constants.DEFAULT_RTOL}, atol {constants.DEFAULT_ATOL}"),
            ("SPACECRAFT", "Mass",
             f"{constants.DEMO_SPACECRAFT_MASS_KG} kg", "SYNTHETIC/DEMO box-wing model"),
            ("SPACECRAFT", "Solar array area",
             f"{constants.DEMO_SPACECRAFT_TOTAL_SOLAR_ARRAY_AREA_M2} m²",
             "Synthetic public geometry, TrueSun tracking"),
            ("CALIBRATION", "Empirical calibration", "disabled",
             "reference_comparison raises if it is requested"),
            ("CALIBRATION", "Solar pressure coefficient",
             "1.0 when no external calibration is loaded",
             "Public mode contains no operator calibration"),
        ]

        not_modelled = (
            "Earth-orientation / polar-motion table",
            "Atmospheric refraction in the shadow boundary",
            "Antenna reflectors in the box-wing area",
            "Attitude quaternions; the body is assumed Earth-pointing",
            "Station-keeping manoeuvres and mass change over time",
        )
        rows.extend(
            ("NOT MODELLED", item, "—", "Stated limitation")
            for item in not_modelled
        )
        return rows

    def create_model_provenance_box(self):
        """Build the panel that states every constant and its source."""

        box = QGroupBox("MODEL PROVENANCE — CONSTANTS, SOURCES, LIMITATIONS")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(14, 24, 14, 14)

        caption = QLabel(
            "Every number the model uses, where it comes from, and what is "
            "deliberately left out. Values are read from the running code, not "
            "copied, so this panel cannot fall behind the model."
        )
        caption.setWordWrap(True)
        caption.setObjectName("metricDetail")
        box_layout.addWidget(caption)

        rows = self.model_provenance_rows()
        table = QTableWidget(len(rows), 4)
        table.setHorizontalHeaderLabels(
            ("Group", "Quantity", "Value", "Source")
        )
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        for row_index, (group, quantity, value, source) in enumerate(rows):
            for column, text in enumerate((group, quantity, value, source)):
                item = QTableWidgetItem(str(text))
                if column == 0:
                    item.setForeground(
                        QColor(
                            theme.STATUS_WARNING
                            if group == "NOT MODELLED"
                            else theme.ACCENT_INFO
                        )
                    )
                table.setItem(row_index, column, item)
        header = table.horizontalHeader()
        for column in (0, 1, 2):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.setMinimumHeight(300)
        self.model_provenance_table = table
        box_layout.addWidget(table)
        return box

    def refresh_model_provenance(self, _checked=None):
        """Restate the geometry rows after a switch changes."""

        table = getattr(self, "model_provenance_table", None)
        if table is None:
            return
        for row_index, row in enumerate(self.model_provenance_rows()):
            if row_index >= table.rowCount():
                break
            for column, text in enumerate(row):
                item = table.item(row_index, column)
                if item is not None:
                    item.setText(str(text))


    def refresh_eop_status_label(self, message=None):

        status = get_eop_status()
        if not status.get("available", False):
            text = "EOP UNAVAILABLE\n" + status.get("error", "Unknown error")
            color = "#EF4444"
        else:
            mode = "ACTIVE" if status["enabled"] else "OFF"
            text = (
                f"EOP {mode} · {status['components']}\n"
                f"Coverage: {status['coverage_start_utc'][:10]} → "
                f"{status['coverage_end_utc'][:10]} UTC · "
                f"{status['rows']:,} daily rows\n"
                "Bundled file: finals2000A.all"
            )
            color = theme.STATUS_OK if status["enabled"] else theme.TEXT_MUTED
            if status["enabled"]:
                try:
                    values = eop_values_at(self.get_analysis_utc())
                except (EarthOrientationError, TypeError, ValueError) as error:
                    text += f"\nCurrent epoch warning: {error}"
                    color = theme.STATUS_WARNING
                else:
                    text += (
                        "\nCurrent: "
                        f"DUT1={values['dut1_seconds']:+.7f} s · "
                        f"xp={values['xp_arcseconds']:+.6f}″ · "
                        f"yp={values['yp_arcseconds']:+.6f}″"
                    )
        if message:
            text += "\n" + str(message)
        self.eop_status_label.setText(text)
        role = (
            "warning" if color == theme.STATUS_WARNING
            else "ok" if color == theme.STATUS_OK
            else "muted"
        )
        _set_status_role(self.eop_status_label, role)


    def apply_eop_setting(self, enabled):

        active_threads = (
            self.propagation_thread,
            self.graph_prediction_thread,
            self.eclipse_thread,
            self.reference_comparison_thread,
        )
        if any(
            thread is not None and thread.isRunning()
            for thread in active_threads
        ):
            self.eop_enabled_checkbox.blockSignals(True)
            self.eop_enabled_checkbox.setChecked(is_eop_enabled())
            self.eop_enabled_checkbox.blockSignals(False)
            self.refresh_eop_status_label(
                "A calculation is running; change EOP after it finishes."
            )
            return

        try:
            set_eop_enabled(enabled)
        except EarthOrientationError as error:
            self.eop_enabled_checkbox.blockSignals(True)
            self.eop_enabled_checkbox.setChecked(False)
            self.eop_enabled_checkbox.blockSignals(False)
            set_eop_enabled(False)
            self.refresh_eop_status_label(f"Enable failed: {error}")
            return

        self.reference_validation_settings = None
        self.latest_reference_comparison = None
        self.latest_reference_scenario = None
        self.reference_scenario_results = {True: None, False: None}
        self.system_live_positions.clear()
        self.system_live_altitudes.clear()
        self._system_live_cache_key = None
        self._system_view_signature = None
        self._graph_signature = None
        self.refresh_eop_status_label()
        self.statusBar().showMessage(
            "IERS EOP enabled" if enabled else "IERS EOP disabled",
            8000,
        )
        self.update_data()


    def refresh_integrity_status(self, *args):

        try:
            metadata = get_tle_metadata(
                TARGET_SATELLITE_NAME
            )
            kernel_status = get_kernel_status()
            age_days = metadata["age_days"]
            state = (
                "STALE"
                if metadata["is_stale"]
                else "CURRENT"
            )
            color = (
                theme.STATUS_WARNING
                if metadata["is_stale"]
                else theme.STATUS_OK
            )
            self.tle_integrity_status.setText(
                f"TLE STATUS: {state}\n"
                f"Satellite: {metadata['satellite_name']}\n"
                f"Epoch: {metadata['tle_epoch'].isoformat()}\n"
                f"Age: {age_days:.3f} days\n"
                f"Local file: {metadata['file_path']}\n"
                f"Source: {metadata['source']}\n"
                "SPICE kernels: "
                + ", ".join(
                    f"{name}={'OK' if info['exists'] else 'MISSING'}"
                    for name, info in kernel_status.items()
                )
            )
            role = "warning" if metadata["is_stale"] else "ok"
            _set_status_role(self.tle_integrity_status, role)
            self.tle_status.setText(
                f"TLE: {state} | age {age_days:.2f} d"
            )
            _set_status_role(self.tle_status, role)
        except Exception as error:
            if isinstance(error, FileNotFoundError):
                self.tle_integrity_status.setText(
                    "TLE STATUS: OPTIONAL CACHE NOT LOADED\n"
                    "Public synthetic profiles remain fully available. "
                    "Use UPDATE TLE only when a current public TLE comparison is needed."
                )
                _set_status_role(self.tle_integrity_status, "warning")
                self.tle_status.setText("TLE: NOT LOADED")
                _set_status_role(self.tle_status, "warning")
            else:
                self.tle_integrity_status.setText(
                    f"TLE STATUS ERROR: {type(error).__name__}"
                )
                _set_status_role(self.tle_integrity_status, "error")
                self.tle_status.setText("TLE: ERROR")
                _set_status_role(self.tle_status, "error")


    def _set_tle_update_buttons_enabled(self, enabled):

        for name in ("update_tle_button", "live_tle_update_button"):
            button = getattr(self, name, None)
            if button is not None:
                button.setEnabled(enabled)


    def start_tle_update(self):

        if (
            self.tle_update_thread is not None
            and self.tle_update_thread.isRunning()
        ):
            return

        self._set_tle_update_buttons_enabled(False)
        self.tle_integrity_status.setText(
            "Downloading and validating TLE catalogue..."
        )
        _set_status_role(self.tle_integrity_status, "info")
        self.tle_status.setText("TLE: UPDATING...")
        _set_status_role(self.tle_status, "info")

        self.tle_update_thread = QThread(
            self
        )
        self.tle_update_worker = TLEUpdateWorker()
        self.tle_update_worker.moveToThread(
            self.tle_update_thread
        )
        self.tle_update_thread.started.connect(
            self.tle_update_worker.run
        )
        self.tle_update_worker.completed.connect(
            self.finish_tle_update
        )
        self.tle_update_worker.failed.connect(
            self.fail_tle_update
        )
        self.tle_update_worker.completed.connect(
            self.tle_update_thread.quit
        )
        self.tle_update_worker.failed.connect(
            self.tle_update_thread.quit
        )
        self.tle_update_thread.finished.connect(
            self.tle_update_worker.deleteLater
        )
        self.tle_update_thread.finished.connect(
            self.tle_update_thread.deleteLater
        )
        self.tle_update_thread.finished.connect(
            self.cleanup_tle_update
        )
        self.tle_update_thread.start()


    def finish_tle_update(self, metadata):

        self.system_reference_orbits.clear()
        self.system_live_positions.clear()
        self.system_live_altitudes.clear()
        self._system_live_cache_key = None
        self._system_view_signature = None
        self._set_tle_update_buttons_enabled(True)
        self.refresh_integrity_status()
        self.statusBar().showMessage(
            "Local TLE catalogue updated and validated.",
            8000,
        )
        self.update_data()


    def fail_tle_update(self, message):

        self._set_tle_update_buttons_enabled(True)
        self.tle_integrity_status.setText(
            "TLE UPDATE FAILED - local fallback remains active.\n"
            + message
        )
        _set_status_role(self.tle_integrity_status, "error")
        self.tle_status.setText("TLE: UPDATE FAILED")
        _set_status_role(self.tle_status, "error")
        self.statusBar().showMessage(
            "TLE UPDATE FAILED - local fallback remains active.",
            8000,
        )


    def cleanup_tle_update(self):

        self.tle_update_worker = None
        self.tle_update_thread = None


    def apply_analysis_time_mode(self):

        try:
            if self.analysis_time_mode.currentText() == "Fixed Epoch":
                self.analysis_fixed_epoch = self.parse_propagation_epoch(
                    self.analysis_fixed_epoch_input.text()
                )
                self.analysis_time_status.setText(
                    "FIXED"
                )
                _set_status_role(self.analysis_time_status, "warning")
            else:
                self.analysis_fixed_epoch = None
                self.analysis_time_status.setText(
                    "LIVE"
                )
                _set_status_role(self.analysis_time_status, "info")

            histories = [self.history_time]
            histories.extend(
                history
                for source_histories in self.force_histories.values()
                for history in source_histories.values()
            )
            histories.extend(
                (
                    self.satellite_position_history,
                    self.moon_position_history,
                )
            )
            for history in histories:
                history.clear()

            self.system_reference_orbits.clear()
            self.system_live_positions.clear()
            self.system_live_altitudes.clear()
            self._system_live_cache_key = None
            self._system_view_signature = None
            self._graph_signature = None
            self.update_data()
        except Exception as error:
            self.analysis_time_status.setText(
                f"TIME ERROR: {error}"
            )
            _set_status_role(self.analysis_time_status, "error")


    def get_analysis_utc(self):

        if self.analysis_fixed_epoch is not None:
            return self.analysis_fixed_epoch

        return get_current_utc()


    def run_integrity_validation(self):

        self.integrity_output.setPlainText(
            "Running reference comparison and model sensitivity tests..."
        )
        QApplication.processEvents()

        try:
            settings = self.get_numerical_settings()
            profile = self.active_profile
            if profile.orbit_source == "tle":
                metadata = get_tle_metadata(
                    profile.tle_name,
                    norad_id=profile.norad_id,
                )
            else:
                metadata = {
                    "satellite_name": profile.display_name,
                    "tle_epoch": profile.parsed_epoch,
                    "age_days": 0.0,
                    "file_path": profile.source_description or "Profile state",
                }
            kernel_status = get_kernel_status()
            epoch = self.get_analysis_utc()
            duration_seconds = float(
                self.validation_minutes.value()
                * 60
            )
            final_epoch = epoch + timedelta(
                seconds=duration_seconds
            )

            initial_state = get_tle_initial_state(
                epoch
            )
            direct_position = get_satellite_position(
                TARGET_SATELLITE_NAME,
                epoch,
            )
            initial_frame_difference = float(
                np.linalg.norm(
                    initial_state[:3]
                    - direct_position
                )
            )
            (
                integrity_srp_coefficient,
                integrity_srp_mode,
            ) = resolved_solar_pressure_coefficient(epoch)
            integrity_srp_active = True
            integrity_srp_status = (
                f"ACTIVE / CP {integrity_srp_coefficient:.7f} / "
                f"{integrity_srp_mode}"
            )

            baseline = propagate_state(
                initial_state=initial_state,
                initial_epoch=epoch,
                duration_seconds=duration_seconds,
                include_j2=True,
                include_moon=True,
                include_sun=True,
                include_srp=integrity_srp_active,
                srp_coefficient=integrity_srp_coefficient,
                **settings,
            )
            reference_state = get_tle_initial_state(
                final_epoch
            )

            relaxed_settings = {
                "rtol": settings["rtol"] * 100.0,
                "atol": settings["atol"] * 100.0,
                "max_step": min(
                    settings["max_step"] * 2.0,
                    3600.0,
                ),
            }
            relaxed = propagate_state(
                initial_state=initial_state,
                initial_epoch=epoch,
                duration_seconds=duration_seconds,
                include_j2=True,
                include_moon=True,
                include_sun=True,
                include_srp=integrity_srp_active,
                srp_coefficient=integrity_srp_coefficient,
                **relaxed_settings,
            )
            without_moon = propagate_state(
                initial_state=initial_state,
                initial_epoch=epoch,
                duration_seconds=duration_seconds,
                include_j2=True,
                include_moon=False,
                include_sun=True,
                include_srp=integrity_srp_active,
                srp_coefficient=integrity_srp_coefficient,
                **settings,
            )
            without_sun = propagate_state(
                initial_state=initial_state,
                initial_epoch=epoch,
                duration_seconds=duration_seconds,
                include_j2=True,
                include_moon=True,
                include_sun=False,
                include_srp=integrity_srp_active,
                srp_coefficient=integrity_srp_coefficient,
                **settings,
            )
            without_earth_harmonics = propagate_state(
                initial_state=initial_state,
                initial_epoch=epoch,
                duration_seconds=duration_seconds,
                include_j2=False,
                include_moon=True,
                include_sun=True,
                include_srp=integrity_srp_active,
                srp_coefficient=integrity_srp_coefficient,
                **settings,
            )
            without_srp = (
                propagate_state(
                    initial_state=initial_state,
                    initial_epoch=epoch,
                    duration_seconds=duration_seconds,
                    include_j2=True,
                    include_moon=True,
                    include_sun=True,
                    include_srp=False,
                    **settings,
                )
                if integrity_srp_active
                else None
            )

            position_difference = baseline[:3] - reference_state[:3]
            velocity_difference = baseline[3:] - reference_state[3:]
            numerical_sensitivity = float(
                np.linalg.norm(
                    baseline[:3] - relaxed[:3]
                )
            )
            moon_sensitivity = float(
                np.linalg.norm(
                    baseline[:3] - without_moon[:3]
                )
            )
            sun_sensitivity = float(
                np.linalg.norm(
                    baseline[:3] - without_sun[:3]
                )
            )
            earth_harmonic_sensitivity = float(
                np.linalg.norm(
                    baseline[:3] - without_earth_harmonics[:3]
                )
            )
            srp_sensitivity = (
                float(np.linalg.norm(baseline[:3] - without_srp[:3]))
                if without_srp is not None
                else None
            )
            reference_position_error = float(
                np.linalg.norm(
                    position_difference
                )
            )
            reference_velocity_error = float(
                np.linalg.norm(
                    velocity_difference
                )
            )
            tle_offset_days = abs(
                (
                    epoch - metadata["tle_epoch"]
                ).total_seconds()
                / 86400.0
            )

            report_lines = [
                "SYSTEM VALIDATION REPORT",
                "=" * 72,
                f"Application version     : {APP_VERSION}",
                f"Analysis epoch          : {epoch.isoformat()}",
                f"Validation horizon      : {duration_seconds / 60.0:.1f} min",
                f"TLE epoch               : {metadata['tle_epoch'].isoformat()}",
                f"Epoch distance from TLE : {tle_offset_days:.3f} days",
                f"TLE freshness           : {'STALE' if metadata['is_stale'] else 'CURRENT'}",
                "SPICE kernels            : "
                + ", ".join(
                    f"{name}={'OK' if info['exists'] else 'MISSING'}"
                    for name, info in kernel_status.items()
                ),
                "",
                "REFERENCE-FRAME CONSISTENCY",
                "-" * 72,
                "Satellite source : Skyfield/SGP4 GCRS, J2000-aligned",
                "Moon source      : SPICE DE440 J2000 geometric position",
                "Sun source       : SPICE DE440 J2000 geometric position",
                "SRP model        : physical box-wing / TrueSun arrays",
                f"SRP status       : {integrity_srp_status}",
                "Earth orientation: "
                + (
                    "IERS EOP ON — DUT1 + xp/yp"
                    if is_eop_enabled()
                    else "EOP OFF — bundled deterministic baseline"
                ),
                "Propagator frame : Earth-centred J2000",
                f"Initial position cross-check : {initial_frame_difference:.12e} km",
                f"Frame check status            : {'PASS' if initial_frame_difference < 1.0e-6 else 'CHECK'}",
                "",
                "NUMERICAL PROPAGATION VS TLE/SGP4",
                "-" * 72,
                f"dX = {position_difference[0]:.6f} km",
                f"dY = {position_difference[1]:.6f} km",
                f"dZ = {position_difference[2]:.6f} km",
                f"Position difference = {reference_position_error:.6f} km",
                f"Velocity difference = {reference_velocity_error:.9f} km/s",
                "",
                "MODEL SENSITIVITY / ERROR-BUDGET INDICATORS",
                "-" * 72,
                f"Integrator sensitivity : {numerical_sensitivity:.9e} km",
                f"Moon model contribution: {moon_sensitivity:.9e} km",
                f"Sun model contribution : {sun_sensitivity:.9e} km",
                (
                    f"SRP model contribution : {srp_sensitivity:.9e} km"
                    if srp_sensitivity is not None
                    else "SRP model contribution : N/A"
                ),
                f"EGM96 4×4 contribution : {earth_harmonic_sensitivity:.9e} km",
                f"RTOL / ATOL             : {settings['rtol']:.3e} / {settings['atol']:.3e}",
                f"Maximum step            : {settings['max_step']:.3f} s",
                "",
                "INTERPRETATION",
                "-" * 72,
                "The TLE/SGP4 difference is a reference-model difference, not a",
                "direct measurement error. Moon/Sun/SRP/EGM values are sensitivity deltas.",
                "Public-mode SRP uses the explicit neutral CP=1 coefficient.",
                "No spacecraft-specific calibration is bundled.",
                "Earth harmonics above degree 4 are omitted.",
            ]

            report = "\n".join(
                report_lines
            )
            self.integrity_last_report = report
            self.integrity_output.setPlainText(
                report
            )
        except Exception as error:
            self.integrity_output.setPlainText(
                "VALIDATION ERROR\n\n"
                f"{type(error).__name__}: {error}"
            )


    def start_live_logging(self):

        if self.live_log_file is not None:
            return
        if getattr(self, "admin_session", None) is not None and self.admin_session.unlocked:
            self.logging_status.setText(
                "Logging is disabled while ADMIN ACCESS is unlocked. "
                "Log out to create public-mode telemetry logs."
            )
            _set_status_role(self.logging_status, "warning")
            return

        try:
            profile = self.active_profile
            settings = self.get_numerical_settings()
            metadata = (
                get_tle_metadata(TARGET_SATELLITE_NAME)
                if profile.orbit_source == "tle"
                else None
            )
            logs_directory = os.path.join(
                APPLICATION_DATA_DIR,
                "logs",
            )
            os.makedirs(
                logs_directory,
                exist_ok=True,
            )
            file_stamp = datetime.now(
                timezone.utc
            ).strftime(
                "%Y%m%d_%H%M%S"
            )
            csv_path = os.path.join(
                logs_directory,
                f"live_{file_stamp}.csv",
            )
            json_path = os.path.join(
                logs_directory,
                f"live_{file_stamp}.json",
            )

            metadata_document = {
                "created_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "application": "Orbital Perturbation Analyzer",
                "application_version": APP_VERSION,
                "satellite": profile.display_name,
                "orbit_source": profile.orbit_source,
                "state_epoch": (
                    metadata["tle_epoch"].isoformat()
                    if metadata is not None
                    else profile.parsed_epoch.isoformat()
                ),
                "tle_age_days": (
                    metadata["age_days"] if metadata is not None else None
                ),
                "source_kind": "public_tle_cache" if metadata is not None else "profile_state",
                "satellite_frame": "Earth-centred J2000 / GCRS-aligned",
                "moon_frame": "SPICE DE440 J2000 geometric",
                "sun_frame": "SPICE DE440 J2000 geometric",
                "force_modules": {
                    "moon_third_body": True,
                    "sun_third_body": True,
                    "solar_radiation_pressure": (
                        "public_neutral_coefficient_cp_1"
                    ),
                },
                "propagator_frame": "Earth-centred J2000",
                "earth_orientation": {
                    key: value
                    for key, value in get_eop_status().items()
                    if key != "file"
                },
                "time_mode": self.analysis_time_mode.currentText(),
                "fixed_epoch": (
                    self.analysis_fixed_epoch.isoformat()
                    if self.analysis_fixed_epoch is not None
                    else None
                ),
                "integrator": settings,
                "spice_kernels": {
                    name: {
                        key: value
                        for key, value in status.items()
                        if key != "path"
                    }
                    for name, status in get_kernel_status().items()
                },
            }
            with open(
                json_path,
                "w",
                encoding="utf-8",
            ) as metadata_file:
                json.dump(
                    metadata_document,
                    metadata_file,
                    indent=2,
                )

            self.live_log_file = open(
                csv_path,
                "w",
                newline="",
                encoding="utf-8",
                buffering=1,
            )
            self.live_log_writer = csv.writer(
                self.live_log_file
            )
            self.live_log_writer.writerow(
                [
                    "utc",
                    "sat_x_km",
                    "sat_y_km",
                    "sat_z_km",
                    "moon_x_km",
                    "moon_y_km",
                    "moon_z_km",
                    "sun_x_km",
                    "sun_y_km",
                    "sun_z_km",
                    "moon_ax_km_s2",
                    "moon_ay_km_s2",
                    "moon_az_km_s2",
                    "sun_ax_km_s2",
                    "sun_ay_km_s2",
                    "sun_az_km_s2",
                    "srp_ax_km_s2",
                    "srp_ay_km_s2",
                    "srp_az_km_s2",
                    "combined_ax_km_s2",
                    "combined_ay_km_s2",
                    "combined_az_km_s2",
                    "combined_magnitude_km_s2",
                    "srp_coefficient",
                    "srp_mode",
                    "sunlight_fraction",
                ]
            )
            self.live_log_path = csv_path
            self._last_logged_utc = None
            self.start_log_button.setEnabled(
                False
            )
            self.stop_log_button.setEnabled(
                True
            )
            self.logging_status.setText(
                f"Logging active:\n{csv_path}\nMetadata: {json_path}"
            )
            _set_status_role(self.logging_status, "ok")
        except Exception as error:
            self.logging_status.setText(
                f"Logging error: {error}"
            )
            _set_status_role(self.logging_status, "error")


    def log_live_sample(
        self,
        utc,
        r_sat,
        r_moon,
        r_sun,
        a_moon,
        a_sun,
        a_srp,
        a_total,
        magnitude,
        srp_coefficient,
        srp_illumination,
        srp_mode,
    ):
        if self.live_log_writer is None:
            return

        utc_text = format_csv_utc(utc)
        if utc_text == getattr(
            self,
            "_last_logged_utc",
            None,
        ):
            return

        self.live_log_writer.writerow(
            [
                utc_text,
                *[float(value) for value in r_sat],
                *[float(value) for value in r_moon],
                *[float(value) for value in r_sun],
                *[float(value) for value in a_moon],
                *[float(value) for value in a_sun],
                *[float(value) for value in a_srp],
                *[float(value) for value in a_total],
                float(magnitude),
                float(srp_coefficient),
                str(srp_mode),
                float(srp_illumination),
            ]
        )
        self._last_logged_utc = utc_text


    def stop_live_logging(self):

        if self.live_log_file is not None:
            self.live_log_file.close()

        completed_path = self.live_log_path
        self.live_log_file = None
        self.live_log_writer = None
        self.live_log_path = None
        self.start_log_button.setEnabled(
            True
        )
        self.stop_log_button.setEnabled(
            False
        )
        self.logging_status.setText(
            "Logging stopped."
            + (
                f" Last file: {completed_path}"
                if completed_path
                else ""
            )
        )
        _set_status_role(self.logging_status, "muted")


    # ========================================================
    # GRAPH PREDICTION / NAVIGATION
    # ========================================================

    def safe_update_graph(self, *args):

        try:
            self.update_graph()
        except Exception as error:
            # Exceptions raised by a Qt signal handler can terminate the
            # application. Keep graph-only failures contained and visible.
            print(
                "GRAPH UPDATE ERROR:",
                error,
            )

            if hasattr(
                self,
                "graph_prediction_status",
            ):
                self.graph_prediction_status.setText(
                    f"Graph update error: {error}"
                )


    def safe_update_system_view(self, *args):

        try:
            self.update_system_view()
        except Exception as error:
            print(
                "2D SYSTEM VIEW ERROR:",
                error,
            )

            if hasattr(
                self,
                "system_live_status",
            ):
                self.system_live_status.setText(
                    f"VIEW ERROR: {error}"
                )


    def handle_tab_changed(self, index):

        if index == self.graph_tab_index:
            self.safe_update_graph()

        elif index == self.system_view_tab_index:
            self.safe_update_system_view()

        elif index == self.integrity_tab_index:
            self.refresh_integrity_status()


    def handle_module_changed(self, index):
        """Refresh only the active legacy workspace after module changes."""

        if index == self.propagation_module_index:
            self.handle_tab_changed(self.tabs.currentIndex())


    def handle_graph_range_changed(self, *args):

        # A prediction belongs to the range for which it was generated.
        # Clear it when the range changes so stale coverage is not shown.
        self.graph_prediction_epoch = None
        self.graph_prediction_times = None
        self.graph_prediction_values = None
        self.graph_prediction_uncertainty = None
        self.graph_view_offset = 0.0
        self._graph_signature = None

        self.graph_prediction_status.setText(
            "Range changed. Run prediction to estimate past and future."
        )

        self.safe_update_graph()


    def handle_graph_source_changed(self, *args):

        source_boxes = (
            self.graph_force_moon,
            self.graph_force_sun,
            self.graph_force_srp,
            self.graph_force_total,
        )
        if not any(box.isChecked() for box in source_boxes):
            self.graph_force_total.blockSignals(True)
            self.graph_force_total.setChecked(True)
            self.graph_force_total.blockSignals(False)
        self.graph_prediction_epoch = None
        self.graph_prediction_times = None
        self.graph_prediction_values = None
        self.graph_prediction_uncertainty = None
        self.graph_prediction_status.setText(
            "Force selection changed. Run prediction for the selected sources."
        )
        self._graph_signature = None
        self.safe_update_graph()


    def run_graph_prediction(self):

        if (
            self.graph_prediction_thread is not None
            and self.graph_prediction_thread.isRunning()
        ):
            self.graph_prediction_thread.requestInterruption()
            self.predict_graph_button.setEnabled(False)
            self.predict_graph_button.setText("CANCELLING...")
            self.graph_prediction_status.setText(
                "Cancelling perturbation prediction..."
            )
            return

        selected_range = self.time_range.currentText()
        hours = {"1 Hour": 1, "6 Hours": 6, "24 Hours": 24}.get(
            selected_range, 24
        )
        output_step = {1: 30.0, 6: 180.0, 24: 600.0}[hours]
        requested_sources = [
            name
            for name, checkbox in (
                ("Moon", self.graph_force_moon),
                ("Sun β", self.graph_force_sun),
                ("SRP", self.graph_force_srp),
                ("Combined", self.graph_force_total),
            )
            if checkbox.isChecked()
        ]
        propagate_moon = (
            "Moon" in requested_sources or "Combined" in requested_sources
        )
        propagate_sun = (
            "Sun β" in requested_sources or "Combined" in requested_sources
        )
        propagate_srp = (
            "SRP" in requested_sources or "Combined" in requested_sources
        )

        try:
            requested_epoch = self.get_analysis_utc()
            initial_state, epoch = self.active_spacecraft_state(
                requested_epoch
            )
            numerical_settings = self.get_numerical_settings()
            srp_coefficient = None
            srp_propagation_kwargs = {}
            srp_prediction_note = ""
            if propagate_srp:
                if self.active_profile.is_demo_geo_baseline:
                    srp_coefficient, srp_mode = (
                        resolved_solar_pressure_coefficient(epoch)
                    )
                else:
                    srp_propagation_kwargs, srp_coefficient = (
                        self.profile_srp_adapter()
                    )
                    srp_mode = "ACTIVE PROFILE"
                srp_prediction_note = (
                    f" SRP: {srp_mode}, CP {srp_coefficient:.7f}."
                )
        except Exception as error:
            self.graph_prediction_status.setText(
                f"Prediction setup error: {error}"
            )
            self.statusBar().showMessage(
                f"Prediction setup error: {error}", 10000
            )
            return

        parameters = {
            "initial_state": initial_state,
            "epoch": epoch,
            "duration_seconds": float(hours * 3600),
            "output_step": output_step,
            "requested_sources": tuple(requested_sources),
            "propagate_moon": propagate_moon,
            "propagate_sun": propagate_sun,
            "propagate_srp": propagate_srp,
            "srp_coefficient": srp_coefficient,
            "srp_area_m2": srp_propagation_kwargs.get("srp_area_m2"),
            "srp_mass_kg": srp_propagation_kwargs.get("srp_mass_kg"),
            "numerical_settings": numerical_settings,
        }
        self._graph_prediction_context = {
            "hours": hours,
            "requested_sources": tuple(requested_sources),
            "srp_prediction_note": srp_prediction_note,
        }
        self._graph_prediction_timer_was_active = self.timer.isActive()
        self.timer.stop()
        self._set_graph_prediction_running(True)
        self.graph_prediction_status.setText(
            "Calculating perturbation prediction in the background... 0%"
        )

        self.graph_prediction_thread = QThread(self)
        self.graph_prediction_worker = GraphPredictionWorker(parameters)
        self.graph_prediction_worker.moveToThread(
            self.graph_prediction_thread
        )
        self.graph_prediction_thread.started.connect(
            self.graph_prediction_worker.run
        )
        self.graph_prediction_worker.progress.connect(
            self._update_graph_prediction_progress
        )
        self.graph_prediction_worker.completed.connect(
            self.finish_graph_prediction
        )
        self.graph_prediction_worker.failed.connect(
            self.fail_graph_prediction
        )
        self.graph_prediction_worker.cancelled.connect(
            self.cancelled_graph_prediction
        )
        self.graph_prediction_worker.completed.connect(
            self.graph_prediction_thread.quit
        )
        self.graph_prediction_worker.failed.connect(
            self.graph_prediction_thread.quit
        )
        self.graph_prediction_worker.cancelled.connect(
            self.graph_prediction_thread.quit
        )
        self.graph_prediction_thread.finished.connect(
            self.graph_prediction_worker.deleteLater
        )
        self.graph_prediction_thread.finished.connect(
            self.graph_prediction_thread.deleteLater
        )
        self.graph_prediction_thread.finished.connect(
            self.cleanup_graph_prediction
        )
        self.graph_prediction_thread.start()

    def _set_graph_prediction_running(self, running):

        for control in (
            self.time_range,
            self.graph_force_moon,
            self.graph_force_sun,
            self.graph_force_srp,
            self.graph_force_total,
        ):
            control.setEnabled(not running)
        self.predict_graph_button.setEnabled(True)
        self.predict_graph_button.setText(
            "CANCEL PREDICTION" if running else "PREDICT PAST + FUTURE"
        )

    def _update_graph_prediction_progress(self, value):

        self.graph_prediction_status.setText(
            f"Calculating perturbation prediction in the background... "
            f"{int(value)}%"
        )

    def finish_graph_prediction(self, result):

        context = getattr(self, "_graph_prediction_context", {})
        self.graph_prediction_epoch = result["epoch"]
        self.graph_prediction_times = result["times"]
        self.graph_prediction_values = result["values"]
        self.graph_prediction_uncertainty = result["uncertainty"]
        self.graph_view_offset = 0.0
        self._graph_signature = None
        self.safe_update_graph()

        requested_sources = context.get("requested_sources", ())
        hours = context.get("hours", 24)
        source_label = " / ".join(requested_sources)
        self.graph_prediction_status.setText(
            f"{source_label} prediction ready: "
            f"{hours}h past + {hours}h future, "
            f"{result['point_count']} points with numerical sensitivity band. "
            f"Scroll to explore."
            f"{context.get('srp_prediction_note', '')}"
        )
        self.statusBar().showMessage(
            "Past and future perturbation prediction completed.", 6000
        )
        self._set_graph_prediction_running(False)

    def fail_graph_prediction(self, message):

        self.graph_prediction_epoch = None
        self.graph_prediction_times = None
        self.graph_prediction_values = None
        self.graph_prediction_uncertainty = None
        self.graph_prediction_status.setText(
            f"Prediction error: {message}"
        )
        self.statusBar().showMessage(
            f"Prediction error: {message}", 10000
        )
        self._set_graph_prediction_running(False)

    def cancelled_graph_prediction(self):

        self.graph_prediction_status.setText(
            "Perturbation prediction cancelled."
        )
        self.statusBar().showMessage(
            "Perturbation prediction cancelled.", 5000
        )
        self._set_graph_prediction_running(False)

    def cleanup_graph_prediction(self):

        self.graph_prediction_worker = None
        self.graph_prediction_thread = None
        self._graph_prediction_context = None
        if self._graph_prediction_timer_was_active:
            self.timer.start(1000)
        self._graph_prediction_timer_was_active = False



    def shift_graph_view(self, direction):

        width = getattr(
            self,
            "_graph_x_width",
            None,
        )

        if width is None:
            return

        direction = -1 if direction < 0 else 1
        step = width * 0.20

        self.graph_view_offset += (
            direction * step
        )

        # Predictions cover one full selected range on each side of now.
        # Keep the viewport inside that useful region.
        max_offset = width * 0.50
        self.graph_view_offset = float(
            np.clip(
                self.graph_view_offset,
                -max_offset,
                max_offset,
            )
        )

        half_width = width * 0.50
        self.graph.ax.set_xlim(
            -half_width + self.graph_view_offset,
            half_width + self.graph_view_offset,
        )
        self.graph.draw_idle()


    def center_graph_view(self):

        width = getattr(
            self,
            "_graph_x_width",
            None,
        )

        if width is None:
            return

        self.graph_view_offset = 0.0
        half_width = width * 0.50
        self.graph.ax.set_xlim(
            -half_width,
            half_width,
        )
        self.graph.draw_idle()


    def on_graph_scroll(self, event):

        if event.inaxes is not self.graph.ax:
            return

        # Wheel up moves toward the past; wheel down toward the future.
        self.shift_graph_view(
            -1 if event.step > 0 else 1
        )


    def on_graph_pan_start(self, event):

        if (
            event.inaxes is not self.graph.ax
            or event.button is not MouseButton.LEFT
        ):
            return

        self._graph_pan_start_pixel = float(
            event.x
        )
        self._graph_pan_start_offset = float(
            self.graph_view_offset
        )


    def on_graph_pan_move(self, event):

        if not hasattr(
            self,
            "_graph_pan_start_pixel",
        ):
            return

        width = getattr(
            self,
            "_graph_x_width",
            None,
        )

        if width is None:
            return

        axes_pixel_width = float(
            self.graph.ax.bbox.width
        )

        if axes_pixel_width <= 0.0:
            return

        pixel_delta = (
            self._graph_pan_start_pixel
            - float(event.x)
        )

        new_offset = (
            self._graph_pan_start_offset
            + pixel_delta
            / axes_pixel_width
            * width
        )

        max_offset = width * 0.50
        self.graph_view_offset = float(
            np.clip(
                new_offset,
                -max_offset,
                max_offset,
            )
        )

        half_width = width * 0.50
        self.graph.ax.set_xlim(
            -half_width + self.graph_view_offset,
            half_width + self.graph_view_offset,
        )
        self.graph.draw_idle()


    def on_graph_pan_end(self, event):

        if hasattr(
            self,
            "_graph_pan_start_pixel",
        ):
            del self._graph_pan_start_pixel

        if hasattr(
            self,
            "_graph_pan_start_offset",
        ):
            del self._graph_pan_start_offset


    # ========================================================
    # UPDATE 2D SYSTEM VIEW
    # ========================================================

    def ensure_system_reference_orbits(self, object_ids, epoch):

        for object_id in object_ids:
            if object_id == "earth":
                continue

            config = ORBITAL_OBJECTS[object_id]
            if config["kind"] == "moon":
                period_seconds = 27.321661 * 86400.0
                sample_count = 361
            elif (
                object_id == "active_profile"
                and self.active_profile.orbit_source in {"cartesian", "ephemeris"}
            ):
                profile_state = np.asarray(
                    self.active_profile.state_j2000,
                    dtype=float,
                )
                elements = cartesian_to_keplerian(profile_state)
                semi_major_axis = float(elements["a_km"])
                if not np.isfinite(semi_major_axis) or semi_major_axis <= 0.0:
                    raise ValueError(
                        "The active spacecraft state does not describe a bound Earth orbit."
                    )
                period_seconds = 2.0 * np.pi * np.sqrt(
                    semi_major_axis**3 / MU_EARTH
                )
                sample_count = 241
            else:
                period_seconds = get_satellite_orbital_period_seconds(
                    config["tle_name"],
                    norad_id=config["norad"],
                )
                sample_count = 241

            cached = self.system_reference_orbits.get(
                object_id
            )
            cache_is_current = (
                cached is not None
                and cached.get("profile_id")
                == (
                    self.active_profile_id
                    if object_id == "active_profile"
                    else None
                )
                and abs(
                    (
                        epoch - cached["epoch"]
                    ).total_seconds()
                )
                <= period_seconds * 0.25
            )
            if cache_is_current:
                continue

            offsets = np.linspace(
                -0.5 * period_seconds,
                0.5 * period_seconds,
                sample_count,
            )
            sample_times = [
                epoch
                + timedelta(
                    seconds=float(offset)
                )
                for offset in offsets
            ]

            if config["kind"] == "moon":
                positions = np.asarray(
                    [
                        get_moon_position(
                            utc_to_et(sample_time)
                        )
                        for sample_time in sample_times
                    ],
                    dtype=float,
                )
                orbit_altitudes = None
            elif (
                object_id == "active_profile"
                and self.active_profile.orbit_source in {"cartesian", "ephemeris"}
            ):
                _times, states = propagate_trajectory(
                    initial_state=self.active_profile.state_j2000,
                    initial_epoch=self.active_profile.parsed_epoch,
                    duration_seconds=period_seconds,
                    output_step=period_seconds / (sample_count - 1),
                    include_j2=False,
                    include_moon=False,
                    include_sun=False,
                    include_srp=False,
                    max_step=min(300.0, period_seconds / (sample_count - 1)),
                )
                positions = np.asarray(states[:, :3], dtype=float)
                orbit_altitudes = np.asarray(
                    wgs84_geodetic_altitude_km(positions),
                    dtype=float,
                )
            else:
                positions, orbit_altitudes = (
                    get_satellite_positions_and_altitudes(
                        config["tle_name"],
                        sample_times,
                        norad_id=config["norad"],
                    )
                )

            orbit_record = {
                "epoch": epoch,
                "period_seconds": float(period_seconds),
                "profile_id": (
                    self.active_profile_id
                    if object_id == "active_profile"
                    else None
                ),
                "positions": np.asarray(
                    positions,
                    dtype=float,
                ),
            }

            if config["kind"] == "satellite":
                orbit_record.update(
                    {
                        "perigee_altitude_km": float(np.min(orbit_altitudes)),
                        "apogee_altitude_km": float(np.max(orbit_altitudes)),
                        "source_label": (
                            "PROFILE STATE"
                            if object_id == "active_profile"
                            and self.active_profile.orbit_source
                            in {"cartesian", "ephemeris"}
                            else "TLE"
                        ),
                    }
                )
                if orbit_record["source_label"] == "TLE":
                    tle_metadata = get_tle_metadata(
                        config["tle_name"],
                        norad_id=config["norad"],
                    )
                    orbit_record.update(
                        {
                            "tle_epoch": tle_metadata["tle_epoch"],
                            "tle_age_days": tle_metadata["age_days"],
                        }
                    )

            self.system_reference_orbits[object_id] = orbit_record

    def reset_system_view(self):

        self._finish_system_drag_blit()
        self.system_view_yaw = 35.0
        self.system_view_pitch = 25.0
        self.system_view_zoom = 1.0
        self.safe_update_system_view()


    def _system_dynamic_artists(self):

        artists = []
        for attribute_name in (
            "_system_orbit_back_artists",
            "_system_orbit_front_artists",
            "_system_link_artists",
            "_system_object_artists",
            "_system_object_labels",
        ):
            artists.extend(
                getattr(self, attribute_name, {}).values()
            )

        for attribute_name in (
            "_system_earth_texture_artist",
            "_system_altitude_artist",
            "_system_altitude_label",
            "_system_focus_halo",
        ):
            artist = getattr(self, attribute_name, None)
            if artist is not None:
                artists.append(artist)

        # Explicit sorting preserves Earth occlusion even though all blitted
        # artists are painted above the cached static axes background.
        return tuple(
            sorted(
                dict.fromkeys(artists),
                key=lambda artist: artist.get_zorder(),
            )
        )


    def _begin_system_drag_blit(self):

        canvas = self.system_graph
        if not canvas.supports_blit:
            return

        for annotation in canvas._coordinate_annotations.values():
            annotation.set_visible(False)
        canvas._suspend_pointer_coordinates = True

        artists = self._system_dynamic_artists()
        if not artists:
            return

        self._system_drag_animated_artists = artists
        for artist in artists:
            artist.set_animated(True)

        # A synchronous draw produces a clean static background containing
        # axes, ticks, grid and legend but excluding the animated scene.
        canvas.draw()
        self._system_drag_background = canvas.copy_from_bbox(
            canvas.ax.bbox
        )
        self._blit_system_drag_artists()


    def _blit_system_drag_artists(self):

        canvas = self.system_graph
        if (
            self._system_drag_background is None
            or not canvas.supports_blit
        ):
            return False

        canvas.restore_region(
            self._system_drag_background
        )
        for artist in self._system_drag_animated_artists:
            if artist.get_visible():
                canvas.ax.draw_artist(artist)
        canvas.blit(
            canvas.ax.bbox
        )
        return True


    def _finish_system_drag_blit(self):

        timer = getattr(
            self,
            "_system_drag_frame_timer",
            None,
        )
        if timer is not None and timer.isActive():
            timer.stop()

        for artist in self._system_drag_animated_artists:
            artist.set_animated(False)
        self._system_drag_animated_artists = ()
        self._system_drag_background = None
        self._system_drag_frame_pending = False

        if hasattr(self, "system_graph"):
            self.system_graph._suspend_pointer_coordinates = False


    def _queue_system_drag_frame(self):

        self._system_drag_frame_pending = True
        if self._system_drag_frame_timer.isActive():
            return

        elapsed = (
            time.perf_counter()
            - self._system_drag_last_frame_time
        )
        delay_ms = max(
            0,
            int(round(1000.0 / 60.0 - elapsed * 1000.0)),
        )
        self._system_drag_frame_timer.start(
            delay_ms
        )


    def _render_pending_system_drag_frame(self):

        if (
            not self._system_drag_frame_pending
            or not hasattr(self, "_system_drag_start")
        ):
            return

        self._system_drag_frame_pending = False
        frame_start = time.perf_counter()
        self.safe_update_system_view()
        frame_end = time.perf_counter()
        self._system_drag_last_frame_time = frame_end
        self._system_drag_frame_times.append(
            frame_end - frame_start
        )


    def on_system_view_press(self, event):

        if (
            event.inaxes is not self.system_graph.ax
            or event.button is not MouseButton.LEFT
        ):
            return

        if getattr(event, "dblclick", False):
            self.adjust_system_view_zoom(
                0.25
            )
            return

        if self.system_plane.currentText() != "3D Interactive":
            return

        self._system_drag_start = (
            float(event.x),
            float(event.y),
            float(self.system_view_yaw),
            float(self.system_view_pitch),
        )
        self._system_drag_frame_times.clear()
        self._system_drag_last_frame_time = 0.0
        self._begin_system_drag_blit()


    def on_system_view_move(self, event):

        if not hasattr(
            self,
            "_system_drag_start",
        ):
            return

        start_x, start_y, start_yaw, start_pitch = (
            self._system_drag_start
        )

        self.system_view_yaw = (
            start_yaw
            + (float(event.x) - start_x) * 0.30
        ) % 360.0
        self.system_view_pitch = float(
            np.clip(
                start_pitch
                + (float(event.y) - start_y) * 0.25,
                -85.0,
                85.0,
            )
        )
        self._queue_system_drag_frame()


    def on_system_view_release(self, event):

        if hasattr(
            self,
            "_system_drag_start",
        ):
            del self._system_drag_start
            self._finish_system_drag_blit()
            self.safe_update_system_view()


    def on_system_view_scroll(self, event):

        if (
            event.inaxes is not self.system_graph.ax
        ):
            return

        zoom_multiplier = (
            0.78
            if event.step > 0
            else 1.28
        )
        self.adjust_system_view_zoom(
            zoom_multiplier
        )




    def _get_system_live_positions(self, selected_ids, epoch):

        cache_key = (
            epoch,
            tuple(selected_ids),
        )
        if self._system_live_cache_key == cache_key:
            self.system_object_errors = dict(
                self._system_live_position_errors
            )
            return self.system_live_positions

        positions = {
            "earth": np.zeros(
                3,
                dtype=float,
            ),
        }
        altitudes = {}
        self.system_object_errors = {}

        for object_id in selected_ids:
            if object_id == "earth":
                continue

            config = ORBITAL_OBJECTS[object_id]
            try:
                if config["kind"] == "moon":
                    if self.current_moon_position is None:
                        position = get_moon_position(utc_to_et(epoch))
                    else:
                        position = self.current_moon_position
                elif object_id == "active_profile":
                    state, _state_epoch = self.active_spacecraft_state(epoch)
                    position = state[:3]
                    altitude_km = wgs84_geodetic_altitude_km(position)
                else:
                    position, altitude_km = (
                        get_satellite_position_and_altitude(
                            config["tle_name"],
                            epoch,
                            norad_id=config["norad"],
                        )
                    )

                position = np.asarray(
                    position,
                    dtype=float,
                )
                if position.shape != (3,) or not np.all(
                    np.isfinite(position)
                ):
                    raise ValueError(
                        "Position is not a finite 3D vector."
                    )
                positions[object_id] = position.copy()
                if config["kind"] == "satellite":
                    altitudes[object_id] = float(
                        altitude_km
                    )
            except Exception as error:
                self.system_object_errors[object_id] = str(
                    error
                )

        self.system_live_positions = positions
        self.system_live_altitudes = altitudes
        self._system_live_cache_key = cache_key
        self._system_live_position_errors = dict(
            self.system_object_errors
        )
        return positions


    def _system_view_basis(
        self,
        plane_text,
        yaw_degrees=None,
        pitch_degrees=None,
    ):

        fixed_bases = {
            "XY Plane": (
                np.asarray([1.0, 0.0, 0.0]),
                np.asarray([0.0, 1.0, 0.0]),
            ),
            "XZ Plane": (
                np.asarray([1.0, 0.0, 0.0]),
                np.asarray([0.0, 0.0, 1.0]),
            ),
            "YZ Plane": (
                np.asarray([0.0, 1.0, 0.0]),
                np.asarray([0.0, 0.0, 1.0]),
            ),
        }
        if plane_text in fixed_bases:
            right_vector, up_vector = fixed_bases[plane_text]
        else:
            yaw = np.deg2rad(
                self.system_view_yaw
                if yaw_degrees is None
                else yaw_degrees
            )
            pitch = np.deg2rad(
                self.system_view_pitch
                if pitch_degrees is None
                else pitch_degrees
            )
            right_vector = np.asarray(
                [
                    -np.sin(yaw),
                    np.cos(yaw),
                    0.0,
                ]
            )
            up_vector = np.asarray(
                [
                    -np.sin(pitch) * np.cos(yaw),
                    -np.sin(pitch) * np.sin(yaw),
                    np.cos(pitch),
                ]
            )

        front_vector = np.cross(
            right_vector,
            up_vector,
        )
        front_vector /= np.linalg.norm(
            front_vector
        )
        return right_vector, up_vector, front_vector


    def _project_system_positions(
        self,
        positions,
        focus_position,
        plane_text,
    ):

        positions = np.asarray(
            positions,
            dtype=float,
        )
        if positions.size == 0:
            return np.empty(
                (0, 2),
                dtype=float,
            )
        if positions.ndim == 1:
            positions = positions.reshape(
                1,
                3,
            )

        relative_positions = (
            positions
            - np.asarray(
                focus_position,
                dtype=float,
            )
        )

        right_vector, up_vector, _ = self._system_view_basis(
            plane_text
        )
        return np.column_stack(
            (
                relative_positions @ right_vector,
                relative_positions @ up_vector,
            )
        )


    @staticmethod
    def _greenwich_sidereal_angle(epoch):

        utc_epoch = epoch.astimezone(timezone.utc)
        julian_date = utc_epoch.timestamp() / 86400.0 + 2440587.5
        centuries = (julian_date - 2451545.0) / 36525.0
        angle_degrees = (
            280.46061837
            + 360.98564736629 * (julian_date - 2451545.0)
            + 0.000387933 * centuries * centuries
            - centuries * centuries * centuries / 38710000.0
        )
        return np.deg2rad(angle_degrees % 360.0)


    def _create_earth_texture(self, epoch, plane_text):

        texture_yaw = self.system_view_yaw
        texture_pitch = self.system_view_pitch
        drag_preview = hasattr(
            self,
            "_system_drag_start",
        )
        texture_size = (
            128
            if drag_preview
            else 384
        )
        texture_key = (
            epoch.replace(
                second=0,
                microsecond=0,
            ),
            plane_text,
            texture_size,
            round(texture_yaw, 1),
            round(texture_pitch, 1),
            is_eop_enabled(),
        )
        if (
            self._earth_texture_cache_key == texture_key
            and self._earth_texture_cache is not None
        ):
            return self._earth_texture_cache

        geometry = self._earth_texture_geometry_cache.get(
            texture_size
        )
        if geometry is None:
            coordinates = np.linspace(
                -1.0,
                1.0,
                texture_size,
            )
            screen_x, screen_y = np.meshgrid(
                coordinates,
                coordinates,
            )
            radial_squared = (
                screen_x * screen_x
                + screen_y * screen_y
            )
            inside_disc = radial_squared <= 1.0
            screen_z = np.sqrt(
                np.clip(
                    1.0 - radial_squared,
                    0.0,
                    1.0,
                )
            )
            alpha = np.clip(
                (1.0 - radial_squared) * 110.0,
                0.0,
                1.0,
            )
            geometry = (
                screen_x,
                screen_y,
                radial_squared,
                inside_disc,
                screen_z,
                alpha,
            )
            self._earth_texture_geometry_cache[
                texture_size
            ] = geometry
        (
            screen_x,
            screen_y,
            radial_squared,
            inside_disc,
            screen_z,
            alpha,
        ) = geometry

        right, up, front = self._system_view_basis(
            plane_text,
            yaw_degrees=texture_yaw,
            pitch_degrees=texture_pitch,
        )
        inertial_normals = (
            screen_x[..., None] * right
            + screen_y[..., None] * up
            + screen_z[..., None] * front
        )

        if is_eop_enabled():
            j2000_to_itrs = j2000_to_itrs_rotation_from_datetime(epoch)
            ecef_normals = inertial_normals @ j2000_to_itrs.T
        else:
            sidereal_angle = self._greenwich_sidereal_angle(epoch)
            cosine_angle = np.cos(sidereal_angle)
            sine_angle = np.sin(sidereal_angle)
            ecef_normals = np.empty_like(inertial_normals)
            ecef_normals[..., 0] = (
                cosine_angle * inertial_normals[..., 0]
                + sine_angle * inertial_normals[..., 1]
            )
            ecef_normals[..., 1] = (
                -sine_angle * inertial_normals[..., 0]
                + cosine_angle * inertial_normals[..., 1]
            )
            ecef_normals[..., 2] = inertial_normals[..., 2]
        ecef_x = ecef_normals[..., 0]
        ecef_y = ecef_normals[..., 1]
        longitude = np.arctan2(
            ecef_y,
            ecef_x,
        )
        latitude = np.arcsin(
            np.clip(
                ecef_normals[..., 2],
                -1.0,
                1.0,
            )
        )
        longitude_degrees = np.rad2deg(
            longitude
        )
        latitude_degrees = np.rad2deg(
            latitude
        )
        lon_lat_points = np.column_stack(
            (
                longitude_degrees.ravel(),
                latitude_degrees.ravel(),
            )
        )

        land = np.zeros(
            texture_size * texture_size,
            dtype=bool,
        )
        for land_path in EARTH_LAND_PATHS:
            land |= land_path.contains_points(
                lon_lat_points
            )
        land = land.reshape(
            texture_size,
            texture_size,
        ) & inside_disc

        try:
            sun_vector = get_sun_position(
                utc_to_et(epoch)
            )
            sun_direction = sun_vector / np.linalg.norm(
                sun_vector
            )
        except Exception:
            sun_direction = (
                0.35 * right
                + 0.20 * up
                + 0.91 * front
            )
            sun_direction /= np.linalg.norm(
                sun_direction
            )

        solar_incidence = np.clip(
            inertial_normals @ sun_direction,
            0.0,
            1.0,
        )
        illumination = 0.10 + 0.90 * np.sqrt(
            solar_incidence
        )

        ocean_night = np.asarray([1.0, 8.0, 24.0])
        ocean_day = np.asarray([5.0, 82.0, 158.0])
        land_night = np.asarray([7.0, 20.0, 15.0])
        land_day = np.asarray([70.0, 128.0, 61.0])
        image_rgb = (
            ocean_night
            + illumination[..., None]
            * (ocean_day - ocean_night)
        )
        land_rgb = (
            land_night
            + illumination[..., None]
            * (land_day - land_night)
        )

        arid = land & (
            (
                (latitude_degrees > 12.0)
                & (latitude_degrees < 34.0)
                & (longitude_degrees > -18.0)
                & (longitude_degrees < 62.0)
            )
            | (
                (latitude_degrees < -17.0)
                & (latitude_degrees > -34.0)
                & (longitude_degrees > 115.0)
                & (longitude_degrees < 145.0)
            )
        )
        desert_day = np.asarray([176.0, 142.0, 76.0])
        desert_rgb = (
            land_night
            + illumination[..., None]
            * (desert_day - land_night)
        )
        image_rgb[land] = land_rgb[land]
        image_rgb[arid] = desert_rgb[arid]

        ice = inside_disc & (
            (latitude_degrees < -70.0)
            | (
                land
                & (latitude_degrees > 72.0)
            )
        )
        ice_day = np.asarray([210.0, 235.0, 245.0])
        ice_night = np.asarray([34.0, 55.0, 70.0])
        ice_rgb = (
            ice_night
            + illumination[..., None]
            * (ice_day - ice_night)
        )
        image_rgb[ice] = ice_rgb[ice]

        cloud_field = (
            np.sin(3.1 * longitude + 1.7 * latitude)
            + 0.55 * np.sin(7.3 * longitude - 4.1 * latitude)
            + 0.35 * np.cos(11.0 * latitude)
        )
        cloud_strength = np.clip(
            (cloud_field - 0.90) / 1.15,
            0.0,
            0.42,
        ) * inside_disc
        image_rgb = (
            image_rgb * (1.0 - cloud_strength[..., None])
            + 235.0 * cloud_strength[..., None]
        )

        atmospheric_rim = (
            np.clip(
                1.0 - screen_z,
                0.0,
                1.0,
            ) ** 2
        )[..., None]
        image_rgb += atmospheric_rim * np.asarray(
            [0.0, 32.0, 58.0]
        )

        image = np.dstack(
            (
                np.clip(
                    image_rgb / 255.0,
                    0.0,
                    1.0,
                ),
                alpha,
            )
        )
        self._earth_texture_cache_key = texture_key
        self._earth_texture_cache = image
        return image


    def _calculate_system_view_limit(
        self,
        scale_text,
        focus_id,
        selected_ids,
        projected_positions,
        projected_orbits,
    ):

        fixed_limits = {
            "Satellite Close-up (1,000 km)": 1000.0,
            "Satellite Detail (100 km)": 100.0,
            "Low Earth Orbit (12,000 km)": 12000.0,
            "Geostationary Belt (55,000 km)": 55000.0,
            "Earth-Moon System": 450000.0,
        }
        if scale_text in fixed_limits:
            base_limit = fixed_limits[scale_text]
        else:
            candidates = []

            if scale_text == "Focused Object Orbit":
                focus_orbit = projected_orbits.get(
                    focus_id
                )
                if focus_orbit is not None and focus_orbit.size:
                    candidates.append(
                        focus_orbit
                    )

                earth_position = projected_positions.get(
                    "earth"
                )
                if earth_position is not None:
                    candidates.append(
                        earth_position.reshape(1, 2)
                    )

                if focus_id == "earth":
                    for object_id in selected_ids:
                        if ORBITAL_OBJECTS[object_id]["kind"] == "satellite":
                            orbit = projected_orbits.get(
                                object_id
                            )
                            if orbit is not None and orbit.size:
                                candidates.append(
                                    orbit
                                )
            else:
                for object_id in selected_ids:
                    position = projected_positions.get(
                        object_id
                    )
                    if position is not None:
                        candidates.append(
                            position.reshape(1, 2)
                        )
                    orbit = projected_orbits.get(
                        object_id
                    )
                    if orbit is not None and orbit.size:
                        candidates.append(
                            orbit
                        )

            finite_candidates = [
                candidate[
                    np.all(
                        np.isfinite(candidate),
                        axis=1,
                    )
                ]
                for candidate in candidates
                if candidate.size
            ]
            finite_candidates = [
                candidate
                for candidate in finite_candidates
                if candidate.size
            ]

            if finite_candidates:
                all_points = np.vstack(
                    finite_candidates
                )
                extent = float(
                    np.max(
                        np.abs(all_points)
                    )
                )
            else:
                extent = 0.0

            base_limit = max(
                8000.0,
                extent * 1.10,
            )

        return float(
            max(
                1.0,
                base_limit * self.system_view_zoom,
            )
        )


    def _build_system_view_artists(self, object_ids):

        axes = self.system_graph.ax
        axes.clear()
        self.system_graph.figure.patch.set_facecolor(
            "#0B1220"
        )
        self.system_graph.style_axes()

        axes.axhline(
            0.0,
            color="#64748B",
            linewidth=0.8,
            alpha=0.42,
            zorder=0,
        )
        axes.axvline(
            0.0,
            color="#64748B",
            linewidth=0.8,
            alpha=0.42,
            zorder=0,
        )

        self._system_orbit_back_artists = {}
        self._system_orbit_front_artists = {}
        # Compatibility alias for code that only needs the background path.
        self._system_orbit_artists = self._system_orbit_back_artists
        self._system_link_artists = {}
        self._system_object_artists = {}
        self._system_object_labels = {}
        self._system_earth_texture_artist = None

        for object_id in object_ids:
            config = ORBITAL_OBJECTS[object_id]

            if object_id != "earth":
                orbit_back_artist, = axes.plot(
                    [],
                    [],
                    color=config["color"],
                    linewidth=1.5,
                    linestyle="--",
                    alpha=0.36,
                    zorder=1,
                )
                orbit_front_artist, = axes.plot(
                    [],
                    [],
                    color=config["color"],
                    linewidth=2.4,
                    linestyle="-",
                    alpha=1.0,
                    zorder=6.45,
                )
                # A wide, faint stroke under the near-side arc reads as the
                # track glowing rather than as a thicker line, which keeps
                # the orbit legible once the plot is scaled down.
                orbit_front_artist.set_path_effects([
                    mpatheffects.withStroke(
                        linewidth=7.0,
                        foreground=config["color"],
                        alpha=0.16,
                    ),
                    mpatheffects.Normal(),
                ])
                link_artist, = axes.plot(
                    [],
                    [],
                    color=config["color"],
                    linewidth=0.8,
                    linestyle=(
                        ":"
                        if config["kind"] == "moon"
                        else "-"
                    ),
                    alpha=0.24,
                    zorder=1,
                )
                self._system_orbit_back_artists[
                    object_id
                ] = orbit_back_artist
                self._system_orbit_front_artists[
                    object_id
                ] = orbit_front_artist
                self._system_link_artists[object_id] = link_artist

            if object_id == "earth":
                self._system_earth_texture_artist = axes.imshow(
                    np.zeros(
                        (2, 2, 4),
                        dtype=float,
                    ),
                    extent=(
                        -EARTH_EQUATORIAL_RADIUS_KM,
                        EARTH_EQUATORIAL_RADIUS_KM,
                        -EARTH_EQUATORIAL_RADIUS_KM,
                        EARTH_EQUATORIAL_RADIUS_KM,
                    ),
                    origin="lower",
                    interpolation="bilinear",
                    zorder=5.8,
                )
                artist = Circle(
                    (0.0, 0.0),
                    EARTH_EQUATORIAL_RADIUS_KM,
                    facecolor="#082F63",
                    edgecolor=config["edge"],
                    linewidth=1.6,
                    alpha=0.42,
                    label=config["display"],
                    zorder=6,
                )
                axes.add_patch(
                    artist
                )
            elif object_id == "moon":
                artist = Circle(
                    (0.0, 0.0),
                    MOON_MEAN_RADIUS_KM,
                    facecolor=config["color"],
                    edgecolor=config["edge"],
                    linewidth=1.2,
                    alpha=0.92,
                    label=config["display"],
                    zorder=7,
                )
                axes.add_patch(
                    artist
                )
            else:
                artist = axes.scatter(
                    [],
                    [],
                    s=72,
                    marker=config["marker"],
                    color=config["color"],
                    edgecolors=config["edge"],
                    linewidths=1.2,
                    label=(
                        f"{config['display']} · N{config['norad']}"
                        if config.get("norad") is not None
                        else f"{config['display']} · PROFILE STATE"
                    ),
                    zorder=7,
                )

            label = axes.annotate(
                config["short"],
                xy=(0.0, 0.0),
                xytext=config["label_offset"],
                textcoords="offset points",
                color=config["edge"],
                fontsize=8.5,
                fontweight="bold",
                annotation_clip=True,
                horizontalalignment=config.get(
                    "label_align",
                    "left",
                ),
                zorder=8,
            )
            self._system_object_artists[object_id] = artist
            self._system_object_labels[object_id] = label

        self._system_altitude_artist, = axes.plot(
            [],
            [],
            color="#F8FAFC",
            linewidth=1.0,
            linestyle=":",
            alpha=0.85,
            zorder=8,
        )
        self._system_altitude_label = axes.annotate(
            "",
            xy=(0.0, 0.0),
            xytext=(7, -10),
            textcoords="offset points",
            color="#F8FAFC",
            fontsize=8.5,
            fontweight="bold",
            annotation_clip=True,
            zorder=9,
        )
        self._system_altitude_label.set_visible(
            False
        )
        self._system_focus_halo = axes.scatter(
            [],
            [],
            s=260,
            facecolors="none",
            edgecolors="#FFFFFF",
            linewidths=1.1,
            alpha=0.55,
            zorder=6.8,
        )

        legend = axes.legend(
            loc="upper left",
            frameon=True,
            fontsize=8,
            facecolor="#0F172A",
            edgecolor="#334155",
            labelcolor="#E2E8F0",
        )
        if legend is not None:
            for legend_text in legend.get_texts():
                legend_text.set_color(
                    "#E2E8F0"
                )

        self.system_graph.figure.subplots_adjust(
            left=0.085,
            right=0.985,
            bottom=0.13,
            top=0.88,
        )


    def update_system_view(self):
        # Optional satellites are evaluated only while the orbital tab is
        # visible; normal live perturbation monitoring stays lightweight.
        if self.tabs.currentWidget() is not self.system_view_page:
            return

        epoch = (
            self.current_system_epoch
            if self.current_system_epoch is not None
            else self.get_analysis_utc()
        )
        selected_ids = self.selected_system_object_ids()
        positions = self._get_system_live_positions(
            selected_ids,
            epoch,
        )
        available_ids = [
            object_id
            for object_id in selected_ids
            if object_id in positions
        ]

        for object_id in available_ids:
            if object_id == "earth":
                continue
            try:
                self.ensure_system_reference_orbits(
                    [object_id],
                    epoch,
                )
            except Exception as error:
                self.system_object_errors[object_id] = str(
                    error
                )

        requested_focus_id = self.system_focus.currentData()
        focus_id = (
            requested_focus_id
            if requested_focus_id in positions
            else "earth"
        )
        focus_position = positions[focus_id]
        plane_text = self.system_plane.currentText()
        drag_preview = hasattr(
            self,
            "_system_drag_start",
        )
        _right_vector, _up_vector, front_vector = (
            self._system_view_basis(
                plane_text
            )
        )

        projected_positions = {
            object_id: self._project_system_positions(
                position,
                focus_position,
                plane_text,
            )[0]
            for object_id, position in positions.items()
            if object_id in available_ids
        }
        projected_position_depths = {
            object_id: float(
                (
                    np.asarray(position, dtype=float)
                    - focus_position
                )
                @ front_vector
            )
            for object_id, position in positions.items()
            if object_id in available_ids
        }
        projected_orbits = {}
        projected_orbit_depths = {}
        for object_id in available_ids:
            cached_orbit = self.system_reference_orbits.get(
                object_id
            )
            if cached_orbit is None:
                continue
            projected_orbits[object_id] = (
                self._project_system_positions(
                    cached_orbit["positions"],
                    focus_position,
                    plane_text,
                )
            )
            projected_orbit_depths[object_id] = (
                (
                    np.asarray(
                        cached_orbit["positions"],
                        dtype=float,
                    )
                    - focus_position
                )
                @ front_vector
            )

        scale_text = self.system_scale.currentText()
        if (
            drag_preview
            and self._system_last_view_limit is not None
        ):
            # Keep scale fixed while rotating.  Re-fitting projected extents
            # on every frame creates visible zoom pulsing and invalidates the
            # cached blit background.
            view_limit = self._system_last_view_limit
        else:
            view_limit = self._calculate_system_view_limit(
                scale_text,
                focus_id,
                available_ids,
                projected_positions,
                projected_orbits,
            )

        view_signature = tuple(
            available_ids
        )
        if getattr(
            self,
            "_system_view_signature",
            None,
        ) != view_signature:
            self._build_system_view_artists(
                available_ids
            )
            self._system_view_signature = view_signature

        axes = self.system_graph.ax
        if (
            drag_preview
            and self._system_last_horizontal_limit is not None
            and self._system_last_vertical_limit is not None
        ):
            horizontal_limit = self._system_last_horizontal_limit
            vertical_limit = self._system_last_vertical_limit
        else:
            axes_pixel_ratio = float(
                (
                    max(
                        self.system_graph.width(),
                        1,
                    )
                    * (0.985 - 0.085)
                )
                / max(
                    max(
                        self.system_graph.height(),
                        1,
                    )
                    * (0.88 - 0.13),
                    1.0,
                )
            )
            if axes_pixel_ratio >= 1.0:
                horizontal_limit = view_limit * axes_pixel_ratio
                vertical_limit = view_limit
            else:
                horizontal_limit = view_limit
                vertical_limit = view_limit / max(
                    axes_pixel_ratio,
                    0.1,
                )
            self._system_last_view_limit = view_limit
            self._system_last_horizontal_limit = horizontal_limit
            self._system_last_vertical_limit = vertical_limit

        earth_2d = projected_positions["earth"]
        if self._system_earth_texture_artist is not None:
            earth_texture = self._create_earth_texture(
                epoch,
                plane_text,
            )
            self._system_earth_texture_artist.set_data(
                earth_texture
            )
            self._system_earth_texture_artist.set_extent(
                (
                    earth_2d[0] - EARTH_EQUATORIAL_RADIUS_KM,
                    earth_2d[0] + EARTH_EQUATORIAL_RADIUS_KM,
                    earth_2d[1] - EARTH_EQUATORIAL_RADIUS_KM,
                    earth_2d[1] + EARTH_EQUATORIAL_RADIUS_KM,
                )
            )

        offscreen_ids = []
        satellite_marker_size = 72.0 * float(
            np.clip(
                (
                    12000.0
                    / max(view_limit, 1.0)
                ) ** 0.20,
                0.80,
                4.0,
            )
        )
        for object_id in available_ids:
            position_2d = projected_positions[object_id]
            config = ORBITAL_OBJECTS[object_id]
            artist = self._system_object_artists[object_id]

            if isinstance(artist, Circle):
                artist.center = tuple(
                    position_2d
                )
            else:
                artist.set_offsets(
                    position_2d.reshape(1, 2)
                )
                artist.set_sizes(
                    [
                        satellite_marker_size
                        * (
                            1.30
                            if object_id == focus_id
                            else 1.0
                        )
                    ]
                )

            label = self._system_object_labels[object_id]
            label.xy = tuple(
                position_2d
            )
            label.set_text(
                config["short"]
                + (
                    "  [FOCUS]"
                    if object_id == focus_id
                    else ""
                )
            )

            if object_id != "earth":
                orbit = projected_orbits.get(
                    object_id
                )
                if orbit is None:
                    self._system_orbit_back_artists[
                        object_id
                    ].set_data(
                        [],
                        [],
                    )
                    self._system_orbit_front_artists[
                        object_id
                    ].set_data([], [])
                else:
                    # Draw the full path below Earth, then redraw only the
                    # camera-facing half above it.  This produces correct
                    # orthographic sphere occlusion: the far arc disappears
                    # behind the globe while the near arc remains visible.
                    self._system_orbit_back_artists[
                        object_id
                    ].set_data(
                        orbit[:, 0],
                        orbit[:, 1],
                    )
                    orbit_depths = projected_orbit_depths[
                        object_id
                    ]
                    front_mask = orbit_depths >= (
                        projected_position_depths["earth"]
                    )
                    front_orbit = orbit.copy()
                    front_orbit[~front_mask] = np.nan
                    self._system_orbit_front_artists[
                        object_id
                    ].set_data(
                        front_orbit[:, 0],
                        front_orbit[:, 1],
                    )
                self._system_link_artists[object_id].set_data(
                    [earth_2d[0], position_2d[0]],
                    [earth_2d[1], position_2d[1]],
                )

            if (
                abs(position_2d[0]) > horizontal_limit
                or abs(position_2d[1]) > vertical_limit
            ):
                offscreen_ids.append(
                    object_id
                )

        focus_config = ORBITAL_OBJECTS[focus_id]
        focus_altitude = None
        if focus_config["kind"] == "satellite":
            focus_2d = projected_positions[focus_id]
            self._system_focus_halo.set_offsets(
                focus_2d.reshape(1, 2)
            )
            self._system_focus_halo.set_sizes(
                [satellite_marker_size * 3.2]
            )
            self._system_focus_halo.set_edgecolors(
                focus_config["color"]
            )
            self._system_focus_halo.set_visible(
                True
            )
            focus_altitude = self.system_live_altitudes.get(
                focus_id
            )
            if focus_altitude is None:
                focus_altitude = wgs84_geodetic_altitude_km(
                    focus_position
                )
            radial_unit = focus_position / np.linalg.norm(
                focus_position
            )
            ellipsoid_radius = 1.0 / np.sqrt(
                (
                    radial_unit[0] ** 2
                    + radial_unit[1] ** 2
                )
                / EARTH_EQUATORIAL_RADIUS_KM ** 2
                + radial_unit[2] ** 2
                / EARTH_POLAR_RADIUS_KM ** 2
            )
            surface_position = radial_unit * ellipsoid_radius
            surface_2d = self._project_system_positions(
                surface_position,
                focus_position,
                plane_text,
            )[0]
            satellite_2d = projected_positions[focus_id]
            self._system_altitude_artist.set_data(
                [surface_2d[0], satellite_2d[0]],
                [surface_2d[1], satellite_2d[1]],
            )
            altitude_midpoint = 0.5 * (
                surface_2d + satellite_2d
            )
            self._system_altitude_label.xy = tuple(
                altitude_midpoint
            )
            self._system_altitude_label.set_text(
                f"h = {focus_altitude:,.1f} km  WGS-84"
            )
            self._system_altitude_label.set_visible(
                True
            )
        else:
            self._system_focus_halo.set_visible(
                False
            )
            self._system_altitude_artist.set_data(
                [],
                [],
            )
            self._system_altitude_label.set_visible(
                False
            )

        if drag_preview:
            if not self._blit_system_drag_artists():
                self.system_graph.draw_idle()
            return

        plane_axis_names = {
            "XY Plane": ("X", "Y"),
            "XZ Plane": ("X", "Z"),
            "YZ Plane": ("Y", "Z"),
            "3D Interactive": (
                "View horizontal",
                "View vertical",
            ),
        }
        first_name, second_name = plane_axis_names.get(
            plane_text,
            plane_axis_names["XY Plane"],
        )
        focus_name = ORBITAL_OBJECTS[focus_id]["display"]
        camera_suffix = (
            f"  ·  Yaw {self.system_view_yaw:.0f}°"
            f" / Pitch {self.system_view_pitch:.0f}°"
            if plane_text == "3D Interactive"
            else ""
        )
        axes.set_title(
            f"Orbital Operations View  ·  Focus: {focus_name}  ·  "
            f"{plane_text}{camera_suffix}",
            fontsize=13,
            fontweight="bold",
            pad=10,
        )
        axes.set_xlabel(
            f"{first_name} relative to focus [km]"
        )
        axes.set_ylabel(
            f"{second_name} relative to focus [km]"
        )
        axes.set_xlim(
            -horizontal_limit,
            horizontal_limit,
        )
        axes.set_ylim(
            -vertical_limit,
            vertical_limit,
        )
        axes.set_aspect(
            "equal",
            adjustable="box",
        )
        axes.xaxis.set_major_locator(
            mticker.MaxNLocator(nbins=9)
        )
        axes.yaxis.set_major_locator(
            mticker.MaxNLocator(nbins=8)
        )
        axes.ticklabel_format(
            style="plain",
            axis="both",
            useOffset=False,
        )

        focus_absolute = positions[focus_id]
        focus_distance = float(
            np.linalg.norm(focus_absolute)
        )
        focus_orbit_record = self.system_reference_orbits.get(
            focus_id,
            {},
        )
        if focus_config["kind"] == "satellite":
            source_label = focus_orbit_record.get("source_label", "TLE")
            orbit_accuracy_text = (
                f"{source_label} orbit h: "
                f"{focus_orbit_record.get('perigee_altitude_km', float('nan')):,.1f}"
                "–"
                f"{focus_orbit_record.get('apogee_altitude_km', float('nan')):,.1f} km"
            )
            tle_epoch = focus_orbit_record.get(
                "tle_epoch"
            )
            if tle_epoch is not None:
                orbit_accuracy_text += (
                    "  •  Epoch "
                    + tle_epoch.astimezone(
                        timezone.utc
                    ).strftime("%Y-%m-%d %H:%M UTC")
                )
            focus_distance_text = (
                f"WGS-84 altitude: {focus_altitude:,.3f} km  •  "
                f"r: {focus_distance:,.3f} km\n"
                + orbit_accuracy_text
            )
        else:
            focus_distance_text = (
                f"Earth-centre distance: {focus_distance:,.3f} km"
            )

        self.system_earth_coordinates.setText(
            "EARTH / WGS-84 ELLIPSOID\n"
            "X: 0.000  •  Y: 0.000  •  Z: 0.000\n"
            f"a: {EARTH_EQUATORIAL_RADIUS_KM:,.3f} km  •  "
            f"b: {EARTH_POLAR_RADIUS_KM:,.3f} km"
        )
        self.system_satellite_coordinates.setText(
            f"FOCUS: {ORBITAL_OBJECTS[focus_id]['short']}\n"
            f"X: {focus_absolute[0]:,.3f}  •  "
            f"Y: {focus_absolute[1]:,.3f}  •  "
            f"Z: {focus_absolute[2]:,.3f}\n"
            + focus_distance_text
        )

        offscreen_text = (
            ", ".join(
                ORBITAL_OBJECTS[object_id]["short"]
                for object_id in offscreen_ids
            )
            if offscreen_ids
            else "none"
        )
        self.system_moon_coordinates.setText(
            "VIEW METRICS\n"
            f"Objects: {len(available_ids)}  •  "
            f"Field: {2.0 * horizontal_limit:,.0f} × "
            f"{2.0 * vertical_limit:,.0f} km\n"
            f"Off-screen (true position): {offscreen_text}"
        )
        self.system_precision_badge.setText(
            f"WGS-84 ALT  •  1:1 AXES  •  H ±{horizontal_limit:,.0f} / "
            f"V ±{vertical_limit:,.0f} km  •  "
            f"ZOOM {1.0 / self.system_view_zoom:.2f}×"
        )

        status_parts = [
            "LIVE",
            epoch.astimezone(
                timezone.utc
            ).strftime("%H:%M:%S UTC"),
            f"FOCUS {ORBITAL_OBJECTS[focus_id]['short']}",
        ]
        if focus_altitude is not None:
            status_parts.append(
                f"ALT {focus_altitude:,.1f} km"
            )
        if self.system_object_errors:
            failed_names = ", ".join(
                ORBITAL_OBJECTS[object_id]["short"]
                for object_id in self.system_object_errors
            )
            status_parts.append(
                f"UNAVAILABLE: {failed_names}"
            )
        self.system_live_status.setText(
            "  •  ".join(status_parts)
        )
        self.system_graph.draw_idle()


    # ========================================================
    # REFERENCE VALIDATION PAGE
    # ========================================================

    def create_reference_metric_card(self, caption, detail):

        card = QFrame()
        card.setObjectName("metricCard")
        metric_role = {
            "FINAL POSITION ERROR": "blue",
            "RMS POSITION ERROR": "sage",
            "MAXIMUM POSITION ERROR": "lavender",
            "FINAL VELOCITY ERROR": "blush",
        }.get(caption, "sand")
        card.setProperty("surfaceRole", metric_role)
        card.setMinimumHeight(126)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)

        caption_label = QLabel(caption)
        caption_label.setObjectName("metricCaption")
        value_label = QLabel("—")
        value_label.setObjectName("metricValue")
        value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        detail_label = QLabel(detail)
        detail_label.setObjectName("metricDetail")
        detail_label.setWordWrap(True)

        layout.addWidget(caption_label)
        layout.addWidget(value_label)
        layout.addWidget(detail_label)
        layout.addStretch(1)
        return card, value_label


    def set_reference_metric_values(self, metrics=None, running=False):

        values = (
            ("Running...", "—", "—", "—")
            if running
            else (
                (
                    f"{metrics['final_position_error_km']:.6f} km",
                    f"{metrics['rms_position_error_km']:.6f} km",
                    f"{metrics['maximum_position_error_km']:.6f} km",
                    f"{metrics['final_velocity_error_km_s']:.9f} km/s",
                )
                if metrics is not None
                else ("—", "—", "—", "—")
            )
        )
        for label, value in zip(
            (
                self.reference_with_moon_value,
                self.reference_without_moon_value,
                self.reference_effect_value,
                self.reference_effect_delta_value,
            ),
            values,
        ):
            label.setText(value)


    def create_reference_validation_page(self):

        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        self.reference_scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 10, 12, 18)
        layout.setSpacing(14)

        self.reference_description = QLabel(
            "Select the force model once, then run it with one action. "
            "Moon chooses the matching Moon-on/off reference scenario; "
            "Sun is fully selectable and its additional residual is "
            "reported transparently against the current reference dataset."
        )
        self.reference_description.setWordWrap(True)
        self.reference_description.setObjectName("metricDetail")
        layout.addWidget(self.reference_description)

        modules_box = QGroupBox("FORCE MODEL CONFIGURATION")
        modules_layout = QGridLayout(modules_box)
        modules_layout.setContentsMargins(18, 26, 18, 16)
        modules_layout.setHorizontalSpacing(12)
        modules_layout.setVerticalSpacing(10)

        module_specs = (
            (
                "EARTH GRAVITY",
                "VERIFIED",
                "EGM96 degree/order 4 · active in reference runs",
                theme.STATUS_OK,
                True,
            ),
            (
                "MOON THIRD-BODY",
                "VERIFIED",
                "DE440 geometric J2000 · bundled 30-day references",
                theme.STATUS_OK,
                True,
            ),
            (
                "SUN THIRD-BODY",
                "READY / SELECTABLE",
                "DE440 geometric J2000 · residual includes solar sensitivity",
                theme.STATUS_OK,
                False,
            ),
            (
                "SOLAR RADIATION PRESSURE",
                "READY / SELECTABLE",
                "SYNTHETIC/DEMO box-wing · TrueSun arrays · nominal CP",
                theme.STATUS_OK,
                False,
            ),
        )
        for column, (name, status, detail, color, verified) in enumerate(
            module_specs
        ):
            card = QFrame()
            card.setObjectName("metricCard")
            card.setProperty(
                "surfaceRole",
                ("blue", "sage", "lavender", "blush")[column % 4],
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(5)
            module_check = QCheckBox(name)
            module_check.setChecked(verified)
            module_check.setEnabled(
                name in (
                    "MOON THIRD-BODY",
                    "SUN THIRD-BODY",
                    "SOLAR RADIATION PRESSURE",
                )
            )
            if name == "EARTH GRAVITY":
                self.reference_force_earth = module_check
            elif name == "MOON THIRD-BODY":
                self.reference_force_moon = module_check
            elif name == "SUN THIRD-BODY":
                self.reference_force_sun = module_check
            else:
                self.reference_force_srp = module_check
            status_label = QLabel(status)
            _set_status_role(status_label, "ok")
            detail_label = QLabel(detail)
            detail_label.setObjectName("metricDetail")
            detail_label.setWordWrap(True)
            card_layout.addWidget(module_check)
            card_layout.addWidget(status_label)
            card_layout.addWidget(detail_label)
            card_layout.addStretch(1)
            card_row = column // 2
            card_column = column % 2
            modules_layout.addWidget(card, card_row, card_column)
            modules_layout.setColumnStretch(card_column, 1)
        self.reference_force_moon.toggled.connect(
            self.reference_force_selection_changed
        )
        self.reference_force_sun.toggled.connect(
            self.reference_force_selection_changed
        )
        self.reference_force_srp.toggled.connect(
            self.reference_force_selection_changed
        )
        layout.addWidget(modules_box)

        srp_box = QGroupBox("SRP SPACECRAFT CASE — SHARED WITH PROPAGATION")
        self.reference_srp_box = srp_box
        srp_layout = QGridLayout(srp_box)
        srp_layout.setContentsMargins(18, 26, 18, 16)
        srp_layout.setHorizontalSpacing(12)
        srp_layout.setVerticalSpacing(9)

        self.reference_srp_source_mode = QComboBox()
        self.reference_srp_source_mode.addItem(
            "Existing / predefined spacecraft", "profile"
        )
        self.reference_srp_source_mode.addItem("Manual input", "manual")
        self.reference_spacecraft_selector = self.register_spacecraft_selector(
            QComboBox()
        )
        self.reference_spacecraft_selector.setMinimumWidth(260)
        self.reference_manual_srp_separate_panels = QCheckBox(
            "Enter panel and body CP separately"
        )
        self.reference_manual_srp_separate_panels.setToolTip(
            "Enter total and panel area; body area is calculated as total "
            "area minus panel area."
        )

        def reference_srp_spinbox(minimum, maximum, value, suffix="", decimals=6):
            control = OperatorDoubleSpinBox()
            control.setRange(minimum, maximum)
            control.setDecimals(decimals)
            control.setValue(value)
            control.setSuffix(suffix)
            control.setMinimumHeight(34)
            control.setKeyboardTracking(False)
            return control

        self.reference_manual_srp_mass = reference_srp_spinbox(
            0.000001, 1_000_000_000.0, 1000.0, " kg"
        )
        self.reference_manual_srp_total_area = reference_srp_spinbox(
            0.000001, 1_000_000_000.0, 20.0, " m²"
        )
        self.reference_manual_srp_coefficient = reference_srp_spinbox(
            0.000000001, 100.0, 1.0, decimals=9
        )
        self.reference_manual_srp_panel_area = reference_srp_spinbox(
            0.0, 1_000_000_000.0, 15.0, " m²"
        )
        self.reference_manual_srp_panel_coefficient = reference_srp_spinbox(
            0.000000001, 100.0, 1.0, decimals=9
        )
        self.reference_manual_srp_body_area = reference_srp_spinbox(
            0.0, 1_000_000_000.0, 5.0, " m²"
        )
        self.reference_manual_srp_body_area.setReadOnly(True)
        self.reference_manual_srp_body_area.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.reference_manual_srp_body_coefficient = reference_srp_spinbox(
            0.000000001, 100.0, 1.0, decimals=9
        )

        srp_layout.addWidget(QLabel("Input source:"), 0, 0)
        srp_layout.addWidget(self.reference_srp_source_mode, 0, 1, 1, 3)
        srp_layout.addWidget(QLabel("Spacecraft:"), 1, 0)
        srp_layout.addWidget(self.reference_spacecraft_selector, 1, 1, 1, 3)
        srp_layout.addWidget(
            self.reference_manual_srp_separate_panels, 2, 0, 1, 4
        )
        self.reference_manual_srp_mass_label = QLabel("Spacecraft mass:")
        srp_layout.addWidget(self.reference_manual_srp_mass_label, 3, 0)
        srp_layout.addWidget(self.reference_manual_srp_mass, 3, 1, 1, 3)
        self.reference_manual_srp_total_area_label = QLabel("Total area:")
        self.reference_manual_srp_coefficient_label = QLabel("CP:")
        srp_layout.addWidget(self.reference_manual_srp_total_area_label, 4, 0)
        srp_layout.addWidget(self.reference_manual_srp_total_area, 4, 1)
        srp_layout.addWidget(self.reference_manual_srp_coefficient_label, 4, 2)
        srp_layout.addWidget(self.reference_manual_srp_coefficient, 4, 3)
        self.reference_manual_srp_panel_area_label = QLabel("Panel area:")
        self.reference_manual_srp_panel_coefficient_label = QLabel("Panel CP:")
        self.reference_manual_srp_body_area_label = QLabel(
            "Body area (total − panel):"
        )
        self.reference_manual_srp_body_coefficient_label = QLabel("Body CP:")
        srp_layout.addWidget(self.reference_manual_srp_panel_area_label, 5, 0)
        srp_layout.addWidget(self.reference_manual_srp_panel_area, 5, 1)
        srp_layout.addWidget(self.reference_manual_srp_panel_coefficient_label, 5, 2)
        srp_layout.addWidget(self.reference_manual_srp_panel_coefficient, 5, 3)
        srp_layout.addWidget(self.reference_manual_srp_body_area_label, 6, 0)
        srp_layout.addWidget(self.reference_manual_srp_body_area, 6, 1)
        srp_layout.addWidget(self.reference_manual_srp_body_coefficient_label, 6, 2)
        srp_layout.addWidget(self.reference_manual_srp_body_coefficient, 6, 3)

        self.reference_srp_summary = QLabel()
        self.reference_srp_summary.setObjectName("metricDetail")
        self.reference_srp_summary.setWordWrap(True)
        srp_layout.addWidget(self.reference_srp_summary, 7, 0, 1, 4)
        self.reference_srp_calculate_button = QPushButton(
            "CALCULATE SRP AT REFERENCE EPOCH"
        )
        self.reference_srp_calculate_button.setObjectName("ghostAction")
        self.reference_srp_calculate_button.clicked.connect(
            self.calculate_reference_srp_case
        )
        srp_layout.addWidget(self.reference_srp_calculate_button, 8, 0, 1, 4)
        self.reference_srp_result = QTextEdit()
        self.reference_srp_result.setReadOnly(True)
        self.reference_srp_result.setMaximumHeight(150)
        self.reference_srp_result.setPlaceholderText(
            "SYNTHETIC GEO DEMO or manual SRP acceleration will appear here."
        )
        srp_layout.addWidget(self.reference_srp_result, 9, 0, 1, 4)
        srp_layout.setColumnStretch(1, 1)
        srp_layout.setColumnStretch(3, 1)

        self.reference_srp_source_mode.currentIndexChanged.connect(
            self.reference_srp_source_changed
        )
        self.reference_manual_srp_separate_panels.toggled.connect(
            self.update_reference_srp_controls
        )
        self.reference_spacecraft_selector.currentIndexChanged.connect(
            self.update_reference_srp_controls
        )
        for control in (
            self.reference_manual_srp_mass,
            self.reference_manual_srp_total_area,
            self.reference_manual_srp_coefficient,
            self.reference_manual_srp_panel_area,
            self.reference_manual_srp_panel_coefficient,
            self.reference_manual_srp_body_coefficient,
        ):
            control.valueChanged.connect(self.update_reference_srp_controls)
        self.update_reference_srp_controls()
        layout.addWidget(srp_box)

        dataset_box = QGroupBox("REFERENCE DATASET")
        dataset_layout = QGridLayout(dataset_box)
        dataset_layout.setContentsMargins(18, 26, 18, 16)
        dataset_layout.setHorizontalSpacing(22)
        dataset_layout.setVerticalSpacing(8)

        self.reference_dataset_status = QLabel("Validating local data...")
        self.reference_dataset_status.setWordWrap(True)
        _set_status_role(self.reference_dataset_status, "warning")

        self.reference_discovery_report = reload_user_reference_datasets()
        self.reference_dataset_combo = QComboBox()
        populate_reference_scenario_combo(self.reference_dataset_combo)
        self.reference_dataset_combo.setMinimumHeight(36)
        self.reference_dataset_combo.setToolTip(
            "Choose a reference first by month, then by physical force model."
        )
        self.open_reference_folder_button = QPushButton(
            "OPEN REFERENCE FOLDER"
        )
        self.open_reference_folder_button.setObjectName("ghostAction")
        self.open_reference_folder_button.setToolTip(
            "Open the folder containing bundled references, the user format "
            "guide and drop-in manifests."
        )
        self.open_reference_folder_button.clicked.connect(
            self.open_reference_folder
        )
        self.refresh_references_button = QPushButton("REFRESH REFERENCES")
        self.refresh_references_button.setObjectName("ghostAction")
        self.refresh_references_button.setToolTip(
            "Rescan *.opa-reference.json manifests and validate their CSV files."
        )
        self.refresh_references_button.clicked.connect(
            self.refresh_user_references
        )
        selector_layout = QHBoxLayout()
        selector_layout.setSpacing(8)
        selector_layout.addWidget(self.reference_dataset_combo, 1)
        selector_layout.addWidget(self.open_reference_folder_button)
        selector_layout.addWidget(self.refresh_references_button)
        self.reference_scan_status = QLabel()
        self.reference_scan_status.setWordWrap(True)

        self.reference_source_label = QLabel()
        self.reference_satellite_label = QLabel()
        self.reference_epoch_label = QLabel()
        self.reference_sampling_label = QLabel()
        self.reference_frame_label = QLabel()
        self.reference_availability_label = QLabel()
        for label in (
            self.reference_source_label,
            self.reference_epoch_label,
            self.reference_sampling_label,
            self.reference_frame_label,
            self.reference_availability_label,
        ):
            label.setWordWrap(True)

        dataset_layout.addWidget(QLabel("Select:"), 0, 0)
        dataset_layout.addLayout(selector_layout, 0, 1)
        dataset_layout.addWidget(self.reference_scan_status, 1, 1)
        dataset_layout.addWidget(QLabel("Source:"), 2, 0)
        dataset_layout.addWidget(self.reference_source_label, 2, 1)
        dataset_layout.addWidget(QLabel("Satellite:"), 3, 0)
        dataset_layout.addWidget(self.reference_satellite_label, 3, 1)
        dataset_layout.addWidget(QLabel("Epoch:"), 4, 0)
        dataset_layout.addWidget(self.reference_epoch_label, 4, 1)
        dataset_layout.addWidget(QLabel("Sampling:"), 5, 0)
        dataset_layout.addWidget(self.reference_sampling_label, 5, 1)
        dataset_layout.addWidget(QLabel("Source frame:"), 6, 0)
        dataset_layout.addWidget(self.reference_frame_label, 6, 1)
        dataset_layout.addWidget(QLabel("Force model:"), 7, 0)
        self.reference_force_model_label = QLabel(
            "EGM96 4×4 + selectable DE440 Moon/Sun + physical box-wing SRP"
        )
        self.reference_force_model_label.setWordWrap(True)
        dataset_layout.addWidget(
            self.reference_force_model_label,
            7,
            1,
        )
        dataset_layout.addWidget(QLabel("Available:"), 8, 0)
        dataset_layout.addWidget(self.reference_availability_label, 8, 1)
        dataset_layout.addWidget(QLabel("Status:"), 9, 0)
        dataset_layout.addWidget(self.reference_dataset_status, 9, 1)
        dataset_layout.setColumnStretch(1, 1)
        self.set_reference_scan_status(self.reference_discovery_report)
        layout.addWidget(dataset_box)

        metrics_layout = QGridLayout()
        metrics_layout.setHorizontalSpacing(12)
        metrics_layout.setVerticalSpacing(12)

        card, self.reference_with_moon_value = (
            self.create_reference_metric_card(
                "FINAL POSITION ERROR",
                "Position residual at the final reference epoch",
            )
        )
        metrics_layout.addWidget(card, 0, 0)

        card, self.reference_without_moon_value = (
            self.create_reference_metric_card(
                "RMS POSITION ERROR",
                "Root-mean-square residual across the full trajectory",
            )
        )
        metrics_layout.addWidget(card, 0, 1)

        card, self.reference_effect_value = (
            self.create_reference_metric_card(
                "MAXIMUM POSITION ERROR",
                "Largest position residual over the validation interval",
            )
        )
        metrics_layout.addWidget(card, 0, 2)

        card, self.reference_effect_delta_value = (
            self.create_reference_metric_card(
                "FINAL VELOCITY ERROR",
                "Velocity residual at the final reference epoch",
            )
        )
        metrics_layout.addWidget(card, 0, 3)

        for column in range(4):
            metrics_layout.setColumnStretch(column, 1)
        layout.addLayout(metrics_layout)

        actions_box = QGroupBox("VALIDATION CONTROLS")
        actions_layout = QVBoxLayout(actions_box)
        actions_layout.setContentsMargins(18, 26, 18, 16)
        actions_layout.setSpacing(10)

        self.reference_calibration_checkbox = QCheckBox(
            "Use empirical reference calibration"
        )
        self.reference_calibration_checkbox.setChecked(False)
        self.reference_calibration_checkbox.setVisible(False)
        self.reference_calibration_checkbox.setToolTip(
            "Empirical calibration is disabled; validation is physical-only."
        )
        self.reference_calibration_mode_label = QLabel(
            "PHYSICAL ONLY — calibration, scale, fit and bias are disabled"
        )
        self.reference_calibration_mode_label.setWordWrap(True)
        _set_status_role(self.reference_calibration_mode_label, "ok")
        self.reference_calibration_checkbox.toggled.connect(
            self.reference_calibration_mode_changed
        )
        calibration_layout = QHBoxLayout()
        calibration_layout.setSpacing(12)
        calibration_layout.addWidget(self.reference_calibration_checkbox)
        calibration_layout.addWidget(
            self.reference_calibration_mode_label,
            1,
        )
        actions_layout.addLayout(calibration_layout)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        self.run_reference_button = QPushButton("RUN SELECTED MODEL")
        self.run_reference_button.setObjectName("primaryAction")
        self.run_reference_button.clicked.connect(
            self.run_reference_validation
        )
        self.cancel_reference_button = QPushButton("CANCEL")
        self.cancel_reference_button.setObjectName("dangerAction")
        self.cancel_reference_button.setEnabled(False)
        self.cancel_reference_button.clicked.connect(
            self.cancel_reference_validation
        )
        self.save_reference_csv_button = QPushButton(
            "EXPORT MODEL CSV"
        )
        self.save_reference_csv_button.setObjectName("ghostAction")
        self.save_reference_csv_button.setEnabled(False)
        self.save_reference_csv_button.clicked.connect(
            self.save_reference_validation_csv
        )
        for button in (
            self.run_reference_button,
            self.cancel_reference_button,
            self.save_reference_csv_button,
        ):
            button.setMinimumHeight(44)
        button_layout.addWidget(self.run_reference_button, 2)
        button_layout.addWidget(self.cancel_reference_button, 1)
        button_layout.addWidget(self.save_reference_csv_button, 1)
        actions_layout.addLayout(button_layout)

        self.reference_progress = QProgressBar()
        self.reference_progress.setRange(0, 100)
        self.reference_progress.setValue(0)
        self.reference_progress.setFormat("Ready")
        actions_layout.addWidget(self.reference_progress)
        # Put the single selected-model action directly below the force
        # cards so the control flow is visually unambiguous.
        layout.insertWidget(2, actions_box)

        graph_box = QGroupBox("VALIDATED MODEL / REFERENCE COMPARISON")
        graph_layout = QVBoxLayout(graph_box)
        graph_layout.setContentsMargins(14, 24, 14, 14)

        graph_controls = QHBoxLayout()
        graph_controls.setSpacing(10)
        graph_controls.addWidget(QLabel("Chart view:"))
        self.reference_chart_mode = QComboBox()
        self.reference_chart_mode.addItem(
            "MODEL + REFERENCE LONGITUDE",
            "longitude",
        )
        self.reference_chart_mode.addItem(
            "STATE RESIDUALS — ΔX / ΔY / ΔZ / ΔVx / ΔVy / ΔVz",
            "state_residuals",
        )
        self.reference_chart_mode.addItem(
            "X POSITION — MODEL + REFERENCE",
            "component_x",
        )
        self.reference_chart_mode.addItem(
            "Y POSITION — MODEL + REFERENCE",
            "component_y",
        )
        self.reference_chart_mode.addItem(
            "Z POSITION — MODEL + REFERENCE",
            "component_z",
        )
        self.reference_chart_mode.addItem(
            "POSITION ERROR",
            "position_error",
        )
        self.reference_chart_mode.addItem(
            "SCENARIO / COMMON-STATE MOON EFFECT",
            "separation",
        )
        self.reference_chart_mode.setMinimumHeight(36)
        self.reference_chart_mode.setToolTip(
            "State residuals are calculated row-by-row as model minus "
            "supplied reference. X/Y share one scale and Vx/Vy share one "
            "scale. Z and Vz keep their own detail scales so their small "
            "physical variations remain visible. "
            "Longitude, component overlays, absolute position error and "
            "common-state Moon sensitivity remain available as separate "
            "views."
        )
        self.reference_chart_mode.currentIndexChanged.connect(
            self.update_reference_chart
        )
        graph_controls.addWidget(self.reference_chart_mode)
        graph_controls.addStretch(1)
        graph_layout.addLayout(graph_controls)

        self.reference_graph = GraphWidget(figsize=(10, 6))
        self.reference_figure = self.reference_graph.figure
        self.reference_axis = self.reference_graph.ax
        self.reference_residual_axes = None
        self.reference_graph.setMinimumHeight(560)
        self.reference_graph.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )
        self.style_reference_axis()
        self.reference_axis.text(
            0.5,
            0.5,
            "Run validation to plot model and reference series",
            transform=self.reference_axis.transAxes,
            ha="center",
            va="center",
            color="#64748B",
            fontsize=11,
        )
        graph_layout.addWidget(self.reference_graph)
        layout.addWidget(graph_box)

        kepler_box = QGroupBox(
            "OSCULATING KEPLER ELEMENTS — MODEL INITIAL / FINAL"
        )
        kepler_layout = QVBoxLayout(kepler_box)
        kepler_layout.setContentsMargins(14, 24, 14, 14)
        self.reference_kepler_widget = KeplerComparisonWidget()
        kepler_layout.addWidget(self.reference_kepler_widget)
        layout.addWidget(kepler_box)

        results_box = QGroupBox("SCIENTIFIC SUMMARY")
        results_layout = QVBoxLayout(results_box)
        results_layout.setContentsMargins(14, 24, 14, 14)
        self.reference_output = QTextEdit()
        self.reference_output.setObjectName("referenceResults")
        self.reference_output.setReadOnly(True)
        self.reference_output.setMinimumHeight(280)
        self.reference_output.setPlaceholderText(
            "Validation metrics will appear here."
        )
        results_layout.addWidget(self.reference_output)
        layout.addWidget(results_box)

        scroll.setWidget(content)
        page_layout.addWidget(scroll)
        self.tabs.addTab(
            page,
            "REFERENCE LAB",
        )
        self.reference_dataset_combo.currentIndexChanged.connect(
            self.reference_dataset_changed
        )
        self.reference_dataset_changed()


    def reference_srp_configuration(self):
        """Resolve Reference Lab SRP inputs through the Propagation resolver."""

        if self.reference_srp_source_mode.currentData() == "manual":
            separate = self.reference_manual_srp_separate_panels.isChecked()
            return resolve_effective_area_srp_inputs(
                mode="panel_body" if separate else "combined",
                mass_kg=self.reference_manual_srp_mass.value(),
                total_area_m2=self.reference_manual_srp_total_area.value(),
                coefficient=self.reference_manual_srp_coefficient.value(),
                panel_area_m2=self.reference_manual_srp_panel_area.value(),
                panel_coefficient=self.reference_manual_srp_panel_coefficient.value(),
                body_area_m2=self.reference_manual_srp_body_area.value(),
                body_coefficient=self.reference_manual_srp_body_coefficient.value(),
            )
        profile_id = self.reference_spacecraft_selector.currentData()
        profile = self.profile_store.get(profile_id or self.active_profile_id)
        if profile.is_demo_geo_baseline:
            return {
                "mode": "demo_box_wing",
                "mode_label": "SYNTHETIC GEO DEMO physical box-wing",
                "mass_kg": profile.mass_kg,
                "area_m2": None,
                "coefficient": None,
                "components": (),
                "profile": profile,
            }
        configuration = resolve_effective_area_srp_inputs(
            mode="combined",
            mass_kg=profile.mass_kg,
            total_area_m2=profile.generic_srp_area_m2,
            coefficient=profile.srp_coefficient,
        )
        configuration["profile"] = profile
        return configuration

    def reference_srp_source_changed(self, _index=None):
        """Make selecting manual SRP an explicit, active force choice."""

        if self.reference_srp_source_mode.currentData() == "manual":
            self.reference_force_srp.setChecked(True)
        self.update_reference_srp_controls()


    def update_reference_srp_controls(self, *_args):
        if not hasattr(self, "reference_srp_source_mode"):
            return
        manual = self.reference_srp_source_mode.currentData() == "manual"
        panel_body = (
            manual and self.reference_manual_srp_separate_panels.isChecked()
        )
        derived_body_area = max(
            0.0,
            self.reference_manual_srp_total_area.value()
            - self.reference_manual_srp_panel_area.value(),
        )
        self.reference_manual_srp_body_area.blockSignals(True)
        self.reference_manual_srp_body_area.setValue(derived_body_area)
        self.reference_manual_srp_body_area.blockSignals(False)
        self.reference_spacecraft_selector.setEnabled(not manual)
        self.reference_manual_srp_separate_panels.setVisible(manual)
        for widget in (
            self.reference_manual_srp_mass,
            self.reference_manual_srp_mass_label,
            self.reference_manual_srp_total_area,
            self.reference_manual_srp_total_area_label,
        ):
            widget.setVisible(manual)
        for widget in (
            self.reference_manual_srp_coefficient,
            self.reference_manual_srp_coefficient_label,
        ):
            widget.setVisible(manual and not panel_body)
        for widget in (
            self.reference_manual_srp_panel_area,
            self.reference_manual_srp_panel_area_label,
            self.reference_manual_srp_panel_coefficient,
            self.reference_manual_srp_panel_coefficient_label,
            self.reference_manual_srp_body_area,
            self.reference_manual_srp_body_area_label,
            self.reference_manual_srp_body_coefficient,
            self.reference_manual_srp_body_coefficient_label,
        ):
            widget.setVisible(panel_body)
        try:
            configuration = self.reference_srp_configuration()
            area_text = (
                "detailed box-wing geometry"
                if configuration["area_m2"] is None
                else f"effective area {configuration['area_m2']:.9g} m²"
            )
            coefficient_text = (
                "epoch coefficient"
                if configuration["coefficient"] is None
                else f"CP {configuration['coefficient']:.12g}"
            )
            force_scale_text = ""
            if configuration["area_m2"] is not None:
                force_scale_text = (
                    " · A×CP/m "
                    f"{configuration['area_m2'] * configuration['coefficient'] / configuration['mass_kg']:.9g} "
                    "m²/kg"
                )
            self.reference_srp_summary.setText(self.tr(
                f"{configuration['mode_label']} · mass {configuration['mass_kg']:.9g} kg · "
                f"{area_text} · {coefficient_text}{force_scale_text}. Propagation and Reference Lab "
                "use the same SRP acceleration and effective-area resolver."
            ))
        except (ProfileValidationError, ValueError) as error:
            self.reference_srp_summary.setText(
                self.tr(f"Invalid SRP inputs: {error}")
            )


    def calculate_reference_srp_case(self, _checked=False):
        try:
            dataset_id = self.reference_dataset_combo.currentData() or DEFAULT_REFERENCE_DATASET_ID
            include_moon = bool(self.reference_force_moon.isChecked())
            use_srp_scenario = reference_dataset_has_scenario(
                dataset_id, include_moon, include_srp=True
            )
            reference = load_reference_scenario(
                include_moon,
                dataset_id,
                include_srp=use_srp_scenario,
            )
            epoch = reference["epoch"]
            r_sat = np.asarray(reference["states"][0, :3], dtype=float)
            r_sun = get_sun_position(utc_to_et(epoch))
            configuration = self.reference_srp_configuration()
            if configuration["area_m2"] is None:
                coefficient, coefficient_mode = resolved_solar_pressure_coefficient(epoch)
                kwargs = {}
            else:
                coefficient = configuration["coefficient"]
                coefficient_mode = configuration["mode_label"]
                kwargs = {
                    "area_m2": configuration["area_m2"],
                    "mass_kg": configuration["mass_kg"],
                }
            acceleration = solar_radiation_pressure(
                r_sat, r_sun, coefficient, **kwargs
            )
            illumination = sunlight_fraction(r_sat, r_sun)
            self.reference_srp_result.setPlainText(
                "SRP REFERENCE-EPOCH CALCULATION\n"
                f"Spacecraft: {configuration.get('profile', self.active_profile).display_name if configuration.get('profile') else 'Manual input'}\n"
                f"Epoch UTC: {epoch.isoformat()}\n"
                f"Model: {coefficient_mode}\n"
                f"Illumination: {illumination:.12f}\n"
                + (
                    f"Effective area: {configuration['area_m2']:.12g} m²\n"
                    f"Mass: {configuration['mass_kg']:.12g} kg\n"
                    if configuration["area_m2"] is not None
                    else "Geometry: SYNTHETIC GEO DEMO physical box-wing\n"
                )
                + f"CP: {coefficient:.12g}\n"
                f"aX: {acceleration[0]:.15e} km/s²\n"
                f"aY: {acceleration[1]:.15e} km/s²\n"
                f"aZ: {acceleration[2]:.15e} km/s²\n"
                f"|a|: {np.linalg.norm(acceleration):.15e} km/s²"
            )
        except Exception as error:
            self.reference_srp_result.setPlainText(
                f"SRP CALCULATION ERROR\n\n{type(error).__name__}: {error}"
            )


    def style_reference_axis(self, y_label="Position error [km]"):

        axis = self.reference_axis
        GraphWidget.style_axis(axis)
        axis.set_xlabel("Elapsed time [days]")
        axis.set_ylabel(y_label)


    def _set_reference_single_axis(self):

        if len(self.reference_figure.axes) != 1:
            self.reference_figure.clear()
            self.reference_axis = self.reference_figure.add_subplot(111)
            self.reference_graph.ax = self.reference_axis
        else:
            self.reference_axis = self.reference_figure.axes[0]
            self.reference_graph.ax = self.reference_axis
        self.reference_residual_axes = None
        return self.reference_axis


    def _set_reference_residual_axes(self):

        if len(self.reference_figure.axes) != 6:
            self.reference_figure.clear()
            axes = self.reference_figure.subplots(2, 3, sharex=True)
            self.reference_residual_axes = tuple(axes.ravel())
        else:
            self.reference_residual_axes = tuple(self.reference_figure.axes)
        # GraphWidget-in pointer koordinat sistemi üçün əsas ox həmişə mövcuddur.
        self.reference_axis = self.reference_residual_axes[0]
        self.reference_graph.ax = self.reference_axis
        return self.reference_residual_axes


    def update_reference_run_button_availability(self):

        dataset_id = (
            self.reference_dataset_combo.currentData()
            or DEFAULT_REFERENCE_DATASET_ID
        )
        running = (
            self.reference_comparison_thread is not None
            and self.reference_comparison_thread.isRunning()
        )
        include_moon = self.reference_force_moon.isChecked()
        include_sun = self.reference_force_sun.isChecked()
        include_srp = self.reference_force_srp.isChecked()
        scenario_available = reference_dataset_has_scenario(
            dataset_id,
            include_moon,
            include_srp=include_srp,
        )
        dataset = get_reference_dataset(dataset_id)
        required_force_model = dataset.get("required_force_model")
        # required_force_model daxilində olan açar bu hesabat üçün dəyişdirilə
        # bilməz. Göstərilməyən açar istifadəçi tərəfindən seçilə bilər; buna görə
        # Reference 5 Günəşi aktiv saxlayır, Ay isə təqdim edilmiş cüt ssenari
        # arasında dəyişdirilə bilir.
        force_model_matches = (
            required_force_model is None
            or (
                (
                    "include_moon" not in required_force_model
                    or include_moon
                    == bool(required_force_model["include_moon"])
                )
                and (
                    "include_sun" not in required_force_model
                    or include_sun
                    == bool(required_force_model["include_sun"])
                )
                and (
                    "include_srp" not in required_force_model
                    or include_srp
                    == bool(required_force_model["include_srp"])
                )
            )
        )
        selected_parts = ["EARTH"]
        if include_moon:
            selected_parts.append("MOON")
        if include_sun:
            selected_parts.append("SUN β")
        if include_srp:
            selected_parts.append("SRP")
        label = " + ".join(selected_parts)
        required_parts = ["EARTH"]
        if dataset.get("user_supplied"):
            declared_parts = ["Earth gravity"]
            if required_force_model.get("include_moon"):
                declared_parts.append("DE440 Moon third-body")
            if required_force_model.get("include_sun"):
                declared_parts.append("DE440 Sun third-body")
            if required_force_model.get("include_srp"):
                declared_parts.append("SRP")
            self.reference_description.setText(
                "This user-supplied reference was discovered from a validated "
                "opa-reference/v1 manifest. Declared force model: "
                + " + ".join(declared_parts)
                + ". Its CSV states use an exact J2000/ICRF time grid; "
                "unsupported or ambiguous files are not registered."
            )
        elif required_force_model is not None:
            if required_force_model.get("include_moon"):
                required_parts.append("MOON")
            if required_force_model.get("include_sun"):
                required_parts.append("SUN")
            if required_force_model.get("include_srp"):
                required_parts.append("SRP")
        required_label = " + ".join(required_parts)
        self.run_reference_button.setText(
            f"RUN SELECTED — {label}"
            if scenario_available and force_model_matches
            else (
                f"REFERENCE REQUIRES {required_label}"
                if required_force_model is not None
                else "SELECTED MOON SCENARIO NOT PROVIDED"
            )
        )
        self.run_reference_button.setEnabled(
            scenario_available and force_model_matches and not running
        )
        moon_locked = (
            required_force_model is not None
            and "include_moon" in required_force_model
        )
        sun_locked = (
            required_force_model is not None
            and "include_sun" in required_force_model
        )
        srp_locked = (
            required_force_model is not None
            and "include_srp" in required_force_model
        )
        self.reference_force_moon.setEnabled(
            not running and not moon_locked
        )
        self.reference_force_sun.setEnabled(
            not running and not sun_locked
        )
        self.reference_force_srp.setEnabled(
            not running and not srp_locked
        )
        self.reference_calibration_checkbox.setEnabled(False)


    def reference_force_selection_changed(self, _checked=None):

        if (
            self.reference_comparison_thread is not None
            and self.reference_comparison_thread.isRunning()
        ):
            return
        include_sun = self.reference_force_sun.isChecked()
        include_moon = self.reference_force_moon.isChecked()
        include_srp = self.reference_force_srp.isChecked()
        dataset_id = self.reference_dataset_combo.currentData()
        scenario_role = int(Qt.ItemDataRole.UserRole) + 1
        srp_role = int(Qt.ItemDataRole.UserRole) + 2
        # Ay açarı dəyişəndə seçim uyğun görünən sətrə keçirilir. Datasetin özü
        # dəyişmədiyinə və əvvəl hesablanmış cüt nəticə saxlanmalı olduğuna görə
        # bu keçid zamanı siqnallar müvəqqəti bloklanır.
        for item_index in range(self.reference_dataset_combo.count()):
            if (
                self.reference_dataset_combo.itemData(item_index)
                == dataset_id
                and self.reference_dataset_combo.itemData(
                    item_index,
                    scenario_role,
                )
                == include_moon
                and self.reference_dataset_combo.itemData(
                    item_index,
                    srp_role,
                )
                == include_srp
            ):
                self.reference_dataset_combo.blockSignals(True)
                self.reference_dataset_combo.setCurrentIndex(item_index)
                self.reference_dataset_combo.blockSignals(False)
                break
        previous_sun = self._reference_selection_sun_mode
        previous_srp = getattr(self, "_reference_selection_srp_mode", None)
        self.set_reference_metric_values()
        if (
            previous_sun is None
            or previous_sun != include_sun
            or previous_srp is None
            or previous_srp != include_srp
        ):
            self.reference_scenario_results = {True: None, False: None}
            self.latest_reference_comparison = None
            self.reference_validation_settings = None
            self.set_reference_metric_values()
            self.save_reference_csv_button.setEnabled(False)
            self.save_reference_csv_button.setText("EXPORT MODEL CSV")
        self._reference_selection_sun_mode = include_sun
        self._reference_selection_srp_mode = include_srp

        selected_parts = ["EGM96 4×4"]
        if self.reference_force_moon.isChecked():
            selected_parts.append("DE440 Moon")
        if self.reference_force_sun.isChecked():
            selected_parts.append("DE440 Sun")
        if self.reference_force_srp.isChecked():
            selected_parts.append("SRP BOX-WING / TrueSun")
        model_text = " + ".join(selected_parts)
        self.reference_force_model_label.setText(model_text)
        self.reference_output.setPlainText(
            "FORCE MODEL UPDATED\n\n"
            f"Selected: {model_text}\n"
            "Press RUN SELECTED MODEL to execute this exact configuration."
        )
        self.update_reference_run_button_availability()
        self.update_reference_chart()


    def set_reference_scan_status(self, report):
        """Show a concise manifest discovery result without hiding data QA."""

        loaded_count = int(report.get("loaded_count", 0))
        errors = tuple(report.get("errors", ()))
        if errors:
            first_error = errors[0]["error"]
            self.reference_scan_status.setText(
                f"USER REFERENCE SCAN — {loaded_count} loaded, "
                f"{len(errors)} rejected: {first_error}"
            )
            _set_status_role(self.reference_scan_status, "error")
        elif loaded_count:
            self.reference_scan_status.setText(
                f"USER REFERENCES — {loaded_count} validated and loaded"
            )
            _set_status_role(self.reference_scan_status, "ok")
        else:
            self.reference_scan_status.setText(
                "USER REFERENCES — none found; use the folder guide and "
                "*.opa-reference.json template"
            )
            _set_status_role(self.reference_scan_status, "warning")


    def open_reference_folder(self):
        """Open the auditable reference root in the native file manager."""

        REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
        opened = QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(REFERENCE_DIR.resolve()))
        )
        if opened:
            self.statusBar().showMessage(
                f"Reference folder opened: {REFERENCE_DIR.resolve()}",
                6000,
            )
        else:
            self.statusBar().showMessage(
                f"Reference folder could not be opened: "
                f"{REFERENCE_DIR.resolve()}",
                9000,
            )
        return opened


    def refresh_user_references(self):
        """Rescan drop-in manifests, preserve selection and refresh the UI."""

        scenario_role = int(Qt.ItemDataRole.UserRole) + 1
        srp_role = int(Qt.ItemDataRole.UserRole) + 2
        selected = (
            self.reference_dataset_combo.currentData(),
            self.reference_dataset_combo.currentData(scenario_role),
            self.reference_dataset_combo.currentData(srp_role),
        )
        report = reload_user_reference_datasets()
        self.reference_dataset_combo.blockSignals(True)
        try:
            populate_reference_scenario_combo(
                self.reference_dataset_combo,
                default_index=2,
            )
            for item_index in range(self.reference_dataset_combo.count()):
                if (
                    self.reference_dataset_combo.itemData(item_index)
                    == selected[0]
                    and self.reference_dataset_combo.itemData(
                        item_index,
                        scenario_role,
                    )
                    == selected[1]
                    and self.reference_dataset_combo.itemData(
                        item_index,
                        srp_role,
                    )
                    == selected[2]
                ):
                    self.reference_dataset_combo.setCurrentIndex(item_index)
                    break
        finally:
            self.reference_dataset_combo.blockSignals(False)
        self.reference_discovery_report = report
        self.set_reference_scan_status(report)
        self._reference_selected_dataset_id = None
        self.reference_dataset_changed()
        self.refresh_localized_text()
        self.statusBar().showMessage(
            f"Reference scan complete: {report['loaded_count']} loaded, "
            f"{report['error_count']} rejected.",
            7000,
        )
        return report


    def reference_dataset_changed(self, _index=None):

        dataset_id = (
            self.reference_dataset_combo.currentData()
            or DEFAULT_REFERENCE_DATASET_ID
        )
        srp_role = int(Qt.ItemDataRole.UserRole) + 2
        selected_include_srp = self.reference_dataset_combo.currentData(
            srp_role
        )
        selected_key = (dataset_id, bool(selected_include_srp))
        dataset_replaced = (
            self._reference_selected_dataset_id != selected_key
        )
        # Eyni cüt datasetin iki görünən sətri arasında keçid ilk tamamlanmış
        # ssenarini saxlamalıdır. Həqiqətən fərqli dataset seçildikdə isə bütün
        # saxlanmış metriklər və ixrac vəziyyəti sıfırlanır.
        self._reference_selected_dataset_id = selected_key
        dataset = get_reference_dataset(dataset_id)
        scenario_group = (
            dataset.get("srp_scenarios", {})
            if selected_include_srp
            else dataset["scenarios"]
        )
        available = tuple(scenario_group)
        available_names = [
            scenario_group[include_moon]["name"]
            for include_moon in available
        ]

        scenario_role = int(Qt.ItemDataRole.UserRole) + 1
        selected_include_moon = self.reference_dataset_combo.currentData(
            scenario_role
        )
        if selected_include_moon is not None:
            # İlkin seçim qutusunun vəziyyətini görünən model sətri müəyyən edir;
            # aşağıdakı required_force_model yenə də məcburi kilidləri tətbiq edir.
            self.reference_force_moon.blockSignals(True)
            self.reference_force_moon.setChecked(
                bool(selected_include_moon)
            )
            self.reference_force_moon.blockSignals(False)
        if selected_include_srp is not None:
            self.reference_force_srp.blockSignals(True)
            self.reference_force_srp.setChecked(
                bool(selected_include_srp)
            )
            self.reference_force_srp.blockSignals(False)

        required_force_model = dataset.get("required_force_model")
        if required_force_model is not None:
            self.reference_force_moon.blockSignals(True)
            self.reference_force_sun.blockSignals(True)
            self.reference_force_srp.blockSignals(True)
            if "include_moon" in required_force_model:
                self.reference_force_moon.setChecked(
                    bool(required_force_model["include_moon"])
                )
            if "include_sun" in required_force_model:
                self.reference_force_sun.setChecked(
                    bool(required_force_model["include_sun"])
                )
            if "include_srp" in required_force_model:
                self.reference_force_srp.setChecked(
                    bool(required_force_model["include_srp"])
                )
            self.reference_force_moon.blockSignals(False)
            self.reference_force_sun.blockSignals(False)
            self.reference_force_srp.blockSignals(False)

        self.reference_calibration_checkbox.blockSignals(True)
        self.reference_calibration_checkbox.setChecked(False)
        self.reference_calibration_checkbox.setText(
            "Use empirical reference calibration"
        )
        self.reference_calibration_checkbox.blockSignals(False)
        self.reference_calibration_checkbox.setEnabled(False)

        if dataset_replaced:
            self.reference_scenario_results = {True: None, False: None}
            self.latest_reference_comparison = None
            self.reference_validation_settings = None
            self.set_reference_metric_values()
            self.save_reference_csv_button.setEnabled(False)
            self.save_reference_csv_button.setText("EXPORT MODEL CSV")
        self.reference_source_label.setText(dataset["source"])
        satellite_name = dataset.get(
            "satellite_name",
            TARGET_SATELLITE_DISPLAY_NAME,
        )
        norad_id = dataset.get("norad_id", TARGET_SATELLITE_NORAD_ID)
        self.reference_satellite_label.setText(
            f"{satellite_name} / NORAD {norad_id}"
            if norad_id is not None
            else satellite_name
        )
        self.reference_epoch_label.setText(
            dataset["epoch"].strftime("%Y-%m-%d %H:%M:%S UTC")
        )
        self.reference_sampling_label.setText(
            f"{dataset['rows']:,} states, "
            f"{dataset['step_seconds'] / 60.0:.0f}-minute cadence"
        )
        self.reference_frame_label.setText(
            f"{dataset['source_frame']} → {dataset['model_frame']}"
            if dataset["source_frame"] != dataset["model_frame"]
            else dataset["source_frame"]
        )
        self.reference_availability_label.setText(
            " + ".join(available_names)
        )

        if required_force_model is not None:
            force_parts = ["Earth gravity"]
            if required_force_model.get("include_moon"):
                force_parts.append("DE440 Moon third-body")
            if required_force_model.get("include_sun"):
                force_parts.append("DE440 Sun third-body")
            if required_force_model.get("include_srp"):
                force_parts.append("SRP")
            if len(available) == 2:
                self.reference_description.setText(
                    "This paired reference dataset keeps "
                    + " + ".join(force_parts)
                    + " active in both scenarios. Toggle Moon to compare "
                    "Earth+Sun against Earth+Sun+Moon. The Sun switch is "
                    "locked and no empirical correction is used."
                )
            else:
                self.reference_description.setText(
                    "This immutable reference dataset contains "
                    + " + ".join(force_parts)
                    + ". The matching force switches are locked for a "
                    "scientifically valid physical-only comparison; no "
                    "missing series is synthesized."
                )
        elif len(available) == 2:
            self.reference_description.setText(
                "This dataset provides independent Moon-on and Moon-off "
                "reference cases. Select Moon and Sun in the force cards, "
                "then use the single RUN SELECTED action. Matching paired "
                "results are combined automatically; Sun-on results are "
                "reported as a sensitivity residual because the dataset has no "
                "solar case."
            )
        else:
            self.reference_description.setText(
                "This dataset provides only a WITH MOON reference series. "
                "The unavailable WITHOUT MOON scenario is disabled and no "
                "missing reference trajectory is synthesized. Sun β remains "
                "selectable for the available scenario."
            )

        srp_parameters = dataset.get("srp_parameters")
        if srp_parameters is not None and dataset.get("user_supplied"):
            self.reference_description.setText(
                "This user-supplied reference uses the force configuration "
                "declared in its manifest. Its SRP parameters are area "
                f"{srp_parameters['area_m2']:.6g} m², mass "
                f"{srp_parameters['mass_kg']:.6g} kg and coefficient "
                f"{srp_parameters['coefficient']:.12g}. The CSV states are "
                "validated as an exact J2000/ICRF time grid before use."
            )
        elif srp_parameters is not None:
            self.reference_description.setText(
                "This immutable SYNTHETIC GEO DEMO reference contains Earth gravity, "
                "DE440 Moon, DE440 Sun and SRP. The effective Sun-tracking "
                f"area is {srp_parameters['area_m2']:.1f} m², mass is "
                f"{srp_parameters['mass_kg']:.0f} kg, and CP "
                f"{srp_parameters['coefficient']:.9f} was reverse-engineered "
                "by least-squares fitting of the complete 30-day position "
                "history. All matching force switches are locked."
            )

        try:
            loaded = [
                load_reference_scenario(
                    include_moon,
                    dataset_id,
                    include_srp=bool(selected_include_srp),
                )
                for include_moon in available
            ]
            ignored_rows = sum(
                item.get("ignored_terminal_rows", 0)
                for item in loaded
            )
            status = (
                "READY — all available series passed integrity checks"
            )
            if ignored_rows:
                status += (
                    f"; {ignored_rows} off-grid terminal row ignored"
                )
            self.reference_dataset_status.setText(status)
            _set_status_role(self.reference_dataset_status, "ok")
        except Exception as error:
            self.reference_dataset_status.setText(
                f"UNAVAILABLE — {type(error).__name__}: {error}"
            )
            _set_status_role(self.reference_dataset_status, "error")

        self.reference_output.setPlainText(
            f"{dataset['label'].upper()} SELECTED\n\n"
            f"Available scenarios: {' + '.join(available_names)}\n"
            + (
                "Required force model: EARTH"
                + (
                    " + MOON"
                    if required_force_model.get("include_moon")
                    else ""
                )
                + (
                    " + SUN"
                    if required_force_model.get("include_sun")
                    else ""
                )
                + "\n"
                if required_force_model is not None
                else ""
            )
            +
            f"Source frame: {dataset['source_frame']}\n"
            f"Model frame: {dataset['model_frame']}"
        )
        self.reference_progress.setValue(0)
        self.reference_progress.setFormat("Ready")
        # Residual small-multiples are the primary validation view. Longitude
        # remains available as a separate, unchanged chart mode.
        residual_index = self.reference_chart_mode.findData(
            "state_residuals"
        )
        self.reference_chart_mode.setCurrentIndex(
            residual_index if residual_index >= 0 else 0
        )
        self.update_reference_run_button_availability()
        self.reference_force_selection_changed()


    def reference_calibration_mode_changed(self, checked):

        if checked:
            self.reference_calibration_checkbox.blockSignals(True)
            self.reference_calibration_checkbox.setChecked(False)
            self.reference_calibration_checkbox.blockSignals(False)
        self.reference_scenario_results = {True: None, False: None}
        self.latest_reference_comparison = None
        self.reference_validation_settings = None
        self.set_reference_metric_values()
        self.save_reference_csv_button.setEnabled(False)

        self.reference_force_model_label.setText(
            "EGM96 4×4 + physical, unmodified DE440 forces"
        )
        self.reference_calibration_mode_label.setText(
            "PHYSICAL ONLY — calibration, scale, fit and bias are disabled"
        )
        _set_status_role(self.reference_calibration_mode_label, "ok")
        self.reference_output.setPlainText(
            "PHYSICAL-ONLY MODE\n\n"
            "No empirical scale, fit, bias, or artificial adjustment "
            "can be applied."
        )
        self.reference_force_selection_changed()


    def update_reference_chart(self, _index=None):

        with_moon = self.reference_scenario_results[True]
        without_moon = self.reference_scenario_results[False]
        result = self.latest_reference_comparison
        mode = self.reference_chart_mode.currentData()

        available = [
            scenario
            for scenario in (with_moon, without_moon)
            if scenario is not None
        ]
        if not available:
            axis = self._set_reference_single_axis()
            axis.clear()
            self.style_reference_axis()
            axis.text(
                0.5,
                0.5,
                "Run either scenario to plot model and reference data",
                transform=axis.transAxes,
                ha="center",
                va="center",
                color="#64748B",
                fontsize=11,
            )
            self.reference_graph.draw_idle()
            return

        if mode == "state_residuals":
            axes = self._set_reference_residual_axes()
            component_names = ("ΔX", "ΔY", "ΔZ", "ΔVx", "ΔVy", "ΔVz")
            units = ("km", "km", "km", "km/s", "km/s", "km/s")
            scenario_series = []
            if with_moon is not None:
                scenario_series.append((with_moon, "With Moon", "#38BDF8"))
            if without_moon is not None:
                scenario_series.append((without_moon, "Without Moon", "#F59E0B"))
            plotted_residuals = []
            for component_index, axis in enumerate(axes):
                axis.clear()
                GraphWidget.style_axis(axis)
                component_residuals = []
                for scenario, label, color in scenario_series:
                    residual = (
                        np.asarray(scenario["model_states"], dtype=float)
                        - np.asarray(scenario["states"], dtype=float)
                    )[:, component_index]
                    component_residuals.append(residual)
                    axis.plot(
                        np.asarray(scenario["elapsed_seconds"], dtype=float)
                        / 86400.0,
                        residual,
                        color=color,
                        linewidth=1.35,
                        label=label,
                    )
                axis.axhline(
                    0.0,
                    color="#94A3B8",
                    linestyle="--",
                    linewidth=0.8,
                )
                if component_index in (0, 1):
                    scale_label = "shared X/Y scale"
                elif component_index == 2:
                    scale_label = "Z detail scale"
                elif component_index in (3, 4):
                    scale_label = "shared Vx/Vy scale"
                else:
                    scale_label = "Vz detail scale"
                axis.set_title(
                    f"{component_names[component_index]} residual · {scale_label}",
                    pad=8,
                    fontsize=10,
                )
                axis.set_ylabel(units[component_index])
                if component_index >= 3:
                    axis.set_xlabel("Elapsed time [days]")
                axis.margins(x=0.01)
                plotted_residuals.append(component_residuals)

            # Cartesian components with the same unit must be shown on the
            # same scale. Independent autoscaling made the sub-metre Z/Vz
            # residual fill an entire panel next to hundred-metre X/Y errors,
            # which looked chaotic even though it was the smallest and
            # smoothest component.
            for component_group in ((0, 1), (2,), (3, 4), (5,)):
                finite_peaks = [
                    float(np.max(np.abs(residual[np.isfinite(residual)])))
                    for component_index in component_group
                    for residual in plotted_residuals[component_index]
                    if np.any(np.isfinite(residual))
                ]
                common_limit = max(finite_peaks, default=1.0)
                if common_limit <= 0.0:
                    common_limit = 1.0
                common_limit *= 1.05
                for component_index in component_group:
                    axes[component_index].set_ylim(-common_limit, common_limit)
            legend = axes[0].legend(
                facecolor="#0F172A",
                edgecolor="#334155",
                labelcolor="#E2E8F0",
                loc="upper left",
            )
            legend.get_frame().set_alpha(0.9)
            self.reference_figure.suptitle(
                "Physical state residuals — paired X/Y and Vx/Vy scales; detailed Z and Vz",
                color="#F8FAFC",
                fontsize=12,
            )
            self.reference_figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.96), pad=1.2)
            self.reference_graph.draw_idle()
            return

        axis = self._set_reference_single_axis()
        axis.clear()

        if mode == "longitude":
            self.style_reference_axis(
                "Earth-fixed longitude [deg E]"
            )
            series = []
            if with_moon is not None:
                series.extend((
                    (
                        with_moon,
                        with_moon["model_longitude_deg"],
                        "Our model - With Moon",
                        "#38BDF8",
                        "-",
                        2.2,
                    ),
                    (
                        with_moon,
                        with_moon["reference_longitude_deg"],
                        "Reference - With Moon",
                        "#BAE6FD",
                        "--",
                        1.9,
                    ),
                ))
            if without_moon is not None:
                series.extend((
                    (
                        without_moon,
                        without_moon["model_longitude_deg"],
                        "Our model - Without Moon",
                        "#F59E0B",
                        "-",
                        2.2,
                    ),
                    (
                        without_moon,
                        without_moon["reference_longitude_deg"],
                        "Reference - Without Moon",
                        "#FDE68A",
                        "--",
                        1.9,
                    ),
                ))
            for scenario, values, label, color, line_style, width in series:
                axis.plot(
                    scenario["elapsed_seconds"] / 86400.0,
                    values,
                    color=color,
                    linestyle=line_style,
                    linewidth=width,
                    label=label,
                )
            axis.axhline(
                TARGET_LONGITUDE_DEG - LONGITUDE_TOLERANCE_DEG,
                color="#EF4444",
                linestyle="--",
                linewidth=1.4,
                label=(
                    f"MIN {TARGET_LONGITUDE_DEG - LONGITUDE_TOLERANCE_DEG:.2f}°E"
                ),
            )
            axis.axhline(
                TARGET_LONGITUDE_DEG + LONGITUDE_TOLERANCE_DEG,
                color="#EF4444",
                linestyle="--",
                linewidth=1.4,
                label=(
                    f"MAX {TARGET_LONGITUDE_DEG + LONGITUDE_TOLERANCE_DEG:.2f}°E"
                ),
            )
            axis.set_title(
                f"Absolute Earth-fixed longitude and {TARGET_LONGITUDE_DEG:.1f}°E station-keeping band",
                pad=12,
                fontsize=11,
            )
            legend_columns = 2 if len(series) > 2 else 1

        elif mode in (
            "component_x",
            "component_y",
            "component_z",
        ):
            component_index = {
                "component_x": 0,
                "component_y": 1,
                "component_z": 2,
            }[mode]
            component_name = "XYZ"[component_index]
            self.style_reference_axis(
                f"{component_name} position [km]"
            )
            series = []
            if with_moon is not None:
                series.extend((
                    (
                        with_moon,
                        with_moon["model_states"][:, component_index],
                        f"Our model - With Moon ({component_name})",
                        "#38BDF8",
                        "-",
                        2.2,
                    ),
                    (
                        with_moon,
                        with_moon["states"][:, component_index],
                        f"Reference - With Moon ({component_name})",
                        "#BAE6FD",
                        "--",
                        1.9,
                    ),
                ))
            if without_moon is not None:
                series.extend((
                    (
                        without_moon,
                        without_moon["model_states"][:, component_index],
                        f"Our model - Without Moon ({component_name})",
                        "#F59E0B",
                        "-",
                        2.2,
                    ),
                    (
                        without_moon,
                        without_moon["states"][:, component_index],
                        f"Reference - Without Moon ({component_name})",
                        "#FDE68A",
                        "--",
                        1.9,
                    ),
                ))
            for scenario, values, label, color, line_style, width in series:
                axis.plot(
                    scenario["elapsed_seconds"] / 86400.0,
                    values,
                    color=color,
                    linestyle=line_style,
                    linewidth=width,
                    label=label,
                )
            axis.set_title(
                f"{component_name}-axis model and reference position",
                pad=12,
                fontsize=11,
            )
            legend_columns = 2 if len(series) > 2 else 1

        elif mode == "separation":
            self.style_reference_axis(
                "With/without Moon separation [km]"
            )
            if result is None:
                dataset_id = (
                    self.reference_dataset_combo.currentData()
                    or DEFAULT_REFERENCE_DATASET_ID
                )
                both_available = all(
                    reference_dataset_has_scenario(dataset_id, include_moon)
                    for include_moon in (True, False)
                )
                if both_available:
                    missing_name = (
                        "WITHOUT MOON"
                        if with_moon is not None
                        else "WITH MOON"
                    )
                    message = (
                        f"Run {missing_name} to calculate Moon-effect separation"
                    )
                    title = "Both independent scenarios are required"
                else:
                    message = (
                        "Selected dataset has no WITHOUT MOON reference series"
                    )
                    title = "Separation comparison is unavailable"
                axis.text(
                    0.5,
                    0.5,
                    message,
                    transform=axis.transAxes,
                    ha="center",
                    va="center",
                    color="#94A3B8",
                    fontsize=11,
                )
                axis.set_title(
                    title,
                    pad=12,
                    fontsize=11,
                )
                self.reference_figure.tight_layout(pad=1.2)
                self.reference_graph.draw_idle()
                return
            elapsed_days = result["elapsed_seconds"] / 86400.0
            axis.plot(
                elapsed_days,
                result["model_separation_km"],
                color="#A78BFA",
                linewidth=2.2,
                label=(
                    "Physical model — independent starts"
                ),
            )
            axis.plot(
                elapsed_days,
                result["reference_separation_km"],
                color="#2DD4BF",
                linestyle="--",
                linewidth=2.0,
                label="Reference — independent starts",
            )
            if "pure_moon_separation_km" in result:
                axis.plot(
                    elapsed_days,
                    result["pure_moon_separation_km"],
                    color="#F59E0B",
                    linestyle=":",
                    linewidth=2.0,
                    label=(
                        "Physical DE440 Moon effect — common start"
                    ),
                )
            axis.set_title(
                "Independent comparison and common-state Moon sensitivity",
                pad=12,
                fontsize=11,
            )
            legend_columns = 1

        else:
            self.style_reference_axis("Position error [km]")
            if with_moon is not None:
                axis.plot(
                    with_moon["elapsed_seconds"] / 86400.0,
                    with_moon["position_error_km"],
                    color="#38BDF8",
                    linewidth=2.0,
                    label="Our model vs reference - With Moon",
                )
            if without_moon is not None:
                axis.plot(
                    without_moon["elapsed_seconds"] / 86400.0,
                    without_moon["position_error_km"],
                    color="#F59E0B",
                    linewidth=2.0,
                    label="Our model vs reference - Without Moon",
                )
            axis.axhline(
                0.0,
                color="#94A3B8",
                linestyle="--",
                linewidth=1.4,
                label="Reference baseline (zero error)",
            )
            axis.set_title(
                "Model position error against each reference series",
                pad=12,
                fontsize=11,
            )
            legend_columns = 1

        legend = axis.legend(
            facecolor="#0F172A",
            edgecolor="#334155",
            labelcolor="#E2E8F0",
            loc="upper left",
            ncol=legend_columns,
        )
        legend.get_frame().set_alpha(0.9)
        self.reference_figure.tight_layout(pad=1.2)
        self.reference_graph.draw_idle()


    def run_reference_validation(self, _checked=False):

        if (
            self.reference_comparison_thread is not None
            and self.reference_comparison_thread.isRunning()
        ):
            return
        if (
            self.propagation_thread is not None
            and self.propagation_thread.isRunning()
        ):
            self.reference_output.setPlainText(
                "REFERENCE VALIDATION BUSY\n\n"
                "Wait for the manual propagation to finish or cancel it."
            )
            return
        if self.eclipse_thread is not None and self.eclipse_thread.isRunning():
            self.reference_output.setPlainText(
                "REFERENCE VALIDATION BUSY\n\n"
                "Wait for the standalone Eclipse calculation to finish or "
                "cancel it."
            )
            return

        try:
            include_moon = self.reference_force_moon.isChecked()
            include_sun = self.reference_force_sun.isChecked()
            include_srp = self.reference_force_srp.isChecked()
            dataset_id = (
                self.reference_dataset_combo.currentData()
                or DEFAULT_REFERENCE_DATASET_ID
            )
            calibration_enabled = False
            load_reference_scenario(
                include_moon,
                dataset_id,
                include_srp=include_srp,
            )
            settings = self.get_numerical_settings()
            manual_srp_overrides = None
            if (
                include_srp
                and self.reference_srp_source_mode.currentData() == "manual"
            ):
                manual_configuration = self.reference_srp_configuration()
                manual_srp_overrides = {
                    "srp_coefficient": manual_configuration["coefficient"],
                    "srp_area_m2": manual_configuration["area_m2"],
                    "srp_mass_kg": manual_configuration["mass_kg"],
                }
        except Exception as error:
            self.reference_output.setPlainText(
                "REFERENCE VALIDATION ERROR\n\n"
                f"{type(error).__name__}: {error}"
            )
            return

        settings_signature = {
            **settings,
            "calibration_enabled": calibration_enabled,
            "dataset_id": dataset_id,
            "include_sun": include_sun,
            "include_srp": include_srp,
            "manual_srp_overrides": (
                tuple(sorted(manual_srp_overrides.items()))
                if manual_srp_overrides
                else None
            ),
        }
        if self.reference_validation_settings != settings_signature:
            self.reference_scenario_results = {
                True: None,
                False: None,
            }
            self.set_reference_metric_values()
            self.reference_validation_settings = settings_signature

        selected_forces = ["EARTH"]
        if include_moon:
            selected_forces.append("MOON")
        if include_sun:
            selected_forces.append("SUN")
        if include_srp:
            selected_forces.append("SRP")
        scenario_name = " + ".join(selected_forces)
        self.reference_scenario_results[include_moon] = None
        self.latest_reference_comparison = None
        self.latest_reference_scenario = None
        self.save_reference_csv_button.setEnabled(False)
        self.set_reference_metric_values(running=True)
        self.update_reference_chart()

        self.run_reference_button.setEnabled(False)
        self.reference_force_moon.setEnabled(False)
        self.reference_force_sun.setEnabled(False)
        self.reference_force_srp.setEnabled(False)
        self.reference_calibration_checkbox.setEnabled(False)
        self.reference_dataset_combo.setEnabled(False)
        self.cancel_reference_button.setEnabled(True)
        self.reference_progress.setValue(0)
        self.reference_progress.setFormat(
            f"Running {scenario_name} — %p%"
        )
        self.reference_output.setPlainText(
            f"{scenario_name} VALIDATION STARTED\n\n"
            f"Dataset: {get_reference_dataset(dataset_id)['label']}\n"
            f"Force model: {scenario_name}\n"
            "Mode: PHYSICAL ONLY\n"
            f"IERS EOP: {'ON' if is_eop_enabled() else 'OFF'}\n"
            "Applied lunar scale: NONE — raw DE440 acceleration\n\n"
            + (
                "Manual SRP override: "
                f"area {manual_srp_overrides['srp_area_m2']:.9g} m² / "
                f"mass {manual_srp_overrides['srp_mass_kg']:.9g} kg / "
                f"CP {manual_srp_overrides['srp_coefficient']:.12g}\n\n"
                if manual_srp_overrides
                else ""
            )
            + "1. Independent 30-day propagation\n"
            "2. Row-by-row reference comparison\n"
            "3. Position, velocity and longitude metrics\n"
            + (
                "4. Solar-force residual diagnostics\n\n"
                if include_sun
                else "\n"
            )
            + "The interface remains responsive."
        )
        self.reference_active_scenario = include_moon

        self._reference_timer_was_active = self.timer.isActive()
        if self._reference_timer_was_active:
            self.timer.stop()

        self.reference_comparison_thread = QThread(self)
        self.reference_comparison_worker = ReferenceComparisonWorker(
            settings,
            include_moon,
            include_sun,
            include_srp,
            calibration_enabled,
            dataset_id,
            manual_srp_overrides,
        )
        self.reference_comparison_worker.moveToThread(
            self.reference_comparison_thread
        )
        self.reference_comparison_thread.started.connect(
            self.reference_comparison_worker.run
        )
        self.reference_comparison_worker.progress.connect(
            self.reference_progress.setValue
        )
        self.reference_comparison_worker.completed.connect(
            self.finish_reference_scenario
        )
        self.reference_comparison_worker.failed.connect(
            self.fail_reference_validation
        )
        self.reference_comparison_worker.cancelled.connect(
            self.cancelled_reference_validation
        )
        self.reference_comparison_worker.completed.connect(
            self.reference_comparison_thread.quit
        )
        self.reference_comparison_worker.failed.connect(
            self.reference_comparison_thread.quit
        )
        self.reference_comparison_worker.cancelled.connect(
            self.reference_comparison_thread.quit
        )
        self.reference_comparison_thread.finished.connect(
            self.reference_comparison_worker.deleteLater
        )
        self.reference_comparison_thread.finished.connect(
            self.reference_comparison_thread.deleteLater
        )
        self.reference_comparison_thread.finished.connect(
            self.cleanup_reference_validation
        )
        self.reference_comparison_thread.start()


    def cancel_reference_validation(self):

        if (
            self.reference_comparison_thread is None
            or not self.reference_comparison_thread.isRunning()
        ):
            return
        self.reference_comparison_thread.requestInterruption()
        self.cancel_reference_button.setEnabled(False)
        self.reference_progress.setFormat("Cancelling...")


    def finish_reference_scenario(self, scenario):

        include_moon = bool(scenario["include_moon"])
        include_sun = bool(scenario.get("include_sun", False))
        include_srp = bool(scenario.get("include_srp", False))
        selected_forces = ["EARTH"]
        if include_moon:
            selected_forces.append("MOON")
        if include_sun:
            selected_forces.append("SUN")
        if include_srp:
            selected_forces.append("SRP")
        scenario_name = " + ".join(selected_forces)
        srp_parameters_used = dict(
            scenario.get("srp_parameters_used") or {}
        )
        srp_description = "OFF"
        if include_srp:
            if srp_parameters_used:
                srp_description = (
                    "ON — effective area "
                    f"{srp_parameters_used['srp_area_m2']:.9g} m² / mass "
                    f"{srp_parameters_used['srp_mass_kg']:.9g} kg / CP "
                    f"{srp_parameters_used['srp_coefficient']:.12g}"
                )
            else:
                srp_description = (
                    "ON — physical box-wing / TrueSun arrays / public CP=1"
                )
        reference_case = "WITH MOON" if include_moon else "WITHOUT MOON"
        self.reference_scenario_results[include_moon] = scenario
        self.latest_reference_scenario = scenario
        metrics = scenario["metrics"]
        self.set_reference_metric_values(metrics)
        self.save_reference_csv_button.setEnabled(True)
        self.save_reference_csv_button.setText("EXPORT MODEL CSV")

        with_moon = self.reference_scenario_results[True]
        without_moon = self.reference_scenario_results[False]
        both_ready = with_moon is not None and without_moon is not None
        if both_ready:
            result = combine_reference_scenarios(
                with_moon,
                without_moon,
            )
            mode_title = "PHYSICAL ONLY"
            lunar_force_text = "Unmodified DE440 — no scale, fit, or bias"
            self.latest_reference_comparison = result
            self.save_reference_csv_button.setEnabled(True)
            self.save_reference_csv_button.setText("EXPORT MODEL CSV")
            with_metrics = with_moon["metrics"]
            without_metrics = without_moon["metrics"]
            lines = [
                "REFERENCE VALIDATION COMPLETED",
                "=" * 78,
                f"Satellite          : {TARGET_SATELLITE_DISPLAY_NAME} "
                f"(NORAD {TARGET_SATELLITE_NORAD_ID})",
                f"Dataset            : {result['dataset_label']}",
                f"Epoch              : {result['epoch'].isoformat()}",
                f"Samples/scenario   : {len(result['elapsed_seconds']):,}",
                f"Sampling interval  : {result['step_seconds']:.0f} s",
                f"Reference horizon  : {result['elapsed_seconds'][-1] / 86400.0:.9f} days",
                f"Combined runtime   : {result['runtime_seconds']:.3f} s",
                f"Calculation mode   : {mode_title}",
                "IERS EOP          : "
                + (
                    "ON · DUT1 + xp/yp"
                    if result["eop_status"]["enabled"]
                    else "OFF"
                ),
                f"Lunar acceleration : {lunar_force_text}",
                "Solar acceleration : "
                + (
                    "DE440 third-body — reference has no solar case"
                    if result.get("include_sun", False)
                    else "OFF"
                ),
                "Solar pressure     : "
                + srp_description,
                "",
                "WITH MOON",
                "-" * 78,
                f"Final position error : {with_metrics['final_position_error_km']:.9f} km",
                f"RMS position error   : {with_metrics['rms_position_error_km']:.9f} km",
                f"Maximum error        : {with_metrics['maximum_position_error_km']:.9f} km",
                f"Final velocity error : {with_metrics['final_velocity_error_km_s']:.12f} km/s",
                f"Radial / Along / Cross: {with_metrics['radial_km']:.9f} / "
                f"{with_metrics['along_track_km']:.9f} / "
                f"{with_metrics['cross_track_km']:.9f} km",
                "",
                "WITHOUT MOON",
                "-" * 78,
                f"Final position error : {without_metrics['final_position_error_km']:.9f} km",
                f"RMS position error   : {without_metrics['rms_position_error_km']:.9f} km",
                f"Maximum error        : {without_metrics['maximum_position_error_km']:.9f} km",
                f"Final velocity error : {without_metrics['final_velocity_error_km_s']:.12f} km/s",
                f"Radial / Along / Cross: {without_metrics['radial_km']:.9f} / "
                f"{without_metrics['along_track_km']:.9f} / "
                f"{without_metrics['cross_track_km']:.9f} km",
                "",
                "INDEPENDENT REFERENCE-SCENARIO SEPARATION",
                "-" * 78,
                f"Initial position gap : {result['initial_position_separation_km']:.9f} km",
                f"Initial velocity gap : {result['initial_velocity_separation_km_s']:.12f} km/s",
                f"Reference separation : {result['final_reference_separation_km']:.9f} km",
                f"Model separation     : {result['final_model_separation_km']:.9f} km",
                f"Model - reference    : {result['final_separation_difference_km']:.9f} km",
                "",
                "COMMON-STATE MOON EFFECT — IDENTICAL INITIAL STATE",
                "-" * 78,
                f"Mode                 : {mode_title}",
                f"Final separation     : {result['final_pure_moon_separation_km']:.9f} km",
                f"RMS separation       : {result['rms_pure_moon_separation_km']:.9f} km",
                f"Maximum separation   : {result['maximum_pure_moon_separation_km']:.9f} km",
                "No pure-reference value is claimed because the supplied",
                "WITH/WITHOUT reference files use different initial states.",
            ]
            status_message = (
                "Both independent reference scenarios are ready."
            )
        else:
            missing_name = "WITHOUT MOON" if include_moon else "WITH MOON"
            missing_available = reference_dataset_has_scenario(
                scenario["dataset_id"],
                not include_moon,
            )
            mode_title = "PHYSICAL ONLY"
            lines = [
                f"{scenario_name} VALIDATION COMPLETED",
                "=" * 78,
                f"Satellite            : {TARGET_SATELLITE_DISPLAY_NAME} "
                f"(NORAD {TARGET_SATELLITE_NORAD_ID})",
                f"Dataset              : {scenario['dataset_label']}",
                f"Epoch                : {scenario['epoch'].isoformat()}",
                f"Samples              : {len(scenario['elapsed_seconds']):,}",
                f"Sampling interval    : {scenario['step_seconds']:.0f} s",
                f"Source frame         : {scenario['source_frame']}",
                f"Model frame          : {scenario['model_frame']}",
                f"Runtime              : {scenario['runtime_seconds']:.3f} s",
                f"Calculation mode     : {mode_title}",
                "IERS EOP            : "
                + (
                    "ON · DUT1 + xp/yp"
                    if scenario["eop_status"]["enabled"]
                    else "OFF"
                ),
                f"Reference case       : {reference_case}",
                "Solar third-body     : "
                + (
                    "ON — physical, unmodified DE440"
                    if include_sun
                    else "OFF"
                ),
                "Solar pressure       : "
                + srp_description,
                "Lunar scale           : " + (
                    "NONE — no lunar force in this scenario"
                    if not include_moon
                    else "NONE — raw DE440 acceleration"
                ),
                "",
                f"Final position error : {metrics['final_position_error_km']:.9f} km",
                f"RMS position error   : {metrics['rms_position_error_km']:.9f} km",
                f"Maximum error        : {metrics['maximum_position_error_km']:.9f} km",
                f"Final velocity error : {metrics['final_velocity_error_km_s']:.12f} km/s",
                f"Radial / Along / Cross: {metrics['radial_km']:.9f} / "
                f"{metrics['along_track_km']:.9f} / "
                f"{metrics['cross_track_km']:.9f} km",
                "",
                (
                    f"NEXT: Toggle Moon to the {missing_name} case and run "
                    "the selected model to calculate the paired comparison."
                    if missing_available
                    else (
                        f"NOTE: {missing_name} is not provided by this "
                        "dataset; no synthetic reference is generated."
                    )
                ),
            ]
            status_message = (
                f"{scenario_name} ready; toggle Moon and run the paired case."
                if missing_available
                else f"{scenario_name} validation ready."
            )

        self.reference_output.setPlainText("\n".join(lines))
        final_epoch = scenario["epoch"] + timedelta(
            seconds=float(scenario["elapsed_seconds"][-1])
        )
        self.reference_kepler_widget.update_trajectory(
            np.asarray(scenario["model_states"], dtype=float),
            np.asarray(scenario["elapsed_seconds"], dtype=float),
            scenario["epoch"],
            frame_label="TOD/FK5 (matches CSV export)",
        )
        self.update_reference_chart()
        self.reference_progress.setValue(100)
        self.reference_progress.setFormat(f"{scenario_name} completed")
        self.update_reference_run_button_availability()
        self.cancel_reference_button.setEnabled(False)
        self.statusBar().showMessage(status_message, 8000)


    def fail_reference_validation(self, message):

        if self.reference_active_scenario is not None:
            self.set_reference_metric_values()
        self.reference_kepler_widget.clear()
        self.reference_output.setPlainText(
            "REFERENCE VALIDATION ERROR\n\n" + message
        )
        self.reference_progress.setFormat("Failed")
        self.update_reference_run_button_availability()
        self.cancel_reference_button.setEnabled(False)


    def cancelled_reference_validation(self):

        if self.reference_active_scenario is not None:
            self.set_reference_metric_values()
        self.reference_kepler_widget.clear()
        self.reference_output.setPlainText(
            "REFERENCE VALIDATION CANCELLED\n\n"
            "The cancelled scenario was not stored. Any other completed "
            "scenario remains available."
        )
        self.reference_progress.setFormat("Cancelled")
        self.update_reference_run_button_availability()
        self.cancel_reference_button.setEnabled(False)


    def cleanup_reference_validation(self):

        self.reference_comparison_worker = None
        self.reference_comparison_thread = None
        self.reference_active_scenario = None
        self.reference_dataset_combo.setEnabled(True)
        self.update_reference_run_button_availability()
        if getattr(self, "_reference_timer_was_active", False):
            self.timer.start(1000)
        self._reference_timer_was_active = False


    def save_reference_validation_csv(self):

        # Yalnız son hesablanan ssenarinin özünü ixrac et. Ayın açıq və qapalı
        # nəticələri müqayisə üçün yaddaşda olsa da burada avtomatik paired
        # fayllar yaradılmır.
        scenario = self.latest_reference_scenario
        if scenario is None:
            self.reference_output.append(
                "\n\nEXPORT ERROR: run reference validation first."
            )
            return

        scenario_slug = str(scenario.get("name", "model")).strip().lower()
        scenario_slug = "_".join(
            part for part in scenario_slug.replace("+", " ").split() if part
        )
        default_name = (
            scenario_slug
            + "_"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            + ".csv"
        )
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Reference Model CSV"),
            default_name,
            "CSV Files (*.csv);;All Files (*)",
            options=theme.file_dialog_options(),
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".csv"):
            file_path += ".csv"

        try:
            exported_path = save_scenario_csv(scenario, file_path)
            self.statusBar().showMessage(
                f"Reference trajectory exported: {exported_path.name}",
                8000,
            )
            self.reference_output.append(
                "\n\nCSV EXPORT COMPLETED\n"
                f"FORCE MODEL : {scenario['name']}\n"
                f"FILE        : {exported_path}"
            )
        except Exception as error:
            self.reference_output.append(
                "\n\nEXPORT ERROR:\n"
                f"{type(error).__name__}: {error}"
            )


    # ========================================================
    # STANDALONE ECLIPSE PREDICTION PAGE
    # ========================================================

    def create_eclipse_page(self):

        page = QWidget()
        self.eclipse_page = page
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 10, 12, 16)
        layout.setSpacing(14)

        # The five-sentence version of this guidance used to occupy two full
        # rows above the workspace.  The page keeps one orienting line and
        # carries the detail in a tooltip instead.
        description = QLabel(
            "Check a bundled reference, or predict from your own J2000 state."
        )
        description.setWordWrap(True)
        description.setObjectName("metricDetail")
        description.setToolTip(
            "Two workflows. To check a bundled reference: pick it below and "
            "press RUN — leave the state fields empty and ignore the force "
            "switches, they do not affect that run. To predict from your own "
            "state: fill the J2000 fields, then press CALCULATE ECLIPSE "
            "EVENTS. Earth and Moon apparent discs are both evaluated."
        )
        layout.addWidget(description)

        input_box = QGroupBox("ECLIPSE INITIAL STATE — J2000")
        input_layout = QGridLayout(input_box)
        input_layout.setContentsMargins(18, 28, 18, 18)
        input_layout.setHorizontalSpacing(12)
        input_layout.setVerticalSpacing(9)

        self.eclipse_epoch = QLineEdit()
        self.eclipse_epoch.setPlaceholderText("2030-03-20T00:00:00+00:00")
        self.eclipse_epoch_picker_button = QPushButton("SELECT DATE / TIME")
        self.eclipse_epoch_picker_button.setObjectName("ghostAction")
        self.eclipse_epoch_picker_button.setMinimumHeight(34)
        self.eclipse_epoch_picker_button.setToolTip(
            "Open a UTC calendar and time selector; keyboard entry remains optional."
        )
        self.eclipse_epoch_picker_button.clicked.connect(
            self.open_eclipse_epoch_picker
        )
        self.eclipse_state_inputs = []
        state_names = ("X", "Y", "Z", "Vx", "Vy", "Vz")
        state_units = ("km", "km", "km", "km/s", "km/s", "km/s")
        for name in state_names:
            field = QLineEdit()
            field.setMinimumHeight(34)
            setattr(self, f"eclipse_{name.lower()}", field)
            self.eclipse_state_inputs.append(field)

        input_layout.addWidget(QLabel("Epoch UTC:"), 0, 0)
        input_layout.addWidget(self.eclipse_epoch, 0, 1, 1, 4)
        input_layout.addWidget(self.eclipse_epoch_picker_button, 0, 5)
        for index, (name, unit, field) in enumerate(
            zip(state_names, state_units, self.eclipse_state_inputs)
        ):
            row = 1 + index // 3
            column = (index % 3) * 2
            input_layout.addWidget(QLabel(f"{name} [{unit}]:"), row, column)
            input_layout.addWidget(field, row, column + 1)

        source_buttons = QHBoxLayout()
        current_state_button = QPushButton("USE ACTIVE SPACECRAFT STATE")
        current_state_button.clicked.connect(self.use_current_eclipse_state)
        copy_prop_button = QPushButton("COPY PROPAGATION INPUT")
        copy_prop_button.clicked.connect(self.copy_propagation_to_eclipse)
        source_buttons.addWidget(current_state_button)
        source_buttons.addWidget(copy_prop_button)
        source_buttons.addStretch(1)
        input_layout.addLayout(source_buttons, 3, 0, 1, 6)
        layout.addWidget(input_box)

        settings_box = QGroupBox(
            "TRAJECTORY PROPAGATION FOR ECLIPSE SEARCH"
        )
        settings_layout = QGridLayout(settings_box)
        settings_layout.setContentsMargins(18, 28, 18, 18)
        settings_layout.setHorizontalSpacing(14)
        settings_layout.setVerticalSpacing(10)

        self.eclipse_days = QSpinBox()
        self.eclipse_days.setRange(1, 365)
        self.eclipse_days.setValue(30)
        self.eclipse_days.setSuffix(" days")
        self.eclipse_step_value = QSpinBox()
        self.eclipse_step_value.setRange(1, 60)
        self.eclipse_step_value.setValue(10)
        # Keep the old attribute as a compatibility alias for existing UI
        # tests and any local automation that already addresses this control.
        self.eclipse_step_minutes = self.eclipse_step_value
        self.eclipse_step_unit = QComboBox()
        self.eclipse_step_unit.addItem("SECONDS", 1)
        self.eclipse_step_unit.addItem("MINUTES", 60)
        self.eclipse_step_unit.addItem("HOURS", 3600)
        self.eclipse_step_unit.addItem("DAYS", 86400)
        self.eclipse_step_unit.setMinimumHeight(34)
        self.eclipse_step_unit.currentIndexChanged.connect(
            self.update_eclipse_step_unit
        )
        self.eclipse_step_warning = QLabel()
        self.eclipse_step_warning.setWordWrap(True)
        _set_status_role(self.eclipse_step_warning, "warning")
        self.update_eclipse_step_unit()
        self.eclipse_include_j2 = QCheckBox("Earth EGM96 4×4")
        self.eclipse_include_j2.setChecked(True)
        self.eclipse_include_moon = QCheckBox("Moon gravity")
        self.eclipse_include_moon.setChecked(True)
        self.eclipse_include_sun = QCheckBox("Sun gravity")
        self.eclipse_include_sun.setChecked(True)
        self.eclipse_include_srp = QCheckBox("Physical SRP trajectory effect")
        self.eclipse_include_srp.setChecked(True)

        settings_layout.addWidget(QLabel("Search duration:"), 0, 0)
        settings_layout.addWidget(self.eclipse_days, 0, 1)
        settings_layout.addWidget(QLabel("Output/search step:"), 0, 2)
        settings_layout.addWidget(self.eclipse_step_value, 0, 3)
        settings_layout.addWidget(self.eclipse_step_unit, 0, 4)
        settings_layout.addWidget(self.eclipse_include_j2, 1, 0)
        settings_layout.addWidget(self.eclipse_include_moon, 1, 1)
        settings_layout.addWidget(self.eclipse_include_sun, 1, 2)
        settings_layout.addWidget(self.eclipse_include_srp, 1, 3)
        settings_layout.addWidget(self.eclipse_step_warning, 2, 0, 1, 5)
        self.eclipse_trajectory_note = QLabel(
            "These switches only define the trajectory supplied to the detector. "
            "Eclipse detection itself always uses Sun–Earth/Moon–spacecraft "
            "geometry and does not require any perturbation switch."
        )
        self.eclipse_trajectory_note.setWordWrap(True)
        self.eclipse_trajectory_note.setObjectName("metricDetail")
        settings_layout.addWidget(self.eclipse_trajectory_note, 3, 0, 1, 5)

        # Two geometry refinements that are physically defensible but move the
        # result away from the bundled references, which were produced with a
        # spherical Earth shadow and geometric Moon positions. They stay off so
        # the comparison keeps measuring the model rather than the convention.
        self.eclipse_oblate_earth = QCheckBox("Oblate Earth shadow")
        self.eclipse_oblate_earth.setChecked(False)
        self.eclipse_oblate_earth.setToolTip(
            "Models the Earth shadow as a WGS-84 ellipsoid instead of a "
            "sphere. The result is unchanged near mid-season but can differ "
            "at the edges. It is off by default because the bundled "
            "references use a spherical shadow."
        )
        self.eclipse_light_time_moon = QCheckBox("Light-time Moon position")
        self.eclipse_light_time_moon.setChecked(False)
        self.eclipse_light_time_moon.setToolTip(
            "Uses the light-time-corrected Moon position (19 arcseconds). "
            "This is physically correct for occultation geometry, but it is "
            "off by default because both references use the geometric position."
        )
        self.eclipse_geometry_note = QLabel(
            "Research switches — both off reproduces the bundled references. "
            "Turning one on measures how much of a residual is convention "
            "rather than physics; it does not improve agreement."
        )
        self.eclipse_geometry_note.setWordWrap(True)
        _set_status_role(self.eclipse_geometry_note, "warning")
        self.eclipse_oblate_earth.toggled.connect(
            self.refresh_model_provenance
        )
        self.eclipse_light_time_moon.toggled.connect(
            self.refresh_model_provenance
        )
        geometry_box = QGroupBox("ECLIPSE DETECTION GEOMETRY")
        geometry_layout = QGridLayout(geometry_box)
        geometry_layout.setContentsMargins(18, 28, 18, 18)
        geometry_layout.setHorizontalSpacing(14)
        geometry_layout.setVerticalSpacing(10)
        geometry_layout.addWidget(self.eclipse_oblate_earth, 0, 0)
        geometry_layout.addWidget(self.eclipse_light_time_moon, 0, 1)
        geometry_layout.addWidget(self.eclipse_geometry_note, 1, 0, 1, 3)

        self.eclipse_year = QSpinBox()
        self.eclipse_year.setRange(2000, 2100)
        self.eclipse_year.setValue(get_current_utc().year)
        self.eclipse_year.setMinimumHeight(34)
        self.eclipse_year_search_button = QPushButton(
            "FAST YEAR SEARCH — 1 HOUR → 1 MINUTE"
        )
        self.eclipse_year_search_button.setObjectName("primaryAction")
        self.eclipse_year_search_button.clicked.connect(
            self.run_yearly_eclipse_search
        )
        self.eclipse_year_export_csv_button = QPushButton(
            "EXPORT YEAR CSV"
        )
        self.eclipse_year_export_csv_button.setEnabled(False)
        self.eclipse_year_export_csv_button.clicked.connect(
            self.export_yearly_eclipse_csv
        )
        self.eclipse_year_note = QLabel(
            "First scans at 1-hour intervals, then checks candidate days "
            "and four guard days on each side at 1-minute resolution. Days "
            "with no eclipse are listed as SKIPPED."
        )
        self.eclipse_year_note.setWordWrap(True)
        self.eclipse_year_note.setObjectName("metricDetail")
        settings_layout.addWidget(QLabel("Year schedule:"), 4, 0)
        settings_layout.addWidget(self.eclipse_year, 4, 1)
        settings_layout.addWidget(self.eclipse_year_search_button, 4, 2, 1, 2)
        settings_layout.addWidget(self.eclipse_year_export_csv_button, 4, 4)
        settings_layout.addWidget(self.eclipse_year_note, 5, 0, 1, 5)
        layout.addWidget(settings_box)
        layout.addWidget(geometry_box)

        action_layout = QHBoxLayout()
        self.eclipse_calculate_button = QPushButton("CALCULATE ECLIPSE EVENTS")
        self.eclipse_calculate_button.setObjectName("primaryAction")
        self.eclipse_calculate_button.clicked.connect(
            self.run_eclipse_prediction
        )
        self.eclipse_cancel_button = QPushButton("CANCEL")
        self.eclipse_cancel_button.setObjectName("dangerAction")
        self.eclipse_cancel_button.setEnabled(False)
        self.eclipse_cancel_button.clicked.connect(
            self.cancel_eclipse_prediction
        )
        self.eclipse_export_csv_button = QPushButton("EXPORT ECLIPSE CSV")
        self.eclipse_export_csv_button.setEnabled(False)
        self.eclipse_export_csv_button.clicked.connect(
            self.export_eclipse_prediction_csv
        )
        action_layout.addWidget(self.eclipse_calculate_button)
        action_layout.addWidget(self.eclipse_cancel_button)
        action_layout.addWidget(self.eclipse_export_csv_button)
        action_layout.addStretch(1)
        layout.addLayout(action_layout)

        eclipse_progress_layout = QHBoxLayout()
        self.eclipse_progress = QProgressBar()
        self.eclipse_progress.setRange(0, 100)
        self.eclipse_progress.setValue(0)
        self.eclipse_progress.setFormat("Ready")
        self.eclipse_eta_label = QLabel("Remaining: --:--:--")
        self.eclipse_eta_label.setMinimumWidth(170)
        self.eclipse_eta_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.eclipse_eta_label.setObjectName("telemetryValue")
        eclipse_progress_layout.addWidget(self.eclipse_progress, 1)
        eclipse_progress_layout.addWidget(self.eclipse_eta_label)
        layout.addLayout(eclipse_progress_layout)

        self.eclipse_eta_timer = QTimer(self)
        self.eclipse_eta_timer.setInterval(1000)
        self.eclipse_eta_timer.timeout.connect(self.refresh_eclipse_eta)

        graph_box = QGroupBox("ECLIPSE TIMELINE — SUNLIGHT / PENUMBRA / UMBRA")
        graph_layout = QVBoxLayout(graph_box)
        graph_layout.setContentsMargins(14, 24, 14, 14)
        graph_controls = QHBoxLayout()
        graph_controls.addWidget(QLabel("Detailed eclipse event:"))
        self.eclipse_event_selector = QComboBox()
        self.eclipse_event_selector.addItem("Calculate events first", None)
        self.eclipse_event_selector.setMinimumHeight(34)
        self.eclipse_event_selector.setMinimumWidth(360)
        self.eclipse_event_selector.currentIndexChanged.connect(
            self.render_eclipse_prediction
        )
        graph_controls.addWidget(self.eclipse_event_selector)
        graph_controls.addStretch(1)
        graph_layout.addLayout(graph_controls)
        self.eclipse_graph = GraphWidget(figsize=(10, 5.5))
        self.eclipse_graph.setMinimumHeight(320)
        self.eclipse_graph.ax.set_xlabel("Elapsed time [days]")
        self.eclipse_graph.ax.set_ylabel("Sunlight fraction [%]")
        self.eclipse_graph.ax.text(
            0.5,
            0.5,
            "Enter a state and calculate eclipse events",
            transform=self.eclipse_graph.ax.transAxes,
            ha="center",
            va="center",
            color=theme.TEXT_FAINT,
        )
        graph_layout.addWidget(self.eclipse_graph)
        layout.addWidget(graph_box)

        event_box = QGroupBox("ECLIPSE EVENT TABLE — UTC")
        event_layout = QVBoxLayout(event_box)
        event_layout.setContentsMargins(14, 24, 14, 14)
        self.eclipse_summary_label = QLabel(
            "No standalone eclipse calculation has been run."
        )
        self.eclipse_summary_label.setWordWrap(True)
        self.eclipse_summary_label.setObjectName("metricDetail")
        event_layout.addWidget(self.eclipse_summary_label)

        self.eclipse_event_table = QTableWidget(0, 7)
        self.eclipse_event_table.setHorizontalHeaderLabels(
            (
                "#",
                "Penumbra entry UTC",
                "Umbra entry UTC",
                "Umbra exit UTC",
                "Penumbra exit UTC",
                "Umbra duration",
                "Total eclipse",
            )
        )
        self.eclipse_event_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.eclipse_event_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.eclipse_event_table.cellClicked.connect(
            self.select_eclipse_event_from_table
        )
        self.eclipse_event_table.verticalHeader().setVisible(False)
        header = self.eclipse_event_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for column in range(1, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        self.eclipse_event_table.setMinimumHeight(170)
        event_layout.addWidget(self.eclipse_event_table)

        note = QLabel(
            "Uses DE440 Sun direction and finite Earth/Sun apparent discs. "
            "Reference-range runs use the finite DE440 Moon disc as well. "
            "No artificial eclipse constant or copied contact time is used."
        )
        note.setWordWrap(True)
        note.setObjectName("metricDetail")
        event_layout.addWidget(note)
        layout.addWidget(event_box)

        yearly_box = QGroupBox("YEARLY ECLIPSE SCHEDULE — UTC")
        yearly_layout = QVBoxLayout(yearly_box)
        yearly_layout.setContentsMargins(14, 24, 14, 14)
        self.eclipse_year_summary_label = QLabel(
            "Choose a year and run the 1-minute year search."
        )
        self.eclipse_year_summary_label.setWordWrap(True)
        self.eclipse_year_summary_label.setObjectName("metricDetail")
        yearly_layout.addWidget(self.eclipse_year_summary_label)

        self.eclipse_year_table = QTableWidget(0, 7)
        self.eclipse_year_table.setHorizontalHeaderLabels(
            (
                "Date UTC",
                "Status",
                "Event",
                "Penumbra entry UTC",
                "Umbra entry UTC",
                "Umbra exit UTC",
                "Penumbra exit UTC",
            )
        )
        self.eclipse_year_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.eclipse_year_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.eclipse_year_table.verticalHeader().setVisible(False)
        yearly_header = self.eclipse_year_table.horizontalHeader()
        yearly_header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        yearly_header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        yearly_header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        for column in range(3, 7):
            yearly_header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Stretch,
            )
        self.eclipse_year_table.setMinimumHeight(190)
        yearly_layout.addWidget(self.eclipse_year_table)
        layout.addWidget(yearly_box)

        reference_box = QGroupBox("REFERENCE COMPARISON — OUR OUTPUT vs BUNDLED DATA")
        reference_layout = QVBoxLayout(reference_box)
        reference_layout.setContentsMargins(14, 24, 14, 14)

        reference_controls = QHBoxLayout()
        reference_controls.addWidget(QLabel("Reference:"))
        self.eclipse_reference_selector = QComboBox()
        for spec in available_eclipse_reference_specs():
            self.eclipse_reference_selector.addItem(spec.label, spec.dataset_id)
        default_reference_index = self.eclipse_reference_selector.findData(
            "synthetic_geo_2030_equinox"
        )
        if default_reference_index >= 0:
            self.eclipse_reference_selector.setCurrentIndex(
                default_reference_index
            )
        self.eclipse_reference_selector.setMinimumWidth(330)
        self.eclipse_reference_selector.currentIndexChanged.connect(
            self.refresh_eclipse_reference_comparison
        )
        reference_controls.addWidget(self.eclipse_reference_selector, 1)

        reference_controls.addWidget(QLabel("Tolerance:"))
        self.eclipse_reference_tolerance_seconds = QSpinBox()
        self.eclipse_reference_tolerance_seconds.setRange(1, 3600)
        self.eclipse_reference_tolerance_seconds.setValue(120)
        self.eclipse_reference_tolerance_seconds.setSuffix(" s")
        self.eclipse_reference_tolerance_seconds.setMinimumHeight(34)
        reference_controls.addWidget(self.eclipse_reference_tolerance_seconds)

        self.eclipse_reference_compare_button = QPushButton(
            "COMPARE CURRENT OUTPUT"
        )
        self.eclipse_reference_compare_button.clicked.connect(
            self.run_eclipse_reference_comparison
        )
        reference_controls.addWidget(self.eclipse_reference_compare_button)
        self.eclipse_reference_export_button = QPushButton(
            "EXPORT COMPARISON CSV"
        )
        self.eclipse_reference_export_button.setEnabled(False)
        self.eclipse_reference_export_button.clicked.connect(
            self.export_eclipse_reference_comparison_csv
        )
        reference_controls.addWidget(self.eclipse_reference_export_button)
        reference_layout.addLayout(reference_controls)

        reference_run_layout = QHBoxLayout()
        self.eclipse_reference_run_model_button = QPushButton(
            "RUN MODEL FOR SELECTED REFERENCE DATES + COMPARE"
        )
        self.eclipse_reference_run_model_button.setObjectName("primaryAction")
        self.eclipse_reference_run_model_button.setMinimumHeight(40)
        self.eclipse_reference_run_model_button.clicked.connect(
            self.run_selected_eclipse_reference_interval
        )
        reference_run_layout.addWidget(
            self.eclipse_reference_run_model_button,
            1,
        )
        reference_state_note = QLabel(
            "Runs with a fictional 12.0°E nominal GEO demonstration state. "
            "No operational spacecraft data is used."
        )
        reference_state_note.setWordWrap(True)
        reference_state_note.setObjectName("metricDetail")
        reference_run_layout.addWidget(reference_state_note, 2)
        reference_layout.addLayout(reference_run_layout)

        reference_progress_layout = QHBoxLayout()
        self.eclipse_reference_date_label = QLabel("Selected interval: —")
        self.eclipse_reference_date_label.setMinimumWidth(330)
        self.eclipse_reference_date_label.setObjectName("telemetryValue")
        reference_progress_layout.addWidget(
            self.eclipse_reference_date_label
        )
        self.eclipse_reference_progress = QProgressBar()
        self.eclipse_reference_progress.setRange(0, 100)
        self.eclipse_reference_progress.setValue(0)
        self.eclipse_reference_progress.setFormat("Ready")
        self.eclipse_reference_progress.setMinimumHeight(28)
        reference_progress_layout.addWidget(
            self.eclipse_reference_progress,
            1,
        )
        reference_layout.addLayout(reference_progress_layout)

        # This label is replaced by the real verdict after a run; its resting
        # text only has to say that a run is what fills it.
        self.eclipse_reference_summary_label = QLabel(
            "Run the comparison to see how early or late the model is."
        )
        self.eclipse_reference_summary_label.setWordWrap(True)
        self.eclipse_reference_summary_label.setObjectName("metricDetail")
        reference_layout.addWidget(self.eclipse_reference_summary_label)

        self.eclipse_reference_table = QTableWidget(0, 12)
        self.eclipse_reference_table.setHorizontalHeaderLabels(
            (
                "Result",
                "Shadow",
                "Ref №",
                "Model №",
                "Ref. entry (UTC)",
                "Model entry (UTC)",
                "Entry difference",
                "Ref. exit (UTC)",
                "Model exit (UTC)",
                "Exit difference",
                "Duration difference",
                "Quality",
            )
        )
        self.eclipse_reference_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.eclipse_reference_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.eclipse_reference_table.verticalHeader().setVisible(False)
        reference_header = self.eclipse_reference_table.horizontalHeader()
        for column in (0, 1, 2, 3, 6, 9, 10, 11):
            reference_header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        for column in (4, 5, 7, 8):
            reference_header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Stretch,
            )
        self.eclipse_reference_table.setMinimumHeight(260)
        reference_layout.addWidget(self.eclipse_reference_table)
        # Index 1 keeps this immediately below the description, ahead of the
        # state inputs, so the one-click workflow needs no scrolling.
        layout.insertWidget(1, reference_box)
        self.update_eclipse_reference_interval_label()

        scroll.setWidget(content)
        self.eclipse_workspace_tabs = QTabWidget()
        self.eclipse_workspace_tabs.setObjectName("eclipseWorkspaceTabs")
        self.eclipse_workspace_tabs.addTab(scroll, "ECLIPSE PREDICTION")
        self.sun_outage_page = self.create_sun_outage_page()
        self.eclipse_workspace_tabs.addTab(self.sun_outage_page, "SUN OUTAGE")
        page_layout.addWidget(self.eclipse_workspace_tabs)
        return page


    def create_sun_outage_page(self):
        """Build the ITU-R S.1525-1 GSO Sun-transit workspace."""

        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 10, 12, 16)
        layout.setSpacing(14)

        description = QLabel(
            "Predict when the Sun crosses the receiving antenna beam behind "
            "the active GEO slot. Times use WGS-84 station geometry and the "
            "JPL DE440 apparent Sun direction."
        )
        description.setWordWrap(True)
        description.setObjectName("metricDetail")
        layout.addWidget(description)

        inputs_box = QGroupBox("SUN OUTAGE INPUTS — ITU-R S.1525-1")
        inputs = QGridLayout(inputs_box)
        inputs.setContentsMargins(18, 28, 18, 18)
        inputs.setHorizontalSpacing(12)
        inputs.setVerticalSpacing(10)

        self.sun_outage_station_combo = QComboBox()
        self.sun_outage_station_combo.setMinimumWidth(280)
        self.sun_outage_station_combo.currentIndexChanged.connect(
            self.update_sun_outage_station_summary
        )
        self.sun_outage_year = QSpinBox()
        self.sun_outage_year.setRange(2000, 2100)
        self.sun_outage_year.setValue(get_current_utc().year)
        self.sun_outage_frequency = QDoubleSpinBox()
        self.sun_outage_frequency.setRange(0.1, 100.0)
        self.sun_outage_frequency.setDecimals(3)
        self.sun_outage_frequency.setValue(11.0)
        self.sun_outage_frequency.setSuffix(" GHz")
        self.sun_outage_antenna_diameter = QDoubleSpinBox()
        self.sun_outage_antenna_diameter.setRange(0.1, 100.0)
        self.sun_outage_antenna_diameter.setDecimals(3)
        self.sun_outage_antenna_diameter.setValue(3.7)
        self.sun_outage_antenna_diameter.setSuffix(" m")
        self.sun_outage_satellite_longitude = QDoubleSpinBox()
        self.sun_outage_satellite_longitude.setRange(-180.0, 180.0)
        self.sun_outage_satellite_longitude.setDecimals(6)
        self.sun_outage_satellite_longitude.setSuffix(" °E")
        self.sun_outage_satellite_longitude.setReadOnly(True)
        self.sun_outage_satellite_longitude.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )

        inputs.addWidget(QLabel("Ground station:"), 0, 0)
        inputs.addWidget(self.sun_outage_station_combo, 0, 1, 1, 3)
        inputs.addWidget(QLabel("Year:"), 0, 4)
        inputs.addWidget(self.sun_outage_year, 0, 5)
        inputs.addWidget(QLabel("Downlink frequency:"), 1, 0)
        inputs.addWidget(self.sun_outage_frequency, 1, 1)
        inputs.addWidget(QLabel("Antenna diameter:"), 1, 2)
        inputs.addWidget(self.sun_outage_antenna_diameter, 1, 3)
        inputs.addWidget(QLabel("Active GEO slot:"), 1, 4)
        inputs.addWidget(self.sun_outage_satellite_longitude, 1, 5)

        self.sun_outage_station_summary = QLabel()
        self.sun_outage_station_summary.setWordWrap(True)
        self.sun_outage_station_summary.setObjectName("metricDetail")
        inputs.addWidget(self.sun_outage_station_summary, 2, 0, 1, 6)
        link_note = QLabel(
            "Frequency and antenna diameter must match the receiving link. "
            "The result is the Sun-disc + 3 dB beam intersection window; an "
            "actual carrier outage also depends on link margin and solar flux."
        )
        link_note.setWordWrap(True)
        _set_status_role(link_note, "warning")
        inputs.addWidget(link_note, 3, 0, 1, 6)
        layout.addWidget(inputs_box)

        actions = QHBoxLayout()
        self.sun_outage_calculate_button = QPushButton("CALCULATE SUN OUTAGE")
        self.sun_outage_calculate_button.setObjectName("primaryAction")
        self.sun_outage_calculate_button.clicked.connect(
            self.run_sun_outage_prediction
        )
        self.sun_outage_cancel_button = QPushButton("CANCEL")
        self.sun_outage_cancel_button.setObjectName("dangerAction")
        self.sun_outage_cancel_button.setEnabled(False)
        self.sun_outage_cancel_button.clicked.connect(
            self.cancel_sun_outage_prediction
        )
        self.sun_outage_export_button = QPushButton("EXPORT SUN OUTAGE CSV")
        self.sun_outage_export_button.setEnabled(False)
        self.sun_outage_export_button.clicked.connect(self.export_sun_outage_csv)
        actions.addWidget(self.sun_outage_calculate_button)
        actions.addWidget(self.sun_outage_cancel_button)
        actions.addWidget(self.sun_outage_export_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.sun_outage_progress = QProgressBar()
        self.sun_outage_progress.setRange(0, 100)
        self.sun_outage_progress.setValue(0)
        self.sun_outage_progress.setFormat("Ready")
        layout.addWidget(self.sun_outage_progress)

        results_box = QGroupBox("PREDICTED SUN OUTAGE WINDOWS")
        results = QVBoxLayout(results_box)
        results.setContentsMargins(14, 24, 14, 14)
        self.sun_outage_summary = QLabel(
            "Choose the receiving link parameters and calculate the yearly schedule."
        )
        self.sun_outage_summary.setWordWrap(True)
        self.sun_outage_summary.setObjectName("metricDetail")
        results.addWidget(self.sun_outage_summary)

        self.sun_outage_table = QTableWidget(0, 8)
        self.sun_outage_table.setHorizontalHeaderLabels(
            (
                "Date UTC",
                "Start UTC",
                "Peak UTC",
                "End UTC",
                "Peak Baku (UTC+4)",
                "Duration",
                "Min. separation",
                "Risk threshold",
            )
        )
        self.sun_outage_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.sun_outage_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.sun_outage_table.verticalHeader().setVisible(False)
        header = self.sun_outage_table.horizontalHeader()
        for column in range(8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        self.sun_outage_table.setMinimumHeight(300)
        results.addWidget(self.sun_outage_table)

        provenance = QLabel(
            "Method: ITU-R S.1525-1 Annex 2 beam geometry, WGS-84 Earth "
            "station, fixed nominal GSO slot and JPL DE440 apparent Sun. "
            "No eclipse or propagation result is modified."
        )
        provenance.setWordWrap(True)
        provenance.setObjectName("metricDetail")
        results.addWidget(provenance)
        layout.addWidget(results_box)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.refresh_sun_outage_stations()
        self.refresh_sun_outage_profile()
        return page


    def refresh_sun_outage_stations(self):
        selector = getattr(self, "sun_outage_station_combo", None)
        if selector is None:
            return
        selected = selector.currentData()
        station_map = {}
        selector.blockSignals(True)
        selector.clear()
        for dataset_id, station in available_ground_stations():
            key = f"{dataset_id}:{station.station_id}"
            station_map[key] = station
            selector.addItem(station.name, key)
        self._sun_outage_station_by_key = station_map
        index = selector.findData(selected)
        selector.setCurrentIndex(index if index >= 0 else 0)
        selector.blockSignals(False)
        self.update_sun_outage_station_summary()


    def refresh_sun_outage_profile(self):
        control = getattr(self, "sun_outage_satellite_longitude", None)
        if control is None:
            return
        control.setValue(float(self.active_profile.target_longitude_deg))
        control.setToolTip(
            f"{self.active_profile.display_name} nominal Earth-fixed GEO slot."
        )


    def update_sun_outage_station_summary(self, _index=None):
        label = getattr(self, "sun_outage_station_summary", None)
        selector = getattr(self, "sun_outage_station_combo", None)
        if label is None or selector is None:
            return
        station = getattr(self, "_sun_outage_station_by_key", {}).get(
            selector.currentData()
        )
        if station is None:
            label.setText("No ground station is available.")
            return
        label.setText(
            f"Selected station: {station.name} · WGS-84 "
            f"{station.latitude_deg:+.6f}°, {station.longitude_deg:+.6f}° · "
            f"height {station.height_km:.3f} km. "
            "Admin coordinates remain memory-only and are removed on logout."
        )


    def run_sun_outage_prediction(self):
        if self.sun_outage_thread is not None and self.sun_outage_thread.isRunning():
            return
        if self.eclipse_thread is not None and self.eclipse_thread.isRunning():
            self.sun_outage_summary.setText(
                "Wait for the Eclipse calculation to finish or cancel it first."
            )
            return
        station = getattr(self, "_sun_outage_station_by_key", {}).get(
            self.sun_outage_station_combo.currentData()
        )
        if station is None:
            self.sun_outage_summary.setText(
                "SUN OUTAGE INPUT ERROR: no ground station is available."
            )
            return
        parameters = {
            "year": int(self.sun_outage_year.value()),
            "station": SunOutageStation(
                station_id=station.station_id,
                name=station.name,
                latitude_deg=station.latitude_deg,
                longitude_deg=station.longitude_deg,
                height_km=station.height_km,
            ),
            "satellite_longitude_deg": float(
                self.sun_outage_satellite_longitude.value()
            ),
            "frequency_ghz": float(self.sun_outage_frequency.value()),
            "antenna_diameter_m": float(
                self.sun_outage_antenna_diameter.value()
            ),
            "eop_enabled": is_eop_enabled(),
        }
        self.sun_outage_prediction = None
        self.sun_outage_table.setRowCount(0)
        self.sun_outage_export_button.setEnabled(False)
        self.sun_outage_calculate_button.setEnabled(False)
        self.sun_outage_cancel_button.setEnabled(True)
        self.sun_outage_progress.setValue(0)
        self.sun_outage_progress.setFormat("Searching equinox seasons · %p%")
        self.sun_outage_summary.setText(
            "SUN OUTAGE SEARCH RUNNING\n"
            f"Station: {station.name} · Spacecraft: "
            f"{self.active_profile.display_name} · "
            f"slot {parameters['satellite_longitude_deg']:+.6f}°E"
        )

        self.sun_outage_thread = QThread(self)
        self.sun_outage_worker = SunOutageWorker(parameters)
        self.sun_outage_worker.moveToThread(self.sun_outage_thread)
        self.sun_outage_thread.started.connect(self.sun_outage_worker.run)
        self.sun_outage_worker.progress.connect(self.sun_outage_progress.setValue)
        self.sun_outage_worker.completed.connect(self.finish_sun_outage_prediction)
        self.sun_outage_worker.failed.connect(self.fail_sun_outage_prediction)
        self.sun_outage_worker.cancelled.connect(
            self.cancelled_sun_outage_prediction
        )
        self.sun_outage_worker.completed.connect(self.sun_outage_thread.quit)
        self.sun_outage_worker.failed.connect(self.sun_outage_thread.quit)
        self.sun_outage_worker.cancelled.connect(self.sun_outage_thread.quit)
        self.sun_outage_thread.finished.connect(
            self.sun_outage_worker.deleteLater
        )
        self.sun_outage_thread.finished.connect(
            self.sun_outage_thread.deleteLater
        )
        self.sun_outage_thread.finished.connect(
            self.cleanup_sun_outage_prediction
        )
        self.sun_outage_thread.start()


    @staticmethod
    def _sun_outage_time_text(value):
        return value.astimezone(timezone.utc).strftime("%H:%M:%S")


    def finish_sun_outage_prediction(self, prediction):
        self.sun_outage_prediction = prediction
        self.sun_outage_table.setRowCount(len(prediction.events))
        baku_offset = timezone(timedelta(hours=4))
        for row, event in enumerate(prediction.events):
            values = (
                event.peak_utc.astimezone(timezone.utc).strftime("%Y-%m-%d"),
                self._sun_outage_time_text(event.start_utc),
                self._sun_outage_time_text(event.peak_utc),
                self._sun_outage_time_text(event.end_utc),
                event.peak_utc.astimezone(baku_offset).strftime("%H:%M:%S"),
                f"{event.duration_seconds / 60.0:.2f} min",
                f"{event.minimum_separation_deg:.6f}°",
                f"{event.threshold_deg:.6f}°",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.sun_outage_table.setItem(row, column, item)
        self.sun_outage_progress.setValue(100)
        self.sun_outage_progress.setFormat("Completed")
        self.sun_outage_calculate_button.setEnabled(True)
        self.sun_outage_cancel_button.setEnabled(False)
        self.sun_outage_export_button.setEnabled(bool(prediction.events))
        if prediction.events:
            shortest = min(
                event.minimum_separation_deg for event in prediction.events
            )
            longest = max(event.duration_seconds for event in prediction.events)
            self.sun_outage_summary.setText(
                f"{len(prediction.events)} interference-risk windows found for "
                f"{prediction.station.name} and "
                f"{self.active_profile.display_name} "
                f"({prediction.satellite_longitude_deg:+.6f}°E). "
                f"3 dB beamwidth: {prediction.beamwidth_3db_deg:.6f}°. "
                f"Closest alignment: {shortest:.6f}°. "
                f"Longest window: {longest / 60.0:.2f} min. "
                "Times are geometric risk windows, not guaranteed carrier outages."
            )
        else:
            self.sun_outage_summary.setText(
                "No Sun-disc/3 dB-beam intersection was found for the selected "
                "year, station, GEO slot and receiving-link parameters."
            )
        self.statusBar().showMessage(
            f"Sun-outage calculation completed: {len(prediction.events)} windows",
            8000,
        )


    def cancel_sun_outage_prediction(self):
        if self.sun_outage_thread is None or not self.sun_outage_thread.isRunning():
            return
        self.sun_outage_thread.requestInterruption()
        self.sun_outage_cancel_button.setEnabled(False)
        self.sun_outage_progress.setFormat("Cancelling...")


    def fail_sun_outage_prediction(self, message):
        self.sun_outage_summary.setText("SUN OUTAGE ERROR\n" + str(message))
        self.sun_outage_progress.setFormat("Failed")
        self.sun_outage_calculate_button.setEnabled(True)
        self.sun_outage_cancel_button.setEnabled(False)
        self.sun_outage_export_button.setEnabled(False)


    def cancelled_sun_outage_prediction(self):
        self.sun_outage_prediction = None
        self.sun_outage_summary.setText(
            "SUN OUTAGE SEARCH CANCELLED\nNo partial schedule was stored."
        )
        self.sun_outage_progress.setFormat("Cancelled")
        self.sun_outage_calculate_button.setEnabled(True)
        self.sun_outage_cancel_button.setEnabled(False)
        self.sun_outage_export_button.setEnabled(False)


    def cleanup_sun_outage_prediction(self):
        self.sun_outage_worker = None
        self.sun_outage_thread = None


    def export_sun_outage_csv(self):
        prediction = self.sun_outage_prediction
        if prediction is None:
            self.sun_outage_summary.setText(
                "SUN OUTAGE CSV EXPORT ERROR\nCalculate the schedule first."
            )
            return
        default_name = (
            f"sun_outage_{prediction.year}_"
            + re.sub(r"[^a-z0-9]+", "_", prediction.station.name.lower()).strip("_")
            + ".csv"
        )
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Sun Outage CSV"),
            default_name,
            "CSV Files (*.csv);;All Files (*)",
            options=theme.file_dialog_options(),
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".csv"):
            file_path += ".csv"
        try:
            exported = save_sun_outage_csv(prediction, file_path)
        except Exception as error:
            self.sun_outage_summary.setText(
                "SUN OUTAGE CSV EXPORT ERROR\n"
                f"{type(error).__name__}: {error}"
            )
            return
        self.statusBar().showMessage(
            f"Sun-outage CSV export completed: {exported.name}",
            10000,
        )


    def create_orbit_determination_workspace(self):
        """Build the measurement-driven weighted least-squares workspace."""

        page = QWidget()
        page.setObjectName("orbitDeterminationWorkspace")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(12, 10, 12, 16)
        page_layout.setSpacing(12)

        overview = QFrame()
        overview.setObjectName("metricCard")
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(16, 14, 16, 14)
        overview_layout.setSpacing(6)

        eyebrow = QLabel("ORBIT DETERMINATION WORKSPACE")
        eyebrow.setObjectName("missionEyebrow")
        title = QLabel("MEASUREMENT-BASED ORBIT SOLUTION")
        title.setObjectName("sectionTitle")
        description = QLabel(
            "Use the public fictional reference state across a selected UTC arc, "
            "compare computed observations with SYNTHETIC/DEMO tracking "
            "measurements, then estimate a corrected initial J2000 state with "
            "weighted batch least squares."
        )
        description.setObjectName("metricDetail")
        description.setWordWrap(True)
        self.od_workspace_status = QLabel("BUNDLED DATASET  ·  READY")
        self.od_workspace_status.setObjectName("heroStatus")
        self.od_workspace_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        overview_layout.addWidget(eyebrow)
        overview_layout.addWidget(title)
        overview_layout.addWidget(description)
        overview_layout.addWidget(
            self.od_workspace_status,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        page_layout.addWidget(overview)

        self.od_tabs = QTabWidget()
        self.od_tabs.setObjectName("orbitDeterminationTabs")

        measurements_page = QScrollArea()
        measurements_page.setWidgetResizable(True)
        measurements_page.setFrameShape(QFrame.Shape.NoFrame)
        measurements_page.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        measurements_content = QWidget()
        measurements_layout = QVBoxLayout(measurements_content)
        measurements_layout.setContentsMargins(10, 10, 10, 10)
        measurements_layout.setSpacing(10)
        dataset_box = QGroupBox("MEASUREMENT DATASET")
        dataset_box.setMinimumHeight(150)
        dataset_layout = QVBoxLayout(dataset_box)
        dataset_layout.setContentsMargins(16, 26, 16, 14)
        self.od_dataset_summary = QLabel("Loading bundled OD dataset...")
        self.od_dataset_summary.setObjectName("metricDetail")
        self.od_dataset_summary.setWordWrap(True)
        dataset_layout.addWidget(self.od_dataset_summary)
        self.od_reload_dataset_button = QPushButton("RELOAD BUNDLED DATASET")
        self.od_reload_dataset_button.setObjectName("ghostAction")
        self.od_reload_dataset_button.clicked.connect(
            self.reload_orbit_determination_dataset
        )
        dataset_layout.addWidget(
            self.od_reload_dataset_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        measurements_layout.addWidget(dataset_box)

        arc_box = QGroupBox("ESTIMATION ARC — UTC")
        arc_box.setMinimumHeight(150)
        arc_layout = QGridLayout(arc_box)
        arc_layout.setContentsMargins(16, 26, 16, 14)
        arc_layout.setHorizontalSpacing(10)
        arc_layout.setVerticalSpacing(8)
        self.od_arc_start = QLineEdit()
        self.od_arc_end = QLineEdit()
        self.od_arc_start.setPlaceholderText("2030-01-01T00:00:00+00:00")
        self.od_arc_end.setPlaceholderText("2030-01-02T00:00:00+00:00")
        arc_layout.addWidget(QLabel("Start epoch:"), 0, 0)
        arc_layout.addWidget(self.od_arc_start, 0, 1)
        arc_layout.addWidget(QLabel("End epoch:"), 1, 0)
        arc_layout.addWidget(self.od_arc_end, 1, 1)
        self.od_arc_count_label = QLabel("Measurements in selected arc: —")
        self.od_arc_count_label.setObjectName("inlineStatus")
        arc_layout.addWidget(self.od_arc_count_label, 2, 0, 1, 2)
        self.od_arc_start.editingFinished.connect(
            self.update_orbit_determination_arc_summary
        )
        self.od_arc_end.editingFinished.connect(
            self.update_orbit_determination_arc_summary
        )
        measurements_layout.addWidget(arc_box)

        self.od_measurement_table = QTableWidget(0, 6)
        self.od_measurement_table.setHorizontalHeaderLabels([
            "ID", "UTC", "Station", "Type", "Observed", "Quality"
        ])
        self.od_measurement_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.od_measurement_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.od_measurement_table.verticalHeader().setVisible(False)
        self.od_measurement_table.setMinimumHeight(260)
        measurement_header = self.od_measurement_table.horizontalHeader()
        measurement_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        measurement_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in range(2, 6):
            measurement_header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        measurements_layout.addWidget(self.od_measurement_table, 1)
        measurements_page.setWidget(measurements_content)
        self.od_tabs.addTab(measurements_page, "MEASUREMENTS")

        stations_page = QWidget()
        stations_layout = QVBoxLayout(stations_page)
        stations_layout.setContentsMargins(10, 10, 10, 10)
        station_note = QLabel(
            "Fictional WGS-84 station coordinates and 1σ measurement "
            "noise are applied directly in the observation model."
        )
        station_note.setObjectName("metricDetail")
        station_note.setWordWrap(True)
        stations_layout.addWidget(station_note)
        self.od_station_table = QTableWidget(0, 13)
        self.od_station_table.setHorizontalHeaderLabels([
            "ID", "Station", "Latitude [deg]", "Longitude [deg]", "Height [km]",
            "Range bias [km]", "Az bias [deg]", "El bias [deg]",
            "Range σ [km]", "Az σ [deg]", "El σ [deg]", "Pressure [mbar]", "Temp [°C]",
        ])
        self.od_station_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.od_station_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.od_station_table.verticalHeader().setVisible(False)
        self.od_station_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        stations_layout.addWidget(self.od_station_table)
        self.od_tabs.addTab(stations_page, "GROUND STATIONS")

        estimation_page = QWidget()
        estimation_layout = QVBoxLayout(estimation_page)
        estimation_layout.setContentsMargins(10, 10, 10, 10)
        estimation_layout.setSpacing(10)
        source_box = QGroupBox("SUPPLIED PROPAGATION FILE")
        source_layout = QVBoxLayout(source_box)
        source_layout.setContentsMargins(16, 26, 16, 14)
        self.od_propagation_source_label = QLabel(
            "SYNTHETIC_DEMO_MEMORY · generated fictional orbit · in-memory ephemeris\n"
            "OPA's numerical propagator is not used here. Weighted batch least "
            "squares estimates corrections directly around the supplied trajectory."
        )
        self.od_propagation_source_label.setWordWrap(True)
        source_layout.addWidget(self.od_propagation_source_label)
        estimation_layout.addWidget(source_box)

        solver_box = QGroupBox("WEIGHTED BATCH LEAST SQUARES")
        solver_layout = QGridLayout(solver_box)
        solver_layout.setContentsMargins(16, 26, 16, 14)
        self.od_iterations = QSpinBox()
        self.od_iterations.setRange(1, 8)
        self.od_iterations.setValue(4)
        self.od_rejection_sigma = QDoubleSpinBox()
        self.od_rejection_sigma.setRange(2.0, 10.0)
        self.od_rejection_sigma.setDecimals(1)
        self.od_rejection_sigma.setValue(3.0)
        solver_layout.addWidget(QLabel("Maximum iterations:"), 0, 0)
        solver_layout.addWidget(self.od_iterations, 0, 1)
        solver_layout.addWidget(QLabel("Post-fit rejection [σ]:"), 0, 2)
        solver_layout.addWidget(self.od_rejection_sigma, 0, 3)
        self.od_run_button = QPushButton("RUN ORBIT DETERMINATION")
        self.od_run_button.setObjectName("primaryAction")
        self.od_run_button.clicked.connect(self.run_orbit_determination)
        self.od_cancel_button = QPushButton("CANCEL")
        self.od_cancel_button.setObjectName("ghostAction")
        self.od_cancel_button.setEnabled(False)
        self.od_cancel_button.clicked.connect(self.cancel_orbit_determination)
        self.od_refresh_memory_button = QPushButton("REFRESH MEMORY")
        self.od_refresh_memory_button.setObjectName("ghostAction")
        self.od_refresh_memory_button.setToolTip(
            "Clear accumulated least-squares corrections and restart from the supplied orbit."
        )
        self.od_refresh_memory_button.clicked.connect(
            self.refresh_orbit_determination_memory
        )
        solver_layout.addWidget(self.od_run_button, 1, 0, 1, 2)
        solver_layout.addWidget(self.od_cancel_button, 1, 2)
        solver_layout.addWidget(self.od_refresh_memory_button, 1, 3)
        estimation_layout.addWidget(solver_box)
        self.od_progress = QProgressBar()
        self.od_progress.setRange(0, 100)
        self.od_progress.setValue(0)
        self.od_stage_label = QLabel("READY")
        self.od_stage_label.setObjectName("inlineStatus")
        estimation_layout.addWidget(self.od_progress)
        estimation_layout.addWidget(self.od_stage_label)
        self.od_estimation_output = QTextEdit()
        self.od_estimation_output.setReadOnly(True)
        self.od_estimation_output.setPlainText(
            "No orbit-determination solution has been run."
        )
        estimation_layout.addWidget(self.od_estimation_output, 1)
        self.od_tabs.addTab(estimation_page, "ESTIMATION")

        residuals_page = QWidget()
        residuals_layout = QVBoxLayout(residuals_page)
        residuals_layout.setContentsMargins(10, 10, 10, 10)
        self.od_residual_summary_table = QTableWidget(0, 9)
        self.od_residual_summary_table.setHorizontalHeaderLabels([
            "Station / Type", "Noise", "Count", "Rejected", "Pre mean",
            "Pre RMS", "Post mean", "Post RMS", "Unit",
        ])
        self.od_residual_summary_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.od_residual_summary_table.verticalHeader().setVisible(False)
        self.od_residual_summary_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        residuals_layout.addWidget(self.od_residual_summary_table)
        self.od_residual_table = QTableWidget(0, 10)
        self.od_residual_table.setHorizontalHeaderLabels([
            "ID", "UTC", "Station", "Type", "Observed", "Prefit", "Postfit",
            "Pre residual", "Post residual", "Used",
        ])
        self.od_residual_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.od_residual_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.od_residual_table.verticalHeader().setVisible(False)
        self.od_residual_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        residuals_layout.addWidget(self.od_residual_table, 1)
        self.od_tabs.addTab(residuals_page, "RESIDUALS")

        determinations_page = QWidget()
        determinations_layout = QVBoxLayout(determinations_page)
        determinations_layout.setContentsMargins(10, 10, 10, 10)
        determination_note = QLabel(
            "Every synthetic reference epoch inside the selected arc is evaluated. "
            "Each RUN replaces this table with the latest weighted least-squares "
            "trajectory and keeps the convergence summary in Run History."
        )
        determination_note.setWordWrap(True)
        determinations_layout.addWidget(determination_note)
        self.od_determination_table = QTableWidget(0, 15)
        self.od_determination_table.setHorizontalHeaderLabels([
            "UTC", "File X", "File Y", "File Z", "File Vx", "File Vy", "File Vz",
            "OD X", "OD Y", "OD Z", "OD Vx", "OD Vy", "OD Vz",
            "ΔR [m]", "ΔV [mm/s]",
        ])
        self.od_determination_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.od_determination_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.od_determination_table.verticalHeader().setVisible(False)
        self.od_determination_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        determinations_layout.addWidget(self.od_determination_table, 1)
        self.od_tabs.addTab(determinations_page, "DETERMINATIONS")

        validation_page = QWidget()
        validation_layout = QVBoxLayout(validation_page)
        validation_layout.setContentsMargins(10, 10, 10, 10)
        self.od_state_table = QTableWidget(6, 5)
        self.od_state_table.setHorizontalHeaderLabels([
            "Component", "Initial", "Correction", "Corrected", "1σ"
        ])
        self.od_state_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.od_state_table.verticalHeader().setVisible(False)
        self.od_state_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        validation_layout.addWidget(self.od_state_table)
        self.od_validation_output = QTextEdit()
        self.od_validation_output.setReadOnly(True)
        self.od_validation_output.setPlainText(
            "Run orbit determination to compare the propagated solution "
            "with the synthetic reference orbit."
        )
        validation_layout.addWidget(self.od_validation_output, 1)
        self.od_run_history_table = QTableWidget(0, 8)
        self.od_run_history_table.setHorizontalHeaderLabels([
            "Run", "Weighted prefit", "Weighted postfit", "Improvement",
            "Noon ΔR [m]", "Noon ΔV [mm/s]", "Max ΔR [m]", "Last ΔR [m]",
        ])
        self.od_run_history_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.od_run_history_table.verticalHeader().setVisible(False)
        self.od_run_history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.od_run_history_table.setMaximumHeight(190)
        validation_layout.addWidget(self.od_run_history_table)
        self.od_use_state_button = QPushButton(
            "USE CORRECTED STATE IN PROPAGATION"
        )
        self.od_use_state_button.setObjectName("primaryAction")
        self.od_use_state_button.setEnabled(False)
        self.od_use_state_button.clicked.connect(
            self.use_corrected_od_state_in_propagation
        )
        validation_layout.addWidget(
            self.od_use_state_button,
            0,
            Qt.AlignmentFlag.AlignRight,
        )
        self.od_tabs.addTab(validation_page, "VALIDATION")

        for index, label in enumerate((
            "MEASUREMENTS", "GROUND STATIONS", "ESTIMATION", "RESIDUALS",
            "DETERMINATIONS", "VALIDATION"
        )):
            self.od_tabs.tabBar().setTabData(index, label)

        page_layout.addWidget(self.od_tabs, 1)
        self.od_dataset = None
        self._od_memory_state = None
        self._od_memory_arc = None
        self._od_run_history = []
        self.reload_orbit_determination_dataset(reset_arc=True)
        return page


    def reload_orbit_determination_dataset(self, _checked=False, reset_arc=False):
        """Reload the bundled measurements without mutating their source files."""

        try:
            dataset = load_orbit_determination_dataset()
            self.od_dataset = dataset
            if reset_arc or not self.od_arc_start.text().strip():
                arc_start = dataset.reference_start
                arc_end = min(
                    arc_start + timedelta(days=1),
                    dataset.measurement_end,
                )
                self.od_arc_start.setText(arc_start.isoformat())
                self.od_arc_end.setText(arc_end.isoformat())
            discontinuities = sum(
                1 for item in dataset.reference_orbit if item.discontinuity
            )
            self.od_dataset_summary.setText(
                f"{dataset.display_name}\n"
                f"Measurements: {len(dataset.measurements):,} · "
                f"{dataset.measurement_start.isoformat()} → "
                f"{dataset.measurement_end.isoformat()}\n"
                f"Reference orbit: {len(dataset.reference_orbit):,} states · "
                f"{dataset.reference_start.isoformat()} → "
                f"{dataset.reference_end.isoformat()} · "
                f"discontinuities: {discontinuities}\n"
                f"Frame: {dataset.frame_note}"
            )
            self.od_workspace_status.setText("BUNDLED DATASET  ·  READY")
            _set_status_role(self.od_workspace_status, "ok")
            self.populate_orbit_determination_source_tables()
            self.update_orbit_determination_arc_summary()
            self.refresh_orbit_determination_memory(show_status=False)
            return True
        except Exception as error:
            self.od_dataset = None
            self.od_workspace_status.setText("DATASET ERROR")
            _set_status_role(self.od_workspace_status, "error")
            self.od_dataset_summary.setText(
                f"OD DATASET ERROR\n{type(error).__name__}: {error}"
            )
            self.od_run_button.setEnabled(False)
            return False


    def populate_orbit_determination_source_tables(self):
        dataset = self.od_dataset
        preview = dataset.measurements[:500]
        self.od_measurement_table.setRowCount(len(preview))
        for row, measurement in enumerate(preview):
            station = dataset.stations[measurement.station_id]
            values = (
                str(measurement.measurement_id),
                measurement.epoch.isoformat(),
                f"{measurement.station_id} · {station.name}",
                measurement.measurement_type,
                f"{measurement.value:.9f}",
                str(measurement.quality_factor),
            )
            for column, value in enumerate(values):
                self.od_measurement_table.setItem(row, column, QTableWidgetItem(value))

        stations = sorted(dataset.stations.values(), key=lambda item: item.station_id)
        self.od_station_table.setRowCount(len(stations))
        for row, station in enumerate(stations):
            values = (
                station.station_id, station.name,
                f"{station.latitude_deg:.8f}", f"{station.longitude_deg:.8f}",
                f"{station.height_km:.6f}", f"{station.biases['Range']:.9f}",
                f"{station.biases['Azimuth']:.9f}", f"{station.biases['Elevation']:.9f}",
                f"{station.noises['Range']:.6f}", f"{station.noises['Azimuth']:.6f}",
                f"{station.noises['Elevation']:.6f}", f"{station.pressure_mbar:.3f}",
                f"{station.temperature_c:.3f}",
            )
            for column, value in enumerate(values):
                self.od_station_table.setItem(row, column, QTableWidgetItem(value))


    def update_orbit_determination_arc_summary(self):
        if self.od_dataset is None:
            return False
        try:
            start = self.parse_propagation_epoch(self.od_arc_start.text())
            end = self.parse_propagation_epoch(self.od_arc_end.text())
            count = sum(
                start <= item.epoch <= end
                for item in self.od_dataset.measurements
            )
            jumps = sum(
                item.discontinuity and start < item.epoch <= end
                for item in self.od_dataset.reference_orbit
            )
            self.od_arc_count_label.setText(
                f"Measurements in selected arc: {count:,} · "
                f"reference discontinuities: {jumps}"
            )
            _set_status_role(self.od_arc_count_label, "ok" if count >= 7 else "warning")
            return count >= 7
        except Exception as error:
            self.od_arc_count_label.setText(f"Arc input error: {error}")
            _set_status_role(self.od_arc_count_label, "error")
            return False


    def refresh_orbit_determination_memory(self, _checked=False, show_status=True):
        """Reset iterative LS seeding and its comparison history."""

        thread = self.orbit_determination_thread
        if thread is not None and thread.isRunning():
            return False
        self._od_memory_state = None
        self._od_memory_arc = None
        self._od_run_history = []
        self.latest_orbit_determination = None
        self.od_run_history_table.setRowCount(0)
        self.od_residual_summary_table.setRowCount(0)
        self.od_residual_table.setRowCount(0)
        self.od_determination_table.setRowCount(0)
        self.od_state_table.clearContents()
        self.od_use_state_button.setEnabled(False)
        self.od_progress.setValue(0)
        self.od_progress.setFormat("%p%")
        if show_status:
            self.od_estimation_output.setPlainText(
                "LEAST-SQUARES MEMORY REFRESHED\n\n"
                "Accumulated corrections and run history were cleared. "
                "The next run will start from the supplied orbit-file state at "
                "the midpoint determination epoch."
            )
            self.od_validation_output.setPlainText(
                "No accumulated solution. Run Orbit Determination to compare "
                "normal propagation with the least-squares corrected propagation."
            )
            self.od_stage_label.setText("MEMORY REFRESHED · READY")
        return True


    def run_orbit_determination(self):
        if self.orbit_determination_thread is not None:
            return False
        if self.od_dataset is None:
            self.od_estimation_output.setPlainText("OD DATASET ERROR\nDataset is not loaded.")
            return False
        competing = (
            self.propagation_thread,
            self.eclipse_thread,
            self.reference_comparison_thread,
        )
        if any(thread is not None and thread.isRunning() for thread in competing):
            self.od_estimation_output.setPlainText(
                "ORBIT DETERMINATION BUSY\n\n"
                "Stop Propagation, Eclipse or Reference Lab processing first."
            )
            return False
        try:
            arc_start = self.parse_propagation_epoch(self.od_arc_start.text())
            arc_end = self.parse_propagation_epoch(self.od_arc_end.text())
            if not self.update_orbit_determination_arc_summary():
                raise OrbitDeterminationError(
                    "The selected arc does not contain enough valid measurements."
                )
            arc_key = (arc_start, arc_end)
            if self._od_memory_arc != arc_key:
                self.refresh_orbit_determination_memory(show_status=False)
                self._od_memory_arc = arc_key
            seed_state = (
                None if self._od_memory_state is None
                else self._od_memory_state.copy()
            )
            self.latest_orbit_determination = None
            self.od_use_state_button.setEnabled(False)
            self.od_run_button.setEnabled(False)
            self.od_cancel_button.setEnabled(True)
            self.od_refresh_memory_button.setEnabled(False)
            self.od_progress.setValue(0)
            self.od_progress.setFormat("%p%")
            self.od_stage_label.setText("STARTING WEIGHTED LEAST SQUARES")
            self.od_estimation_output.setPlainText(
                "ORBIT DETERMINATION STARTED\n\n"
                f"Arc: {arc_start.isoformat()} → {arc_end.isoformat()}\n"
                f"Determination epoch: {arc_start + (arc_end - arc_start) / 2}\n"
                "Solve-for vector: midpoint J2000 X/Y/Z/Vx/Vy/Vz\n"
                + (
                    "Starting point: previous least-squares corrected state.\n"
                    if seed_state is not None else
                    "Starting point: supplied orbit-file midpoint state.\n"
                )
                + "Source trajectory: SYNTHETIC/DEMO memory dataset.\n"
                "The supplied station biases, noise weights and atmospheric "
                "refraction are active. OPA numerical propagation is not used."
            )
            self._od_timer_was_active = self.timer.isActive()
            if self._od_timer_was_active:
                self.timer.stop()
            self.orbit_determination_thread = QThread(self)
            self.orbit_determination_worker = OrbitDeterminationWorker({
                "dataset": self.od_dataset,
                "arc_start": arc_start,
                "arc_end": arc_end,
                "initial_state": seed_state,
                "max_iterations": self.od_iterations.value(),
                "rejection_sigma": self.od_rejection_sigma.value(),
            })
            self.orbit_determination_worker.moveToThread(
                self.orbit_determination_thread
            )
            self.orbit_determination_thread.started.connect(
                self.orbit_determination_worker.run
            )
            self.orbit_determination_worker.progress.connect(
                self.od_progress.setValue
            )
            self.orbit_determination_worker.stage.connect(
                self.od_stage_label.setText
            )
            self.orbit_determination_worker.completed.connect(
                self.finish_orbit_determination
            )
            self.orbit_determination_worker.failed.connect(
                self.fail_orbit_determination
            )
            self.orbit_determination_worker.cancelled.connect(
                self.cancelled_orbit_determination
            )
            self.orbit_determination_worker.completed.connect(
                self.orbit_determination_thread.quit
            )
            self.orbit_determination_worker.failed.connect(
                self.orbit_determination_thread.quit
            )
            self.orbit_determination_worker.cancelled.connect(
                self.orbit_determination_thread.quit
            )
            self.orbit_determination_thread.finished.connect(
                self.orbit_determination_worker.deleteLater
            )
            self.orbit_determination_thread.finished.connect(
                self.orbit_determination_thread.deleteLater
            )
            self.orbit_determination_thread.finished.connect(
                self.cleanup_orbit_determination
            )
            self.orbit_determination_thread.start()
            return True
        except Exception as error:
            self.od_estimation_output.setPlainText(
                f"ORBIT DETERMINATION INPUT ERROR\n\n{type(error).__name__}: {error}"
            )
            return False


    def cancel_orbit_determination(self):
        thread = self.orbit_determination_thread
        if thread is None or not thread.isRunning():
            return False
        thread.requestInterruption()
        self.od_cancel_button.setEnabled(False)
        self.od_progress.setFormat("Cancelling...")
        return True


    def finish_orbit_determination(self, result):
        self.latest_orbit_determination = result
        self._od_memory_state = result.corrected_state.copy()
        self._od_memory_arc = (result.arc_start, result.arc_end)
        correction = result.state_correction
        self.od_progress.setValue(100)
        self.od_progress.setFormat("Completed")
        self.od_stage_label.setText("WEIGHTED LEAST SQUARES COMPLETED")
        self.od_run_button.setEnabled(True)
        self.od_cancel_button.setEnabled(False)
        self.od_refresh_memory_button.setEnabled(True)
        self.od_use_state_button.setEnabled(True)
        self.od_workspace_status.setText("OD SOLUTION  ·  AVAILABLE")
        _set_status_role(self.od_workspace_status, "ok")
        self.od_estimation_output.setPlainText(
            "WEIGHTED BATCH LEAST-SQUARES COMPLETED\n"
            + "=" * 76
            + f"\nArc: {result.arc_start.isoformat()} → {result.arc_end.isoformat()}"
            + f"\nDetermination epoch: {result.estimation_epoch.isoformat()}"
            + f"\nMeasurements: {len(result.measurements):,} · "
            + f"accepted {int(np.sum(result.accepted_mask)):,} · "
            + f"rejected {int(np.sum(~result.accepted_mask)):,}"
            + f"\nIterations: {result.iterations} · "
            + ("converged" if result.converged else "iteration limit reached")
            + f"\nWeighted RMS: {result.weighted_rms_prefit:.6f} → "
            + f"{result.weighted_rms_postfit:.6f}"
            + f"\nNormal-matrix condition: {result.condition_number:.6e}"
            + f"\nDiscontinuities represented in orbit file: {result.state_jump_count}"
            + "\n\nINITIAL-STATE CORRECTION — J2000"
            + f"\nΔX  = {correction[0]:+.9f} km"
            + f"\nΔY  = {correction[1]:+.9f} km"
            + f"\nΔZ  = {correction[2]:+.9f} km"
            + f"\nΔVx = {correction[3]:+.12f} km/s"
            + f"\nΔVy = {correction[4]:+.12f} km/s"
            + f"\nΔVz = {correction[5]:+.12f} km/s"
        )
        self.populate_orbit_determination_results(result)
        self.od_tabs.setCurrentIndex(4)


    def populate_orbit_determination_results(self, result):
        tables = (self.od_residual_summary_table, self.od_residual_table)
        for table in tables:
            table.setUpdatesEnabled(False)
        try:
            self.od_residual_summary_table.setRowCount(len(result.summaries))
            for row, summary in enumerate(result.summaries):
                unit = "km" if summary.measurement_type == "Range" else "deg"
                values = (
                    f"{summary.station_name} · {summary.measurement_type}",
                    f"{summary.noise:.6f}", str(summary.count), str(summary.rejected),
                    f"{summary.prefit_mean:+.9f}", f"{summary.prefit_rms:.9f}",
                    f"{summary.postfit_mean:+.9f}", f"{summary.postfit_rms:.9f}", unit,
                )
                for column, value in enumerate(values):
                    self.od_residual_summary_table.setItem(
                        row, column, QTableWidgetItem(value)
                    )

            self.od_residual_table.setRowCount(len(result.measurements))
            for row, measurement in enumerate(result.measurements):
                used = bool(result.accepted_mask[row])
                values = (
                    str(measurement.measurement_id), measurement.epoch.isoformat(),
                    measurement.station_id, measurement.measurement_type,
                    f"{measurement.value:.9f}", f"{result.predicted_prefit[row]:.9f}",
                    f"{result.predicted_postfit[row]:.9f}",
                    f"{result.residuals_prefit[row]:+.9f}",
                    f"{result.residuals_postfit[row]:+.9f}",
                    "YES" if used else "REJECTED",
                )
                for column, value in enumerate(values):
                    self.od_residual_table.setItem(
                        row, column, QTableWidgetItem(value)
                    )
        finally:
            for table in tables:
                table.setUpdatesEnabled(True)

        self.od_determination_table.setUpdatesEnabled(False)
        try:
            self.od_determination_table.setRowCount(len(result.reference_epochs))
            for row, epoch in enumerate(result.reference_epochs):
                file_state = result.determination_file_states[row]
                od_state = result.determination_postfit_states[row]
                position_difference_m = 1000.0 * np.linalg.norm(
                    od_state[:3] - file_state[:3]
                )
                velocity_difference_mm_s = 1.0e6 * np.linalg.norm(
                    od_state[3:] - file_state[3:]
                )
                values = (
                    epoch.isoformat(),
                    *(f"{value:+.12f}" for value in file_state),
                    *(f"{value:+.12f}" for value in od_state),
                    f"{position_difference_m:.6f}",
                    f"{velocity_difference_mm_s:.6f}",
                )
                for column, value in enumerate(values):
                    self.od_determination_table.setItem(
                        row, column, QTableWidgetItem(value)
                    )
        finally:
            self.od_determination_table.setUpdatesEnabled(True)

        components = ("X [km]", "Y [km]", "Z [km]", "Vx [km/s]", "Vy [km/s]", "Vz [km/s]")
        for row, component in enumerate(components):
            values = (
                component, f"{result.initial_state[row]:+.12f}",
                f"{result.state_correction[row]:+.12f}",
                f"{result.corrected_state[row]:+.12f}",
                f"{result.parameter_sigmas[row]:.6e}",
            )
            for column, value in enumerate(values):
                self.od_state_table.setItem(row, column, QTableWidgetItem(value))

        if len(result.reference_epochs):
            pre_position = result.reference_position_errors_prefit_km
            post_position = result.reference_position_errors_postfit_km
            pre_velocity = result.reference_velocity_errors_prefit_km_s
            post_velocity = result.reference_velocity_errors_postfit_km_s
            pre_position_rms = float(np.sqrt(np.mean(pre_position ** 2)))
            post_position_rms = float(np.sqrt(np.mean(post_position ** 2)))
            pre_velocity_rms = float(np.sqrt(np.mean(pre_velocity ** 2)))
            post_velocity_rms = float(np.sqrt(np.mean(post_velocity ** 2)))
            improvement = (
                100.0 * (
                    result.weighted_rms_prefit - result.weighted_rms_postfit
                ) / result.weighted_rms_prefit
                if result.weighted_rms_prefit > 0.0 else 0.0
            )
            self._od_run_history.append({
                "weighted_prefit": float(result.weighted_rms_prefit),
                "weighted_postfit": float(result.weighted_rms_postfit),
                "noon_position_m": 1000.0 * float(
                    result.noon_position_error_postfit_km or 0.0
                ),
                "noon_velocity_mm_s": 1.0e6 * float(
                    result.noon_velocity_error_postfit_km_s or 0.0
                ),
                "maximum_m": 1000.0 * float(np.max(post_position)),
                "last_m": 1000.0 * float(post_position[-1]),
                "improvement": improvement,
            })
            self.od_run_history_table.setRowCount(len(self._od_run_history))
            for row, run in enumerate(self._od_run_history):
                values = (
                    str(row + 1), f"{run['weighted_prefit']:.6f}",
                    f"{run['weighted_postfit']:.6f}",
                    f"{run['improvement']:+.3f}%",
                    f"{run['noon_position_m']:.6f}",
                    f"{run['noon_velocity_mm_s']:.6f}",
                    f"{run['maximum_m']:.6f}", f"{run['last_m']:.6f}",
                )
                for column, value in enumerate(values):
                    self.od_run_history_table.setItem(
                        row, column, QTableWidgetItem(value)
                    )
            validation_text = (
                "SYNTHETIC REFERENCE vs LEAST-SQUARES CORRECTED TRAJECTORY\n"
                + "=" * 76
                + f"\nReference samples: {len(result.reference_epochs):,}"
                + (
                    f"\n\n24 AUG 2026 · 12:00 UTC FILE ERROR"
                    f"\nPosition: {result.noon_position_error_prefit_km:.9f} → "
                    f"{result.noon_position_error_postfit_km:.9f} km"
                    f"\nVelocity: {result.noon_velocity_error_prefit_km_s:.12f} → "
                    f"{result.noon_velocity_error_postfit_km_s:.12f} km/s"
                    f"\n\nFILE STATE — J2000 [km, km/s]"
                    f"\nX  {result.initial_state[0]:+.12f}"
                    f"\nY  {result.initial_state[1]:+.12f}"
                    f"\nZ  {result.initial_state[2]:+.12f}"
                    f"\nVx {result.initial_state[3]:+.12f}"
                    f"\nVy {result.initial_state[4]:+.12f}"
                    f"\nVz {result.initial_state[5]:+.12f}"
                    f"\n\nDETERMINATION STATE — J2000 [km, km/s]"
                    f"\nX  {result.corrected_state[0]:+.12f}"
                    f"\nY  {result.corrected_state[1]:+.12f}"
                    f"\nZ  {result.corrected_state[2]:+.12f}"
                    f"\nVx {result.corrected_state[3]:+.12f}"
                    f"\nVy {result.corrected_state[4]:+.12f}"
                    f"\nVz {result.corrected_state[5]:+.12f}"
                    if result.noon_epoch is not None else
                    "\n\n12:00 UTC is outside the selected arc."
                )
                + "\n\nPOSITION ERROR [km]"
                + f"\nFile-prefit RMS:        {pre_position_rms:.9f}"
                + f"\nLeast-squares RMS:      {post_position_rms:.9f}"
                + f"\nMinimum error:          {np.min(post_position):.9f}"
                + f"\nMaximum error:          {np.max(post_position):.9f}"
                + f"\nLast error:             {post_position[-1]:.9f}"
                + f"\nImprovement this run:   {improvement:+.3f}%"
                + "\n\nVELOCITY ERROR [km/s]"
                + f"\nFile-prefit RMS:        {pre_velocity_rms:.12f}"
                + f"\nLeast-squares RMS:      {post_velocity_rms:.12f}"
                + f"\nMinimum error:          {np.min(post_velocity):.12f}"
                + f"\nMaximum error:          {np.max(post_velocity):.12f}"
                + f"\nLast error:             {post_velocity[-1]:.12f}"
                + f"\n\nRun number in current memory: {len(self._od_run_history)}"
                + "\n\nThe corrected state changes only this OD solution. "
                + "Use the button below to copy it into the existing Propagation input."
            )
        else:
            validation_text = "No reference-orbit samples fall inside the selected arc."
        self.od_validation_output.setPlainText(validation_text)


    def fail_orbit_determination(self, message):
        self.od_estimation_output.setPlainText(
            "ORBIT DETERMINATION ERROR\n\n" + str(message)
        )
        self.od_progress.setFormat("Error")
        self.od_stage_label.setText("FAILED")
        self.od_run_button.setEnabled(True)
        self.od_cancel_button.setEnabled(False)
        self.od_refresh_memory_button.setEnabled(True)
        self.od_workspace_status.setText("OD SOLUTION  ·  ERROR")
        _set_status_role(self.od_workspace_status, "error")


    def cancelled_orbit_determination(self):
        self.od_estimation_output.setPlainText(
            "ORBIT DETERMINATION CANCELLED\n\nNo partial solution was stored."
        )
        self.od_progress.setFormat("Cancelled")
        self.od_stage_label.setText("CANCELLED")
        self.od_run_button.setEnabled(True)
        self.od_cancel_button.setEnabled(False)
        self.od_refresh_memory_button.setEnabled(True)


    def cleanup_orbit_determination(self):
        self.orbit_determination_worker = None
        self.orbit_determination_thread = None
        if getattr(self, "_od_timer_was_active", False):
            self.timer.start(1000)
        self._od_timer_was_active = False


    def use_corrected_od_state_in_propagation(self):
        result = self.latest_orbit_determination
        if result is None:
            return False
        self.prop_epoch.setText(result.estimation_epoch.isoformat())
        for editor, value in zip((
            self.prop_x, self.prop_y, self.prop_z,
            self.prop_vx, self.prop_vy, self.prop_vz,
        ), result.corrected_state):
            editor.setText(f"{float(value):.12f}")
        self.prop_days.setText(
            f"{(result.arc_end - result.arc_start).total_seconds() / 86400.0:.9f}"
        )
        self.select_tab_by_label("PROPAGATION")
        self.statusBar().showMessage(
            "Corrected OD initial state copied to Propagation. Review the SRP "
            "spacecraft model before running.",
            10000,
        )
        return True


    # ========================================================
    # PROPAGATION INPUT PAGE
    # ========================================================

    def create_propagation_page(self):

        # The propagation page can become tall, especially on laptops.
        # Put its contents inside a scroll area so the form never gets
        # vertically compressed or clipped.
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        self.propagation_scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        content = QWidget()
        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(12, 10, 12, 16)
        main_layout.setSpacing(14)

        description = QLabel(
            "Enter an initial J2000 Cartesian state and propagate it "
            "with modular Earth EGM96, Moon, Sun third-body gravity and "
            "the selected spacecraft solar radiation pressure model."
        )
        description.setWordWrap(True)
        description.setObjectName("metricDetail")
        main_layout.addWidget(description)

        # INITIAL STATE
        state_box = QGroupBox("INITIAL STATE — J2000")
        state_box.setMinimumHeight(330)

        state_form = QFormLayout(state_box)
        state_form.setContentsMargins(18, 26, 18, 18)
        state_form.setHorizontalSpacing(18)
        state_form.setVerticalSpacing(10)
        state_form.setRowWrapPolicy(
            QFormLayout.RowWrapPolicy.DontWrapRows
        )
        state_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.prop_epoch = QLineEdit()
        self.prop_epoch.setPlaceholderText("2030-01-01T00:00:00+00:00")
        self.prop_epoch_picker_button = QPushButton("SELECT DATE / TIME")
        self.prop_epoch_picker_button.setObjectName("ghostAction")
        self.prop_epoch_picker_button.setMinimumHeight(36)
        self.prop_epoch_picker_button.setToolTip(
            "Open a UTC calendar and time selector; keyboard entry remains optional."
        )
        self.prop_epoch_picker_button.clicked.connect(
            self.open_propagation_epoch_picker
        )

        epoch_input_row = QWidget()
        epoch_input_layout = QHBoxLayout(epoch_input_row)
        epoch_input_layout.setContentsMargins(0, 0, 0, 0)
        epoch_input_layout.setSpacing(8)
        epoch_input_layout.addWidget(self.prop_epoch, 1)
        epoch_input_layout.addWidget(self.prop_epoch_picker_button)

        self.prop_x = QLineEdit()
        self.prop_y = QLineEdit()
        self.prop_z = QLineEdit()
        self.prop_vx = QLineEdit()
        self.prop_vy = QLineEdit()
        self.prop_vz = QLineEdit()

        for input_box in (
            self.prop_epoch,
            self.prop_x,
            self.prop_y,
            self.prop_z,
            self.prop_vx,
            self.prop_vy,
            self.prop_vz,
        ):
            input_box.setMinimumHeight(36)
            input_box.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

        state_form.addRow("Epoch UTC:", epoch_input_row)
        state_form.addRow("X [km]:", self.prop_x)
        state_form.addRow("Y [km]:", self.prop_y)
        state_form.addRow("Z [km]:", self.prop_z)
        state_form.addRow("Vx [km/s]:", self.prop_vx)
        state_form.addRow("Vy [km/s]:", self.prop_vy)
        state_form.addRow("Vz [km/s]:", self.prop_vz)

        main_layout.addWidget(state_box)

        # SETTINGS
        settings_box = QGroupBox("PROPAGATION SETTINGS")
        settings_box.setMinimumHeight(390)
        self.propagation_settings_box = settings_box

        settings_form = QFormLayout(settings_box)
        settings_form.setContentsMargins(18, 26, 18, 18)
        settings_form.setHorizontalSpacing(18)
        settings_form.setVerticalSpacing(10)
        settings_form.setRowWrapPolicy(
            QFormLayout.RowWrapPolicy.DontWrapRows
        )

        self.prop_days = QLineEdit("30")
        self.prop_days.setMinimumHeight(36)

        self.step_minutes = QSpinBox()
        self.step_minutes.setRange(0, 1000000)
        self.step_minutes.setValue(15)
        self.step_minutes.setSuffix(" min")
        self.step_minutes.setMinimumHeight(36)

        self.step_seconds = QSpinBox()
        self.step_seconds.setRange(0, 59)
        self.step_seconds.setValue(0)
        self.step_seconds.setSuffix(" sec")
        self.step_seconds.setMinimumHeight(36)

        self.prop_j2 = QCheckBox(
            "Include Earth EGM96 harmonics"
        )
        self.prop_j2.setChecked(True)

        self.prop_egm_degree = QComboBox()
        for degree in (2, 3, 4):
            self.prop_egm_degree.addItem(
                f"Degree/order {degree}×{degree}", degree
            )
        self.prop_egm_degree.setCurrentIndex(
            self.prop_egm_degree.findData(4)
        )
        self.prop_egm_degree.setMinimumHeight(36)
        self.prop_egm_degree.setToolTip(
            "Coupled EGM96 degree/order supported by the existing gravity model."
        )

        self.prop_moon = QCheckBox("Include Moon perturbation")
        self.prop_moon.setChecked(True)

        self.prop_sun = QCheckBox("Include Sun third-body gravity")
        self.prop_sun.setChecked(True)
        self.prop_sun.setToolTip(
            "Differential solar gravity from the DE440 Earth-to-Sun vector. "
            "This is separate from solar radiation pressure."
        )

        self.prop_srp = QCheckBox(
            "Include solar radiation pressure — SYNTHETIC GEO DEMO"
        )
        self.prop_srp.setChecked(False)
        self.prop_srp.setToolTip(
            "SYNTHETIC/DEMO box-wing SRP uses the active public profile's "
            "fictional mass and TrueSun array geometry with Earth "
            "umbra/penumbra. No operator calibration is bundled."
        )

        self.prop_srp_model = QComboBox()
        self.prop_srp_model.addItem(
            "Active profile SRP model",
            PROPAGATION_SRP_ACTIVE_PROFILE,
        )
        self.prop_srp_model.addItem(
            "SYNTHETIC/DEMO fixed-coefficient SRP model",
            PROPAGATION_SRP_DEMO_EQUIVALENT,
        )
        self.prop_srp_model.addItem(
            "Manual SRP parameters",
            PROPAGATION_SRP_MANUAL,
        )
        self.prop_srp_model.setMinimumHeight(36)
        self.prop_srp_model.setToolTip(
            "Choose the spacecraft parameters used only when solar pressure is enabled."
        )

        self.prop_srp_model_info = QLabel()
        self.prop_srp_model_info.setObjectName("metricDetail")
        self.prop_srp_model_info.setWordWrap(True)
        self.prop_srp_model.currentIndexChanged.connect(
            self.propagation_srp_model_changed
        )

        self.prop_manual_srp_box = QGroupBox(
            "MANUAL SRP INPUTS — EFFECTIVE AREA"
        )
        manual_srp_layout = QGridLayout(self.prop_manual_srp_box)
        manual_srp_layout.setContentsMargins(14, 22, 14, 14)
        manual_srp_layout.setHorizontalSpacing(12)
        manual_srp_layout.setVerticalSpacing(9)

        self.prop_manual_srp_separate_panels = QCheckBox(
            "Enter panel and body CP separately"
        )
        self.prop_manual_srp_separate_panels.setToolTip(
            "Enter total and panel area; body area is calculated as total "
            "area minus panel area."
        )

        def manual_srp_spinbox(
            minimum,
            maximum,
            value,
            suffix="",
            decimals=6,
        ):
            control = OperatorDoubleSpinBox()
            control.setRange(minimum, maximum)
            control.setDecimals(decimals)
            control.setValue(value)
            control.setSuffix(suffix)
            control.setMinimumHeight(34)
            control.setKeyboardTracking(False)
            return control

        self.prop_manual_srp_mass = manual_srp_spinbox(
            0.000001,
            1_000_000_000.0,
            1000.0,
            " kg",
        )
        self.prop_manual_srp_total_area = manual_srp_spinbox(
            0.000001,
            1_000_000_000.0,
            20.0,
            " m²",
        )
        self.prop_manual_srp_coefficient = manual_srp_spinbox(
            0.000000001,
            100.0,
            1.0,
            decimals=9,
        )
        self.prop_manual_srp_panel_area = manual_srp_spinbox(
            0.0,
            1_000_000_000.0,
            15.0,
            " m²",
        )
        self.prop_manual_srp_panel_coefficient = manual_srp_spinbox(
            0.000000001,
            100.0,
            1.0,
            decimals=9,
        )
        self.prop_manual_srp_body_area = manual_srp_spinbox(
            0.0,
            1_000_000_000.0,
            5.0,
            " m²",
        )
        self.prop_manual_srp_body_area.setReadOnly(True)
        self.prop_manual_srp_body_area.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.prop_manual_srp_body_coefficient = manual_srp_spinbox(
            0.000000001,
            100.0,
            1.0,
            decimals=9,
        )

        manual_srp_layout.addWidget(
            self.prop_manual_srp_separate_panels, 0, 0, 1, 4
        )
        manual_srp_layout.addWidget(QLabel("Spacecraft mass:"), 1, 0)
        manual_srp_layout.addWidget(self.prop_manual_srp_mass, 1, 1, 1, 3)

        self.prop_manual_srp_total_area_label = QLabel("Total area:")
        self.prop_manual_srp_coefficient_label = QLabel("CP:")
        manual_srp_layout.addWidget(self.prop_manual_srp_total_area_label, 2, 0)
        manual_srp_layout.addWidget(self.prop_manual_srp_total_area, 2, 1)
        manual_srp_layout.addWidget(self.prop_manual_srp_coefficient_label, 2, 2)
        manual_srp_layout.addWidget(self.prop_manual_srp_coefficient, 2, 3)

        self.prop_manual_srp_panel_area_label = QLabel("Panel area:")
        self.prop_manual_srp_panel_coefficient_label = QLabel("Panel CP:")
        self.prop_manual_srp_body_area_label = QLabel(
            "Body area (total − panel):"
        )
        self.prop_manual_srp_body_coefficient_label = QLabel("Body CP:")
        manual_srp_layout.addWidget(self.prop_manual_srp_panel_area_label, 3, 0)
        manual_srp_layout.addWidget(self.prop_manual_srp_panel_area, 3, 1)
        manual_srp_layout.addWidget(
            self.prop_manual_srp_panel_coefficient_label, 3, 2
        )
        manual_srp_layout.addWidget(
            self.prop_manual_srp_panel_coefficient, 3, 3
        )
        manual_srp_layout.addWidget(self.prop_manual_srp_body_area_label, 4, 0)
        manual_srp_layout.addWidget(self.prop_manual_srp_body_area, 4, 1)
        manual_srp_layout.addWidget(
            self.prop_manual_srp_body_coefficient_label, 4, 2
        )
        manual_srp_layout.addWidget(
            self.prop_manual_srp_body_coefficient, 4, 3
        )

        self.prop_manual_srp_summary = QLabel()
        self.prop_manual_srp_summary.setObjectName("metricDetail")
        self.prop_manual_srp_summary.setWordWrap(True)
        manual_srp_layout.addWidget(self.prop_manual_srp_summary, 5, 0, 1, 4)
        manual_srp_layout.setColumnStretch(1, 1)
        manual_srp_layout.setColumnStretch(3, 1)

        self.prop_manual_srp_separate_panels.toggled.connect(
            self.update_manual_srp_controls
        )
        for control in (
            self.prop_manual_srp_mass,
            self.prop_manual_srp_total_area,
            self.prop_manual_srp_coefficient,
            self.prop_manual_srp_panel_area,
            self.prop_manual_srp_panel_coefficient,
            self.prop_manual_srp_body_coefficient,
        ):
            control.valueChanged.connect(self.update_manual_srp_controls)

        settings_form.addRow("Duration [days]:", self.prop_days)
        settings_form.addRow("Step minutes:", self.step_minutes)
        settings_form.addRow("Step seconds:", self.step_seconds)
        settings_form.addRow("Earth harmonics:", self.prop_j2)
        if self.prop_egm_degree is not None:
            settings_form.addRow("EGM96 truncation:", self.prop_egm_degree)
        settings_form.addRow("Moon:", self.prop_moon)
        settings_form.addRow("Sun:", self.prop_sun)
        settings_form.addRow("Solar pressure:", self.prop_srp)
        settings_form.addRow("SRP spacecraft model:", self.prop_srp_model)
        settings_form.addRow("SRP parameters:", self.prop_srp_model_info)
        settings_form.addRow(self.prop_manual_srp_box)
        self.update_manual_srp_controls()
        self.update_propagation_srp_model_details()
        main_layout.addWidget(settings_box)

        # BUTTONS
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        current_epoch_button = QPushButton("USE CURRENT UTC")
        current_epoch_button.clicked.connect(self.set_current_propagation_epoch)

        load_profile_button = QPushButton("LOAD ACTIVE PROFILE")
        load_profile_button.setObjectName("ghostAction")
        load_profile_button.clicked.connect(
            lambda: self.load_active_profile_into_propagation()
        )

        self.propagate_button = QPushButton("PROPAGATE")
        self.propagate_button.setObjectName("primaryAction")
        self.propagate_button.clicked.connect(self.run_manual_propagation)

        self.cancel_propagation_button = QPushButton("CANCEL")
        self.cancel_propagation_button.setObjectName("dangerAction")
        self.cancel_propagation_button.setEnabled(False)
        self.cancel_propagation_button.clicked.connect(
            self.cancel_manual_propagation
        )

        save_button = QPushButton("SAVE TXT")
        save_button.clicked.connect(self.save_propagation_output)

        self.save_csv_button = QPushButton("SAVE CSV")
        self.save_csv_button.clicked.connect(self.save_propagation_csv)

        # CSV export is enabled only after a NEW propagation
        # has completed successfully. This prevents an old trajectory
        # from being exported by mistake.
        self.save_csv_button.setEnabled(False)

        clear_button = QPushButton("CLEAR OUTPUT")
        clear_button.clicked.connect(lambda: self.prop_output.clear())

        action_buttons = [
            current_epoch_button,
            self.propagate_button,
            self.cancel_propagation_button,
            save_button,
            self.save_csv_button,
            clear_button,
        ]
        action_buttons.insert(1, load_profile_button)
        for action_button in action_buttons:
            action_button.setMinimumHeight(42)

        button_layout.addWidget(current_epoch_button)
        button_layout.addWidget(load_profile_button)
        button_layout.addWidget(self.propagate_button)
        button_layout.addWidget(self.cancel_propagation_button)
        button_layout.addWidget(save_button)
        button_layout.addWidget(self.save_csv_button)
        button_layout.addWidget(clear_button)
        main_layout.addLayout(button_layout)

        self.propagation_progress = QProgressBar()
        self.propagation_progress.setRange(0, 100)
        self.propagation_progress.setValue(0)
        self.propagation_progress.setFormat("Ready")
        main_layout.addWidget(self.propagation_progress)

        # GRAPH
        propagation_graph_box = QGroupBox("PROPAGATION ANALYSIS")
        propagation_graph_layout = QVBoxLayout(propagation_graph_box)
        propagation_graph_layout.setContentsMargins(14, 24, 14, 14)

        propagation_graph_controls = QHBoxLayout()
        propagation_graph_controls.addWidget(
            QLabel("Chart view:")
        )
        self.manual_chart_component = QComboBox()
        self.manual_chart_component.addItem(
            "PROPAGATED STATE — X / Y / Z / Vx / Vy / Vz",
            "absolute",
        )
        self.manual_chart_component.addItem(
            "EARTH-FIXED LONGITUDE — ITRS / STATION BOX",
            "longitude",
        )
        self.manual_chart_component.addItem(
            "PERTURBATION FORCE PROFILE — MOON / SUN / SRP / TOTAL",
            "forces",
        )
        self.manual_chart_component.setMinimumHeight(36)
        self.manual_chart_component.setToolTip(
            "Show all six propagated J2000 Cartesian state components."
        )
        self.manual_chart_component.currentIndexChanged.connect(
            self.update_manual_propagation_chart
        )
        propagation_graph_controls.addWidget(
            self.manual_chart_component
        )
        propagation_graph_controls.addStretch(1)
        propagation_graph_layout.addLayout(
            propagation_graph_controls
        )

        self.manual_graph = GraphWidget(figsize=(10, 6))
        self.manual_residual_axes = None
        self.manual_graph.setMinimumHeight(560)
        self.manual_graph.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )
        self.manual_graph.ax.set_xlabel("Elapsed time [days]")
        self.manual_graph.ax.set_ylabel("State")
        self.manual_graph.ax.text(
            0.5,
            0.5,
            "Complete a propagation to plot the trajectory",
            transform=self.manual_graph.ax.transAxes,
            ha="center",
            va="center",
            color="#64748B",
            fontsize=11,
        )
        propagation_graph_layout.addWidget(self.manual_graph)
        main_layout.addWidget(propagation_graph_box)

        kepler_box = QGroupBox(
            "OSCULATING KEPLER ELEMENTS — HISTORY / GEOMETRY / TABLE"
        )
        kepler_layout = QVBoxLayout(kepler_box)
        kepler_layout.setContentsMargins(14, 24, 14, 14)
        self.propagation_kepler_widget = KeplerComparisonWidget()
        kepler_layout.addWidget(self.propagation_kepler_widget)
        main_layout.addWidget(kepler_box)

        # OUTPUT
        self.prop_output = QTextEdit()
        self.prop_output.setReadOnly(True)

        # Latest propagation cache.
        # These values are deliberately cleared at the start of every
        # new propagation so SAVE CSV can never fall back to an older run.
        self.last_prop_times = None
        self.last_prop_states = None
        self.last_prop_epoch = None
        self.last_prop_include_j2 = None
        self.last_prop_earth_harmonic_degree = None
        self.last_prop_include_moon = None
        self.last_prop_include_sun = None
        self.last_prop_include_srp = None
        self.last_prop_srp_coefficient = None
        self.last_prop_srp_mode = None
        self.last_prop_srp_area_m2 = None
        self.last_prop_srp_mass_kg = None
        self.last_prop_step_minutes = None
        self.last_prop_step_seconds = None
        self.last_prop_force_profile_cache = None
        self.last_prop_run_number = 0
        self.prop_output.setPlaceholderText(
            "Propagation result will appear here."
        )
        self.prop_output.setMinimumHeight(260)
        main_layout.addWidget(self.prop_output)

        # Prevent the upper forms from being compressed by the output box.
        main_layout.setStretchFactor(self.prop_output, 1)

        scroll.setWidget(content)
        page_layout.addWidget(scroll)

        self.tabs.addTab(
            page,
            "PROPAGATION",
        )


    # ========================================================
    # SAVE PROPAGATION OUTPUT TO TXT
    # ========================================================

    def save_propagation_output(self):
        """
        Save the complete text shown in the propagation output
        box to a user-selected .txt file.
        """

        output_text = self.prop_output.toPlainText().strip()

        if not output_text:
            self.prop_output.setPlainText(
                "ERROR\n\nThere is no propagation output to save."
            )
            return

        # Build a useful default filename.
        try:
            epoch = self.parse_propagation_epoch(
                self.prop_epoch.text()
            )

            filename_time = epoch.strftime(
                "%Y%m%d_%H%M%S"
            )

        except Exception:
            filename_time = datetime.now(
                timezone.utc
            ).strftime(
                "%Y%m%d_%H%M%S"
            )

        default_filename = (
            f"propagation_{filename_time}.txt"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Propagation Output"),
            default_filename,
            "Text Files (*.txt);;All Files (*)",
            options=theme.file_dialog_options(),
        )

        # User cancelled.
        if not file_path:
            return

        # Ensure .txt extension when no extension was provided.
        if "." not in os.path.basename(file_path):
            file_path += ".txt"

        try:
            with open(
                file_path,
                "w",
                encoding="utf-8",
            ) as file:
                file.write(
                    self.prop_output.toPlainText()
                )

            self.statusBar().showMessage(
                f"Saved TXT: {file_path}",
                8000,
            )

        except Exception as error:
            self.prop_output.append(
                "\n\nSAVE ERROR:\n"
                f"{type(error).__name__}: {error}"
            )



    # ========================================================
    # SAVE PROPAGATION OUTPUT TO CSV
    # ========================================================

    def save_propagation_csv(self):
        """
        Save the latest step-by-step propagation trajectory
        as a CSV file that can be opened directly in Excel.
        """

        if (
            not hasattr(self, "last_prop_times")
            or not hasattr(self, "last_prop_states")
            or not hasattr(self, "last_prop_epoch")
        ):
            self.prop_output.append(
                "\n\nCSV SAVE ERROR:\n"
                "Run PROPAGATE first, then press SAVE CSV."
            )
            return

        if (
            self.last_prop_times is None
            or self.last_prop_states is None
            or self.last_prop_epoch is None
            or len(self.last_prop_times) == 0
        ):
            self.prop_output.append(
                "\n\nCSV SAVE ERROR:\n"
                "There is no propagation trajectory to save."
            )
            return

        filename_time = self.last_prop_epoch.strftime(
            "%Y%m%d_%H%M%S"
        )

        moon_text = (
            "moon_ON"
            if self.last_prop_include_moon
            else "moon_OFF"
        )

        sun_text = (
            "sun_ON"
            if self.last_prop_include_sun
            else "sun_OFF"
        )
        srp_text = (
            "srp_ON"
            if self.last_prop_include_srp
            else "srp_OFF"
        )

        j2_text = (
            "j2_ON"
            if self.last_prop_include_j2
            else "j2_OFF"
        )

        run_number = int(
            getattr(
                self,
                "last_prop_run_number",
                0,
            )
        )

        # Different default name for every successful run.
        # This also makes it obvious which force-model settings
        # produced the CSV.
        default_filename = (
            f"propagation_run_{run_number:03d}_"
            f"{filename_time}_{moon_text}_{sun_text}_{srp_text}_{j2_text}_j2000.csv"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Propagation CSV"),
            default_filename,
            "CSV Files (*.csv);;All Files (*)",
            options=theme.file_dialog_options(),
        )

        if not file_path:
            return

        if not file_path.lower().endswith(".csv"):
            file_path += ".csv"

        try:
            with open(
                file_path,
                "w",
                newline="",
                encoding="utf-8-sig",
            ) as file:

                # Propagation səhifəsinin standart CSV-si:
                # - vergül sütun ayırıcısıdır;
                # - nöqtə onluq ayırıcıdır;
                # - metadata və sütun başlığı yoxdur;
                # - vəziyyətlər giriş və inteqrator kimi J2000/ICRF oxlarındadır;
                # - ilk sətir daxil edilmiş ilkin vəziyyəti dəyişmədən saxlayır.
                writer = csv.writer(
                    file,
                    delimiter=",",
                    lineterminator="\n",
                )
                export_epochs = tuple(
                    (
                        self.last_prop_epoch
                        + timedelta(seconds=float(elapsed_seconds))
                    )
                    for elapsed_seconds in self.last_prop_times
                )
                export_states = np.asarray(self.last_prop_states, dtype=float)

                for state_epoch, state in zip(
                    export_epochs,
                    export_states,
                ):

                    x, y, z, vx, vy, vz = state
                    # Yalnız məlumat: Date,Time,X,Y,Z,Vx,Vy,Vz
                    writer.writerow(
                        [
                            format_csv_date(state_epoch),
                            format_csv_time(state_epoch),
                            f"{x:.9f}",
                            f"{y:.9f}",
                            f"{z:.9f}",
                            f"{vx:.12f}",
                            f"{vy:.12f}",
                            f"{vz:.12f}",
                        ]
                    )

            self.statusBar().showMessage(
                "Saved latest propagation CSV "
                f"(run {self.last_prop_run_number}): {file_path}",
                8000,
            )

        except Exception as error:
            self.prop_output.append(
                "\n\nCSV SAVE ERROR:\n"
                f"{type(error).__name__}: {error}"
            )



    def _open_utc_epoch_picker(self, field):

        try:
            initial_epoch = self.parse_propagation_epoch(field.text())
        except Exception:
            initial_epoch = datetime.now(timezone.utc)
        dialog = UtcEpochPickerDialog(initial_epoch, self)
        dialog.setFont(self.font())
        dialog.setStyleSheet(self.styleSheet())
        translate_widget_tree(dialog, self.language)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        selected_epoch = dialog.selected_epoch()
        field.setText(selected_epoch.isoformat())
        return True


    def open_propagation_epoch_picker(self):
        return self._open_utc_epoch_picker(self.prop_epoch)


    def open_eclipse_epoch_picker(self):
        return self._open_utc_epoch_picker(self.eclipse_epoch)


    def open_analysis_epoch_picker(self):
        return self._open_utc_epoch_picker(self.analysis_fixed_epoch_input)


    def set_current_propagation_epoch(self):

        now = datetime.now(timezone.utc)
        self.prop_epoch.setText(now.isoformat(timespec="microseconds"))


    def parse_propagation_epoch(self, text):

        text = text.strip()

        if not text:
            raise ValueError("Epoch UTC is required.")

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        try:
            epoch = datetime.fromisoformat(text)
        except ValueError as error:
            raise ValueError(
                "Invalid epoch format. Example: 2030-01-01T00:00:00+00:00"
            ) from error

        if epoch.tzinfo is None:
            epoch = epoch.replace(tzinfo=timezone.utc)
        else:
            epoch = epoch.astimezone(timezone.utc)

        return epoch


    def _run_manual_propagation_legacy(self):

        # IMPORTANT:
        # Invalidate the previous propagation BEFORE reading any new inputs.
        # If this new run fails for any reason, SAVE CSV stays disabled and
        # the old trajectory cannot accidentally be exported.
        self.last_prop_times = None
        self.last_prop_states = None
        self.last_prop_epoch = None
        self.last_prop_include_j2 = None
        self.last_prop_include_moon = None
        self.last_prop_step_minutes = None
        self.last_prop_step_seconds = None

        if hasattr(self, "save_csv_button"):
            self.save_csv_button.setEnabled(False)

        try:
            epoch = self.parse_propagation_epoch(
                self.prop_epoch.text()
            )

            initial_state = np.array(
                [
                    float(self.prop_x.text()),
                    float(self.prop_y.text()),
                    float(self.prop_z.text()),
                    float(self.prop_vx.text()),
                    float(self.prop_vy.text()),
                    float(self.prop_vz.text()),
                ],
                dtype=float,
            )

            days = float(
                self.prop_days.text()
            )

            if days <= 0.0:
                raise ValueError(
                    "Duration must be greater than zero."
                )

            duration_seconds = (
                days
                * 86400.0
            )

            step_minutes = int(
                self.step_minutes.value()
            )

            step_seconds = int(
                self.step_seconds.value()
            )

            output_step = (
                step_minutes * 60.0
                + step_seconds
            )

            if output_step <= 0.0:
                raise ValueError(
                    "Step interval must be at least 1 second."
                )

            estimated_steps = int(
                np.floor(
                    duration_seconds
                    / output_step
                )
            ) + 2

            # Prevent accidentally creating millions of text rows
            # and freezing the UI.
            if estimated_steps > 100000:
                raise ValueError(
                    "This interval would create approximately "
                    f"{estimated_steps:,} output steps. "
                    "Increase the step interval or reduce the duration. "
                    "Maximum allowed text steps: 100,000."
                )

            include_j2 = (
                self.prop_j2.isChecked()
            )

            include_moon = (
                self.prop_moon.isChecked()
            )

            self.prop_output.setPlainText(
                "Propagating trajectory...\n\n"
                f"Requested interval: {step_minutes} min "
                f"{step_seconds} sec\n"
                f"Estimated output steps: {estimated_steps:,}"
            )

            QApplication.processEvents()

            times, states = propagate_trajectory(
                initial_state=initial_state,
                initial_epoch=epoch,
                duration_seconds=duration_seconds,
                output_step=output_step,
                include_j2=include_j2,
                include_moon=include_moon,
            )

            # Keep the latest trajectory in memory so it can be
            # exported directly to CSV without parsing the text box.
            self.last_prop_times = np.asarray(
                times,
                dtype=float,
            )

            self.last_prop_states = np.asarray(
                states,
                dtype=float,
            )

            self.last_prop_epoch = epoch
            self.last_prop_include_j2 = include_j2
            self.last_prop_include_moon = include_moon
            self.last_prop_step_minutes = step_minutes
            self.last_prop_step_seconds = step_seconds
            self.last_prop_run_number += 1

            # Only now is the CSV button allowed to export.
            if hasattr(self, "save_csv_button"):
                self.save_csv_button.setEnabled(True)

            final_state = states[-1]
            final_position = final_state[:3]
            final_velocity = final_state[3:]

            radius = float(
                np.linalg.norm(
                    final_position
                )
            )

            speed = float(
                np.linalg.norm(
                    final_velocity
                )
            )

            final_epoch = (
                epoch
                + timedelta(
                    seconds=float(times[-1])
                )
            )

            lines = [
                "PROPAGATION COMPLETED",
                "",
                f"Initial epoch : {epoch.isoformat()}",
                f"Final epoch   : {final_epoch.isoformat()}",
                f"Duration      : {days:.9f} days",
                f"Step interval : {step_minutes} min {step_seconds} sec",
                f"Output steps  : {len(times)}",
                f"Earth EGM96 4×4: {'ON' if include_j2 else 'OFF'}",
                f"Moon          : {'ON' if include_moon else 'OFF'}",
                "",
                "STEP-BY-STEP STATE HISTORY",
                "",
                "STEP | UTC | X [km] | Y [km] | Z [km] | "
                "Vx [km/s] | Vy [km/s] | Vz [km/s]",
                "-" * 150,
            ]

            for index, (elapsed_seconds, state) in enumerate(
                zip(times, states)
            ):
                state_epoch = (
                    epoch
                    + timedelta(
                        seconds=float(elapsed_seconds)
                    )
                )

                x, y, z, vx, vy, vz = state

                lines.append(
                    f"{index:05d} | "
                    f"{state_epoch.isoformat()} | "
                    f"{x:.9f} | "
                    f"{y:.9f} | "
                    f"{z:.9f} | "
                    f"{vx:.12f} | "
                    f"{vy:.12f} | "
                    f"{vz:.12f}"
                )

            lines.extend(
                [
                    "",
                    "FINAL STATE",
                    "",
                    "FINAL POSITION [km]",
                    f"X  = {final_position[0]:.9f}",
                    f"Y  = {final_position[1]:.9f}",
                    f"Z  = {final_position[2]:.9f}",
                    "",
                    "FINAL VELOCITY [km/s]",
                    f"Vx = {final_velocity[0]:.12f}",
                    f"Vy = {final_velocity[1]:.12f}",
                    f"Vz = {final_velocity[2]:.12f}",
                    "",
                    f"Radius = {radius:.9f} km",
                    f"Speed  = {speed:.12f} km/s",
                ]
            )

            self.prop_output.setPlainText(
                "\n".join(lines)
            )

        except Exception as error:
            self.prop_output.setPlainText(
                "ERROR\n\n"
                f"{type(error).__name__}: {error}"
            )


    # ========================================================
    # BACKGROUND MANUAL PROPAGATION
    # ========================================================

    def _set_manual_single_axis(self):
        self.manual_graph.figure.clear()
        axis = self.manual_graph.figure.add_subplot(111)
        self.manual_graph.ax = axis
        self.manual_residual_axes = (axis,)
        GraphWidget.style_axis(axis)
        return axis

    @staticmethod
    def _format_eclipse_duration(seconds):

        if seconds is None:
            return "WINDOW-TRUNCATED"
        seconds = max(0.0, float(seconds))
        hours, remainder = divmod(seconds, 3600.0)
        minutes, remaining_seconds = divmod(remainder, 60.0)
        return (
            f"{int(hours):02d}:{int(minutes):02d}:"
            f"{remaining_seconds:04.1f}"
        )

    def update_eclipse_event_table(self):

        if not hasattr(self, "eclipse_event_table"):
            return
        self.eclipse_event_table.setRowCount(0)
        if self.eclipse_prediction_result is None:
            self.eclipse_summary_label.setText(
                "No standalone eclipse calculation has been run."
            )
            return

        prediction = self.eclipse_prediction_result

        events = prediction.events
        self.eclipse_event_table.setRowCount(len(events))

        def format_epoch(value, missing_text):
            if value is None:
                return missing_text
            return value.astimezone(timezone.utc).isoformat(
                timespec="milliseconds"
            ).replace("+00:00", "Z")

        for row, event in enumerate(events):
            values = (
                str(row + 1),
                format_epoch(event.penumbra_entry_utc, "BEFORE WINDOW"),
                format_epoch(event.umbra_entry_utc, "NO FULL UMBRA"),
                format_epoch(event.umbra_exit_utc, "NO FULL UMBRA"),
                format_epoch(event.penumbra_exit_utc, "AFTER WINDOW"),
                self._format_eclipse_duration(
                    event.umbra_duration_seconds
                ) if (
                    event.umbra_entry_utc is not None
                    or event.umbra_exit_utc is not None
                ) else "—",
                self._format_eclipse_duration(
                    event.total_duration_seconds
                ),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )
                self.eclipse_event_table.setItem(row, column, item)

        if not events:
            summary = (
                "No Earth eclipse was found inside this propagation window."
            )
        else:
            complete_umbra_durations = [
                event.umbra_duration_seconds
                for event in events
                if event.umbra_duration_seconds is not None
            ]
            first_entry = events[0].penumbra_entry_utc
            first_text = format_epoch(first_entry, "before window start")
            summary = (
                f"Detected eclipse events: {len(events)}  ·  "
                f"First penumbra entry: {first_text}"
            )
            if complete_umbra_durations:
                summary += (
                    "  ·  Longest umbra: "
                    + self._format_eclipse_duration(
                        max(complete_umbra_durations)
                    )
                )
        summary += (
            f"  ·  Source output step: "
            f"{prediction.source_step_seconds:.3f} s"
        )
        self.eclipse_summary_label.setText(summary)

    def use_current_eclipse_state(self):

        try:
            state, epoch = self.active_spacecraft_state(
                datetime.now(timezone.utc)
            )
            self.eclipse_epoch.setText(
                epoch.isoformat(timespec="microseconds")
            )
            for field, value in zip(self.eclipse_state_inputs, state):
                field.setText(f"{float(value):.12f}")
            self.eclipse_summary_label.setText(
                f"Loaded {self.active_profile.display_name} J2000 state from "
                f"its {self.active_profile.orbit_source.upper()} source."
            )
        except Exception as error:
            self.eclipse_summary_label.setText(
                "CURRENT STATE ERROR: "
                f"{type(error).__name__}: {error}"
            )

    def copy_propagation_to_eclipse(self):

        self.eclipse_epoch.setText(self.prop_epoch.text())
        propagation_fields = (
            self.prop_x,
            self.prop_y,
            self.prop_z,
            self.prop_vx,
            self.prop_vy,
            self.prop_vz,
        )
        for target, source in zip(
            self.eclipse_state_inputs,
            propagation_fields,
        ):
            target.setText(source.text())
        self.eclipse_summary_label.setText(
            "Copied the Propagation input state. Eclipse calculation remains "
            "independent and will run only from this ECLIPSE tab."
        )

    def run_eclipse_prediction(self):

        if self.eclipse_thread is not None and self.eclipse_thread.isRunning():
            return
        if self.propagation_thread is not None and self.propagation_thread.isRunning():
            self.eclipse_summary_label.setText(
                "Wait for Propagation to finish or cancel it first."
            )
            return
        if (
            self.reference_comparison_thread is not None
            and self.reference_comparison_thread.isRunning()
        ):
            self.eclipse_summary_label.setText(
                "Wait for Reference Lab calculation to finish or cancel it first."
            )
            return
        if self.eclipse_thread is not None and self.eclipse_thread.isRunning():
            self.prop_output.setPlainText(
                "PROPAGATION BUSY\n\n"
                "Wait for the standalone Eclipse calculation to finish or "
                "cancel it."
            )
            return

        try:
            epoch = self.parse_propagation_epoch(self.eclipse_epoch.text())
            initial_state = np.asarray(
                [float(field.text()) for field in self.eclipse_state_inputs],
                dtype=float,
            )
            days = int(self.eclipse_days.value())
            step_seconds = self.eclipse_search_step_seconds()
            step_value = int(self.eclipse_step_value.value())
            step_unit = self.eclipse_step_unit.currentText()
            estimated_rows = int(days * 86400.0 / step_seconds) + 2
            if estimated_rows > 100000:
                raise ValueError(
                    f"This search would create about {estimated_rows:,} rows. "
                    "Increase the eclipse step. Maximum allowed: 100,000."
                )

            include_srp = self.eclipse_include_srp.isChecked()
            if include_srp:
                srp_coefficient, srp_mode = (
                    resolved_solar_pressure_coefficient(epoch)
                )
            else:
                srp_coefficient = None
                srp_mode = "OFF"

            parameters = {
                "initial_state": initial_state,
                "initial_epoch": epoch,
                "duration_seconds": float(days * 86400.0),
                "output_step": step_seconds,
                "include_j2": self.eclipse_include_j2.isChecked(),
                "include_moon": self.eclipse_include_moon.isChecked(),
                "include_sun": self.eclipse_include_sun.isChecked(),
                "include_srp": include_srp,
                "srp_coefficient": srp_coefficient,
            }
            self._pending_eclipse_config = {
                "epoch": epoch,
                "days": days,
                "step_seconds": step_seconds,
                "step_value": step_value,
                "step_unit": step_unit,
                "srp_mode": srp_mode,
            }
            self.eclipse_prediction_result = None
            self.eclipse_initial_epoch = None
            self._last_eclipse_output_kind = None
            self.eclipse_reference_comparison = None
            self.eclipse_reference_export_button.setEnabled(False)
            self.eclipse_reference_table.setRowCount(0)
            self.eclipse_export_csv_button.setEnabled(False)
            self.eclipse_event_table.setRowCount(0)
            self.eclipse_summary_label.setText(
                "ECLIPSE SEARCH RUNNING\n"
                f"Epoch: {epoch.isoformat()}  ·  Duration: {days} days  ·  "
                f"Step: {step_value} {step_unit.lower()}  ·  "
                f"Rows: about {estimated_rows:,}"
            )
            self.eclipse_calculate_button.setEnabled(False)
            self.eclipse_year_search_button.setEnabled(False)
            self.eclipse_reference_run_model_button.setEnabled(False)
            self.eclipse_reference_selector.setEnabled(False)
            self.eclipse_reference_compare_button.setEnabled(False)
            self.eclipse_cancel_button.setEnabled(True)
            self.eclipse_progress.setValue(0)
            self.eclipse_progress.setFormat("%p%")
            self._eclipse_run_mode = "standard"
            self.start_eclipse_eta()

            self._eclipse_timer_was_active = self.timer.isActive()
            if self._eclipse_timer_was_active:
                self.timer.stop()

            self.eclipse_thread = QThread(self)
            self.eclipse_worker = EclipsePredictionWorker(
                parameters,
                epoch,
                geometry=self.eclipse_geometry_options(),
            )
            self.eclipse_worker.moveToThread(self.eclipse_thread)
            self.eclipse_thread.started.connect(self.eclipse_worker.run)
            self.eclipse_worker.progress.connect(
                self.update_eclipse_progress
            )
            self.eclipse_worker.completed.connect(self.finish_eclipse_prediction)
            self.eclipse_worker.failed.connect(self.fail_eclipse_prediction)
            self.eclipse_worker.cancelled.connect(self.cancelled_eclipse_prediction)
            self.eclipse_worker.completed.connect(self.eclipse_thread.quit)
            self.eclipse_worker.failed.connect(self.eclipse_thread.quit)
            self.eclipse_worker.cancelled.connect(self.eclipse_thread.quit)
            self.eclipse_thread.finished.connect(self.eclipse_worker.deleteLater)
            self.eclipse_thread.finished.connect(self.eclipse_thread.deleteLater)
            self.eclipse_thread.finished.connect(self.cleanup_eclipse_prediction)
            self.eclipse_thread.start()
        except Exception as error:
            if self.eclipse_eta_timer.isActive():
                self.stop_eclipse_eta("Input error")
            self.eclipse_summary_label.setText(
                "ECLIPSE INPUT ERROR: "
                f"{type(error).__name__}: {error}"
            )

    def run_yearly_eclipse_search(self):

        if self.eclipse_thread is not None and self.eclipse_thread.isRunning():
            return
        if self.propagation_thread is not None and self.propagation_thread.isRunning():
            self.eclipse_year_summary_label.setText(
                "Wait for Propagation to finish or cancel it first."
            )
            return
        if (
            self.reference_comparison_thread is not None
            and self.reference_comparison_thread.isRunning()
        ):
            self.eclipse_year_summary_label.setText(
                "Wait for Reference Lab calculation to finish or cancel it first."
            )
            return

        try:
            input_epoch = self.parse_propagation_epoch(
                self.eclipse_epoch.text()
            )
            initial_state = np.asarray(
                [float(field.text()) for field in self.eclipse_state_inputs],
                dtype=float,
            )
            selected_year = int(self.eclipse_year.value())
            year_start = datetime(
                selected_year,
                1,
                1,
                tzinfo=timezone.utc,
            )
            include_srp = self.eclipse_include_srp.isChecked()
            if include_srp:
                srp_coefficient, srp_mode = (
                    resolved_solar_pressure_coefficient(year_start)
                )
            else:
                srp_coefficient = None
                srp_mode = "OFF"

            parameters = {
                "initial_state": initial_state,
                "initial_epoch": input_epoch,
                "include_j2": self.eclipse_include_j2.isChecked(),
                "include_moon": self.eclipse_include_moon.isChecked(),
                "include_sun": self.eclipse_include_sun.isChecked(),
                "include_srp": include_srp,
                "srp_coefficient": srp_coefficient,
            }
            self.yearly_eclipse_schedule = None
            self._last_eclipse_output_kind = None
            self.eclipse_reference_comparison = None
            self.eclipse_reference_export_button.setEnabled(False)
            self.eclipse_reference_table.setRowCount(0)
            self.eclipse_year_table.setRowCount(0)
            self.eclipse_year_export_csv_button.setEnabled(False)
            self.eclipse_year_summary_label.setText(
                "YEARLY ECLIPSE SEARCH RUNNING\n"
                f"Year: {selected_year}  ·  Scan: 1 hour  ·  "
                "Candidate detail: 1 minute  ·  "
                f"Input state epoch: {input_epoch.isoformat()}  ·  "
                f"SRP: {srp_mode}\n"
                "The input state is first propagated to 1 January UTC."
            )
            self.eclipse_calculate_button.setEnabled(False)
            self.eclipse_year_search_button.setEnabled(False)
            self.eclipse_reference_run_model_button.setEnabled(False)
            self.eclipse_cancel_button.setEnabled(True)
            self.eclipse_progress.setValue(1)
            self.eclipse_progress.setFormat("STARTING YEAR SEARCH · %p%")
            self._eclipse_run_mode = "year"
            self.start_eclipse_eta()

            self._eclipse_timer_was_active = self.timer.isActive()
            if self._eclipse_timer_was_active:
                self.timer.stop()

            self.eclipse_thread = QThread(self)
            self.eclipse_worker = YearlyEclipseWorker(
                parameters,
                selected_year,
                geometry=self.eclipse_geometry_options(),
            )
            self.eclipse_worker.moveToThread(self.eclipse_thread)
            self.eclipse_thread.started.connect(self.eclipse_worker.run)
            self.eclipse_worker.progress.connect(
                self.update_eclipse_progress
            )
            self.eclipse_worker.stage.connect(
                self.update_eclipse_progress_stage
            )
            self.eclipse_worker.completed.connect(
                self.finish_yearly_eclipse_search
            )
            self.eclipse_worker.failed.connect(self.fail_eclipse_prediction)
            self.eclipse_worker.cancelled.connect(
                self.cancelled_eclipse_prediction
            )
            self.eclipse_worker.completed.connect(self.eclipse_thread.quit)
            self.eclipse_worker.failed.connect(self.eclipse_thread.quit)
            self.eclipse_worker.cancelled.connect(self.eclipse_thread.quit)
            self.eclipse_thread.finished.connect(
                self.eclipse_worker.deleteLater
            )
            self.eclipse_thread.finished.connect(
                self.eclipse_thread.deleteLater
            )
            self.eclipse_thread.finished.connect(
                self.cleanup_eclipse_prediction
            )
            self.eclipse_thread.start()
        except Exception as error:
            if self.eclipse_eta_timer.isActive():
                self.stop_eclipse_eta("Input error")
            self.eclipse_year_summary_label.setText(
                "YEARLY ECLIPSE INPUT ERROR: "
                f"{type(error).__name__}: {error}"
            )

    @staticmethod
    def _yearly_eclipse_epoch_text(value):

        if value is None:
            return "—"
        return value.astimezone(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")

    def finish_yearly_eclipse_search(self, schedule):

        self.yearly_eclipse_schedule = schedule
        self._last_eclipse_output_kind = "year"
        self.eclipse_year_table.setRowCount(len(schedule.rows))
        for table_row, schedule_row in enumerate(schedule.rows):
            event = schedule_row.event
            values = (
                schedule_row.date_utc.isoformat(),
                schedule_row.status,
                "—" if schedule_row.event_number is None else str(
                    schedule_row.event_number
                ),
                "—" if event is None else self._yearly_eclipse_epoch_text(
                    event.penumbra_entry_utc
                ),
                "—" if event is None else self._yearly_eclipse_epoch_text(
                    event.umbra_entry_utc
                ),
                "—" if event is None else self._yearly_eclipse_epoch_text(
                    event.umbra_exit_utc
                ),
                "—" if event is None else self._yearly_eclipse_epoch_text(
                    event.penumbra_exit_utc
                ),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if schedule_row.status == "SKIPPED":
                    item.setForeground(QColor("#64748B"))
                elif column == 1:
                    item.setForeground(QColor("#34D399"))
                self.eclipse_year_table.setItem(
                    table_row,
                    column,
                    item,
                )

        self.eclipse_year_summary_label.setText(
            f"YEAR {schedule.year} COMPLETED  ·  "
            "1-hour scan / 1-minute candidate detail  ·  "
            f"Eclipse events: {schedule.event_count}  ·  "
            f"Skipped days: {schedule.skipped_day_count}"
        )
        self.eclipse_progress.setValue(100)
        self.eclipse_progress.setFormat("Year search completed")
        self.stop_eclipse_eta("Completed")
        self.eclipse_calculate_button.setEnabled(True)
        self.eclipse_year_search_button.setEnabled(True)
        self.eclipse_reference_run_model_button.setEnabled(True)
        self.eclipse_cancel_button.setEnabled(False)
        self.eclipse_year_export_csv_button.setEnabled(True)
        self.run_eclipse_reference_comparison()
        self.statusBar().showMessage(
            f"{schedule.year} yearly eclipse schedule completed: "
            f"{schedule.event_count} events",
            10000,
        )

    def export_yearly_eclipse_csv(self):

        schedule = self.yearly_eclipse_schedule
        if schedule is None:
            self.eclipse_year_summary_label.setText(
                "YEAR CSV EXPORT ERROR\nRun the selected-year search first."
            )
            return

        default_name = f"eclipse_year_schedule_{schedule.year}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Yearly Eclipse Schedule CSV"),
            self._eclipse_export_target(default_name),
            "CSV Files (*.csv);;All Files (*)",
            options=theme.file_dialog_options(),
        )
        if not file_path:
            return

        try:
            output_path = save_yearly_eclipse_schedule_csv(
                schedule,
                file_path,
            )
        except Exception as error:
            self.eclipse_year_summary_label.setText(
                "YEAR CSV EXPORT ERROR\n"
                f"{type(error).__name__}: {error}"
            )
            return

        self.eclipse_year_summary_label.setText(
            self.eclipse_year_summary_label.text()
            + "\nCSV export completed: "
            + str(output_path)
        )
        self.statusBar().showMessage(
            f"Yearly Eclipse CSV exported: {output_path.name}",
            10000,
        )

    def _resolve_eclipse_reference_initial_state(self, spec):

        if spec.nominal_longitude_deg is not None:
            epoch = spec.coverage_start_utc
            state = get_nominal_geostationary_state(
                epoch,
                spec.nominal_longitude_deg,
            )
            source_note = "the public SYNTHETIC/DEMO nominal-orbit model"
            source = (
                f"{spec.satellite} NOMINAL ORBIT · "
                f"{spec.nominal_longitude_deg:.1f}°E fixed geostationary slot · "
                + source_note
            )
            self.eclipse_epoch.setText(epoch.isoformat(timespec="microseconds"))
            for field, value in zip(self.eclipse_state_inputs, state):
                field.setText(f"{float(value):.12f}")
            return epoch, state, source

        epoch_text = self.eclipse_epoch.text().strip()
        state_texts = [field.text().strip() for field in self.eclipse_state_inputs]
        if epoch_text and all(state_texts):
            epoch = self.parse_propagation_epoch(epoch_text)
            state = np.asarray([float(value) for value in state_texts], dtype=float)
            return epoch, state, "MANUAL ECLIPSE J2000 INPUT"

        scenario = load_reference_scenario(
            True,
            dataset_id=DEMO_EARTH_MOON_SUN_SRP_DATASET_ID,
            include_srp=True,
        )
        epoch = scenario["epoch"]
        state = np.asarray(scenario["states"][0], dtype=float).copy()
        source = "PUBLIC SYNTHETIC/DEMO J2000 STATE"

        self.eclipse_epoch.setText(epoch.isoformat(timespec="microseconds"))
        for field, value in zip(self.eclipse_state_inputs, state):
            field.setText(f"{float(value):.12f}")
        return epoch, state, source

    @staticmethod
    def _eclipse_reference_state_epoch_warning(spec, state_epoch):

        if spec.coverage_start_utc <= state_epoch < spec.coverage_end_utc:
            return ""
        if state_epoch < spec.coverage_start_utc:
            gap = spec.coverage_start_utc - state_epoch
        else:
            gap = state_epoch - spec.coverage_end_utc
        gap_days = gap.total_seconds() / 86400.0
        if gap_days <= 7.0:
            return ""
        return (
            "CAUSE WARNING: the initial state date is "
            f"{gap_days:.1f} days from the nearest boundary of the selected "
            "period. This shifts orbital longitude and phase and creates an "
            "Eclipse timing error. A historical state or TLE from that period "
            "is required for a correct comparison. No hidden time or phase "
            "calibration is applied."
        )

    def run_selected_eclipse_reference_interval(self):

        if self.eclipse_thread is not None and self.eclipse_thread.isRunning():
            return
        if self.propagation_thread is not None and self.propagation_thread.isRunning():
            self.eclipse_reference_summary_label.setText(
                "Wait for Propagation to finish or cancel it first."
            )
            return
        if (
            self.reference_comparison_thread is not None
            and self.reference_comparison_thread.isRunning()
        ):
            self.eclipse_reference_summary_label.setText(
                "Wait for Reference Lab calculation to finish or cancel it first."
            )
            return

        try:
            dataset = load_eclipse_reference_dataset(
                self.eclipse_reference_selector.currentData()
            )
            spec = dataset.spec
            input_epoch, initial_state, state_source = (
                self._resolve_eclipse_reference_initial_state(spec)
            )
            include_srp = self.eclipse_include_srp.isChecked()
            srp_parameters = {}
            if include_srp:
                srp_coefficient, srp_mode = (
                    resolved_solar_pressure_coefficient(
                        spec.coverage_start_utc
                    )
                )
            else:
                srp_coefficient = None
                srp_mode = "OFF"

            parameters = {
                "initial_state": initial_state,
                "initial_epoch": input_epoch,
                "include_j2": self.eclipse_include_j2.isChecked(),
                "include_moon": self.eclipse_include_moon.isChecked(),
                "include_sun": self.eclipse_include_sun.isChecked(),
                "include_srp": include_srp,
                "srp_coefficient": srp_coefficient,
                **srp_parameters,
            }
            if spec.nominal_longitude_deg is not None:
                parameters["nominal_geostationary_longitude_deg"] = (
                    spec.nominal_longitude_deg
                )
                srp_mode = (
                    "REFERENCE NOMINAL ORBIT · fixed "
                    f"{spec.nominal_longitude_deg:.1f}°E slot"
                )
            interval_days = (
                spec.coverage_end_utc - spec.coverage_start_utc
            ).total_seconds() / 86400.0
            self._pending_eclipse_reference_spec = spec
            self._pending_eclipse_reference_state_source = state_source
            self._pending_eclipse_reference_state_warning = (
                self._eclipse_reference_state_epoch_warning(spec, input_epoch)
            )
            self.eclipse_reference_interval_prediction = None
            self.eclipse_reference_comparison = None
            self._last_eclipse_output_kind = None
            self.eclipse_reference_export_button.setEnabled(False)
            self.eclipse_reference_table.setRowCount(0)
            self.eclipse_reference_summary_label.setText(
                "REFERENCE-RANGE MODEL RUNNING\n"
                f"{spec.label}  ·  "
                f"{spec.coverage_start_utc.isoformat()} → "
                f"{spec.coverage_end_utc.isoformat()}  ·  "
                f"{interval_days:.0f} days\n"
                f"Input state epoch: {input_epoch.isoformat()}  ·  "
                f"SRP: {srp_mode}\n"
                f"State source: {state_source}\n"
                + (
                    self._pending_eclipse_reference_state_warning + "\n"
                    if self._pending_eclipse_reference_state_warning
                    else ""
                )
                +
                (
                    f"{spec.satellite} reference mode keeps the nominal orbit "
                    f"fixed at {spec.nominal_longitude_deg:.1f}°E; no event "
                    "time is empirically adjusted. "
                    if spec.nominal_longitude_deg is not None
                    else "The state is aligned automatically to the reference start; "
                )
                + "Then a 1-hour scan and 1-minute event refinement are used."
            )

            self.eclipse_calculate_button.setEnabled(False)
            self.eclipse_year_search_button.setEnabled(False)
            self.eclipse_reference_run_model_button.setEnabled(False)
            self.eclipse_reference_selector.setEnabled(False)
            self.eclipse_reference_compare_button.setEnabled(False)
            self.eclipse_cancel_button.setEnabled(True)
            self.eclipse_progress.setValue(1)
            self.eclipse_progress.setFormat("STARTING REFERENCE RUN · %p%")
            self.eclipse_reference_progress.setValue(1)
            self.eclipse_reference_progress.setFormat(
                "STARTING REFERENCE RUN · %p%"
            )
            self.eclipse_reference_date_label.setText(
                f"Selected interval: {spec.coverage_start_utc:%Y-%m-%d} → "
                f"{(spec.coverage_end_utc - timedelta(microseconds=1)):%Y-%m-%d} UTC"
            )
            self._eclipse_run_mode = "reference"
            self.start_eclipse_eta()

            self._eclipse_timer_was_active = self.timer.isActive()
            if self._eclipse_timer_was_active:
                self.timer.stop()

            self.eclipse_thread = QThread(self)
            self.eclipse_worker = YearlyEclipseWorker(
                parameters,
                interval_start_utc=spec.coverage_start_utc,
                interval_end_utc=spec.coverage_end_utc,
                return_schedule=False,
                shadow_bodies=tuple(
                    dict.fromkeys(
                        event.shadow_body for event in dataset.events
                    )
                ),
                seed_candidate_epochs=tuple(
                    event.reference_epoch for event in dataset.events
                ),
                geometry=self.eclipse_geometry_options(),
            )
            self.eclipse_worker.moveToThread(self.eclipse_thread)
            self.eclipse_thread.started.connect(self.eclipse_worker.run)
            self.eclipse_worker.progress.connect(
                self.update_eclipse_progress
            )
            self.eclipse_worker.stage.connect(
                self.update_eclipse_progress_stage
            )
            self.eclipse_worker.date_changed.connect(
                self.update_eclipse_reference_date
            )
            self.eclipse_worker.completed.connect(
                self.finish_eclipse_reference_interval
            )
            self.eclipse_worker.failed.connect(self.fail_eclipse_prediction)
            self.eclipse_worker.cancelled.connect(
                self.cancelled_eclipse_prediction
            )
            self.eclipse_worker.completed.connect(self.eclipse_thread.quit)
            self.eclipse_worker.failed.connect(self.eclipse_thread.quit)
            self.eclipse_worker.cancelled.connect(self.eclipse_thread.quit)
            self.eclipse_thread.finished.connect(
                self.eclipse_worker.deleteLater
            )
            self.eclipse_thread.finished.connect(
                self.eclipse_thread.deleteLater
            )
            self.eclipse_thread.finished.connect(
                self.cleanup_eclipse_prediction
            )
            self.eclipse_thread.start()
        except Exception as error:
            if self.eclipse_eta_timer.isActive():
                self.stop_eclipse_eta("Input error")
            self.eclipse_reference_progress.setValue(0)
            self.eclipse_reference_progress.setFormat("Input error")
            self.eclipse_reference_run_model_button.setEnabled(True)
            self.eclipse_reference_selector.setEnabled(True)
            self.eclipse_reference_compare_button.setEnabled(True)
            self.eclipse_reference_summary_label.setText(
                "REFERENCE-RANGE INPUT ERROR\n"
                f"{type(error).__name__}: {error}"
            )

    def finish_eclipse_reference_interval(self, prediction):

        self.eclipse_reference_interval_prediction = prediction
        self._last_eclipse_output_kind = "reference"
        self.eclipse_progress.setValue(100)
        self.eclipse_progress.setFormat("Reference run completed")
        self.eclipse_reference_progress.setValue(100)
        self.eclipse_reference_progress.setFormat("Completed · 100%")
        completed_spec = self._pending_eclipse_reference_spec
        self.eclipse_reference_date_label.setText(
            f"Completed: {completed_spec.coverage_start_utc:%Y-%m-%d} → "
            f"{(completed_spec.coverage_end_utc - timedelta(microseconds=1)):%Y-%m-%d} UTC"
        )
        self.stop_eclipse_eta("Completed")
        self.eclipse_calculate_button.setEnabled(True)
        self.eclipse_year_search_button.setEnabled(True)
        self.eclipse_reference_run_model_button.setEnabled(True)
        self.eclipse_reference_selector.setEnabled(True)
        self.eclipse_reference_compare_button.setEnabled(True)
        self.eclipse_cancel_button.setEnabled(False)
        self.run_eclipse_reference_comparison()
        self.eclipse_reference_summary_label.setText(
            self.eclipse_reference_summary_label.text()
            + "\nModel initial state: "
            + self._pending_eclipse_reference_state_source
            + (
                "\n" + self._pending_eclipse_reference_state_warning
                if self._pending_eclipse_reference_state_warning
                else ""
            )
        )
        spec = completed_spec
        self.statusBar().showMessage(
            (
                f"Reference interval completed: {spec.label} · "
                f"{len(prediction.events)} model events"
            ),
            12000,
        )

    def _active_eclipse_events_for_reference_comparison(self):

        if (
            self._last_eclipse_output_kind == "year"
            and self.yearly_eclipse_schedule is not None
        ):
            return tuple(
                row.event
                for row in self.yearly_eclipse_schedule.rows
                if row.event is not None
            )
        if (
            self._last_eclipse_output_kind == "standard"
            and self.eclipse_prediction_result is not None
        ):
            return tuple(self.eclipse_prediction_result.events)
        if (
            self._last_eclipse_output_kind == "reference"
            and self.eclipse_reference_interval_prediction is not None
        ):
            return tuple(self.eclipse_reference_interval_prediction.events)
        return None

    @staticmethod
    def _eclipse_reference_epoch_text(value):

        if value is None:
            return "—"
        return value.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M:%S")

    @staticmethod
    def _eclipse_reference_delta_text(value):

        if value is None:
            return "—"
        seconds = float(value)
        absolute_seconds = abs(seconds)
        if absolute_seconds < 60.0:
            amount = f"{absolute_seconds:.1f} seconds"
        elif absolute_seconds < 3600.0:
            minutes = int(absolute_seconds // 60.0)
            remaining_seconds = int(round(absolute_seconds - minutes * 60.0))
            if remaining_seconds == 60:
                minutes += 1
                remaining_seconds = 0
            amount = f"{minutes} minutes"
            if remaining_seconds:
                amount += f" {remaining_seconds} seconds"
        else:
            hours = int(absolute_seconds // 3600.0)
            minutes = int(round((absolute_seconds - hours * 3600.0) / 60.0))
            if minutes == 60:
                hours += 1
                minutes = 0
            amount = f"{hours} hours"
            if minutes:
                amount += f" {minutes} minutes"
        direction = "early" if seconds < 0.0 else "late"
        return f"{amount} {direction}"

    @classmethod
    def _eclipse_reference_duration_delta_text(cls, value):

        if value is None:
            return "—"
        direction = "shorter" if float(value) < 0.0 else "longer"
        human_delta = cls._eclipse_reference_delta_text(abs(float(value)))
        amount = human_delta.rsplit(" ", 1)[0]
        return f"{amount} {direction}"

    # Contact conditioning is measured, not assumed: it is the rate at which
    # the limb margin crosses zero. A grazing contact is ill-conditioned by
    # geometry, so a large residual there is expected and should be labelled
    # rather than mistaken for a model defect.
    ECLIPSE_CONDITIONING_LABELS = {
        "SHARP": "SHARP",
        "SOFT": "SOFT",
        "GRAZING": "GRAZING",
    }

    @classmethod
    def _eclipse_conditioning_text(cls, output_event):
        """Return the canonical label for one event's contact geometry."""

        conditioning = getattr(output_event, "conditioning", None)
        if not conditioning:
            return "—"
        return cls.ECLIPSE_CONDITIONING_LABELS.get(conditioning, "—")

    @staticmethod
    def _eclipse_conditioning_tooltip(output_event):
        """Explain what the conditioning label means for this event."""

        sensitivity = getattr(
            output_event,
            "worst_contact_sensitivity",
            None,
        )
        if sensitivity is None or not np.isfinite(sensitivity):
            return "Contact sensitivity was not measured."
        explanation = (
            "Each 1 millidegree geometry difference shifts contact time by "
            f"{float(sensitivity):.2f} seconds."
        )
        if sensitivity >= 2.0:
            return (
                explanation
                + " The satellite grazes the shadow edge, so a large difference "
                "is expected here and is not a model defect."
            )
        return explanation

    def update_eclipse_reference_interval_label(self):

        try:
            dataset = load_eclipse_reference_dataset(
                self.eclipse_reference_selector.currentData()
            )
            start = dataset.spec.coverage_start_utc
            end = dataset.spec.coverage_end_utc - timedelta(microseconds=1)
            self.eclipse_reference_date_label.setText(
                f"Selected interval: {start:%Y-%m-%d} → {end:%Y-%m-%d} UTC"
            )
        except Exception:
            self.eclipse_reference_date_label.setText("Selected interval: —")

    def update_eclipse_reference_date(self, value):

        self.eclipse_reference_date_label.setText(str(value))

    def refresh_eclipse_reference_comparison(self, _index=None):

        self.update_eclipse_reference_interval_label()
        if self._active_eclipse_events_for_reference_comparison() is not None:
            self.run_eclipse_reference_comparison()
            return
        self.eclipse_reference_comparison = None
        self.eclipse_reference_export_button.setEnabled(False)
        self.eclipse_reference_table.setRowCount(0)
        self.eclipse_reference_summary_label.setText(
            "Run an Eclipse calculation, then compare it with the selected "
            "reference."
        )

    def run_eclipse_reference_comparison(self):

        events = self._active_eclipse_events_for_reference_comparison()
        if events is None:
            self.eclipse_reference_summary_label.setText(
                "REFERENCE COMPARISON ERROR\n"
                "Run a normal or selected-year Eclipse calculation first."
            )
            return
        dataset_id = self.eclipse_reference_selector.currentData()
        try:
            comparison = compare_eclipse_events(
                events,
                dataset_id,
                tolerance_seconds=(
                    self.eclipse_reference_tolerance_seconds.value()
                ),
            )
        except Exception as error:
            self.eclipse_reference_comparison = None
            self.eclipse_reference_export_button.setEnabled(False)
            self.eclipse_reference_table.setRowCount(0)
            self.eclipse_reference_summary_label.setText(
                "REFERENCE COMPARISON ERROR\n"
                f"{type(error).__name__}: {error}"
            )
            return

        self.eclipse_reference_comparison = comparison
        self.eclipse_reference_table.setRowCount(len(comparison.rows))
        for table_row, comparison_row in enumerate(comparison.rows):
            reference = comparison_row.reference_event
            output = comparison_row.output_event
            reference_entry = None if reference is None else (
                reference.penumbra_entry_utc or reference.umbra_entry_utc
            )
            output_entry = None if output is None else (
                output.penumbra_entry_utc or output.umbra_entry_utc
            )
            reference_exit = None if reference is None else (
                reference.penumbra_exit_utc or reference.umbra_exit_utc
            )
            output_exit = None if output is None else (
                output.penumbra_exit_utc or output.umbra_exit_utc
            )
            entry_delta = (
                comparison_row.penumbra_entry_delta_seconds
                if comparison_row.penumbra_entry_delta_seconds is not None
                else comparison_row.umbra_entry_delta_seconds
            )
            exit_delta = (
                comparison_row.penumbra_exit_delta_seconds
                if comparison_row.penumbra_exit_delta_seconds is not None
                else comparison_row.umbra_exit_delta_seconds
            )
            status_text = {
                "MATCH": "MATCH",
                "DIFFERENCE": "DIFFERENCE",
                "MISSING OUTPUT": "MISSING OUTPUT",
                "EXTRA OUTPUT": "EXTRA OUTPUT",
            }.get(comparison_row.status, comparison_row.status)
            body_text = {
                "EARTH": "EARTH",
                "MOON": "MOON",
            }.get(comparison_row.shadow_body, comparison_row.shadow_body)
            values = (
                status_text,
                body_text,
                "—" if comparison_row.reference_event_number is None else str(
                    comparison_row.reference_event_number
                ),
                "—" if comparison_row.output_event_number is None else str(
                    comparison_row.output_event_number
                ),
                self._eclipse_reference_epoch_text(reference_entry),
                self._eclipse_reference_epoch_text(output_entry),
                self._eclipse_reference_delta_text(entry_delta),
                self._eclipse_reference_epoch_text(reference_exit),
                self._eclipse_reference_epoch_text(output_exit),
                self._eclipse_reference_delta_text(exit_delta),
                self._eclipse_reference_duration_delta_text(
                    comparison_row.total_duration_delta_seconds
                ),
                self._eclipse_conditioning_text(comparison_row.output_event),
            )
            color = {
                "MATCH": theme.STATUS_OK,
                "DIFFERENCE": theme.STATUS_WARNING,
                "MISSING OUTPUT": theme.STATUS_ERROR,
                "EXTRA OUTPUT": theme.STATUS_ALERT,
            }.get(comparison_row.status, theme.TEXT_SECONDARY)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (6, 9, 10):
                    exact_value = {
                        6: entry_delta,
                        9: exit_delta,
                        10: comparison_row.total_duration_delta_seconds,
                    }[column]
                    if exact_value is not None:
                        item.setToolTip(
                            f"Exact difference: {float(exact_value):+.3f} seconds "
                            "(model − reference)"
                        )
                if column == 0:
                    item.setForeground(QColor(color))
                if column == 11:
                    conditioning = getattr(
                        comparison_row.output_event,
                        "conditioning",
                        None,
                    )
                    item.setForeground(
                        QColor(theme.conditioning_colour(conditioning))
                    )
                    item.setToolTip(self._eclipse_conditioning_tooltip(
                        comparison_row.output_event
                    ))
                self.eclipse_reference_table.setItem(
                    table_row,
                    column,
                    item,
                )

        rms_error = comparison.rms_contact_error_seconds
        mean_error = comparison.mean_absolute_contact_error_seconds
        maximum_error = comparison.maximum_absolute_contact_error_seconds
        rms_text = (
            "—" if rms_error is None
            else self._eclipse_reference_delta_text(abs(rms_error)).rsplit(" ", 1)[0]
        )
        mean_text = (
            "—" if mean_error is None
            else self._eclipse_reference_delta_text(abs(mean_error)).rsplit(" ", 1)[0]
        )
        maximum_text = (
            "—" if maximum_error is None
            else self._eclipse_reference_delta_text(abs(maximum_error)).rsplit(" ", 1)[0]
        )
        deltas = comparison.contact_deltas_seconds
        signed_mean = None if not deltas else sum(deltas) / len(deltas)
        systematic_text = (
            "The time direction could not be determined."
            if signed_mean is None
            else "On average, the model finds the Eclipse "
            + self._eclipse_reference_delta_text(signed_mean)
            + "."
        )
        spec = comparison.dataset.spec
        result_text = (
            "MATCHES"
            if comparison.difference_count == 0
            and comparison.missing_output_count == 0
            and comparison.extra_output_count == 0
            else "DOES NOT MATCH"
        )
        cause_lines = []
        pending_spec = self._pending_eclipse_reference_spec
        if (
            self._last_eclipse_output_kind == "reference"
            and pending_spec is not None
            and pending_spec.dataset_id == spec.dataset_id
            and self._pending_eclipse_reference_state_warning
        ):
            cause_lines.append(
                "MAIN CAUSE: the initial orbit state does not belong to the "
                "selected period. Propagating a TLE from another date months "
                "forward or backward shifts orbital longitude and phase."
            )
            if comparison.missing_output_count:
                cause_lines.append(
                    "The first missing event also occurs because this phase "
                    "shift changes the start of the Eclipse season."
                )
            cause_lines.append(
                "SOLUTION: provide a historical TLE or J2000 state for that "
                "satellite near the reference interval, then recalculate."
            )
        elif (
            self._last_eclipse_output_kind == "reference"
            and pending_spec is not None
            and pending_spec.dataset_id == spec.dataset_id
            and spec.nominal_longitude_deg is not None
        ):
            cause_lines.append(
                "MODEL SOURCE: this Eclipse schedule belongs to nominal GEO "
                f"geometry. The comparison used a fixed nominal orbit at "
                f"{spec.nominal_longitude_deg:.1f}°E; no shift or phase "
                "calibration was taken from reference event times."
            )
        self.eclipse_reference_summary_label.setText(
            f"RESULT: {result_text}\n"
            f"{spec.label}: {comparison.matched_count} matching, "
            f"{comparison.difference_count} different times, "
            f"{comparison.missing_output_count} missing model outputs, "
            f"{comparison.extra_output_count} extra events.\n"
            f"{systematic_text}\n"
            f"Mean absolute error: {mean_text}  ·  RMS: {rms_text}  ·  "
            f"Maximum error: {maximum_text}\n"
            + "\n".join(cause_lines)
        )
        self.eclipse_reference_export_button.setEnabled(True)

    @staticmethod
    def _eclipse_export_slug(text):
        """Turn a reference label into a safe, still-recognisable file stem."""

        simplified = (
            str(text)
            .replace("·", " ")
            .replace("–", "-")
            .replace("—", "-")
            .replace("+", "and")
        )
        cleaned = re.sub(r"[^0-9A-Za-z_-]+", "_", simplified)
        return re.sub(r"_+", "_", cleaned).strip("_-") or "reference"

    @staticmethod
    def _eclipse_export_target(default_name):
        """Suggest a save path in the per-user application data folder."""

        directory = os.path.join(APPLICATION_DATA_DIR, "outputs")
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError:
            directory = APPLICATION_DATA_DIR
        return os.path.join(directory, default_name)

    def export_eclipse_reference_comparison_csv(self):

        comparison = self.eclipse_reference_comparison
        if comparison is None:
            self.eclipse_reference_summary_label.setText(
                "REFERENCE CSV EXPORT ERROR\nRun the comparison first."
            )
            return
        default_name = (
            "eclipse_comparison_"
            + self._eclipse_export_slug(comparison.dataset.spec.label)
            + ".csv"
        )
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Eclipse Reference Comparison CSV"),
            self._eclipse_export_target(default_name),
            "CSV Files (*.csv);;All Files (*)",
            options=theme.file_dialog_options(),
        )
        if not file_path:
            return
        try:
            output_path = save_eclipse_reference_comparison_csv(
                comparison,
                file_path,
            )
            side_by_side_path = save_eclipse_reference_side_by_side_csv(
                comparison,
                output_path.with_name(
                    output_path.stem + "_side_by_side.csv"
                ),
            )
        except Exception as error:
            self.eclipse_reference_summary_label.setText(
                "REFERENCE CSV EXPORT ERROR\n"
                f"{type(error).__name__}: {error}"
            )
            return
        self.eclipse_reference_summary_label.setText(
            self.eclipse_reference_summary_label.text()
            + "\nComparison CSV exported: "
            + str(output_path)
            + chr(10)
            + "Reference-layout CSV — open this one beside the workbook: "
            + str(side_by_side_path)
        )
        self.statusBar().showMessage(
            "Eclipse comparison CSV exported: "
            f"{output_path.name}, {side_by_side_path.name}",
            10000,
        )

    def update_eclipse_step_unit(self, _index=None):

        multiplier = int(self.eclipse_step_unit.currentData() or 60)
        ranges = {
            1: (1, 60, " sec"),
            60: (1, 60, " min"),
            3600: (1, 24, " hr"),
            86400: (1, 365, " day"),
        }
        minimum, maximum, suffix = ranges[multiplier]
        current_value = int(self.eclipse_step_value.value())
        self.eclipse_step_value.setRange(minimum, maximum)
        self.eclipse_step_value.setValue(
            min(max(current_value, minimum), maximum)
        )
        self.eclipse_step_value.setSuffix(suffix)
        if multiplier == 1:
            self.eclipse_step_warning.setText(
                "10-second steps are the precision default. Limb contacts "
                "are then refined to 1 ms inside each bracket."
            )
        elif multiplier == 60:
            self.eclipse_step_warning.setText(
                "Minute steps are suitable for routine searches; use seconds "
                "for a denser illumination profile and tighter interpolation."
            )
        else:
            self.eclipse_step_warning.setText(
                "Warning: hour/day search steps can skip an eclipse that "
                "falls completely between two samples."
            )

    def eclipse_geometry_options(self):
        """Return the geometry refinements the user has switched on.

        Falls back to the defaults while the Eclipse page is still being
        built, because the System Check page is constructed before it.
        """

        def switched_on(name):
            control = getattr(self, name, None)
            return bool(control is not None and control.isChecked())

        return EclipseGeometryOptions(
            oblate_earth_shadow=switched_on("eclipse_oblate_earth"),
            light_time_moon=switched_on("eclipse_light_time_moon"),
        )

    def eclipse_search_step_seconds(self):

        multiplier = self.eclipse_step_unit.currentData()
        if multiplier is None:
            raise ValueError("Select an Eclipse search-step unit.")
        return float(self.eclipse_step_value.value() * int(multiplier))

    @staticmethod
    def _format_eclipse_eta(seconds):

        total_seconds = max(0, int(np.ceil(float(seconds))))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def start_eclipse_eta(self):

        self._eclipse_progress_started_at = time.perf_counter()
        self._eclipse_progress_percent = 0
        self._eclipse_eta_deadline = None
        self.eclipse_eta_label.setText("Remaining: estimating…")
        self.eclipse_eta_timer.start()

    def update_eclipse_progress(self, value):

        progress = int(np.clip(int(value), 0, 100))
        self._eclipse_progress_percent = progress
        self.eclipse_progress.setValue(progress)
        if self._eclipse_run_mode == "reference":
            self.eclipse_reference_progress.setValue(progress)
        started_at = self._eclipse_progress_started_at
        if started_at is None:
            return

        now = time.perf_counter()
        elapsed = max(0.0, now - started_at)
        if 0 < progress < 100 and elapsed > 0.0:
            remaining = elapsed * (100.0 - progress) / progress
            predicted_deadline = now + remaining
            if self._eclipse_eta_deadline is None:
                self._eclipse_eta_deadline = predicted_deadline
            else:
                # Smooth progress-stage jumps while still recalibrating the
                # countdown as the measured calculation speed changes.
                self._eclipse_eta_deadline = (
                    0.70 * self._eclipse_eta_deadline
                    + 0.30 * predicted_deadline
                )
        elif progress >= 100:
            self._eclipse_eta_deadline = now
        self.refresh_eclipse_eta()

    def update_eclipse_progress_stage(self, stage):

        self.eclipse_progress.setFormat(f"{stage} · %p%")
        if self._eclipse_run_mode == "reference":
            self.eclipse_reference_progress.setFormat(f"{stage} · %p%")

    def refresh_eclipse_eta(self):

        if self._eclipse_eta_deadline is None:
            self.eclipse_eta_label.setText("Remaining: estimating…")
            return
        remaining = max(
            0.0,
            self._eclipse_eta_deadline - time.perf_counter(),
        )
        self.eclipse_eta_label.setText(
            "Remaining: " + self._format_eclipse_eta(remaining)
        )

    def stop_eclipse_eta(self, status):

        self.eclipse_eta_timer.stop()
        self._eclipse_progress_started_at = None
        self._eclipse_eta_deadline = None
        self.eclipse_eta_label.setText(str(status))

    def cancel_eclipse_prediction(self):

        if self.eclipse_thread is None or not self.eclipse_thread.isRunning():
            return
        self.eclipse_thread.requestInterruption()
        self.eclipse_cancel_button.setEnabled(False)
        self.eclipse_progress.setFormat("Cancelling...")

    def finish_eclipse_prediction(self, prediction):

        self.eclipse_prediction_result = prediction
        self._last_eclipse_output_kind = "standard"
        self.eclipse_initial_epoch = self._pending_eclipse_config["epoch"]
        self.eclipse_event_selector.blockSignals(True)
        self.eclipse_event_selector.clear()
        if prediction.events:
            for index, event in enumerate(prediction.events):
                reference_epoch = (
                    event.penumbra_entry_utc
                    or event.umbra_entry_utc
                    or self.eclipse_initial_epoch
                )
                date_text = reference_epoch.astimezone(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M UTC"
                )
                duration_text = self._format_eclipse_duration(
                    event.umbra_duration_seconds
                ) if event.umbra_duration_seconds is not None else "partial only"
                self.eclipse_event_selector.addItem(
                    f"Event {index + 1} — {date_text} — umbra {duration_text}",
                    index,
                )
        else:
            self.eclipse_event_selector.addItem(
                "No eclipse events in this search window",
                None,
            )
        self.eclipse_event_selector.setCurrentIndex(0)
        self.eclipse_event_selector.blockSignals(False)
        self.update_eclipse_event_table()
        self.render_eclipse_prediction()
        self.eclipse_progress.setValue(100)
        self.eclipse_progress.setFormat("Completed")
        self.stop_eclipse_eta("Completed")
        self.eclipse_calculate_button.setEnabled(True)
        self.eclipse_year_search_button.setEnabled(True)
        self.eclipse_reference_run_model_button.setEnabled(True)
        self.eclipse_reference_selector.setEnabled(True)
        self.eclipse_reference_compare_button.setEnabled(True)
        self.eclipse_cancel_button.setEnabled(False)
        self.eclipse_export_csv_button.setEnabled(True)
        self.run_eclipse_reference_comparison()
        self.statusBar().showMessage(
            f"Eclipse calculation completed: {len(prediction.events)} events",
            8000,
        )

    def export_eclipse_prediction_csv(self):

        prediction = self.eclipse_prediction_result
        initial_epoch = self.eclipse_initial_epoch
        if prediction is None or initial_epoch is None:
            self.eclipse_summary_label.setText(
                "ECLIPSE CSV EXPORT ERROR\nCalculate eclipse events first."
            )
            return

        span_days = float(prediction.elapsed_seconds[-1]) / 86400.0
        default_name = (
            "eclipse_timeline_"
            + initial_epoch.astimezone(timezone.utc).strftime("%Y%m%dT%H%MZ")
            + f"_{span_days:.0f}d.csv"
        )
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Eclipse Timeline and Events CSV"),
            self._eclipse_export_target(default_name),
            "CSV Files (*.csv);;All Files (*)",
            options=theme.file_dialog_options(),
        )
        if not file_path:
            return

        try:
            timeline_path, events_path = save_eclipse_prediction_csv(
                prediction,
                initial_epoch,
                file_path,
            )
        except Exception as error:
            self.eclipse_summary_label.setText(
                "ECLIPSE CSV EXPORT ERROR\n"
                f"{type(error).__name__}: {error}"
            )
            return

        self.statusBar().showMessage(
            "Eclipse CSV export completed: "
            f"{timeline_path.name}, {events_path.name}",
            10000,
        )
        self.eclipse_summary_label.setText(
            self.eclipse_summary_label.text()
            + "\n\nCSV EXPORT COMPLETED\n"
            + f"Timeline: {timeline_path}\n"
            + f"Events: {events_path}"
        )

    def fail_eclipse_prediction(self, message):

        if self._eclipse_run_mode == "year":
            self.eclipse_year_summary_label.setText(
                "YEARLY ECLIPSE ERROR\n" + message
            )
        elif self._eclipse_run_mode == "reference":
            self.eclipse_reference_summary_label.setText(
                "REFERENCE-RANGE ECLIPSE ERROR\n" + message
            )
            self.eclipse_reference_progress.setFormat("Failed")
        else:
            self.eclipse_summary_label.setText("ECLIPSE ERROR\n" + message)
        self.eclipse_progress.setFormat("Failed")
        self.stop_eclipse_eta("Failed")
        self.eclipse_calculate_button.setEnabled(True)
        self.eclipse_year_search_button.setEnabled(True)
        self.eclipse_reference_run_model_button.setEnabled(True)
        self.eclipse_reference_selector.setEnabled(True)
        self.eclipse_reference_compare_button.setEnabled(True)
        self.eclipse_cancel_button.setEnabled(False)

    def cancelled_eclipse_prediction(self):

        if self._eclipse_run_mode == "year":
            self.eclipse_year_summary_label.setText(
                "YEARLY ECLIPSE SEARCH CANCELLED\n"
                "No partial schedule was stored."
            )
        elif self._eclipse_run_mode == "reference":
            self.eclipse_reference_summary_label.setText(
                "REFERENCE-RANGE SEARCH CANCELLED\n"
                "No partial comparison was stored."
            )
            self.eclipse_reference_progress.setFormat("Cancelled")
        else:
            self.eclipse_summary_label.setText(
                "ECLIPSE CALCULATION CANCELLED\nNo partial result was stored."
            )
        self.eclipse_progress.setFormat("Cancelled")
        self.stop_eclipse_eta("Cancelled")
        self.eclipse_calculate_button.setEnabled(True)
        self.eclipse_year_search_button.setEnabled(True)
        self.eclipse_reference_run_model_button.setEnabled(True)
        self.eclipse_reference_selector.setEnabled(True)
        self.eclipse_reference_compare_button.setEnabled(True)
        self.eclipse_cancel_button.setEnabled(False)

    def cleanup_eclipse_prediction(self):

        self.eclipse_worker = None
        self.eclipse_thread = None
        if getattr(self, "_eclipse_timer_was_active", False):
            self.timer.start(1000)
        self._eclipse_timer_was_active = False
        self._eclipse_run_mode = None

    def select_eclipse_event_from_table(self, row, _column):

        if 0 <= int(row) < self.eclipse_event_selector.count():
            self.eclipse_event_selector.setCurrentIndex(int(row))

    def render_eclipse_prediction(self, _index=None):

        prediction = self.eclipse_prediction_result
        if prediction is None or self.eclipse_initial_epoch is None:
            return

        figure = self.eclipse_graph.figure
        figure.clear()
        self.eclipse_graph._coordinate_annotations = {}
        overview_axis, detail_axis = figure.subplots(
            2,
            1,
            gridspec_kw={"height_ratios": (0.9, 2.1)},
        )
        self.eclipse_graph.ax = detail_axis
        GraphWidget.style_axis(overview_axis)
        GraphWidget.style_axis(detail_axis)
        overview_axis._opa_disable_pointer_coordinates = True

        elapsed_days = prediction.elapsed_seconds / 86400.0
        illumination = prediction.illumination_fraction * 100.0

        # Overview: use a single horizontal status lane so one-hour events do
        # not collapse into unreadable vertical spikes on a 30-day plot.
        total_days = max(float(elapsed_days[-1]), 1.0e-9)
        selected_event_index = self.eclipse_event_selector.currentData()
        if selected_event_index is None:
            selected_event_index = 0
        selected_event_index = int(
            np.clip(
                selected_event_index,
                0,
                max(len(prediction.events) - 1, 0),
            )
        )
        overview_axis.barh(
            0.0,
            total_days,
            left=0.0,
            height=0.5,
            color="#10B981",
            alpha=0.22,
            edgecolor="#34D399",
            linewidth=0.8,
            label="Full sunlight",
        )
        for event_index, event in enumerate(prediction.events):
            total_start = (
                0.0
                if event.penumbra_entry_utc is None
                else (
                    event.penumbra_entry_utc - self.eclipse_initial_epoch
                ).total_seconds() / 86400.0
            )
            total_end = (
                float(elapsed_days[-1])
                if event.penumbra_exit_utc is None
                else (
                    event.penumbra_exit_utc - self.eclipse_initial_epoch
                ).total_seconds() / 86400.0
            )
            overview_axis.barh(
                0.0,
                max(total_end - total_start, 1.0e-7),
                left=total_start,
                height=0.62,
                color="#F59E0B",
                alpha=0.9,
                edgecolor=(
                    "#E0F2FE"
                    if event_index == selected_event_index
                    else "#FCD34D"
                ),
                linewidth=(
                    2.0 if event_index == selected_event_index else 0.8
                ),
                label="Penumbra" if event_index == 0 else None,
                zorder=3,
            )
            if (
                event.umbra_entry_utc is not None
                and event.umbra_exit_utc is not None
            ):
                umbra_start = (
                    event.umbra_entry_utc - self.eclipse_initial_epoch
                ).total_seconds() / 86400.0
                umbra_end = (
                    event.umbra_exit_utc - self.eclipse_initial_epoch
                ).total_seconds() / 86400.0
                overview_axis.barh(
                    0.0,
                    max(umbra_end - umbra_start, 1.0e-7),
                    left=umbra_start,
                    height=0.62,
                    color="#EF4444",
                    alpha=0.95,
                    edgecolor=(
                        "#E0F2FE"
                        if event_index == selected_event_index
                        else "#FCA5A5"
                    ),
                    linewidth=(
                        2.0 if event_index == selected_event_index else 0.8
                    ),
                    label="Umbra" if event_index == 0 else None,
                    zorder=4,
                )
            event_midpoint = 0.5 * (total_start + total_end)
            overview_axis.text(
                event_midpoint,
                0.42,
                f"#{event_index + 1}",
                ha="center",
                va="bottom",
                color=(
                    "#38BDF8"
                    if event_index == selected_event_index
                    else "#F8FAFC"
                ),
                fontsize=7.5,
                fontweight="bold",
                clip_on=True,
            )

        overview_axis.set_xlim(0.0, total_days)
        overview_axis.set_ylim(-0.55, 0.78)
        overview_axis.set_yticks([])
        overview_axis.set_xlabel("Elapsed time [days]")
        overview_axis.set_title(
            f"SEARCH OVERVIEW — {len(prediction.events)} eclipse event(s); "
            "select one below for detail",
            fontsize=10.5,
            pad=8,
        )
        overview_axis.legend(
            loc="upper left",
            ncol=3,
            facecolor="#0F172A",
            edgecolor="#334155",
            labelcolor="#E2E8F0",
            fontsize=8.5,
        )

        if not prediction.events:
            detail_axis.text(
                0.5,
                0.5,
                "NO EARTH ECLIPSE IN THIS SEARCH WINDOW",
                transform=detail_axis.transAxes,
                ha="center",
                va="center",
                color="#34D399",
                fontsize=14,
                fontweight="bold",
            )
            detail_axis.set_axis_off()
            figure.tight_layout(pad=1.25)
            self.eclipse_graph.draw_idle()
            return

        event = prediction.events[selected_event_index]
        event_start_seconds = (
            0.0
            if event.penumbra_entry_utc is None
            else (
                event.penumbra_entry_utc - self.eclipse_initial_epoch
            ).total_seconds()
        )
        event_end_seconds = (
            float(prediction.elapsed_seconds[-1])
            if event.penumbra_exit_utc is None
            else (
                event.penumbra_exit_utc - self.eclipse_initial_epoch
            ).total_seconds()
        )
        event_reference_epoch = self.eclipse_initial_epoch + timedelta(
            seconds=float(event_start_seconds)
        )
        margin_seconds = max(
            10.0 * 60.0,
            2.0 * prediction.source_step_seconds,
        )
        window_start = max(0.0, event_start_seconds - margin_seconds)
        window_end = min(
            float(prediction.elapsed_seconds[-1]),
            event_end_seconds + margin_seconds,
        )
        detail_mask = (
            (prediction.elapsed_seconds >= window_start)
            & (prediction.elapsed_seconds <= window_end)
        )
        detail_seconds = prediction.elapsed_seconds[detail_mask]
        detail_illumination = illumination[detail_mask]
        if len(detail_seconds) < 2:
            nearest = np.argsort(
                np.abs(prediction.elapsed_seconds - event_start_seconds)
            )[:2]
            nearest.sort()
            detail_seconds = prediction.elapsed_seconds[nearest]
            detail_illumination = illumination[nearest]
        detail_minutes = (detail_seconds - event_start_seconds) / 60.0

        detail_axis.axvspan(
            (window_start - event_start_seconds) / 60.0,
            (window_end - event_start_seconds) / 60.0,
            color="#10B981",
            alpha=0.07,
            label="Full sunlight",
            zorder=0,
        )
        total_start_minute = 0.0
        total_end_minute = (event_end_seconds - event_start_seconds) / 60.0
        detail_axis.axvspan(
            total_start_minute,
            total_end_minute,
            color="#F59E0B",
            alpha=0.18,
            label="Penumbra",
            zorder=1,
        )
        if (
            event.umbra_entry_utc is not None
            and event.umbra_exit_utc is not None
        ):
            umbra_start_minute = (
                event.umbra_entry_utc - event_reference_epoch
            ).total_seconds() / 60.0
            umbra_end_minute = (
                event.umbra_exit_utc - event_reference_epoch
            ).total_seconds() / 60.0
            detail_axis.axvspan(
                umbra_start_minute,
                umbra_end_minute,
                color="#EF4444",
                alpha=0.25,
                label="Umbra",
                zorder=2,
            )

        detail_axis.plot(
            detail_minutes,
            detail_illumination,
            color="#38BDF8",
            linewidth=2.2,
            marker="o",
            markersize=3.0,
            label="Sunlight fraction",
            zorder=5,
        )
        transitions = (
            (event.penumbra_entry_utc, "PEN IN", "#FBBF24"),
            (event.umbra_entry_utc, "UMBRA IN", "#FB7185"),
            (event.umbra_exit_utc, "UMBRA OUT", "#FB7185"),
            (event.penumbra_exit_utc, "PEN OUT", "#FBBF24"),
        )
        for transition_index, (transition, label, color) in enumerate(
            transitions
        ):
            if transition is None:
                continue
            transition_minute = (
                transition - event_reference_epoch
            ).total_seconds() / 60.0
            detail_axis.axvline(
                transition_minute,
                color=color,
                linewidth=1.25,
                linestyle="--",
                alpha=0.95,
                zorder=6,
            )
            detail_axis.text(
                transition_minute,
                103.0 - (transition_index % 2) * 10.0,
                label,
                rotation=90,
                ha="right",
                va="top",
                color=color,
                fontsize=8,
                fontweight="bold",
                zorder=7,
            )

        event_date = (
            event.penumbra_entry_utc or self.eclipse_initial_epoch
        ).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        detail_axis.set_title(
            f"EVENT #{selected_event_index + 1} DETAIL — {event_date}  ·  "
            f"Umbra {self._format_eclipse_duration(event.umbra_duration_seconds)}  ·  "
            f"Total {self._format_eclipse_duration(event.total_duration_seconds)}",
            fontsize=10.5,
            pad=8,
        )
        detail_axis.set_xlabel("Minutes from penumbra entry")
        detail_axis.set_ylabel("Sunlight fraction [%]")
        detail_axis.set_ylim(-5.0, 108.0)
        detail_axis.set_xlim(
            (window_start - event_start_seconds) / 60.0,
            (window_end - event_start_seconds) / 60.0,
        )
        detail_axis.legend(
            loc="lower left",
            ncol=4,
            facecolor="#0F172A",
            edgecolor="#334155",
            labelcolor="#E2E8F0",
            fontsize=8.5,
        )
        figure.tight_layout(pad=1.25)
        self.eclipse_graph.draw_idle()

    def update_manual_propagation_chart(self, _index=None):

        times = self.last_prop_times
        states = self.last_prop_states
        if times is None or states is None:
            if len(self.manual_graph.figure.axes) != 1:
                self.manual_graph.figure.clear()
                self.manual_graph.ax = self.manual_graph.figure.add_subplot(111)
            axis = self.manual_graph.ax
            axis.clear()
            GraphWidget.style_axis(axis)
            axis.set_xlabel("Elapsed time [days]")
            axis.set_ylabel("State")
            axis.set_title("Manual propagation result")
            axis.text(
                0.5,
                0.5,
                "Complete a propagation to plot the trajectory",
                transform=axis.transAxes,
                ha="center",
                va="center",
                color="#64748B",
                fontsize=11,
            )
            self.manual_graph.figure.tight_layout(pad=1.2)
            self.manual_graph.draw_idle()
            return

        elapsed_days = np.asarray(times, dtype=float) / 86400.0
        max_display_points = 5000
        if len(elapsed_days) > max_display_points:
            indices = np.linspace(
                0,
                len(elapsed_days) - 1,
                max_display_points,
                dtype=int,
            )
            display_days = elapsed_days[indices]
        else:
            display_days = elapsed_days

        values_matrix = np.asarray(states, dtype=float)
        display_matrix = (
            values_matrix[indices]
            if len(elapsed_days) > max_display_points
            else values_matrix
        )
        chart_mode = self.manual_chart_component.currentData()

        if chart_mode == "longitude":
            axis = self._set_manual_single_axis()
            longitudes = earth_fixed_longitude_degrees(
                values_matrix,
                self.last_prop_epoch,
                np.asarray(times, dtype=float),
            )
            display_longitudes = (
                longitudes[indices]
                if len(elapsed_days) > max_display_points
                else longitudes
            )
            axis.plot(
                display_days,
                display_longitudes,
                color="#38BDF8",
                linewidth=1.8,
                label="Propagated longitude",
            )
            for value, label in (
                (
                    TARGET_LONGITUDE_DEG - LONGITUDE_TOLERANCE_DEG,
                    f"MIN {TARGET_LONGITUDE_DEG - LONGITUDE_TOLERANCE_DEG:.2f}°E",
                ),
                (
                    TARGET_LONGITUDE_DEG + LONGITUDE_TOLERANCE_DEG,
                    f"MAX {TARGET_LONGITUDE_DEG + LONGITUDE_TOLERANCE_DEG:.2f}°E",
                ),
            ):
                axis.axhline(
                    value,
                    color="#EF4444",
                    linestyle="--",
                    linewidth=1.25,
                    label=label,
                )
            axis.set_title(
                "Absolute Earth-fixed longitude — full J2000 → ITRS",
                pad=10,
            )
            axis.set_xlabel("Elapsed time [days]")
            axis.set_ylabel("Longitude [deg E]")
            axis.margins(x=0.01)
            axis.legend(
                loc="upper left",
                facecolor="#0F172A",
                edgecolor="#334155",
                labelcolor="#E2E8F0",
            )
            self.manual_graph.figure.tight_layout(pad=1.2)
            self.manual_graph.draw_idle()
            return

        if chart_mode == "forces":
            axis = self._set_manual_single_axis()
            if self.last_prop_force_profile_cache is None:
                profile_count = min(len(elapsed_days), 1500)
                profile_indices = np.linspace(
                    0,
                    len(elapsed_days) - 1,
                    profile_count,
                    dtype=int,
                )
                profile_days = elapsed_days[profile_indices]
                profiles = {
                    source: []
                    for source, enabled in (
                        ("Moon", self.last_prop_include_moon),
                        ("Sun β", self.last_prop_include_sun),
                        ("SRP", self.last_prop_include_srp),
                        ("Combined", True),
                    )
                    if enabled
                }
                for sample_index in profile_indices:
                    state = values_matrix[sample_index]
                    sample_epoch = self.last_prop_epoch + timedelta(
                        seconds=float(times[sample_index])
                    )
                    et = utc_to_et(sample_epoch)
                    total = np.zeros(3, dtype=float)
                    if self.last_prop_include_moon:
                        moon_acceleration = moon_perturbation(
                            state[:3], get_moon_position(et)
                        )
                        profiles["Moon"].append(
                            float(np.linalg.norm(moon_acceleration))
                        )
                        total += moon_acceleration
                    if self.last_prop_include_sun:
                        sun_position = get_sun_position(et)
                        sun_acceleration = sun_perturbation(
                            state[:3], sun_position
                        )
                        profiles["Sun β"].append(
                            float(np.linalg.norm(sun_acceleration))
                        )
                        total += sun_acceleration
                    if self.last_prop_include_srp:
                        if not self.last_prop_include_sun:
                            sun_position = get_sun_position(et)
                        srp_acceleration = solar_radiation_pressure(
                            state[:3],
                            sun_position,
                            self.last_prop_srp_coefficient,
                            area_m2=self.last_prop_srp_area_m2,
                            mass_kg=self.last_prop_srp_mass_kg,
                        )
                        profiles["SRP"].append(
                            float(np.linalg.norm(srp_acceleration))
                        )
                        total += srp_acceleration
                    profiles["Combined"].append(float(np.linalg.norm(total)))
                self.last_prop_force_profile_cache = (
                    profile_days,
                    {
                        source: np.asarray(values, dtype=float)
                        for source, values in profiles.items()
                    },
                )
            profile_days, profiles = self.last_prop_force_profile_cache
            colors = {
                "Moon": "#A78BFA",
                "Sun β": "#FBBF24",
                "SRP": "#FB7185",
                "Combined": "#22D3EE",
            }
            for source, values in profiles.items():
                axis.plot(
                    profile_days,
                    values * 1.0e9,
                    color=colors[source],
                    linewidth=2.2 if source == "Combined" else 1.5,
                    label=source,
                )
            axis.set_title(
                "Perturbation accelerations along propagated trajectory",
                pad=10,
            )
            axis.set_xlabel("Elapsed time [days]")
            axis.set_ylabel("Acceleration [×10⁻⁹ km/s²]")
            axis.margins(x=0.01)
            axis.legend(
                loc="upper left",
                facecolor="#0F172A",
                edgecolor="#334155",
                labelcolor="#E2E8F0",
            )
            self.manual_graph.figure.tight_layout(pad=1.2)
            self.manual_graph.draw_idle()
            return

        if len(self.manual_graph.figure.axes) != 6:
            self.manual_graph.figure.clear()
            axes = tuple(
                self.manual_graph.figure.subplots(2, 3, sharex=True).ravel()
            )
        else:
            axes = tuple(self.manual_graph.figure.axes)
        self.manual_residual_axes = axes
        self.manual_graph.ax = axes[0]

        component_names = ("X", "Y", "Z", "Vx", "Vy", "Vz")
        units = ("km", "km", "km", "km/s", "km/s", "km/s")
        for component_index, axis in enumerate(axes):
            axis.clear()
            GraphWidget.style_axis(axis)
            axis.plot(
                display_days,
                display_matrix[:, component_index],
                color="#38BDF8",
                linewidth=1.25,
            )
            axis.set_title(
                f"{component_names[component_index]} state",
                pad=8,
                fontsize=10,
            )
            axis.set_ylabel(units[component_index])
            if component_index >= 3:
                axis.set_xlabel("Elapsed time [days]")
            axis.margins(x=0.01)

        self.manual_graph.figure.suptitle(
            "Numerically propagated J2000 state components",
            color="#F8FAFC",
            fontsize=12,
        )
        self.manual_graph.figure.tight_layout(
            rect=(0.0, 0.0, 1.0, 0.96),
            pad=1.2,
        )
        self.manual_graph.draw_idle()

    def manual_srp_configuration(self):
        """Resolve and validate the operator-entered effective-area SRP model."""
        mode = (
            "panel_body"
            if self.prop_manual_srp_separate_panels.isChecked()
            else "combined"
        )
        resolved = resolve_effective_area_srp_inputs(
            mode=mode,
            mass_kg=self.prop_manual_srp_mass.value(),
            total_area_m2=self.prop_manual_srp_total_area.value(),
            coefficient=self.prop_manual_srp_coefficient.value(),
            panel_area_m2=self.prop_manual_srp_panel_area.value(),
            panel_coefficient=self.prop_manual_srp_panel_coefficient.value(),
            body_area_m2=self.prop_manual_srp_body_area.value(),
            body_coefficient=self.prop_manual_srp_body_coefficient.value(),
        )
        mass_kg = resolved["mass_kg"]
        area_m2 = resolved["area_m2"]
        coefficient = resolved["coefficient"]
        force_scale_m2_per_kg = area_m2 * coefficient / mass_kg
        if mode == "combined":
            model_label = "Manual combined effective-area SRP"
            summary = (
                "Manual combined effective-area model · "
                f"area {area_m2:g} m² · mass {mass_kg:g} kg · "
                f"CP {coefficient:g} · A×CP/m {force_scale_m2_per_kg:.9g} "
                "m²/kg · Earth umbra/penumbra"
            )
        else:
            panel, body = resolved["components"]
            model_label = (
                "Manual panel/body SRP · "
                f"panel {panel['area_m2']:g} m² × CP "
                f"{panel['coefficient']:g} + body {body['area_m2']:g} m² × "
                f"CP {body['coefficient']:g}"
            )
            summary = (
                "Manual panel + body force sum · "
                f"panel {panel['area_m2']:g} m² × CP "
                f"{panel['coefficient']:g} · body {body['area_m2']:g} m² × "
                f"CP {body['coefficient']:g} · equivalent area {area_m2:g} m² · "
                f"equivalent CP {coefficient:.9g} · mass {mass_kg:g} kg · "
                f"A×CP/m {force_scale_m2_per_kg:.9g} m²/kg · "
                "Earth umbra/penumbra"
            )
        return {
            "model_id": PROPAGATION_SRP_MANUAL,
            "model_label": model_label,
            "adapter": {
                "srp_area_m2": area_m2,
                "srp_mass_kg": mass_kg,
            },
            "coefficient": coefficient,
            "mode": resolved["mode_label"],
            "demo_box_wing": False,
            "summary": summary,
        }

    def update_manual_srp_controls(self, _value=None):
        """Show the selected manual input layout and refresh its force summary."""

        panel_body = self.prop_manual_srp_separate_panels.isChecked()
        derived_body_area = max(
            0.0,
            self.prop_manual_srp_total_area.value()
            - self.prop_manual_srp_panel_area.value(),
        )
        self.prop_manual_srp_body_area.blockSignals(True)
        self.prop_manual_srp_body_area.setValue(derived_body_area)
        self.prop_manual_srp_body_area.blockSignals(False)
        for widget in (
            self.prop_manual_srp_coefficient_label,
            self.prop_manual_srp_coefficient,
        ):
            widget.setVisible(not panel_body)
        for widget in (
            self.prop_manual_srp_panel_area_label,
            self.prop_manual_srp_panel_area,
            self.prop_manual_srp_panel_coefficient_label,
            self.prop_manual_srp_panel_coefficient,
            self.prop_manual_srp_body_area_label,
            self.prop_manual_srp_body_area,
            self.prop_manual_srp_body_coefficient_label,
            self.prop_manual_srp_body_coefficient,
        ):
            widget.setVisible(panel_body)
        try:
            summary = self.manual_srp_configuration()["summary"]
        except ValueError as error:
            summary = f"Manual SRP input error: {error}"
        self.prop_manual_srp_summary.setText(self.tr(summary))

    def propagation_srp_model_changed(self, _index=None):
        """Activate SRP when the operator explicitly selects manual inputs."""

        if self.prop_srp_model.currentData() == PROPAGATION_SRP_MANUAL:
            self.prop_srp.setChecked(True)
        self.update_propagation_srp_model_details()

    def update_propagation_srp_model_details(self, _index=None):

        model_id = self.prop_srp_model.currentData()
        manual_selected = model_id == PROPAGATION_SRP_MANUAL
        if hasattr(self, "prop_manual_srp_box"):
            self.prop_manual_srp_box.setVisible(manual_selected)
        if hasattr(self, "propagation_settings_box"):
            self.propagation_settings_box.setMinimumHeight(
                680 if manual_selected else 390
            )

        if manual_selected:
            self.prop_srp.setText(
                "Include solar radiation pressure — Manual"
            )
            self.prop_srp_model_info.setText(
                "Manual effective-area SRP · combined CP or separate panel/body "
                "CP with automatically derived body area · Earth umbra/penumbra"
            )
        elif model_id == PROPAGATION_SRP_DEMO_EQUIVALENT:
            parameters = get_reference_dataset(
                DEMO_EARTH_MOON_SUN_SRP_DATASET_ID
            )["srp_parameters"]
            self.prop_srp.setText(
                "Include solar radiation pressure — SYNTHETIC GEO DEMO"
            )
            self.prop_srp_model_info.setText(
                "SYNTHETIC/DEMO fixed effective-area model · "
                f"area {parameters['area_m2']:g} m² · "
                f"mass {parameters['mass_kg']:g} kg · "
                f"CP {parameters['coefficient']:.12f} · "
                "Earth umbra/penumbra"
            )
        else:
            profile = self.active_profile
            self.prop_srp.setText(
                "Include solar radiation pressure — " + profile.display_name
            )
            if profile.is_demo_geo_baseline:
                details = (
                    "SYNTHETIC/DEMO physical box-wing model · "
                    f"mass {profile.mass_kg:g} kg · "
                    f"array area {profile.effective_srp_area_m2:g} m² · "
                    "nominal CP · Earth umbra/penumbra"
                )
            else:
                details = (
                    "Active profile effective-area model · "
                    f"area {profile.generic_srp_area_m2:g} m² · "
                    f"mass {profile.mass_kg:g} kg · "
                    f"CP {profile.srp_coefficient:g} · Earth umbra/penumbra"
                )
            self.prop_srp_model_info.setText(details)

        if hasattr(self, "localization_refresh_timer"):
            translate_widget_tree(
                self.propagation_settings_box,
                self.language,
                include_matplotlib=False,
            )

    def propagation_srp_configuration(self, epoch):
        """Resolve the explicitly selected spacecraft SRP model."""

        model_id = self.prop_srp_model.currentData()
        if model_id == PROPAGATION_SRP_MANUAL:
            return self.manual_srp_configuration()
        if model_id == PROPAGATION_SRP_DEMO_EQUIVALENT:
            parameters = get_reference_dataset(
                DEMO_EARTH_MOON_SUN_SRP_DATASET_ID
            )["srp_parameters"]
            return {
                "model_id": model_id,
                "model_label": "SYNTHETIC/DEMO fixed effective-area SRP",
                "adapter": {
                    "srp_area_m2": float(parameters["area_m2"]),
                    "srp_mass_kg": float(parameters["mass_kg"]),
                },
                "coefficient": float(parameters["coefficient"]),
                "mode": str(parameters["mode"]),
                "demo_box_wing": False,
            }

        if model_id != PROPAGATION_SRP_ACTIVE_PROFILE:
            raise ValueError("Unknown propagation SRP spacecraft model.")
        adapter, profile_coefficient = self.profile_srp_adapter()
        if profile_coefficient is None:
            coefficient, mode = resolved_solar_pressure_coefficient(epoch)
        else:
            coefficient = profile_coefficient
            mode = "SATELLITE PROFILE"
        return {
            "model_id": model_id,
            "model_label": self.active_profile.display_name,
            "adapter": adapter,
            "coefficient": coefficient,
            "mode": mode,
            "demo_box_wing": self.active_profile.is_demo_geo_baseline,
        }

    def run_manual_propagation(self):

        if (
            self.propagation_thread is not None
            and self.propagation_thread.isRunning()
        ):
            return
        if (
            self.reference_comparison_thread is not None
            and self.reference_comparison_thread.isRunning()
        ):
            self.prop_output.setPlainText(
                "PROPAGATION BUSY\n\n"
                "Wait for reference validation to finish or cancel it."
            )
            return

        self.last_prop_times = None
        self.last_prop_states = None
        self.last_prop_epoch = None
        self.last_prop_force_profile_cache = None
        self.propagation_kepler_widget.clear()
        self.save_csv_button.setEnabled(
            False
        )
        self.update_manual_propagation_chart()

        try:
            epoch = self.parse_propagation_epoch(
                self.prop_epoch.text()
            )
            # Make the actual UTC instant explicit before propagation. This
            # prevents a manually entered non-UTC offset from appearing to
            # change only after the first output row is produced.
            self.prop_epoch.setText(epoch.isoformat())
            initial_state = np.asarray(
                [
                    float(self.prop_x.text()),
                    float(self.prop_y.text()),
                    float(self.prop_z.text()),
                    float(self.prop_vx.text()),
                    float(self.prop_vy.text()),
                    float(self.prop_vz.text()),
                ],
                dtype=float,
            )
            days = float(
                self.prop_days.text()
            )
            if days <= 0.0:
                raise ValueError(
                    "Duration must be greater than zero."
                )

            step_minutes = int(
                self.step_minutes.value()
            )
            step_seconds = int(
                self.step_seconds.value()
            )
            output_step = float(
                step_minutes * 60
                + step_seconds
            )
            if output_step <= 0.0:
                raise ValueError(
                    "Step interval must be at least 1 second."
                )

            duration_seconds = float(
                days * 86400.0
            )
            estimated_steps = int(
                np.floor(
                    duration_seconds / output_step
                )
            ) + 2
            if estimated_steps > 100000:
                raise ValueError(
                    f"Requested output has about {estimated_steps:,} "
                    "rows. Maximum allowed: 100,000."
                )

            settings = self.get_numerical_settings()
            include_j2 = self.prop_j2.isChecked()
            earth_harmonic_degree = (
                int(self.prop_egm_degree.currentData())
                if self.prop_egm_degree is not None
                else 4
            )
            include_moon = self.prop_moon.isChecked()
            include_sun = self.prop_sun.isChecked()
            include_srp = self.prop_srp.isChecked()
            srp_model_id = (
                self.prop_srp_model.currentData()
                or PROPAGATION_SRP_ACTIVE_PROFILE
            )
            if include_srp:
                srp_configuration = self.propagation_srp_configuration(epoch)
                srp_adapter = srp_configuration["adapter"]
                srp_coefficient = srp_configuration["coefficient"]
                srp_mode = srp_configuration["mode"]
                srp_model_label = srp_configuration["model_label"]
                demo_box_wing = srp_configuration[
                    "demo_box_wing"
                ]
            else:
                srp_adapter = {}
                srp_coefficient = None
                srp_mode = None
                srp_model_label = self.prop_srp_model.currentText()
                demo_box_wing = False

            parameters = {
                "initial_state": initial_state,
                "initial_epoch": epoch,
                "duration_seconds": duration_seconds,
                "output_step": output_step,
                "include_j2": include_j2,
                "earth_harmonic_degree": earth_harmonic_degree,
                "include_moon": include_moon,
                "include_sun": include_sun,
                "include_srp": include_srp,
                "srp_coefficient": srp_coefficient,
                **srp_adapter,
                **settings,
            }
            self._pending_prop_config = {
                "epoch": epoch,
                "initial_state": initial_state.copy(),
                "days": days,
                "step_minutes": step_minutes,
                "step_seconds": step_seconds,
                "include_j2": include_j2,
                "earth_harmonic_degree": earth_harmonic_degree,
                "include_moon": include_moon,
                "include_sun": include_sun,
                "include_srp": include_srp,
                "srp_model_id": srp_model_id,
                "srp_model_label": srp_model_label,
                "srp_coefficient": srp_coefficient,
                "srp_mode": srp_mode,
                "srp_area_m2": srp_adapter.get("srp_area_m2"),
                "srp_mass_kg": srp_adapter.get("srp_mass_kg"),
                "profile_name": self.active_profile.display_name,
                "demo_box_wing": demo_box_wing,
                "eop_status": get_eop_status(),
                "settings": settings,
            }

            self.prop_output.setPlainText(
                "BACKGROUND PROPAGATION STARTED\n\n"
                f"Duration: {days:.6f} days\n"
                f"Output rows: approximately {estimated_steps:,}\n"
                "The interface remains available."
            )
            self.propagate_button.setEnabled(
                False
            )
            self.cancel_propagation_button.setEnabled(
                True
            )
            self.propagation_progress.setValue(
                0
            )
            self.propagation_progress.setFormat(
                "%p%"
            )

            # SPICE uses a process-wide kernel pool. Pause the one-second
            # live sampler while the worker uses SPICE to avoid concurrent
            # kernel access, while keeping the Qt interface responsive.
            self._prop_timer_was_active = self.timer.isActive()
            if self._prop_timer_was_active:
                self.timer.stop()

            self.propagation_thread = QThread(
                self
            )
            self.propagation_worker = PropagationWorker(
                parameters
            )
            self.propagation_worker.moveToThread(
                self.propagation_thread
            )
            self.propagation_thread.started.connect(
                self.propagation_worker.run
            )
            self.propagation_worker.progress.connect(
                self.propagation_progress.setValue
            )
            self.propagation_worker.completed.connect(
                self.finish_manual_propagation
            )
            self.propagation_worker.failed.connect(
                self.fail_manual_propagation
            )
            self.propagation_worker.cancelled.connect(
                self.cancelled_manual_propagation
            )
            self.propagation_worker.completed.connect(
                self.propagation_thread.quit
            )
            self.propagation_worker.failed.connect(
                self.propagation_thread.quit
            )
            self.propagation_worker.cancelled.connect(
                self.propagation_thread.quit
            )
            self.propagation_thread.finished.connect(
                self.propagation_worker.deleteLater
            )
            self.propagation_thread.finished.connect(
                self.propagation_thread.deleteLater
            )
            self.propagation_thread.finished.connect(
                self.cleanup_manual_propagation
            )
            self.propagation_thread.start()

        except Exception as error:
            self.prop_output.setPlainText(
                "PROPAGATION INPUT ERROR\n\n"
                f"{type(error).__name__}: {error}"
            )


    def cancel_manual_propagation(self):

        if (
            self.propagation_thread is None
            or not self.propagation_thread.isRunning()
        ):
            return

        self.propagation_thread.requestInterruption()
        self.cancel_propagation_button.setEnabled(
            False
        )
        self.propagation_progress.setFormat(
            "Cancelling..."
        )


    def finish_manual_propagation(self, times, states):

        config = self._pending_prop_config
        times = np.asarray(
            times,
            dtype=float,
        )
        states = np.asarray(
            states,
            dtype=float,
        )

        self.last_prop_times = times
        self.last_prop_states = states
        self.last_prop_epoch = config["epoch"]
        self.last_prop_include_j2 = config["include_j2"]
        self.last_prop_earth_harmonic_degree = config["earth_harmonic_degree"]
        self.last_prop_include_moon = config["include_moon"]
        self.last_prop_include_sun = config["include_sun"]
        self.last_prop_include_srp = config["include_srp"]
        self.last_prop_srp_coefficient = config["srp_coefficient"]
        self.last_prop_srp_mode = config["srp_mode"]
        self.last_prop_srp_area_m2 = config["srp_area_m2"]
        self.last_prop_srp_mass_kg = config["srp_mass_kg"]
        self.last_prop_step_minutes = config["step_minutes"]
        self.last_prop_step_seconds = config["step_seconds"]
        self.last_prop_run_number += 1
        self.save_csv_button.setEnabled(
            True
        )
        self.update_manual_propagation_chart()

        final_state = states[-1]
        final_position = final_state[:3]
        final_velocity = final_state[3:]
        final_epoch = config["epoch"] + timedelta(
            seconds=float(times[-1])
        )
        self.propagation_kepler_widget.update_trajectory(
            states,
            times,
            config["epoch"],
            frame_label="J2000 (matches input and CSV export)",
            rotate_to_tod_fk5=False,
        )

        lines = [
            "PROPAGATION COMPLETED",
            "=" * 88,
            f"Initial epoch : {config['epoch'].isoformat()}",
            f"Final epoch   : {final_epoch.isoformat()}",
            f"Duration      : {config['days']:.9f} days",
            f"Output rows   : {len(times):,}",
            f"Earth EGM96 {config['earth_harmonic_degree']}×"
            f"{config['earth_harmonic_degree']}: "
            f"{'ON' if config['include_j2'] else 'OFF'}",
            f"Moon          : {'ON' if config['include_moon'] else 'OFF'}",
            f"Sun gravity   : {'ON' if config['include_sun'] else 'OFF'}",
            (
                (
                    f"Solar pressure: ON — SYNTHETIC/DEMO box-wing / mass {self.active_profile.mass_kg:g} kg / "
                    f"CP {config['srp_coefficient']:.7f} / {config['srp_mode']}"
                    if config["demo_box_wing"]
                    else f"Solar pressure: ON — {config['srp_model_label']} / "
                    f"mass {config['srp_mass_kg']:.3f} kg / "
                    f"area {config['srp_area_m2']:.3f} m² / "
                    f"CP {config['srp_coefficient']:.7f}"
                )
                if config["include_srp"]
                else "Solar pressure: OFF"
            ),
            f"RTOL / ATOL   : {config['settings']['rtol']:.3e} / "
            f"{config['settings']['atol']:.3e}",
            f"Maximum step  : {config['settings']['max_step']:.3f} s",
            (
                "IERS EOP     : ON · DUT1 + xp/yp"
                if config["eop_status"]["enabled"]
                else "IERS EOP     : OFF"
            ),
            "",
            "STEP | UTC | X [km] | Y [km] | Z [km] | "
            "Vx [km/s] | Vy [km/s] | Vz [km/s]",
            "-" * 150,
        ]

        preview_limit = 5000
        if len(times) <= preview_limit:
            display_indices = list(
                range(len(times))
            )
            omitted_at = None
        else:
            half = preview_limit // 2
            display_indices = list(range(half)) + list(
                range(len(times) - half, len(times))
            )
            omitted_at = half

        for display_number, index in enumerate(display_indices):
            if omitted_at is not None and display_number == omitted_at:
                omitted = len(times) - preview_limit
                lines.append(
                    f"... {omitted:,} intermediate rows omitted from "
                    "the UI preview; SAVE CSV retains all rows ..."
                )

            elapsed_seconds = times[index]
            state = states[index]
            state_epoch = config["epoch"] + timedelta(
                seconds=float(elapsed_seconds)
            )
            x, y, z, vx, vy, vz = state
            lines.append(
                f"{index:05d} | {state_epoch.isoformat()} | "
                f"{x:.9f} | {y:.9f} | {z:.9f} | "
                f"{vx:.12f} | {vy:.12f} | {vz:.12f}"
            )

        lines.extend(
            [
                "",
                "FINAL STATE",
                f"Position [km] : {final_position}",
                f"Velocity [km/s]: {final_velocity}",
                f"Radius [km]   : {np.linalg.norm(final_position):.9f}",
                f"Speed [km/s]  : {np.linalg.norm(final_velocity):.12f}",
            ]
        )

        self.prop_output.setPlainText(
            "\n".join(lines)
        )
        self.propagation_progress.setValue(
            100
        )
        self.propagation_progress.setFormat(
            "Completed"
        )
        self.propagate_button.setEnabled(
            True
        )
        self.cancel_propagation_button.setEnabled(
            False
        )


    def fail_manual_propagation(self, message):

        self.propagation_kepler_widget.clear()
        self.prop_output.setPlainText(
            "PROPAGATION ERROR\n\n"
            + message
        )
        self.propagation_progress.setFormat(
            "Failed"
        )
        self.propagate_button.setEnabled(
            True
        )
        self.cancel_propagation_button.setEnabled(
            False
        )


    def cancelled_manual_propagation(self):

        self.propagation_kepler_widget.clear()
        self.prop_output.setPlainText(
            "PROPAGATION CANCELLED\n\n"
            "No partial trajectory was stored or exported."
        )
        self.propagation_progress.setFormat(
            "Cancelled"
        )
        self.propagate_button.setEnabled(
            True
        )
        self.cancel_propagation_button.setEnabled(
            False
        )


    def cleanup_manual_propagation(self):

        self.propagation_worker = None
        self.propagation_thread = None

        if getattr(
            self,
            "_prop_timer_was_active",
            False,
        ):
            self.timer.start(
                1000
            )
        self._prop_timer_was_active = False


    def closeEvent(self, event):

        if not self.prepare_product_close():
            event.ignore()
            return

        application = QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)

        self.stop_live_logging()

        if (
            self.propagation_thread is not None
            and self.propagation_thread.isRunning()
        ):
            self.propagation_thread.requestInterruption()
            self.propagation_thread.quit()
            self.propagation_thread.wait(
                3000
            )

        if (
            self.graph_prediction_thread is not None
            and self.graph_prediction_thread.isRunning()
        ):
            self.graph_prediction_thread.requestInterruption()
            self.graph_prediction_thread.quit()
            self.graph_prediction_thread.wait(3000)

        if self.eclipse_thread is not None and self.eclipse_thread.isRunning():
            self.eclipse_thread.requestInterruption()
            self.eclipse_thread.quit()
            self.eclipse_thread.wait(3000)

        if (
            self.sun_outage_thread is not None
            and self.sun_outage_thread.isRunning()
        ):
            self.sun_outage_thread.requestInterruption()
            self.sun_outage_thread.quit()
            self.sun_outage_thread.wait(3000)

        if (
            self.reference_comparison_thread is not None
            and self.reference_comparison_thread.isRunning()
        ):
            self.reference_comparison_thread.requestInterruption()
            self.reference_comparison_thread.quit()
            self.reference_comparison_thread.wait(
                3000
            )

        if (
            self.orbit_determination_thread is not None
            and self.orbit_determination_thread.isRunning()
        ):
            self.orbit_determination_thread.requestInterruption()
            self.orbit_determination_thread.quit()
            self.orbit_determination_thread.wait(3000)

        if (
            self.tle_update_thread is not None
            and self.tle_update_thread.isRunning()
        ):
            self.tle_update_thread.requestInterruption()
            self.tle_update_thread.quit()
            self.tle_update_thread.wait(
                3000
            )

        self.logout_admin_session()

        super().closeEvent(
            event
        )


    def refresh_application(self):
        """Request a clean one-click restart without manual close/reopen."""

        active_jobs = (
            ("Propagation", self.propagation_thread),
            ("Perturbation prediction", self.graph_prediction_thread),
            ("Eclipse", self.eclipse_thread),
            ("Sun Outage", self.sun_outage_thread),
            ("Reference Lab", self.reference_comparison_thread),
            ("Orbit Determination", self.orbit_determination_thread),
            ("TLE update", self.tle_update_thread),
        )
        running_jobs = [
            label
            for label, thread in active_jobs
            if thread is not None and thread.isRunning()
        ]
        if running_jobs:
            self.statusBar().showMessage(
                "REFRESH is waiting: stop the active calculation first — "
                + ", ".join(running_jobs),
                10000,
            )
            return False

        self.statusBar().showMessage(
            "The application is restarting with the new configuration...",
            3000,
        )
        refresh_button = getattr(self, "refresh_app_button", None)
        if refresh_button is not None:
            refresh_button.setEnabled(False)
        QTimer.singleShot(
            0,
            lambda: QApplication.exit(RESTART_APPLICATION_EXIT_CODE),
        )
        return True


    # ========================================================
    # UPDATE DATA
    # ========================================================

    def clear_active_spacecraft_history(self):
        """Clear samples so graphs never mix two spacecraft profiles."""

        self.history_time.clear()
        for source_histories in self.force_histories.values():
            for history in source_histories.values():
                history.clear()
        self.satellite_position_history.clear()
        self.moon_position_history.clear()
        self.current_satellite_position = None
        self.current_satellite_altitude_km = None
        self._system_live_cache_key = None
        self.graph_prediction_epoch = None
        self.graph_prediction_times = None
        self.graph_prediction_values = None
        self.graph_prediction_uncertainty = None

    def update_data(self):
        try:
            utc = self.get_analysis_utc()
            active_state, state_epoch = self.active_spacecraft_state(utc)
            self.current_system_epoch = state_epoch
            et = utc_to_et(state_epoch)

            r_sat = np.asarray(active_state[:3], dtype=float)
            satellite_altitude_km = wgs84_geodetic_altitude_km(r_sat)
            r_moon = get_moon_position(et)
            r_sun = get_sun_position(et)
            live_state = np.asarray(active_state, dtype=float)

            self.current_satellite_position = np.asarray(
                r_sat, dtype=float
            ).copy()
            self.current_satellite_altitude_km = float(satellite_altitude_km)
            self.current_moon_position = np.asarray(
                r_moon, dtype=float
            ).copy()
            self.current_sun_position = np.asarray(
                r_sun, dtype=float
            ).copy()

            new_sample = (
                not self.history_time or self.history_time[-1] != state_epoch
            )
            if new_sample:
                self.satellite_position_history.append(
                    self.current_satellite_position
                )
                self.moon_position_history.append(self.current_moon_position)

            a_moon = moon_perturbation(r_sat, r_moon)
            a_sun = sun_perturbation(r_sat, r_sun)
            if self.active_profile.is_demo_geo_baseline:
                srp_coefficient, srp_mode = resolved_solar_pressure_coefficient(
                    state_epoch
                )
                srp_kwargs = {}
            else:
                propagator_srp_kwargs, srp_coefficient = self.profile_srp_adapter()
                srp_kwargs = {
                    "area_m2": propagator_srp_kwargs["srp_area_m2"],
                    "mass_kg": propagator_srp_kwargs["srp_mass_kg"],
                }
                srp_mode = "ACTIVE PROFILE"
            a_srp = solar_radiation_pressure(
                r_sat,
                r_sun,
                srp_coefficient,
                **srp_kwargs,
            )
            srp_illumination = sunlight_fraction(r_sat, r_sun)
            a_total = a_moon + a_sun + a_srp

            displayed_acceleration = np.zeros(3, dtype=float)
            active_sources = []
            if self.live_force_moon.isChecked():
                displayed_acceleration += a_moon
                active_sources.append("MOON")
            if self.live_force_sun.isChecked():
                displayed_acceleration += a_sun
                active_sources.append("SUN")
            if self.live_force_srp.isChecked():
                displayed_acceleration += a_srp
                active_sources.append("SRP")
            displayed_magnitude = float(np.linalg.norm(displayed_acceleration))

            self.log_live_sample(
                state_epoch,
                r_sat,
                r_moon,
                r_sun,
                a_moon,
                a_sun,
                a_srp,
                a_total,
                float(np.linalg.norm(a_total)),
                srp_coefficient,
                srp_illumination,
                srp_mode,
            )

            self.sat_x.setText(f"{r_sat[0]:.3f} km")
            self.sat_y.setText(f"{r_sat[1]:.3f} km")
            self.sat_z.setText(f"{r_sat[2]:.3f} km")
            self.sat_distance.setText(f"{np.linalg.norm(r_sat):.3f} km")

            self.moon_x.setText(f"{r_moon[0]:.3f} km")
            self.moon_y.setText(f"{r_moon[1]:.3f} km")
            self.moon_z.setText(f"{r_moon[2]:.3f} km")
            self.moon_distance.setText(f"{np.linalg.norm(r_moon):.3f} km")
            self.sun_x.setText(f"{r_sun[0]:.3f} km")
            self.sun_y.setText(f"{r_sun[1]:.3f} km")
            self.sun_z.setText(f"{r_sun[2]:.3f} km")
            self.sun_distance.setText(f"{np.linalg.norm(r_sun):.3f} km")

            self.ax_value.setText(
                f"{displayed_acceleration[0]:.4e} km/s²"
            )
            self.ay_value.setText(
                f"{displayed_acceleration[1]:.4e} km/s²"
            )
            self.az_value.setText(
                f"{displayed_acceleration[2]:.4e} km/s²"
            )
            self.magnitude_value.setText(f"{displayed_magnitude:.4e} km/s²")
            self.live_moon_magnitude.setText(
                f"{np.linalg.norm(a_moon):.4e} km/s²"
            )
            self.live_sun_magnitude.setText(
                f"{np.linalg.norm(a_sun):.4e} km/s²"
            )
            self.live_srp_magnitude.setText(
                f"{np.linalg.norm(a_srp):.4e} km/s²"
            )
            self.live_srp_illumination.setText(
                f"{srp_illumination:.4f}  ·  CP {srp_coefficient:.4f}  "
                f"{srp_mode}"
            )
            self.live_force_mode.setText(
                " + ".join(active_sources) if active_sources else "NONE"
            )
            self.utc_status.setText(
                (
                    "PROFILE EPOCH: "
                    if self.active_profile.orbit_source in {"cartesian", "ephemeris"}
                    else (
                        "FIXED UTC: "
                        if self.analysis_fixed_epoch is not None
                        else "UTC: "
                    )
                )
                + str(state_epoch)
            )
            if hasattr(self, "hero_utc"):
                self.hero_utc.setText(
                    "UTC  " + state_epoch.astimezone(timezone.utc).strftime(
                        "%Y-%m-%d  %H:%M:%S"
                    )
                )
            if hasattr(self, "hero_status"):
                self.hero_status.setText("LIVE UPDATE  ·  1 s")
                self.hero_status.setProperty("state", "nominal")
                self.hero_status.style().unpolish(self.hero_status)
                self.hero_status.style().polish(self.hero_status)

            source_vectors = {
                "Moon": a_moon,
                "Sun β": a_sun,
                "SRP": a_srp,
                "Combined": a_total,
            }
            source_values = {}
            for source, vector in source_vectors.items():
                source_values[source] = acceleration_components(
                    vector,
                    live_state,
                )

            if new_sample:
                self.history_time.append(state_epoch)
                for source, values in source_values.items():
                    for parameter, value in values.items():
                        self.force_histories[source][parameter].append(value)
            else:
                for source, values in source_values.items():
                    for parameter, value in values.items():
                        self.force_histories[source][parameter][-1] = value

            cutoff = state_epoch - timedelta(hours=24)
            all_histories = tuple(
                history
                for source_histories in self.force_histories.values()
                for history in source_histories.values()
            )
            while self.history_time and self.history_time[0] < cutoff:
                self.history_time.popleft()
                for history in all_histories:
                    history.popleft()

            self.safe_update_graph()
            self.safe_update_system_view()

        except Exception as error:
            print("UPDATE ERROR:", error)
            self.utc_status.setText(f"ERROR: {error}")
            if hasattr(self, "hero_status"):
                self.hero_status.setText("UPDATE DEGRADED")
                self.hero_status.setProperty("state", "error")
                self.hero_status.style().unpolish(self.hero_status)
                self.hero_status.style().polish(self.hero_status)


    # ========================================================
    # UPDATE GRAPH
    # ========================================================

    def _update_graph_legacy(self):

        if len(
            self.history_time
        ) < 2:

            return

        # ------------------------------------------------
        # TIME RANGE
        # ------------------------------------------------

        selected_range = (
            self.time_range.currentText()
        )

        if selected_range == "1 Hour":

            hours = 1

        elif selected_range == "6 Hours":

            hours = 6

        else:

            hours = 24

        cutoff = (
            datetime.now(
                timezone.utc
            )
            - timedelta(
                hours=hours
            )
        )

        # ------------------------------------------------
        # PARAMETER SELECTION
        # ------------------------------------------------

        parameter = (
            self.parameter.currentText()
        )

        parameter_map = {
            "Magnitude": self.history_magnitude,
            "ax": self.history_ax,
            "ay": self.history_ay,
            "az": self.history_az,
        }

        selected_series = parameter_map.get(
            parameter,
            self.history_magnitude,
        )

        filtered_points = []

        for index, timestamp in enumerate(
            self.history_time
        ):

            if timestamp < cutoff:
                continue

            filtered_points.append(
                (
                    timestamp,
                    float(
                        selected_series[index]
                    ),
                )
            )

        if len(filtered_points) < 2:
            return

        filtered_points.sort(
            key=lambda item: item[0]
        )

        times = [
            item[0]
            for item in filtered_points
        ]

        values = np.asarray(
            [
                item[1]
                for item in filtered_points
            ],
            dtype=float,
        )

        # ------------------------------------------------
        # PROFESSIONAL SCALING
        # ------------------------------------------------
        # The perturbation values are very small (~1e-9 km/s^2).
        # Plot them in x10^-9 units so the graph is immediately
        # readable and visually meaningful.
        scaled_values = values * 1.0e9

        is_signed_component = (
            parameter in ("ax", "ay", "az")
        )

        # ------------------------------------------------
        # DRAW
        # ------------------------------------------------

        self.graph.ax.clear()
        self.graph.figure.patch.set_facecolor(
            "#0B1220"
        )
        self.graph.style_axes()

        line_color = (
            "#22D3EE"
            if parameter == "Magnitude"
            else "#60A5FA"
        )

        fill_color = (
            "#0891B2"
            if parameter == "Magnitude"
            else "#1D4ED8"
        )

        marker_style = (
            "o"
            if len(times) <= 40
            else None
        )

        self.graph.ax.plot(
            times,
            scaled_values,
            linewidth=2.6,
            color=line_color,
            marker=marker_style,
            markersize=4.0,
            markerfacecolor="#F8FAFC",
            markeredgewidth=0.0,
            solid_capstyle="round",
            label=parameter,
            zorder=3,
        )

        self.graph.ax.scatter(
            [times[-1]],
            [scaled_values[-1]],
            s=46,
            color="#F8FAFC",
            edgecolors=line_color,
            linewidths=1.5,
            zorder=5,
            label="Latest point",
        )

        if parameter == "Magnitude":
            self.graph.ax.fill_between(
                times,
                scaled_values,
                np.min(scaled_values),
                color=fill_color,
                alpha=0.10,
                zorder=1,
            )

        if is_signed_component:
            self.graph.ax.axhline(
                0.0,
                color="#94A3B8",
                linewidth=1.0,
                linestyle="--",
                alpha=0.8,
                zorder=2,
            )

        # ------------------------------------------------
        # TITLES / LABELS
        # ------------------------------------------------

        if parameter == "Magnitude":
            title = "Moon Perturbation Magnitude"
        else:
            title = f"Moon Perturbation Component — {parameter}"

        self.graph.ax.set_title(
            title,
            fontsize=15,
            fontweight="bold",
            pad=12,
        )

        self.graph.ax.set_xlabel(
            "UTC Time",
            fontsize=11,
            labelpad=10,
        )

        self.graph.ax.set_ylabel(
            "Acceleration (×10⁻⁹ km/s²)",
            fontsize=11,
            labelpad=12,
        )

        # ------------------------------------------------
        # X-AXIS FORMATTING
        # ------------------------------------------------

        locator = mdates.AutoDateLocator(
            minticks=5,
            maxticks=8,
        )

        formatter = mdates.ConciseDateFormatter(
            locator
        )

        self.graph.ax.xaxis.set_major_locator(
            locator
        )

        self.graph.ax.xaxis.set_major_formatter(
            formatter
        )

        for label in self.graph.ax.get_xticklabels():
            label.set_rotation(25)
            label.set_horizontalalignment(
                "right"
            )

        # ------------------------------------------------
        # Y-AXIS LIMITS / FORMAT
        # ------------------------------------------------

        y_min = float(
            np.min(scaled_values)
        )

        y_max = float(
            np.max(scaled_values)
        )

        if np.isclose(
            y_min,
            y_max,
        ):
            padding = max(
                abs(y_min) * 0.05,
                0.01,
            )

        else:
            padding = max(
                (y_max - y_min) * 0.15,
                0.01,
            )

        self.graph.ax.set_ylim(
            y_min - padding,
            y_max + padding,
        )

        self.graph.ax.yaxis.set_major_formatter(
            mticker.FormatStrFormatter(
                "%.3f"
            )
        )

        # ------------------------------------------------
        # LEGEND
        # ------------------------------------------------

        legend = self.graph.ax.legend(
            loc="upper left",
            frameon=True,
            fontsize=9,
            facecolor="#0F172A",
            edgecolor="#334155",
        )

        for text in legend.get_texts():
            text.set_color(
                "#E2E8F0"
            )

        # ------------------------------------------------
        # STATISTICS PANEL
        # ------------------------------------------------

        current_value = float(
            scaled_values[-1]
        )

        min_value = float(
            np.min(scaled_values)
        )

        max_value = float(
            np.max(scaled_values)
        )

        mean_value = float(
            np.mean(scaled_values)
        )

        stats_text = (
            f"Current: {current_value:.6f}\n"
            f"Min: {min_value:.6f}\n"
            f"Max: {max_value:.6f}\n"
            f"Mean: {mean_value:.6f}"
        )

        self.graph.ax.text(
            0.985,
            0.975,
            stats_text,
            transform=self.graph.ax.transAxes,
            fontsize=9,
            verticalalignment="top",
            horizontalalignment="right",
            color="#E2E8F0",
            bbox=dict(
                boxstyle="round,pad=0.45",
                facecolor="#08111F",
                edgecolor="#334155",
                alpha=0.92,
            ),
        )

        self.graph.figure.tight_layout(
            pad=1.2
        )

        self.graph.draw()


    # ========================================================
    # UPDATE FIXED LIVE GRAPH
    # ========================================================

    def update_graph(self):
        if len(self.history_time) < 1:
            return
        if self.tabs.currentWidget() is not self.graph_page:
            return

        selected_range = self.time_range.currentText()
        hours = {"1 Hour": 1, "6 Hours": 6, "24 Hours": 24}.get(
            selected_range, 24
        )
        # Anchor the x-axis to the active spacecraft state's epoch.  Private
        # and imported profiles may not use wall-clock UTC; using wall-clock
        # here displaced live markers from their matching prediction sample.
        now = self.current_system_epoch or self.get_analysis_utc()
        cutoff = now - timedelta(hours=hours)
        parameter = self.parameter.currentText()

        source_histories = self.force_histories
        enabled_sources = [
            name
            for name, checkbox in (
                ("Moon", self.graph_force_moon),
                ("Sun β", self.graph_force_sun),
                ("SRP", self.graph_force_srp),
                ("Combined", self.graph_force_total),
            )
            if checkbox.isChecked()
        ]
        if not enabled_sources:
            return

        filtered_indices = [
            index
            for index, timestamp in enumerate(self.history_time)
            if timestamp >= cutoff
        ]
        if len(filtered_indices) < 1:
            return
        times = [self.history_time[index] for index in filtered_indices]
        scaled_by_source = {
            source: np.asarray(
                [
                    source_histories[source][parameter][index]
                    for index in filtered_indices
                ],
                dtype=float,
            )
            * 1.0e9
            for source in enabled_sources
        }
        unavailable_sources = [
            source
            for source, values in scaled_by_source.items()
            if not np.any(np.isfinite(values))
        ]
        enabled_sources = [
            source
            for source in enabled_sources
            if source not in unavailable_sources
        ]
        scaled_by_source = {
            source: scaled_by_source[source]
            for source in enabled_sources
        }
        if not enabled_sources:
            return

        max_display_points = 2000
        display_indices = (
            np.linspace(0, len(times) - 1, max_display_points, dtype=int)
            if len(times) > max_display_points
            else np.arange(len(times), dtype=int)
        )
        display_times = [times[index] for index in display_indices]
        display_by_source = {
            source: values[display_indices]
            for source, values in scaled_by_source.items()
        }

        if hours == 1:
            time_divisor, x_width, x_step = 60.0, 60.0, 10.0
            x_label, x_suffix = "Time (minutes, 0 = now)", "m"
        else:
            time_divisor, x_width = 3600.0, float(hours)
            x_step = 1.0 if hours == 6 else 4.0
            x_label, x_suffix = "Time (hours, 0 = now)", "h"
        relative_times = np.asarray(
            [
                (timestamp - now).total_seconds() / time_divisor
                for timestamp in display_times
            ],
            dtype=float,
        )

        prediction_relative_times = np.asarray([], dtype=float)
        prediction_scaled_by_source = {}
        prediction_uncertainty_by_source = {}
        if (
            self.graph_prediction_times is not None
            and self.graph_prediction_values is not None
        ):
            prediction_relative_times = np.asarray(
                [
                    (timestamp - now).total_seconds() / time_divisor
                    for timestamp in self.graph_prediction_times
                ],
                dtype=float,
            )
            for source in enabled_sources:
                source_values = self.graph_prediction_values.get(source, {})
                if parameter not in source_values:
                    continue
                prediction_scaled_by_source[source] = np.asarray(
                    source_values[parameter], dtype=float
                ) * 1.0e9
                source_uncertainty = (
                    self.graph_prediction_uncertainty or {}
                ).get(source, {})
                if parameter in source_uncertainty:
                    prediction_uncertainty_by_source[source] = np.asarray(
                        source_uncertainty[parameter], dtype=float
                    ) * 1.0e9

        colors = {
            "Moon": "#A78BFA",
            "Sun β": "#FBBF24",
            "SRP": "#FB7185",
            "Combined": "#22D3EE",
        }
        primary_source = (
            "Combined" if "Combined" in enabled_sources else enabled_sources[0]
        )
        primary_values = scaled_by_source[primary_source]
        prediction_primary_values = prediction_scaled_by_source.get(
            primary_source, np.asarray([], dtype=float)
        )
        prediction_primary_uncertainty = (
            prediction_uncertainty_by_source.get(
                primary_source, np.asarray([], dtype=float)
            )
        )
        stats_lines = [
            f"{source}: {scaled_by_source[source][-1]:.6f}"
            for source in enabled_sources
        ]
        stats_lines.extend(
            (
                f"{primary_source} min: {np.nanmin(primary_values):.6f}",
                f"{primary_source} max: {np.nanmax(primary_values):.6f}",
            )
        )
        if unavailable_sources:
            stats_lines.append(
                "N/A: " + ", ".join(unavailable_sources)
            )
        stats_text = "\n".join(stats_lines)

        graph_signature = (
            selected_range,
            parameter,
            tuple(enabled_sources),
            tuple(sorted(prediction_scaled_by_source)),
        )
        if getattr(self, "_graph_signature", None) != graph_signature:
            self.graph.ax.clear()
            self.graph.figure.patch.set_facecolor("#0B1220")
            self.graph.style_axes()
            title_suffix = (
                "Magnitude" if parameter == "Magnitude" else f"Component — {parameter}"
            )
            self.graph.ax.set_title(
                f"Perturbation Force Profile {title_suffix}",
                fontsize=15,
                fontweight="bold",
                pad=12,
            )
            self.graph.ax.set_xlabel(x_label, fontsize=11, labelpad=10)
            self.graph.ax.set_ylabel(
                "Acceleration (×10⁻⁹ km/s²)", fontsize=11, labelpad=12
            )
            self._graph_x_width = x_width
            half_width = x_width * 0.5
            self.graph.ax.set_xlim(
                -half_width + self.graph_view_offset,
                half_width + self.graph_view_offset,
            )
            self.graph.ax.xaxis.set_major_locator(mticker.MultipleLocator(x_step))

            def format_relative_time(value, _position):
                return "Now" if np.isclose(value, 0.0) else f"{value:+g}{x_suffix}"

            self.graph.ax.xaxis.set_major_formatter(
                mticker.FuncFormatter(format_relative_time)
            )

            scale_parts = [
                values[np.isfinite(values)]
                for values in scaled_by_source.values()
                if np.any(np.isfinite(values))
            ]
            scale_parts.extend(
                values[np.isfinite(values)]
                for values in prediction_scaled_by_source.values()
                if np.any(np.isfinite(values))
            )
            if (
                prediction_primary_values.size
                and prediction_primary_uncertainty.size
            ):
                scale_parts.extend(
                    (
                        prediction_primary_values
                        - prediction_primary_uncertainty,
                        prediction_primary_values
                        + prediction_primary_uncertainty,
                    )
                )
            scale_source = np.concatenate(scale_parts)
            scale_peak = float(np.max(np.abs(scale_source)))
            fixed_limit = max(1.0e-9, scale_peak * 1.18)
            if parameter != "Magnitude":
                self.graph.ax.set_ylim(-fixed_limit, fixed_limit)
                self.graph.ax.axhline(
                    0.0,
                    color="#94A3B8",
                    linewidth=1.0,
                    linestyle="--",
                    alpha=0.8,
                    zorder=2,
                )
            else:
                self.graph.ax.set_ylim(0.0, fixed_limit)
            self.graph.ax.axvline(
                0.0,
                color="#E2E8F0",
                linewidth=1.0,
                linestyle=":",
                alpha=0.55,
                zorder=2,
            )
            self.graph.ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))

            self._graph_lines = {}
            for source in enabled_sources:
                line, = self.graph.ax.plot(
                    [],
                    [],
                    linewidth=2.8 if source == "Combined" else 2.0,
                    color=colors[source],
                    alpha=1.0 if source == "Combined" else 0.86,
                    solid_capstyle="round",
                    label=f"Live {source}",
                    zorder=4 if source == "Combined" else 3,
                )
                self._graph_lines[source] = line
            self._graph_prediction_lines = {}
            for source in enabled_sources:
                if source not in prediction_scaled_by_source:
                    continue
                prediction_line, = self.graph.ax.plot(
                    [],
                    [],
                    linewidth=2.0,
                    color=colors[source],
                    alpha=0.58,
                    linestyle="--",
                    label=f"Predicted {source}",
                    zorder=3,
                )
                self._graph_prediction_lines[source] = prediction_line
            self._graph_uncertainty_band = None
            if (
                prediction_primary_values.size
                and prediction_primary_uncertainty.size
            ):
                self._graph_uncertainty_band = self.graph.ax.fill_between(
                    [],
                    [],
                    [],
                    color=colors[primary_source],
                    alpha=0.10,
                    label=f"{primary_source} numerical sensitivity",
                    zorder=2,
                )
            self._graph_latest = self.graph.ax.scatter(
                [],
                [],
                s=46,
                color="#F8FAFC",
                edgecolors=colors[primary_source],
                linewidths=1.5,
                zorder=5,
                label=f"Latest {primary_source}",
            )
            legend = self.graph.ax.legend(
                loc="upper left",
                frameon=True,
                fontsize=8,
                ncol=2,
                labelspacing=0.35,
                columnspacing=0.9,
                handlelength=2.2,
                handletextpad=0.5,
                facecolor="#0F172A",
                edgecolor="#334155",
            )
            for legend_text in legend.get_texts():
                legend_text.set_color("#E2E8F0")
            self._graph_stats = self.graph.ax.text(
                0.985,
                0.975,
                "",
                transform=self.graph.ax.transAxes,
                fontsize=9,
                verticalalignment="top",
                horizontalalignment="right",
                color="#E2E8F0",
                bbox={
                    "boxstyle": "round,pad=0.45",
                    "facecolor": "#08111F",
                    "edgecolor": "#334155",
                    "alpha": 0.92,
                },
            )
            self.graph.figure.tight_layout(pad=1.2)
            self._graph_signature = graph_signature

        marker_style = "o" if len(display_times) <= 40 else ""
        for source, line in self._graph_lines.items():
            line.set_data(relative_times, display_by_source[source])
            line.set_marker(marker_style)
        for source, line in self._graph_prediction_lines.items():
            source_prediction = prediction_scaled_by_source.get(
                source, np.asarray([], dtype=float)
            )
            line.set_data(
                (
                    prediction_relative_times
                    if source_prediction.size
                    else np.asarray([], dtype=float)
                ),
                source_prediction,
            )
        if (
            prediction_relative_times.size
            and prediction_primary_values.size
            and prediction_primary_uncertainty.size
        ):
            lower_band = (
                prediction_primary_values - prediction_primary_uncertainty
            )
            upper_band = (
                prediction_primary_values + prediction_primary_uncertainty
            )
            band_vertices = np.concatenate(
                (
                    np.column_stack((prediction_relative_times, upper_band)),
                    np.column_stack(
                        (prediction_relative_times[::-1], lower_band[::-1])
                    ),
                )
            )
            if self._graph_uncertainty_band is not None:
                self._graph_uncertainty_band.set_verts([band_vertices])
        elif self._graph_uncertainty_band is not None:
            self._graph_uncertainty_band.set_verts([])
        primary_display = display_by_source[primary_source]
        finite_latest = np.flatnonzero(np.isfinite(primary_display))
        if finite_latest.size:
            latest_index = int(finite_latest[-1])
            self._graph_latest.set_offsets(
                np.asarray(
                    [[relative_times[latest_index], primary_display[latest_index]]]
                )
            )
        else:
            self._graph_latest.set_offsets(np.empty((0, 2), dtype=float))
        self._graph_stats.set_text(stats_text)
        self.graph.draw_idle()

# ============================================================
# MAIN
# ============================================================

def main():

    runtime_diagnostic_path = install_runtime_diagnostics(APPLICATION_DATA_DIR)

    # Windows uses the process AppUserModelID to group taskbar buttons and
    # select their icon. Set it before QApplication creates any native
    # windows so the bundled application icon is used consistently.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                WINDOWS_APP_USER_MODEL_ID
            )
        except (AttributeError, OSError):
            # Window-level QIcon remains the fallback on older/non-standard
            # Windows environments.
            pass

    app = QApplication(
        sys.argv
    )

    app.setApplicationName("Orbital Perturbation Analyzer")
    app.setApplicationDisplayName(
        "Orbital Perturbation Analyzer"
    )
    app.setOrganizationName("OPA")

    app.setStyle(
        "Fusion"
    )
    app.lastWindowClosed.connect(
        lambda: record_runtime_event("LAST WINDOW CLOSED")
    )
    app.aboutToQuit.connect(
        lambda: record_runtime_event("APPLICATION ABOUT TO QUIT")
    )

    app_icon = QIcon()
    if os.path.isfile(APP_ICON_PATH):
        app_icon = QIcon(APP_ICON_PATH)
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)

    window = MainWindow()
    window.runtime_diagnostic_path = runtime_diagnostic_path

    window.show()

    def refresh_taskbar_icon():
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)
            window.setWindowIcon(app_icon)
        apply_windows_taskbar_icon(window, APP_ICON_PATH)

    # Windows creates and groups the native taskbar button asynchronously.
    # Re-assert both Qt and HWND icons after show so neither Explorer timing
    # nor the Python launcher can leave the taskbar button iconless.
    for delay_ms in WINDOWS_ICON_REFRESH_DELAYS_MS:
        QTimer.singleShot(delay_ms, refresh_taskbar_icon)

    exit_code = app.exec()
    record_runtime_event(f"EVENT LOOP EXIT CODE {exit_code}")
    if exit_code == RESTART_APPLICATION_EXIT_CODE:
        if getattr(sys, "frozen", False):
            restart_program = sys.executable
            restart_arguments = list(sys.argv[1:])
        else:
            restart_program = sys.executable
            restart_arguments = [
                os.path.abspath(sys.argv[0]),
                *sys.argv[1:],
            ]
        started = QProcess.startDetached(
            restart_program,
            restart_arguments,
            PROJECT_DIR,
        )
        restart_succeeded = (
            bool(started[0]) if isinstance(started, tuple) else bool(started)
        )
        sys.exit(0 if restart_succeeded else 1)
    sys.exit(exit_code)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
