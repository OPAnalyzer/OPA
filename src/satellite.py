from datetime import datetime, timezone
import os
import shutil
import urllib.request

import numpy as np

from skyfield.api import load, wgs84

from earth_orientation import (
    skyfield_time_from_datetime,
    skyfield_time_from_datetimes,
)
from application_config import default_application_config_path

# Parsing the complete active-satellite TLE catalogue is expensive. Parse it
# once, build exact name/NORAD indexes, and keep resolved objects in memory.
_satellite_cache = {}
_satellite_catalog = None
_satellites_by_name = {}
_satellites_by_norad = {}

TLE_FILE = default_application_config_path().parent / "tle" / "active.tle"

CELESTRAK_URL = (
    "https://celestrak.org/NORAD/elements/"
    "gp.php?GROUP=active&FORMAT=tle"
)

TARGET_SATELLITE_NAME = "ISS (ZARYA)"
TARGET_SATELLITE_DISPLAY_NAME = "ISS (PUBLIC TLE DEMO)"
TARGET_SATELLITE_NORAD_ID = 25544


def clear_satellite_cache():

    global _satellite_catalog

    _satellite_cache.clear()
    _satellite_catalog = None
    _satellites_by_name.clear()
    _satellites_by_norad.clear()


def _normalise_satellite_name(satellite_name):

    return " ".join(
        str(satellite_name).strip().upper().split()
    )


def _ensure_satellite_catalog():

    global _satellite_catalog

    if _satellite_catalog is not None:
        return _satellite_catalog

    if not TLE_FILE.exists():
        raise FileNotFoundError(
            f"Local TLE file not found: {TLE_FILE}"
        )

    _satellite_catalog = load.tle_file(
        str(TLE_FILE)
    )

    for satellite in _satellite_catalog:
        normalised_name = _normalise_satellite_name(
            satellite.name
        )
        _satellites_by_name[normalised_name] = satellite

        satnum = getattr(
            satellite.model,
            "satnum",
            None,
        )
        if satnum is not None:
            _satellites_by_norad[int(satnum)] = satellite

    return _satellite_catalog


def load_satellite(satellite_name=None, norad_id=None):

    if satellite_name is None and norad_id is None:
        raise ValueError(
            "satellite_name or norad_id must be provided."
        )

    if norad_id is not None:
        norad_id = int(norad_id)
        cache_key = ("norad", norad_id)

        if cache_key in _satellite_cache:
            return _satellite_cache[cache_key]

        _ensure_satellite_catalog()
        satellite = _satellites_by_norad.get(
            norad_id
        )
        if satellite is None:
            raise ValueError(
                f"NORAD {norad_id} not found."
            )

        _satellite_cache[cache_key] = satellite
        return satellite

    normalised_name = _normalise_satellite_name(
        satellite_name
    )
    cache_key = ("name", normalised_name)

    if cache_key in _satellite_cache:
        return _satellite_cache[cache_key]

    satellites = _ensure_satellite_catalog()

    # Prefer an exact catalogue name. The substring fallback preserves the
    # public API used by older parts of the application.
    satellite = _satellites_by_name.get(
        normalised_name
    )
    if satellite is not None:
        _satellite_cache[cache_key] = satellite
        return satellite

    for satellite in satellites:
        if normalised_name in _normalise_satellite_name(
            satellite.name
        ):
            _satellite_cache[cache_key] = satellite
            return satellite

    raise ValueError(f"{satellite_name} not found.")


def get_tle_metadata(
    satellite_name=TARGET_SATELLITE_NAME,
    norad_id=None,
):

    satellite = load_satellite(
        satellite_name,
        norad_id=norad_id,
    )
    tle_epoch = satellite.epoch.utc_datetime().astimezone(
        timezone.utc
    )
    now = datetime.now(
        timezone.utc
    )
    age_days = (
        now - tle_epoch
    ).total_seconds() / 86400.0

    return {
        "satellite_name": satellite.name.strip(),
        "tle_epoch": tle_epoch,
        "age_days": float(age_days),
        "file_path": str(TLE_FILE),
        "file_modified": datetime.fromtimestamp(
            TLE_FILE.stat().st_mtime,
            tz=timezone.utc,
        ),
        "source": "CelesTrak active satellites (local cache)",
        "is_stale": bool(age_days > 3.0),
    }


def update_local_tle(timeout=15.0):
    """Download, validate, and atomically replace the local TLE file."""

    request = urllib.request.Request(
        CELESTRAK_URL,
        headers={
            "User-Agent": "Orbital-Perturbation-Analyzer/2.1",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=float(timeout),
    ) as response:
        payload = response.read()

    text = payload.decode(
        "utf-8",
        errors="replace",
    )

    if "\n1 " not in text or "\n2 " not in text:
        raise ValueError(
            "Downloaded TLE catalogue failed validation."
        )

    TLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = TLE_FILE.with_suffix(
        ".download.tmp"
    )
    backup_file = TLE_FILE.with_name(
        "active.previous.tle"
    )

    temporary_file.write_bytes(
        payload
    )

    if TLE_FILE.exists():
        shutil.copy2(
            TLE_FILE,
            backup_file,
        )

    os.replace(
        temporary_file,
        TLE_FILE,
    )
    clear_satellite_cache()

    # Parsing the requested satellite validates the new catalogue again.
    return get_tle_metadata(
        TARGET_SATELLITE_NAME
    )


def get_satellite_position(
    satellite_name,
    utc_time,
    norad_id=None,
):
    """
    Returns the satellite position with respect to Earth's center.

    Parameters
    ----------
    satellite_name : str
        Public TLE catalogue name (for example, "ISS (ZARYA)").

    utc_time : datetime
        UTC datetime object

    Returns
    -------
    numpy.ndarray
        Satellite position [km]
    """

    return get_satellite_state(
        satellite_name,
        utc_time,
        norad_id=norad_id,
    )[:3]


def get_satellite_state(
    satellite_name,
    utc_time,
    norad_id=None,
):
    """Return the event-time Skyfield/SGP4 J2000 state in km and km/s."""

    satellite = load_satellite(
        satellite_name,
        norad_id=norad_id,
    )

    t = skyfield_time_from_datetime(utc_time)

    geocentric = satellite.at(t)
    return np.concatenate(
        (
            np.asarray(geocentric.position.km, dtype=float),
            np.asarray(geocentric.velocity.km_per_s, dtype=float),
        )
    )


def get_satellite_position_and_altitude(
    satellite_name,
    utc_time,
    norad_id=None,
):
    """Return GCRS position and Skyfield WGS-84 geodetic height."""

    satellite = load_satellite(
        satellite_name,
        norad_id=norad_id,
    )
    skyfield_time = skyfield_time_from_datetime(utc_time)
    geocentric = satellite.at(
        skyfield_time
    )
    position = np.asarray(
        geocentric.position.km,
        dtype=float,
    )
    altitude_km = float(
        wgs84.height_of(geocentric).km
    )
    return position, altitude_km


def get_satellite_positions(
    satellite_name,
    utc_times,
    norad_id=None,
):
    """Return multiple GCRS positions with one vectorised SGP4 call."""

    utc_times = list(
        utc_times
    )
    if not utc_times:
        return np.empty(
            (0, 3),
            dtype=float,
        )

    satellite = load_satellite(
        satellite_name,
        norad_id=norad_id,
    )
    skyfield_times = skyfield_time_from_datetimes(utc_times)
    positions = np.asarray(
        satellite.at(skyfield_times).position.km,
        dtype=float,
    )

    return positions.T


def get_satellite_positions_and_altitudes(
    satellite_name,
    utc_times,
    norad_id=None,
):
    """Vectorised GCRS positions and exact Skyfield WGS-84 heights."""

    utc_times = list(
        utc_times
    )
    if not utc_times:
        return (
            np.empty((0, 3), dtype=float),
            np.empty((0,), dtype=float),
        )

    satellite = load_satellite(
        satellite_name,
        norad_id=norad_id,
    )
    skyfield_times = skyfield_time_from_datetimes(utc_times)
    geocentric = satellite.at(
        skyfield_times
    )
    positions = np.asarray(
        geocentric.position.km,
        dtype=float,
    ).T
    altitudes = np.asarray(
        wgs84.height_of(geocentric).km,
        dtype=float,
    )
    return positions, altitudes


def get_satellite_orbital_period_seconds(
    satellite_name,
    norad_id=None,
):
    """Return the TLE mean orbital period in seconds."""

    satellite = load_satellite(
        satellite_name,
        norad_id=norad_id,
    )
    mean_motion_radians_per_minute = float(
        satellite.model.no_kozai
    )
    if mean_motion_radians_per_minute <= 0.0:
        raise ValueError(
            "TLE mean motion must be positive."
        )

    return float(
        2.0
        * np.pi
        / mean_motion_radians_per_minute
        * 60.0
    )
