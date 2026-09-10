"""Versioned satellite profiles for the desktop product layer.

Profiles describe user inputs only and never replace propagation formulas.
Public built-ins are explicitly synthetic, non-operational examples.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from gordam import GordamImportError, load_gordam_solution

import constants


PROFILE_SCHEMA_VERSION = 3
BUILTIN_DEMO_GEO_ID = "synthetic_geo_demo"
BUILTIN_DEMO_ID = BUILTIN_DEMO_GEO_ID


class ProfileValidationError(ValueError):
    """Raised when profile content is incomplete or physically invalid."""


def default_profile_directory() -> Path:
    override = os.environ.get("OPA_PROFILE_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "OrbitalPerturbationAnalyzer" / "profiles"
    return Path.home() / ".opa" / "profiles"


def _finite_number(value: Any, name: str, *, minimum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ProfileValidationError(f"{name} must be numeric.") from error
    if not math.isfinite(number):
        raise ProfileValidationError(f"{name} must be finite.")
    if minimum is not None and number < minimum:
        raise ProfileValidationError(f"{name} must be at least {minimum}.")
    return number


def _optional_positive(value: Any, name: str) -> float | None:
    if value in (None, ""):
        return None
    number = _finite_number(value, name, minimum=0.0)
    if number <= 0.0:
        raise ProfileValidationError(f"{name} must be greater than zero.")
    return number


def _boolean(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ProfileValidationError(f"{name} must be true or false.")


def _normalise_epoch(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        epoch = datetime.fromisoformat(text)
    except ValueError as error:
        raise ProfileValidationError("Profile epoch must be ISO-8601.") from error
    if epoch.tzinfo is None:
        raise ProfileValidationError("Profile epoch must include a UTC offset.")
    return epoch.astimezone(timezone.utc).isoformat()


def _normalise_state(value: Any) -> tuple[float, ...] | None:
    if value in (None, ""):
        return None
    try:
        values = tuple(float(component) for component in value)
    except (TypeError, ValueError) as error:
        raise ProfileValidationError(
            "J2000 state must contain six numeric values."
        ) from error
    if len(values) != 6 or not all(math.isfinite(component) for component in values):
        raise ProfileValidationError(
            "J2000 state must contain six finite values."
        )
    if math.sqrt(sum(component * component for component in values[:3])) <= 0.0:
        raise ProfileValidationError("J2000 position magnitude must be positive.")
    return values


def _profile_id(value: Any) -> str:
    identifier = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").strip().lower())
    identifier = identifier.strip("-_")
    if not identifier:
        identifier = f"profile-{uuid4().hex[:10]}"
    return identifier[:64]


@dataclass(frozen=True)
class SatelliteProfile:
    profile_id: str
    display_name: str
    operator: str = ""
    notes: str = ""
    built_in: bool = False
    orbit_source: str = "tle"
    tle_name: str = ""
    norad_id: int | None = None
    epoch_utc: str | None = None
    state_j2000: tuple[float, ...] | None = None
    reference_frame: str = "J2000"
    source_description: str = ""
    mass_kg: float = 1000.0
    effective_area_m2: float | None = None
    dry_mass_kg: float | None = None
    propellant_mass_kg: float | None = None
    body_x_m: float = 1.0
    body_y_m: float = 1.0
    body_z_m: float = 1.0
    body_specular: float = 0.0
    body_diffuse: float = 0.0
    body_absorption: float = 1.0
    solar_array_count: int = 0
    solar_array_width_m: float = 0.0
    solar_array_height_m: float = 0.0
    solar_array_tracking_mode: str = "TrueSun"
    solar_array_specular: float = 0.0
    solar_array_diffuse: float = 0.0
    solar_array_absorption: float = 1.0
    srp_coefficient: float = 1.0
    thruster_isp_s: float | None = None
    earth_gravity_enabled: bool = True
    include_j2: bool = True
    egm96_degree: int = 4
    egm96_order: int = 4
    include_moon: bool = True
    include_sun: bool = True
    include_srp: bool = False
    eop_enabled: bool = False
    target_longitude_deg: float = 12.0
    station_box_half_width_deg: float = 0.1
    inclination_warning_deg: float = 0.08
    inclination_limit_deg: float = 0.1
    eccentricity_warning: float = 0.0007
    eccentricity_limit: float = 0.001
    annual_delta_v_budget_m_s: float | None = None
    schema_version: int = PROFILE_SCHEMA_VERSION

    @property
    def effective_srp_area_m2(self) -> float:
        return (
            float(self.solar_array_count)
            * self.solar_array_width_m
            * self.solar_array_height_m
        )

    @property
    def generic_srp_area_m2(self) -> float:
        """Supported equivalent area for the existing generic SRP adapter."""

        if self.effective_area_m2 is not None:
            return float(self.effective_area_m2)
        array_area = self.effective_srp_area_m2
        if array_area > 0.0:
            return array_area
        return max(
            self.body_x_m * self.body_y_m,
            self.body_x_m * self.body_z_m,
            self.body_y_m * self.body_z_m,
        )

    @property
    def is_demo_geo_baseline(self) -> bool:
        return self.profile_id == BUILTIN_DEMO_GEO_ID and self.built_in

    @property
    def parsed_epoch(self) -> datetime | None:
        if self.epoch_utc is None:
            return None
        return datetime.fromisoformat(self.epoch_utc).astimezone(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.state_j2000 is not None:
            payload["state_j2000"] = list(self.state_j2000)
        return payload

    def editable_copy(self, *, name: str | None = None) -> "SatelliteProfile":
        return replace(
            self,
            profile_id=f"profile-{uuid4().hex[:10]}",
            display_name=name or f"{self.display_name} Copy",
            built_in=False,
        )


def validate_profile(payload: Mapping[str, Any] | SatelliteProfile) -> SatelliteProfile:
    source = payload.to_dict() if isinstance(payload, SatelliteProfile) else dict(payload)
    version = int(source.get("schema_version", PROFILE_SCHEMA_VERSION))
    if version not in {1, 2, PROFILE_SCHEMA_VERSION}:
        raise ProfileValidationError(
            f"Unsupported satellite-profile schema version: {version}."
        )
    name = str(source.get("display_name", "")).strip()
    if not name:
        raise ProfileValidationError("Profile display name is required.")
    orbit_source = str(source.get("orbit_source", "tle")).strip().lower()
    if orbit_source not in {"tle", "cartesian", "ephemeris"}:
        raise ProfileValidationError(
            "Orbit source must be TLE, manual Cartesian or imported ephemeris."
        )
    tle_name = str(source.get("tle_name", "")).strip()
    raw_norad = source.get("norad_id")
    norad_id = None if raw_norad in (None, "", 0, "0") else int(raw_norad)
    if norad_id is not None and norad_id <= 0:
        raise ProfileValidationError("NORAD ID must be positive.")
    epoch_utc = _normalise_epoch(source.get("epoch_utc"))
    state = _normalise_state(source.get("state_j2000"))
    if orbit_source == "tle" and not (tle_name or norad_id):
        raise ProfileValidationError("A TLE profile needs a name or NORAD ID.")
    if orbit_source in {"cartesian", "ephemeris"} and (
        epoch_utc is None or state is None
    ):
        raise ProfileValidationError(
            "A Cartesian/ephemeris profile needs a timezone-aware epoch and "
            "six-state vector."
        )
    reference_frame = str(source.get("reference_frame", "J2000")).strip().upper()
    if reference_frame not in {"J2000", "ICRF"}:
        raise ProfileValidationError(
            "Only J2000/ICRF ephemeris states are supported by the current backend."
        )
    reference_frame = "J2000"
    source_description = str(source.get("source_description", "")).strip()
    if orbit_source == "ephemeris" and not source_description:
        raise ProfileValidationError(
            "An imported ephemeris state requires a source/provenance description."
        )

    mass = _finite_number(source.get("mass_kg", 1000.0), "Mass", minimum=0.0)
    if mass <= 0.0:
        raise ProfileValidationError("Mass must be greater than zero.")
    effective_area = _optional_positive(
        source.get("effective_area_m2"),
        "Effective area",
    )
    dry_mass = _optional_positive(source.get("dry_mass_kg"), "Dry mass")
    propellant = _optional_positive(
        source.get("propellant_mass_kg"), "Propellant mass"
    )
    if dry_mass is not None and dry_mass > mass:
        raise ProfileValidationError("Dry mass cannot exceed total mass.")
    if propellant is not None and propellant > mass:
        raise ProfileValidationError("Propellant mass cannot exceed total mass.")
    if dry_mass is not None and propellant is not None and dry_mass + propellant > mass:
        raise ProfileValidationError(
            "Dry mass plus propellant mass cannot exceed total mass."
        )

    optical_groups = (
        ("body_specular", "body_diffuse", "body_absorption", "Body"),
        (
            "solar_array_specular",
            "solar_array_diffuse",
            "solar_array_absorption",
            "Solar-array",
        ),
    )
    optical: dict[str, float] = {}
    for specular_key, diffuse_key, absorption_key, label in optical_groups:
        values = tuple(
            _finite_number(source.get(key, 0.0), key.replace("_", " "), minimum=0.0)
            for key in (specular_key, diffuse_key, absorption_key)
        )
        if any(value > 1.0 for value in values):
            raise ProfileValidationError(f"{label} optical shares cannot exceed 1.")
        if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1.0e-6):
            raise ProfileValidationError(
                f"{label} specular + diffuse + absorption must equal 1."
            )
        optical.update(zip((specular_key, diffuse_key, absorption_key), values))

    array_count = int(source.get("solar_array_count", 0))
    if array_count < 0:
        raise ProfileValidationError("Solar-array count cannot be negative.")
    dimensions = {
        key: _finite_number(source.get(key, default), key.replace("_", " "), minimum=0.0)
        for key, default in (
            ("body_x_m", 1.0),
            ("body_y_m", 1.0),
            ("body_z_m", 1.0),
            ("solar_array_width_m", 0.0),
            ("solar_array_height_m", 0.0),
        )
    }
    if any(dimensions[key] <= 0.0 for key in ("body_x_m", "body_y_m", "body_z_m")):
        raise ProfileValidationError("Body dimensions must be greater than zero.")
    if array_count and (
        dimensions["solar_array_width_m"] <= 0.0
        or dimensions["solar_array_height_m"] <= 0.0
    ):
        raise ProfileValidationError("Solar-array dimensions must be positive.")

    box = _finite_number(
        source.get("station_box_half_width_deg", 0.1),
        "Station-box half-width",
        minimum=0.0,
    )
    if box <= 0.0 or box > 180.0:
        raise ProfileValidationError("Station-box half-width must be in (0, 180].")
    inc_warning = _finite_number(
        source.get("inclination_warning_deg", 0.08), "Inclination warning", minimum=0.0
    )
    inc_limit = _finite_number(
        source.get("inclination_limit_deg", 0.1), "Inclination limit", minimum=0.0
    )
    ecc_warning = _finite_number(
        source.get("eccentricity_warning", 0.0007), "Eccentricity warning", minimum=0.0
    )
    ecc_limit = _finite_number(
        source.get("eccentricity_limit", 0.001), "Eccentricity limit", minimum=0.0
    )
    if inc_warning > inc_limit or ecc_warning > ecc_limit:
        raise ProfileValidationError("Warning thresholds cannot exceed limits.")

    tracking_mode = (
        str(source.get("solar_array_tracking_mode", "TrueSun")).strip()
        or "TrueSun"
    )
    if tracking_mode not in {"TrueSun", "EquivalentSunNormalArea"}:
        raise ProfileValidationError(
            "Solar-array mode must be TrueSun or EquivalentSunNormalArea; "
            "body-fixed attitude is not supported without attitude data."
        )

    earth_gravity_enabled = _boolean(
        source.get("earth_gravity_enabled", True), "Earth gravity enabled"
    )
    if not earth_gravity_enabled:
        raise ProfileValidationError(
            "Earth central gravity is mandatory for the existing propagator."
        )
    try:
        egm96_degree = int(source.get("egm96_degree", 4))
        egm96_order = int(source.get("egm96_order", egm96_degree))
    except (TypeError, ValueError) as error:
        raise ProfileValidationError("EGM96 degree/order must be integers.") from error
    if egm96_degree not in {2, 3, 4} or egm96_order != egm96_degree:
        raise ProfileValidationError(
            "The existing propagator supports coupled EGM96 2×2, 3×3 or 4×4."
        )

    return SatelliteProfile(
        profile_id=_profile_id(source.get("profile_id")),
        display_name=name,
        operator=str(source.get("operator", "")).strip(),
        notes=str(source.get("notes", "")).strip(),
        built_in=_boolean(source.get("built_in", False), "Built-in status"),
        orbit_source=orbit_source,
        tle_name=tle_name,
        norad_id=norad_id,
        epoch_utc=epoch_utc,
        state_j2000=state,
        reference_frame=reference_frame,
        source_description=source_description,
        mass_kg=mass,
        effective_area_m2=effective_area,
        dry_mass_kg=dry_mass,
        propellant_mass_kg=propellant,
        body_x_m=dimensions["body_x_m"],
        body_y_m=dimensions["body_y_m"],
        body_z_m=dimensions["body_z_m"],
        body_specular=optical["body_specular"],
        body_diffuse=optical["body_diffuse"],
        body_absorption=optical["body_absorption"],
        solar_array_count=array_count,
        solar_array_width_m=dimensions["solar_array_width_m"],
        solar_array_height_m=dimensions["solar_array_height_m"],
        solar_array_tracking_mode=tracking_mode,
        solar_array_specular=optical["solar_array_specular"],
        solar_array_diffuse=optical["solar_array_diffuse"],
        solar_array_absorption=optical["solar_array_absorption"],
        srp_coefficient=_finite_number(
            source.get("srp_coefficient", 1.0), "SRP coefficient", minimum=1.0e-12
        ),
        thruster_isp_s=_optional_positive(source.get("thruster_isp_s"), "Thruster Isp"),
        earth_gravity_enabled=True,
        include_j2=_boolean(source.get("include_j2", True), "EGM96 enabled"),
        egm96_degree=egm96_degree,
        egm96_order=egm96_order,
        include_moon=_boolean(source.get("include_moon", True), "Moon enabled"),
        include_sun=_boolean(source.get("include_sun", True), "Sun enabled"),
        include_srp=_boolean(source.get("include_srp", False), "SRP enabled"),
        eop_enabled=_boolean(source.get("eop_enabled", False), "EOP enabled"),
        target_longitude_deg=_finite_number(
            source.get("target_longitude_deg", 12.0), "Target longitude"
        ),
        station_box_half_width_deg=box,
        inclination_warning_deg=inc_warning,
        inclination_limit_deg=inc_limit,
        eccentricity_warning=ecc_warning,
        eccentricity_limit=ecc_limit,
        annual_delta_v_budget_m_s=_optional_positive(
            source.get("annual_delta_v_budget_m_s"), "Annual delta-v budget"
        ),
        schema_version=PROFILE_SCHEMA_VERSION,
    )


def load_ephemeris_state_file(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load one explicit J2000 state from a human-readable JSON document.

    The import is intentionally strict: an epoch, reference frame and six-state
    vector must be named in the file.  This prevents an unlabeled TOD/ECEF CSV
    row from being silently treated as J2000 telemetry.
    """

    source_path = Path(path)
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProfileValidationError(
            f"Could not read ephemeris-state JSON: {error}"
        ) from error
    if not isinstance(payload, Mapping):
        raise ProfileValidationError("Ephemeris-state JSON root must be an object.")
    epoch = _normalise_epoch(payload.get("epoch_utc") or payload.get("epoch"))
    state = _normalise_state(
        payload.get("state_j2000") or payload.get("state")
    )
    frame = str(payload.get("reference_frame") or "").strip().upper()
    if epoch is None or state is None:
        raise ProfileValidationError(
            "Ephemeris-state JSON requires epoch_utc and six state_j2000 values."
        )
    if frame not in {"J2000", "ICRF"}:
        raise ProfileValidationError(
            "Imported ephemeris reference_frame must be J2000 or ICRF."
        )
    description = str(
        payload.get("source_description")
        or payload.get("provenance")
        or f"Imported from {source_path.name}"
    ).strip()
    return {
        "epoch_utc": epoch,
        "state_j2000": state,
        "reference_frame": "J2000",
        "source_description": description,
    }


def load_gordam_state_file(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load one audited GORDAM OD state without inventing a nominal slot."""

    try:
        solution = load_gordam_solution(path)
    except GordamImportError as error:
        raise ProfileValidationError(str(error)) from error
    provenance = (
        f"GORDAM OD solution imported from {solution.source_name}; "
        f"solution epoch {solution.epoch_utc.isoformat()}; "
        f"reported longitude {solution.longitude_deg:.6f} deg E."
    )
    return {
        "display_name": solution.satellite,
        "epoch_utc": solution.epoch_utc.isoformat(),
        "state_j2000": solution.state_j2000,
        "reference_frame": "J2000",
        "source_description": provenance,
        "mass_kg": solution.mass_kg,
        "target_longitude_deg": solution.longitude_deg,
        "cp_scale_factor": solution.cp_scale_factor,
    }


def _builtin_profiles() -> Mapping[str, SatelliteProfile]:
    synthetic_geo = validate_profile(
        {
            "profile_id": BUILTIN_DEMO_GEO_ID,
            "display_name": "SYNTHETIC GEO DEMO",
            "operator": "Public demonstration",
            "notes": "Fictional non-operational geostationary training profile.",
            "built_in": True,
            "orbit_source": "cartesian",
            "epoch_utc": "2030-01-01T00:00:00+00:00",
            "state_j2000": [41200.0, 9000.0, 50.0, -0.656, 3.004, 0.001],
            "source_description": (
                "SYNTHETIC/DEMO state generated for public software testing; "
                "not derived from a real spacecraft."
            ),
            "mass_kg": constants.DEMO_SPACECRAFT_MASS_KG,
            "body_x_m": constants.DEMO_SPACECRAFT_BODY_X_M,
            "body_y_m": constants.DEMO_SPACECRAFT_BODY_Y_M,
            "body_z_m": constants.DEMO_SPACECRAFT_BODY_Z_M,
            "body_specular": constants.DEMO_SPACECRAFT_BODY_SPECULAR,
            "body_diffuse": constants.DEMO_SPACECRAFT_BODY_DIFFUSE,
            "body_absorption": constants.DEMO_SPACECRAFT_BODY_ABSORPTION,
            "solar_array_count": constants.DEMO_SPACECRAFT_SOLAR_ARRAY_COUNT,
            "solar_array_width_m": constants.DEMO_SPACECRAFT_SOLAR_ARRAY_WIDTH_M,
            "solar_array_height_m": constants.DEMO_SPACECRAFT_SOLAR_ARRAY_HEIGHT_M,
            "solar_array_tracking_mode": constants.DEMO_SPACECRAFT_SOLAR_ARRAY_TRACKING_MODE,
            "solar_array_specular": constants.DEMO_SPACECRAFT_SOLAR_ARRAY_SPECULAR,
            "solar_array_diffuse": constants.DEMO_SPACECRAFT_SOLAR_ARRAY_DIFFUSE,
            "solar_array_absorption": constants.DEMO_SPACECRAFT_SOLAR_ARRAY_ABSORPTION,
            "srp_coefficient": 1.15,
            "include_j2": True,
            "earth_gravity_enabled": True,
            "egm96_degree": 4,
            "egm96_order": 4,
            "include_moon": True,
            "include_sun": True,
            "include_srp": False,
            "eop_enabled": False,
            "target_longitude_deg": 12.0,
            "station_box_half_width_deg": 0.2,
            "inclination_warning_deg": 0.10,
            "inclination_limit_deg": 0.15,
            "eccentricity_warning": 0.001,
            "eccentricity_limit": 0.002,
            "annual_delta_v_budget_m_s": 45.0,
        }
    )
    return MappingProxyType(
        {synthetic_geo.profile_id: synthetic_geo}
    )


BUILTIN_PROFILES = _builtin_profiles()


def new_basic_profile_template() -> SatelliteProfile:
    """Return a valid basic spacecraft with no propulsion data required."""

    return validate_profile(
        {
            "profile_id": f"profile-{uuid4().hex[:10]}",
            "display_name": "New Spacecraft",
            "built_in": False,
            "orbit_source": "cartesian",
            "epoch_utc": "2030-01-01T00:00:00+00:00",
            "state_j2000": [42164.0, 0.0, 0.0, 0.0, 3.07466, 0.0],
            "source_description": "User-created generic J2000 spacecraft profile.",
            "mass_kg": 1000.0,
            "effective_area_m2": 20.0,
            "body_x_m": 1.0,
            "body_y_m": 1.0,
            "body_z_m": 1.0,
            "body_specular": 0.0,
            "body_diffuse": 0.0,
            "body_absorption": 1.0,
            "solar_array_count": 0,
            "solar_array_width_m": 0.0,
            "solar_array_height_m": 0.0,
            "solar_array_specular": 0.0,
            "solar_array_diffuse": 0.0,
            "solar_array_absorption": 1.0,
            "srp_coefficient": 1.0,
            "earth_gravity_enabled": True,
            "include_j2": True,
            "egm96_degree": 4,
            "egm96_order": 4,
            "include_moon": True,
            "include_sun": True,
            "include_srp": False,
            "eop_enabled": False,
        }
    )


class SatelliteProfileStore:
    """Load immutable built-ins plus validated per-user JSON profiles."""

    def __init__(self, directory: str | os.PathLike[str] | None = None):
        self.directory = Path(directory) if directory is not None else default_profile_directory()
        self._profiles: dict[str, SatelliteProfile] = {}
        self._session_profiles: dict[str, SatelliteProfile] = {}
        self.reload()

    def reload(self) -> None:
        profiles = dict(BUILTIN_PROFILES)
        if self.directory.is_dir():
            for path in sorted(self.directory.glob("*.json")):
                try:
                    profile = validate_profile(json.loads(path.read_text(encoding="utf-8")))
                except (
                    OSError,
                    json.JSONDecodeError,
                    ProfileValidationError,
                    TypeError,
                    ValueError,
                ):
                    continue
                if not profile.built_in and profile.profile_id not in BUILTIN_PROFILES:
                    profiles[profile.profile_id] = profile
        profiles.update(self._session_profiles)
        self._profiles = profiles

    def set_session_profiles(
        self, profiles: tuple[SatelliteProfile, ...] | list[SatelliteProfile]
    ) -> None:
        """Install validated volatile profiles without writing them to disk."""

        session_profiles: dict[str, SatelliteProfile] = {}
        for profile in profiles:
            validated = validate_profile(profile)
            if validated.profile_id in BUILTIN_PROFILES:
                raise ProfileValidationError(
                    "Session profiles cannot replace public built-ins."
                )
            session_profiles[validated.profile_id] = validated
        self._session_profiles = session_profiles
        self.reload()

    def clear_session_profiles(self) -> None:
        self._session_profiles.clear()
        self.reload()

    def is_session_profile(self, profile_id: str) -> bool:
        return str(profile_id) in self._session_profiles

    def all(self) -> tuple[SatelliteProfile, ...]:
        return tuple(self._profiles.values())

    def get(self, profile_id: str) -> SatelliteProfile:
        try:
            return self._profiles[str(profile_id)]
        except KeyError as error:
            raise ProfileValidationError(f"Unknown satellite profile: {profile_id}") from error

    def save(self, profile: SatelliteProfile | Mapping[str, Any]) -> SatelliteProfile:
        validated = validate_profile(profile)
        if (
            validated.built_in
            or validated.profile_id in BUILTIN_PROFILES
            or validated.profile_id in self._session_profiles
        ):
            raise ProfileValidationError("Built-in profiles cannot be overwritten.")
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{validated.profile_id}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(validated.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
        self._profiles[validated.profile_id] = validated
        return validated

    def delete(self, profile_id: str) -> None:
        profile = self.get(profile_id)
        if profile.built_in or self.is_session_profile(profile.profile_id):
            raise ProfileValidationError("Built-in profiles cannot be deleted.")
        path = self.directory / f"{profile.profile_id}.json"
        if path.exists():
            path.unlink()
        self._profiles.pop(profile.profile_id, None)

    def import_file(self, path: str | os.PathLike[str]) -> SatelliteProfile:
        source = Path(path)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ProfileValidationError(f"Could not read profile: {error}") from error
        if not isinstance(payload, dict):
            raise ProfileValidationError("Imported profile root must be a JSON object.")
        payload["built_in"] = False
        if _profile_id(payload.get("profile_id")) in BUILTIN_PROFILES:
            payload["profile_id"] = f"profile-{uuid4().hex[:10]}"
        return self.save(payload)

    def export_file(self, profile_id: str, path: str | os.PathLike[str]) -> Path:
        profile = self.get(profile_id)
        destination = Path(path)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(
            json.dumps(profile.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
        return destination
