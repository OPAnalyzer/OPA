"""Device-bound, signed and encrypted local admin extension packages.

Public mode needs no enrollment or package.  Admin content is data-only JSON:
no Python modules, archive extraction, paths, commands, or executable objects
are accepted.  Package signatures are verified before DPAPI or decryption is
attempted.
"""

from __future__ import annotations

from base64 import b64decode, b64encode
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import sys
import time
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_public_key,
)

from application_config import default_application_config_path
from satellite_profiles import SatelliteProfile, validate_profile


PACKAGE_SCHEMA = "opa-admin-package/v1"
SHARED_PACKAGE_DEVICE_ID = "shared-team-access"
CONTENT_SCHEMA = "opa-admin-content/v2"
ENROLLMENT_SCHEMA = "opa-admin-enrollment/v1"
PACKAGE_VERSION = 1
SHARED_PACKAGE_VERSION = 2
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
MAX_PROFILES = 64
MAX_REFERENCE_DATASETS = 32
MAX_ECLIPSE_REFERENCE_DATASETS = 32
MAX_ORBIT_DETERMINATION_DATASETS = 8
MAX_ADMIN_MODULES = 16
KDF_TIME_COST = 3
KDF_MEMORY_COST_KIB = 64 * 1024
KDF_PARALLELISM = 2
KDF_SALT_BYTES = 16
NONCE_BYTES = 12
DEVICE_SECRET_BYTES = 32


class AdminSecurityError(RuntimeError):
    """Safe user-facing failure that never embeds secrets or private paths."""


class DeviceProtector(Protocol):
    def protect(self, data: bytes) -> bytes: ...
    def unprotect(self, data: bytes) -> bytes: ...


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class WindowsDpapiProtector:
    """Bind a device secret to the current Windows user through DPAPI."""

    _description = "Orbital Perturbation Analyzer admin enrollment"
    _entropy = b"OPA.AdminEnrollment.v1"
    _ui_forbidden = 0x01

    @staticmethod
    def _blob(data: bytes) -> tuple[_DataBlob, Any]:
        buffer = ctypes.create_string_buffer(data, len(data))
        blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        return blob, buffer

    def protect(self, data: bytes) -> bytes:
        if sys.platform != "win32":
            raise AdminSecurityError("Device enrollment requires Windows DPAPI.")
        input_blob, input_buffer = self._blob(bytes(data))
        entropy_blob, entropy_buffer = self._blob(self._entropy)
        output_blob = _DataBlob()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        result = crypt32.CryptProtectData(
            ctypes.byref(input_blob),
            self._description,
            ctypes.byref(entropy_blob),
            None,
            None,
            self._ui_forbidden,
            ctypes.byref(output_blob),
        )
        del input_buffer, entropy_buffer
        if not result:
            raise AdminSecurityError("Windows could not protect the device enrollment.")
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            kernel32.LocalFree(output_blob.pbData)

    def unprotect(self, data: bytes) -> bytes:
        if sys.platform != "win32":
            raise AdminSecurityError("Device enrollment requires Windows DPAPI.")
        input_blob, input_buffer = self._blob(bytes(data))
        entropy_blob, entropy_buffer = self._blob(self._entropy)
        output_blob = _DataBlob()
        description = wintypes.LPWSTR()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        result = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob),
            ctypes.byref(description),
            ctypes.byref(entropy_blob),
            None,
            None,
            self._ui_forbidden,
            ctypes.byref(output_blob),
        )
        del input_buffer, entropy_buffer
        if not result:
            raise AdminSecurityError("This Windows user/device is not enrolled.")
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            if description:
                kernel32.LocalFree(description)
            kernel32.LocalFree(output_blob.pbData)


@dataclass(frozen=True)
class AdminModuleDescriptor:
    module_id: str
    label: str
    description: str


@dataclass(frozen=True)
class AdminContent:
    profiles: tuple[SatelliteProfile, ...]
    reference_datasets: tuple[dict[str, Any], ...]
    eclipse_reference_datasets: tuple[dict[str, Any], ...]
    orbit_determination_datasets: tuple[dict[str, Any], ...]
    admin_modules: tuple[AdminModuleDescriptor, ...]


@dataclass(frozen=True)
class Enrollment:
    device_id: str
    key_id: str
    verification_key: bytes
    protected_device_secret: bytes


def _b64encode(value: bytes) -> str:
    return b64encode(value).decode("ascii")


def _b64decode(value: Any, label: str, expected_length: int | None = None) -> bytes:
    if not isinstance(value, str) or len(value) > 64 * 1024 * 1024:
        raise AdminSecurityError(f"Invalid {label}.")
    try:
        decoded = b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as error:
        raise AdminSecurityError(f"Invalid {label}.") from error
    if expected_length is not None and len(decoded) != expected_length:
        raise AdminSecurityError(f"Invalid {label}.")
    return decoded


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _reject_duplicate_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AdminSecurityError("Package contains duplicate JSON keys.")
        result[key] = value
    return result


def _load_json_bytes(data: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(
            data.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs
        )
    except AdminSecurityError:
        raise
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise AdminSecurityError("Admin package is not valid JSON.") from error
    if not isinstance(payload, dict):
        raise AdminSecurityError("Admin package root must be an object.")
    return payload


def _require_keys(
    payload: Mapping[str, Any],
    required: set[str],
    optional: set[str] | frozenset[str] = frozenset(),
) -> None:
    keys = set(payload)
    if not required.issubset(keys) or keys - required - optional:
        raise AdminSecurityError("Admin package schema is invalid.")


def _safe_text(value: Any, label: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str):
        raise AdminSecurityError(f"Invalid {label}.")
    text = value.strip()
    if not text or len(text) > maximum or "\x00" in text:
        raise AdminSecurityError(f"Invalid {label}.")
    return text


def _finite(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise AdminSecurityError(f"Invalid {label}.") from error
    if not math.isfinite(number):
        raise AdminSecurityError(f"Invalid {label}.")
    return number


def _validate_reference_dataset(source: Any) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        raise AdminSecurityError("Invalid admin reference dataset.")
    _require_keys(
        source,
        {"id", "label", "epoch_utc", "step_seconds", "scenarios"},
        {"required_force_model", "srp_parameters", "source_frame"},
    )
    dataset_id = _safe_text(source["id"], "dataset id", maximum=64)
    label = _safe_text(source["label"], "dataset label", maximum=160)
    try:
        epoch = datetime.fromisoformat(str(source["epoch_utc"]).replace("Z", "+00:00"))
    except ValueError as error:
        raise AdminSecurityError("Invalid reference epoch.") from error
    if epoch.tzinfo is None:
        raise AdminSecurityError("Reference epoch must include a UTC offset.")
    step_seconds = _finite(source["step_seconds"], "reference step")
    if step_seconds <= 0.0 or step_seconds > 86400.0:
        raise AdminSecurityError("Invalid reference step.")
    raw_scenarios = source["scenarios"]
    if not isinstance(raw_scenarios, list) or not 1 <= len(raw_scenarios) <= 8:
        raise AdminSecurityError("Invalid reference scenarios.")
    scenarios = []
    row_count = None
    for raw in raw_scenarios:
        if not isinstance(raw, Mapping):
            raise AdminSecurityError("Invalid reference scenario.")
        _require_keys(raw, {"name", "include_moon", "include_srp", "states"})
        states = raw["states"]
        if not isinstance(states, list) or not 2 <= len(states) <= 100000:
            raise AdminSecurityError("Invalid reference state series.")
        if row_count is None:
            row_count = len(states)
        elif row_count != len(states):
            raise AdminSecurityError("Reference scenarios must share one time grid.")
        normalized_states = []
        for state in states:
            if not isinstance(state, list) or len(state) != 6:
                raise AdminSecurityError("Every reference state needs six values.")
            normalized_states.append([_finite(item, "reference state") for item in state])
        scenarios.append(
            {
                "name": _safe_text(raw["name"], "scenario name", maximum=160),
                "include_moon": bool(raw["include_moon"]),
                "include_srp": bool(raw["include_srp"]),
                "states": normalized_states,
            }
        )
    required_force_model = source.get("required_force_model", {})
    if not isinstance(required_force_model, Mapping) or set(required_force_model) - {
        "include_moon", "include_sun", "include_srp"
    }:
        raise AdminSecurityError("Invalid required force model.")
    srp_parameters = source.get("srp_parameters")
    if srp_parameters is not None:
        if not isinstance(srp_parameters, Mapping):
            raise AdminSecurityError("Invalid SRP parameters.")
        _require_keys(srp_parameters, {"area_m2", "mass_kg", "coefficient"})
        srp_parameters = {
            key: _finite(srp_parameters[key], f"SRP {key}")
            for key in ("area_m2", "mass_kg", "coefficient")
        }
        if any(value <= 0.0 for value in srp_parameters.values()):
            raise AdminSecurityError("SRP parameters must be positive.")
    return {
        "id": dataset_id,
        "label": label,
        "epoch_utc": epoch.astimezone(timezone.utc).isoformat(),
        "step_seconds": step_seconds,
        "rows": int(row_count or 0),
        "source_frame": _safe_text(
            source.get("source_frame", "J2000/ICRF"), "source frame", maximum=80
        ),
        "required_force_model": {
            str(key): bool(value) for key, value in required_force_model.items()
        },
        "srp_parameters": srp_parameters,
        "scenarios": scenarios,
    }


def _utc_text(value: Any, label: str, *, optional: bool = False) -> str | None:
    if optional and value in (None, ""):
        return None
    try:
        epoch = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise AdminSecurityError(f"Invalid {label}.") from error
    if epoch.tzinfo is None:
        raise AdminSecurityError(f"{label} must include a UTC offset.")
    return epoch.astimezone(timezone.utc).isoformat()


def _optional_finite(value: Any, label: str) -> float | None:
    if value in (None, ""):
        return None
    return _finite(value, label)


def _validate_eclipse_reference_dataset(source: Any) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        raise AdminSecurityError("Invalid admin Eclipse reference dataset.")
    _require_keys(
        source,
        {
            "id", "label", "satellite", "nominal_longitude_deg",
            "coverage_start_utc", "coverage_end_utc", "events",
        },
    )
    events = source["events"]
    if not isinstance(events, list) or not 1 <= len(events) <= 10000:
        raise AdminSecurityError("Invalid admin Eclipse event collection.")
    normalized_events = []
    for raw in events:
        if not isinstance(raw, Mapping):
            raise AdminSecurityError("Invalid admin Eclipse event.")
        _require_keys(
            raw,
            {
                "event_number", "shadow_body", "penumbra_entry_utc",
                "umbra_entry_utc", "center_utc", "umbra_exit_utc",
                "penumbra_exit_utc", "total_duration_seconds",
                "minimum_sunlight_fraction",
            },
        )
        contacts = {
            key: _utc_text(raw[key], key.replace("_", " "), optional=True)
            for key in (
                "penumbra_entry_utc", "umbra_entry_utc", "center_utc",
                "umbra_exit_utc", "penumbra_exit_utc",
            )
        }
        if not any(contacts.values()):
            raise AdminSecurityError("Every Eclipse event needs a contact epoch.")
        duration = _optional_finite(
            raw["total_duration_seconds"], "Eclipse duration"
        )
        if duration is not None and duration < 0.0:
            raise AdminSecurityError("Eclipse duration cannot be negative.")
        minimum = _optional_finite(
            raw["minimum_sunlight_fraction"], "minimum sunlight fraction"
        )
        if minimum is not None and not 0.0 <= minimum <= 1.0:
            raise AdminSecurityError("Minimum sunlight fraction is out of range.")
        normalized_events.append(
            {
                "event_number": int(raw["event_number"]),
                "shadow_body": _safe_text(
                    raw["shadow_body"], "shadow body", maximum=16
                ).upper(),
                **contacts,
                "total_duration_seconds": duration,
                "minimum_sunlight_fraction": minimum,
            }
        )
    start = _utc_text(source["coverage_start_utc"], "coverage start")
    end = _utc_text(source["coverage_end_utc"], "coverage end")
    if datetime.fromisoformat(start) >= datetime.fromisoformat(end):
        raise AdminSecurityError("Eclipse coverage interval is invalid.")
    return {
        "id": _safe_text(source["id"], "Eclipse dataset id", maximum=64),
        "label": _safe_text(source["label"], "Eclipse label", maximum=160),
        "satellite": _safe_text(
            source["satellite"], "Eclipse satellite", maximum=100
        ),
        "nominal_longitude_deg": _finite(
            source["nominal_longitude_deg"], "nominal longitude"
        ),
        "coverage_start_utc": start,
        "coverage_end_utc": end,
        "events": normalized_events,
    }


def _validate_orbit_determination_dataset(source: Any) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        raise AdminSecurityError("Invalid admin orbit-determination dataset.")
    _require_keys(
        source,
        {
            "id", "display_name", "frame_note", "spacecraft_mass_kg",
            "cp_scale_factor", "stations", "measurements", "reference_orbit",
        },
    )
    stations = source["stations"]
    if not isinstance(stations, list) or not 1 <= len(stations) <= 64:
        raise AdminSecurityError("Invalid admin ground-station collection.")
    normalized_stations = []
    station_ids = set()
    for raw in stations:
        if not isinstance(raw, Mapping):
            raise AdminSecurityError("Invalid admin ground station.")
        _require_keys(
            raw,
            {
                "station_id", "name", "latitude_deg", "longitude_deg",
                "height_km", "temperature_c", "pressure_mbar",
                "humidity_percent", "biases", "noises", "range_ambiguity_km",
            },
        )
        station_id = _safe_text(raw["station_id"], "station id", maximum=64)
        if station_id in station_ids:
            raise AdminSecurityError("Ground-station identifiers must be unique.")
        station_ids.add(station_id)
        biases = raw["biases"]
        noises = raw["noises"]
        expected_types = {"Range", "Azimuth", "Elevation"}
        if (
            not isinstance(biases, Mapping)
            or not isinstance(noises, Mapping)
            or set(biases) != expected_types
            or set(noises) != expected_types
        ):
            raise AdminSecurityError("Ground-station error models are invalid.")
        normalized_noises = {
            key: _finite(noises[key], f"{key} noise") for key in expected_types
        }
        if any(value <= 0.0 for value in normalized_noises.values()):
            raise AdminSecurityError("Ground-station noises must be positive.")
        normalized_stations.append(
            {
                "station_id": station_id,
                "name": _safe_text(raw["name"], "station name", maximum=100),
                "latitude_deg": _finite(raw["latitude_deg"], "station latitude"),
                "longitude_deg": _finite(raw["longitude_deg"], "station longitude"),
                "height_km": _finite(raw["height_km"], "station height"),
                "temperature_c": _finite(raw["temperature_c"], "temperature"),
                "pressure_mbar": _finite(raw["pressure_mbar"], "pressure"),
                "humidity_percent": _finite(raw["humidity_percent"], "humidity"),
                "biases": {
                    key: _finite(biases[key], f"{key} bias") for key in expected_types
                },
                "noises": normalized_noises,
                "range_ambiguity_km": _finite(
                    raw["range_ambiguity_km"], "range ambiguity"
                ),
            }
        )
    measurements = source["measurements"]
    if not isinstance(measurements, list) or not 1 <= len(measurements) <= 200000:
        raise AdminSecurityError("Invalid admin measurement collection.")
    normalized_measurements = []
    for raw in measurements:
        if not isinstance(raw, Mapping):
            raise AdminSecurityError("Invalid admin measurement.")
        _require_keys(
            raw,
            {"measurement_id", "quality_factor", "station_id", "type", "epoch_utc", "value"},
        )
        station_id = _safe_text(raw["station_id"], "measurement station", maximum=64)
        measurement_type = _safe_text(raw["type"], "measurement type", maximum=16)
        if station_id not in station_ids or measurement_type not in {
            "Range", "Azimuth", "Elevation"
        }:
            raise AdminSecurityError("Admin measurement metadata is invalid.")
        normalized_measurements.append(
            {
                "measurement_id": int(raw["measurement_id"]),
                "quality_factor": int(raw["quality_factor"]),
                "station_id": station_id,
                "type": measurement_type,
                "epoch_utc": _utc_text(raw["epoch_utc"], "measurement epoch"),
                "value": _finite(raw["value"], "measurement value"),
            }
        )
    reference = source["reference_orbit"]
    if not isinstance(reference, list) or not 1 <= len(reference) <= 100000:
        raise AdminSecurityError("Invalid admin reference-orbit collection.")
    normalized_reference = []
    for raw in reference:
        if not isinstance(raw, Mapping):
            raise AdminSecurityError("Invalid admin reference-orbit record.")
        _require_keys(
            raw,
            {"epoch_utc", "elements", "cp_scale_factor", "discontinuity"},
        )
        elements = raw["elements"]
        if not isinstance(elements, list) or len(elements) != 6:
            raise AdminSecurityError("Reference-orbit state must contain six values.")
        normalized_reference.append(
            {
                "epoch_utc": _utc_text(raw["epoch_utc"], "reference epoch"),
                "elements": [_finite(value, "reference element") for value in elements],
                "cp_scale_factor": _finite(raw["cp_scale_factor"], "CP scale factor"),
                "discontinuity": bool(raw["discontinuity"]),
            }
        )
    return {
        "id": _safe_text(source["id"], "OD dataset id", maximum=64),
        "display_name": _safe_text(
            source["display_name"], "OD display name", maximum=160
        ),
        "frame_note": _safe_text(source["frame_note"], "OD frame note", maximum=500),
        "spacecraft_mass_kg": _finite(source["spacecraft_mass_kg"], "spacecraft mass"),
        "cp_scale_factor": _finite(source["cp_scale_factor"], "CP scale factor"),
        "stations": normalized_stations,
        "measurements": normalized_measurements,
        "reference_orbit": normalized_reference,
    }


def validate_admin_content(payload: Any) -> AdminContent:
    if not isinstance(payload, Mapping):
        raise AdminSecurityError("Admin content root must be an object.")
    _require_keys(
        payload,
        {
            "schema", "profiles", "reference_datasets",
            "eclipse_reference_datasets", "orbit_determination_datasets",
            "admin_modules",
        },
    )
    if payload["schema"] != CONTENT_SCHEMA:
        raise AdminSecurityError("Unsupported admin content schema.")
    raw_profiles = payload["profiles"]
    raw_references = payload["reference_datasets"]
    raw_eclipse_references = payload["eclipse_reference_datasets"]
    raw_orbit_determination = payload["orbit_determination_datasets"]
    raw_modules = payload["admin_modules"]
    if not isinstance(raw_profiles, list) or len(raw_profiles) > MAX_PROFILES:
        raise AdminSecurityError("Invalid admin profile collection.")
    if not isinstance(raw_references, list) or len(raw_references) > MAX_REFERENCE_DATASETS:
        raise AdminSecurityError("Invalid admin reference collection.")
    if (
        not isinstance(raw_eclipse_references, list)
        or len(raw_eclipse_references) > MAX_ECLIPSE_REFERENCE_DATASETS
    ):
        raise AdminSecurityError("Invalid admin Eclipse reference collection.")
    if (
        not isinstance(raw_orbit_determination, list)
        or len(raw_orbit_determination) > MAX_ORBIT_DETERMINATION_DATASETS
    ):
        raise AdminSecurityError("Invalid admin orbit-determination collection.")
    if not isinstance(raw_modules, list) or len(raw_modules) > MAX_ADMIN_MODULES:
        raise AdminSecurityError("Invalid admin module collection.")
    profiles = []
    profile_ids = set()
    for raw_profile in raw_profiles:
        if not isinstance(raw_profile, Mapping):
            raise AdminSecurityError("Invalid admin profile.")
        normalized_profile = dict(raw_profile)
        normalized_profile["built_in"] = False
        try:
            profile = validate_profile(normalized_profile)
        except Exception as error:
            raise AdminSecurityError("Admin package contains an invalid profile.") from error
        if profile.profile_id in profile_ids:
            raise AdminSecurityError("Admin profile identifiers must be unique.")
        profile_ids.add(profile.profile_id)
        profiles.append(profile)
    references = tuple(_validate_reference_dataset(item) for item in raw_references)
    if len({item["id"] for item in references}) != len(references):
        raise AdminSecurityError("Admin reference identifiers must be unique.")
    eclipse_references = tuple(
        _validate_eclipse_reference_dataset(item) for item in raw_eclipse_references
    )
    if len({item["id"] for item in eclipse_references}) != len(eclipse_references):
        raise AdminSecurityError("Admin Eclipse identifiers must be unique.")
    orbit_determination = tuple(
        _validate_orbit_determination_dataset(item)
        for item in raw_orbit_determination
    )
    if len({item["id"] for item in orbit_determination}) != len(orbit_determination):
        raise AdminSecurityError("Admin OD identifiers must be unique.")
    modules = []
    module_ids = set()
    for raw_module in raw_modules:
        if not isinstance(raw_module, Mapping):
            raise AdminSecurityError("Invalid admin module descriptor.")
        _require_keys(raw_module, {"id", "label", "description"})
        module_id = _safe_text(raw_module["id"], "module id", maximum=64)
        if module_id in module_ids:
            raise AdminSecurityError("Admin module identifiers must be unique.")
        module_ids.add(module_id)
        modules.append(
            AdminModuleDescriptor(
                module_id=module_id,
                label=_safe_text(raw_module["label"], "module label", maximum=100),
                description=_safe_text(
                    raw_module["description"], "module description", maximum=1000
                ),
            )
        )
    return AdminContent(
        tuple(profiles),
        references,
        eclipse_references,
        orbit_determination,
        tuple(modules),
    )


def default_enrollment_path() -> Path:
    return default_application_config_path().parent / "admin" / "enrollment.json"


def default_admin_package_path() -> Path:
    """Return the standard local package location; never persist it in config."""

    return default_enrollment_path().parent / "private.opa-admin"


def _key_id(verification_key: bytes) -> str:
    return hashlib.sha256(verification_key).hexdigest()[:24]


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def enroll_device(
    verification_key: bytes,
    *,
    enrollment_path: str | os.PathLike[str] | None = None,
    protector: DeviceProtector | None = None,
) -> Enrollment:
    """Create a new per-user/per-device enrollment; never return its secret."""

    verification_key = bytes(verification_key)
    if len(verification_key) != 32:
        raise AdminSecurityError("The Ed25519 verification key must be 32 bytes.")
    Ed25519PublicKey.from_public_bytes(verification_key)
    protector = protector or WindowsDpapiProtector()
    device_secret = bytearray(secrets.token_bytes(DEVICE_SECRET_BYTES))
    try:
        protected = protector.protect(bytes(device_secret))
    finally:
        device_secret[:] = b"\x00" * len(device_secret)
    enrollment = Enrollment(
        device_id=str(uuid4()),
        key_id=_key_id(verification_key),
        verification_key=verification_key,
        protected_device_secret=protected,
    )
    path = Path(enrollment_path) if enrollment_path else default_enrollment_path()
    _write_json_atomic(
        path,
        {
            "schema": ENROLLMENT_SCHEMA,
            "device_id": enrollment.device_id,
            "key_id": enrollment.key_id,
            "verification_key": _b64encode(enrollment.verification_key),
            "protected_device_secret": _b64encode(enrollment.protected_device_secret),
        },
    )
    return enrollment


def load_enrollment(path: str | os.PathLike[str] | None = None) -> Enrollment:
    enrollment_path = Path(path) if path else default_enrollment_path()
    try:
        raw = enrollment_path.read_bytes()
    except OSError as error:
        raise AdminSecurityError("This Windows user/device is not enrolled.") from error
    if len(raw) > 64 * 1024:
        raise AdminSecurityError("Device enrollment is invalid.")
    payload = _load_json_bytes(raw)
    _require_keys(
        payload,
        {"schema", "device_id", "key_id", "verification_key", "protected_device_secret"},
    )
    if payload["schema"] != ENROLLMENT_SCHEMA:
        raise AdminSecurityError("Device enrollment version is unsupported.")
    verification_key = _b64decode(payload["verification_key"], "verification key", 32)
    key_id = _safe_text(payload["key_id"], "key id", maximum=64)
    if key_id != _key_id(verification_key):
        raise AdminSecurityError("Device enrollment integrity check failed.")
    return Enrollment(
        device_id=_safe_text(payload["device_id"], "device id", maximum=64),
        key_id=key_id,
        verification_key=verification_key,
        protected_device_secret=_b64decode(
            payload["protected_device_secret"], "protected device secret"
        ),
    )


def _derive_key(password: str, device_secret: bytes, salt: bytes) -> bytearray:
    if not isinstance(password, str) or not password:
        raise AdminSecurityError("Admin password is required.")
    if len(password) > 4096:
        raise AdminSecurityError("Admin password is invalid.")
    combined = bytearray(password.encode("utf-8") + b"\x00" + bytes(device_secret))
    try:
        return bytearray(
            hash_secret_raw(
                secret=bytes(combined),
                salt=salt,
                time_cost=KDF_TIME_COST,
                memory_cost=KDF_MEMORY_COST_KIB,
                parallelism=KDF_PARALLELISM,
                hash_len=32,
                type=Type.ID,
            )
        )
    finally:
        combined[:] = b"\x00" * len(combined)


def _derive_shared_key(password: str, salt: bytes) -> bytearray:
    """Derive a key for a signed shared package without a device secret."""

    if not isinstance(password, str) or not password:
        raise AdminSecurityError("Admin password is required.")
    if len(password) > 4096:
        raise AdminSecurityError("Admin password is invalid.")
    encoded = bytearray(password.encode("utf-8"))
    try:
        return bytearray(
            hash_secret_raw(
                secret=bytes(encoded),
                salt=salt,
                time_cost=KDF_TIME_COST,
                memory_cost=KDF_MEMORY_COST_KIB,
                parallelism=KDF_PARALLELISM,
                hash_len=32,
                type=Type.ID,
            )
        )
    finally:
        encoded[:] = b"\x00" * len(encoded)


def _signature_payload(envelope: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in envelope.items() if key != "signature"}


def build_signed_package(
    content: Mapping[str, Any],
    password: str,
    enrollment: Enrollment,
    signing_key: Ed25519PrivateKey,
    *,
    protector: DeviceProtector | None = None,
) -> bytes:
    """Build a package in memory; signing secrets remain caller-owned."""

    validate_admin_content(content)
    protector = protector or WindowsDpapiProtector()
    device_secret = bytearray(protector.unprotect(enrollment.protected_device_secret))
    if len(device_secret) != DEVICE_SECRET_BYTES:
        device_secret[:] = b"\x00" * len(device_secret)
        raise AdminSecurityError("Device enrollment is invalid.")
    salt = secrets.token_bytes(KDF_SALT_BYTES)
    nonce = secrets.token_bytes(NONCE_BYTES)
    key = _derive_key(password, bytes(device_secret), salt)
    device_secret[:] = b"\x00" * len(device_secret)
    plaintext = bytearray(_canonical_json(content))
    aad = _canonical_json(
        {
            "schema": PACKAGE_SCHEMA,
            "package_version": PACKAGE_VERSION,
            "device_id": enrollment.device_id,
            "key_id": enrollment.key_id,
        }
    )
    try:
        ciphertext = AESGCM(bytes(key)).encrypt(nonce, bytes(plaintext), aad)
    finally:
        key[:] = b"\x00" * len(key)
        plaintext[:] = b"\x00" * len(plaintext)
    envelope = {
        "schema": PACKAGE_SCHEMA,
        "package_version": PACKAGE_VERSION,
        "device_id": enrollment.device_id,
        "key_id": enrollment.key_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "kdf": {
            "name": "argon2id",
            "salt": _b64encode(salt),
            "time_cost": KDF_TIME_COST,
            "memory_cost_kib": KDF_MEMORY_COST_KIB,
            "parallelism": KDF_PARALLELISM,
        },
        "aead": {
            "name": "AES-256-GCM",
            "nonce": _b64encode(nonce),
            "ciphertext": _b64encode(ciphertext),
        },
    }
    envelope["signature"] = _b64encode(signing_key.sign(_canonical_json(envelope)))
    return _canonical_json(envelope) + b"\n"


def build_shared_access_package(
    content: Mapping[str, Any],
    password: str,
    verification_key: bytes,
    signing_key: Ed25519PrivateKey,
) -> bytes:
    """Build a signed password-protected package for enrolled team devices.

    A shared package deliberately trades per-device exclusivity for offline
    distribution: any computer enrolled with this verification key and given
    the password can open it. The signature still binds the content to the
    holder of the private signing key.
    """

    validate_admin_content(content)
    verification_key = bytes(verification_key)
    if len(verification_key) != 32:
        raise AdminSecurityError("The Ed25519 verification key must be 32 bytes.")
    Ed25519PublicKey.from_public_bytes(verification_key)
    signing_public_key = signing_key.public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw
    )
    if signing_public_key != verification_key:
        raise AdminSecurityError(
            "The signing key does not match the shared package verification key."
        )
    salt = secrets.token_bytes(KDF_SALT_BYTES)
    nonce = secrets.token_bytes(NONCE_BYTES)
    key = _derive_shared_key(password, salt)
    plaintext = bytearray(_canonical_json(content))
    aad = _canonical_json(
        {
            "schema": PACKAGE_SCHEMA,
            "package_version": SHARED_PACKAGE_VERSION,
            "device_id": SHARED_PACKAGE_DEVICE_ID,
            "key_id": _key_id(verification_key),
        }
    )
    try:
        ciphertext = AESGCM(bytes(key)).encrypt(nonce, bytes(plaintext), aad)
    finally:
        key[:] = b"\x00" * len(key)
        plaintext[:] = b"\x00" * len(plaintext)
    envelope = {
        "schema": PACKAGE_SCHEMA,
        "package_version": SHARED_PACKAGE_VERSION,
        "device_id": SHARED_PACKAGE_DEVICE_ID,
        "key_id": _key_id(verification_key),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "kdf": {
            "name": "argon2id-password",
            "salt": _b64encode(salt),
            "time_cost": KDF_TIME_COST,
            "memory_cost_kib": KDF_MEMORY_COST_KIB,
            "parallelism": KDF_PARALLELISM,
        },
        "aead": {
            "name": "AES-256-GCM",
            "nonce": _b64encode(nonce),
            "ciphertext": _b64encode(ciphertext),
        },
    }
    envelope["signature"] = _b64encode(signing_key.sign(_canonical_json(envelope)))
    return _canonical_json(envelope) + b"\n"


class AttemptLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._failures = 0
        self._next_allowed = 0.0

    def check(self) -> None:
        remaining = self._next_allowed - self._clock()
        if remaining > 0:
            raise AdminSecurityError(
                f"Admin access is temporarily rate-limited; retry in {math.ceil(remaining)} seconds."
            )

    def failure(self) -> None:
        self._failures += 1
        delay = min(300.0, float(2 ** min(self._failures - 1, 8)))
        self._next_allowed = self._clock() + delay

    def success(self) -> None:
        self._failures = 0
        self._next_allowed = 0.0


class AdminSessionManager:
    """Own the volatile unlocked content; every process begins locked."""

    def __init__(
        self,
        *,
        enrollment_path: str | os.PathLike[str] | None = None,
        protector: DeviceProtector | None = None,
        limiter: AttemptLimiter | None = None,
    ):
        self.enrollment_path = Path(enrollment_path) if enrollment_path else default_enrollment_path()
        self.protector = protector or WindowsDpapiProtector()
        self.limiter = limiter or AttemptLimiter()
        self._content: AdminContent | None = None

    @property
    def unlocked(self) -> bool:
        return self._content is not None

    @property
    def content(self) -> AdminContent | None:
        return self._content

    def logout(self) -> None:
        self._content = None

    def unlock(self, package_path: str | os.PathLike[str], password: str) -> AdminContent:
        self.limiter.check()
        try:
            package = Path(package_path)
            size = package.stat().st_size
            if size <= 0 or size > MAX_PACKAGE_BYTES:
                raise AdminSecurityError("Admin package size is invalid.")
            raw = package.read_bytes()
            envelope = _load_json_bytes(raw)
            _require_keys(
                envelope,
                {
                    "schema", "package_version", "device_id", "key_id", "created_utc",
                    "kdf", "aead", "signature",
                },
            )
            package_version = envelope["package_version"]
            if (
                envelope["schema"] != PACKAGE_SCHEMA
                or package_version not in {PACKAGE_VERSION, SHARED_PACKAGE_VERSION}
            ):
                raise AdminSecurityError("Admin package version is unsupported.")
            enrollment = load_enrollment(self.enrollment_path)
            shared_package = package_version == SHARED_PACKAGE_VERSION
            if shared_package and envelope["device_id"] != SHARED_PACKAGE_DEVICE_ID:
                raise AdminSecurityError("Shared admin package identity is invalid.")
            if envelope["key_id"] != enrollment.key_id or (
                not shared_package and envelope["device_id"] != enrollment.device_id
            ):
                raise AdminSecurityError("This package is not authorized for this device.")
            signature = _b64decode(envelope["signature"], "package signature", 64)
            try:
                Ed25519PublicKey.from_public_bytes(enrollment.verification_key).verify(
                    signature, _canonical_json(_signature_payload(envelope))
                )
            except InvalidSignature as error:
                raise AdminSecurityError("Admin package signature verification failed.") from error
            kdf = envelope["kdf"]
            aead = envelope["aead"]
            if not isinstance(kdf, Mapping) or not isinstance(aead, Mapping):
                raise AdminSecurityError("Admin package cryptographic metadata is invalid.")
            _require_keys(kdf, {"name", "salt", "time_cost", "memory_cost_kib", "parallelism"})
            _require_keys(aead, {"name", "nonce", "ciphertext"})
            if (
                kdf["name"] != (
                    "argon2id-password" if shared_package else "argon2id"
                )
                or kdf["time_cost"] != KDF_TIME_COST
                or kdf["memory_cost_kib"] != KDF_MEMORY_COST_KIB
                or kdf["parallelism"] != KDF_PARALLELISM
                or aead["name"] != "AES-256-GCM"
            ):
                raise AdminSecurityError("Admin package cryptographic policy is unsupported.")
            salt = _b64decode(kdf["salt"], "KDF salt", KDF_SALT_BYTES)
            nonce = _b64decode(aead["nonce"], "AEAD nonce", NONCE_BYTES)
            ciphertext = _b64decode(aead["ciphertext"], "ciphertext")
            if shared_package:
                key = _derive_shared_key(password, salt)
            else:
                device_secret = bytearray(
                    self.protector.unprotect(enrollment.protected_device_secret)
                )
                try:
                    if len(device_secret) != DEVICE_SECRET_BYTES:
                        raise AdminSecurityError("Device enrollment is invalid.")
                    key = _derive_key(password, bytes(device_secret), salt)
                finally:
                    device_secret[:] = b"\x00" * len(device_secret)
            aad = _canonical_json(
                {
                    "schema": PACKAGE_SCHEMA,
                    "package_version": package_version,
                    "device_id": (
                        SHARED_PACKAGE_DEVICE_ID
                        if shared_package
                        else enrollment.device_id
                    ),
                    "key_id": enrollment.key_id,
                }
            )
            try:
                plaintext = bytearray(AESGCM(bytes(key)).decrypt(nonce, ciphertext, aad))
            except InvalidTag as error:
                raise AdminSecurityError("Admin unlock failed.") from error
            finally:
                key[:] = b"\x00" * len(key)
            try:
                content_payload = _load_json_bytes(bytes(plaintext))
                content = validate_admin_content(content_payload)
            finally:
                plaintext[:] = b"\x00" * len(plaintext)
            self._content = content
            self.limiter.success()
            return content
        except AdminSecurityError:
            self._content = None
            self.limiter.failure()
            raise
        except (OSError, ValueError, TypeError) as error:
            self._content = None
            self.limiter.failure()
            raise AdminSecurityError("Admin package could not be opened safely.") from error


def generate_signing_key() -> tuple[bytes, bytes]:
    """Return raw private/public Ed25519 keys for an external provisioning tool."""

    private_key = Ed25519PrivateKey.generate()
    return (
        private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()),
        private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw),
    )


def load_verification_key_file(path: str | os.PathLike[str]) -> bytes:
    """Load a raw, base64 or PEM Ed25519 public verification key."""

    try:
        raw = Path(path).read_bytes()
    except OSError as error:
        raise AdminSecurityError("Verification key could not be read.") from error
    if len(raw) > 16 * 1024:
        raise AdminSecurityError("Verification key file is invalid.")
    if len(raw) == 32:
        key = raw
    elif raw.lstrip().startswith(b"-----BEGIN"):
        try:
            public = load_pem_public_key(raw)
            if not isinstance(public, Ed25519PublicKey):
                raise TypeError
            key = public.public_bytes(Encoding.Raw, PublicFormat.Raw)
        except (TypeError, ValueError) as error:
            raise AdminSecurityError("Verification key file is invalid.") from error
    else:
        key = _b64decode(raw.decode("ascii").strip(), "verification key", 32)
    Ed25519PublicKey.from_public_bytes(key)
    return key
