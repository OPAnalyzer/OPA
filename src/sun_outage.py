"""GSO Earth-station Sun-transit prediction.

The geometry follows the simplified operational method in ITU-R S.1525-1,
Annex 2.  DE440 supplies the apparent Sun direction while the Earth station is
placed on WGS-84.  When an audited Cartesian state is available, the selected
spacecraft follows the inclined/eccentric daily motion implied by that state at
the station-kept sidereal rate.  The fixed nominal Earth-fixed GSO slot remains
an explicit fallback.  The reported interval is the intersection of the solar
disc and the antenna 3 dB beam; it is a geometric interference-risk window,
not a carrier-specific link-budget outage guarantee.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timedelta, timezone
import math
from pathlib import Path
from typing import Callable

import numpy as np
import spiceypy as spice
from scipy.optimize import brentq, minimize_scalar

from constants import MU_EARTH, R_EARTH, SUN_MEAN_RADIUS_KM, WGS84_FLATTENING
from earth_orientation import j2000_to_itrs_rotation_from_datetime
from satellite import get_satellite_position, get_satellite_state, get_tle_metadata
from spice_loader import load_kernels
from time_utils import format_csv_utc, utc_to_et


SPEED_OF_LIGHT_M_S = 299_792_458.0
NOMINAL_GSO_RADIUS_KM = 42_164.0
EARTH_SIDEREAL_DAY_SECONDS = 86_164.0905
EARTH_SIDEREAL_RATE_RAD_S = 2.0 * math.pi / EARTH_SIDEREAL_DAY_SECONDS
ITU_R_S_1525_URL = (
    "https://www.itu.int/rec/R-REC-S.1525/en"
)


class SunOutageError(ValueError):
    """Raised when a Sun-outage request is physically invalid."""


class SunOutageCancelled(RuntimeError):
    """Raised when the background year search is cancelled."""


def profile_reference_longitude(profile, reference_specs):
    """Resolve an unambiguous nominal slot by exact normalized spacecraft identity.

    Station-keeping targets may be schema defaults in older profiles, so they
    are not authoritative evidence of a spacecraft's Sun-transit slot.
    """
    def identity(value):
        return "".join(char for char in str(value).casefold() if char.isalnum())

    names = {identity(profile.display_name), identity(profile.tle_name),
             identity(profile.profile_id)} - {""}
    slots = {
        float(spec.nominal_longitude_deg)
        for spec in reference_specs
        if identity(spec.satellite) in names and spec.nominal_longitude_deg is not None
    }
    if any(not math.isfinite(value) or not -180 <= value <= 180 for value in slots):
        raise SunOutageError("Invalid nominal longitude in the spacecraft reference.")
    if len(slots) > 1:
        raise SunOutageError("Conflicting nominal longitudes in spacecraft references.")
    return next(iter(slots)) if slots else None


@dataclass(frozen=True)
class SunOutageStation:
    station_id: str
    name: str
    latitude_deg: float
    longitude_deg: float
    height_km: float = 0.0


@dataclass(frozen=True)
class SunOutageEvent:
    start_utc: datetime
    peak_utc: datetime
    end_utc: datetime
    minimum_separation_deg: float
    threshold_deg: float
    sun_angular_diameter_deg: float
    beamwidth_3db_deg: float

    @property
    def duration_seconds(self) -> float:
        return (self.end_utc - self.start_utc).total_seconds()


@dataclass(frozen=True)
class GeosynchronousOrbitModel:
    """Periodic GEO geometry derived from one audited J2000 state.

    The osculating eccentricity, orbital plane and anomaly come directly from
    the supplied state.  Only the mean angular rate is constrained to the
    physical sidereal rate so that an isolated state is not extrapolated as an
    uncontrolled longitude drift across an entire Sun-outage season.
    """

    epoch_utc: datetime
    semi_major_axis_km: float
    eccentricity: float
    periapsis_hat_j2000: tuple[float, float, float]
    quadrature_hat_j2000: tuple[float, float, float]
    mean_anomaly_at_epoch_rad: float
    ecef_longitude_rotation_rad: float

    def position_ecef(
        self,
        epoch: datetime,
        *,
        eop_enabled: bool | None = None,
    ) -> np.ndarray:
        """Return the model spacecraft position in ITRS/ECEF kilometres."""

        if not isinstance(epoch, datetime) or epoch.tzinfo is None:
            raise SunOutageError("Epoch must be timezone-aware.")
        utc = epoch.astimezone(timezone.utc)
        elapsed = (utc - self.epoch_utc).total_seconds()
        mean_anomaly = (
            self.mean_anomaly_at_epoch_rad
            + EARTH_SIDEREAL_RATE_RAD_S * elapsed
        ) % (2.0 * math.pi)
        eccentric_anomaly = mean_anomaly
        for _iteration in range(10):
            residual = (
                eccentric_anomaly
                - self.eccentricity * math.sin(eccentric_anomaly)
                - mean_anomaly
            )
            derivative = 1.0 - self.eccentricity * math.cos(eccentric_anomaly)
            correction = residual / derivative
            eccentric_anomaly -= correction
            if abs(correction) <= 1.0e-14:
                break

        periapsis = np.asarray(self.periapsis_hat_j2000, dtype=float)
        quadrature = np.asarray(self.quadrature_hat_j2000, dtype=float)
        root = math.sqrt(1.0 - self.eccentricity * self.eccentricity)
        position_j2000 = self.semi_major_axis_km * (
            (math.cos(eccentric_anomaly) - self.eccentricity) * periapsis
            + root * math.sin(eccentric_anomaly) * quadrature
        )
        position_ecef = np.asarray(
            j2000_to_itrs_rotation_from_datetime(
                utc,
                eop_enabled=eop_enabled,
            ) @ position_j2000,
            dtype=float,
        )
        cosine = math.cos(self.ecef_longitude_rotation_rad)
        sine = math.sin(self.ecef_longitude_rotation_rad)
        x_value, y_value, z_value = position_ecef
        return np.asarray(
            (
                cosine * x_value - sine * y_value,
                sine * x_value + cosine * y_value,
                z_value,
            ),
            dtype=float,
        )


@dataclass(frozen=True)
class SunOutagePrediction:
    year: int
    station: SunOutageStation
    satellite_longitude_deg: float
    frequency_ghz: float
    antenna_diameter_m: float
    beamwidth_3db_deg: float
    events: tuple[SunOutageEvent, ...]
    method: str = "ITU-R S.1525-1 Annex 2 geometry + JPL DE440 Sun"
    spacecraft_geometry: str = "fixed nominal Earth-fixed GSO slot"


def half_power_beamwidth_deg(frequency_ghz: float, antenna_diameter_m: float) -> float:
    """Return the ITU-R S.1525-1 estimate ``70 λ / d`` in degrees."""

    frequency = _positive(frequency_ghz, "Frequency")
    diameter = _positive(antenna_diameter_m, "Antenna diameter")
    wavelength_m = SPEED_OF_LIGHT_M_S / (frequency * 1.0e9)
    return 70.0 * wavelength_m / diameter


def _positive(value, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise SunOutageError(f"{label} must be numeric.") from error
    if not math.isfinite(result) or result <= 0.0:
        raise SunOutageError(f"{label} must be finite and greater than zero.")
    return result


def _validated_station(station: SunOutageStation) -> SunOutageStation:
    if not isinstance(station, SunOutageStation):
        raise SunOutageError("A valid ground station is required.")
    latitude = float(station.latitude_deg)
    longitude = float(station.longitude_deg)
    height = float(station.height_km)
    if not all(math.isfinite(value) for value in (latitude, longitude, height)):
        raise SunOutageError("Ground-station coordinates must be finite.")
    if not -90.0 <= latitude <= 90.0:
        raise SunOutageError("Ground-station latitude must be within ±90 degrees.")
    if not -180.0 <= longitude <= 180.0:
        raise SunOutageError("Ground-station longitude must be within ±180 degrees.")
    if height < -1.0 or height > 20.0:
        raise SunOutageError("Ground-station height is outside the supported range.")
    return station


def _geodetic_to_ecef(station: SunOutageStation) -> np.ndarray:
    latitude = math.radians(station.latitude_deg)
    longitude = math.radians(station.longitude_deg)
    eccentricity_squared = WGS84_FLATTENING * (2.0 - WGS84_FLATTENING)
    prime_vertical = R_EARTH / math.sqrt(
        1.0 - eccentricity_squared * math.sin(latitude) ** 2
    )
    radius = prime_vertical + station.height_km
    return np.asarray(
        [
            radius * math.cos(latitude) * math.cos(longitude),
            radius * math.cos(latitude) * math.sin(longitude),
            (prime_vertical * (1.0 - eccentricity_squared) + station.height_km)
            * math.sin(latitude),
        ],
        dtype=float,
    )


def _gso_ecef(longitude_deg: float) -> np.ndarray:
    longitude = math.radians(longitude_deg)
    return np.asarray(
        [
            NOMINAL_GSO_RADIUS_KM * math.cos(longitude),
            NOMINAL_GSO_RADIUS_KM * math.sin(longitude),
            0.0,
        ],
        dtype=float,
    )


def geosynchronous_orbit_from_state(
    state_j2000,
    epoch_utc: datetime,
    anchor_longitude_deg: float,
    *,
    eop_enabled: bool | None = None,
) -> GeosynchronousOrbitModel:
    """Build a station-kept periodic GEO model from a real Cartesian state.

    The reference schedule is not an input to this inversion.  The optional
    longitude anchor is the independently supplied operational slot shown in
    the UI; it rotates the state-derived orbit about Earth's spin axis without
    changing its inclination, eccentricity, phase or radius.
    """

    values = np.asarray(state_j2000, dtype=float)
    if values.shape != (6,) or not np.all(np.isfinite(values)):
        raise SunOutageError("Spacecraft state must contain six finite J2000 values.")
    if not isinstance(epoch_utc, datetime) or epoch_utc.tzinfo is None:
        raise SunOutageError("Spacecraft state epoch must be timezone-aware.")
    anchor = float(anchor_longitude_deg)
    if not math.isfinite(anchor) or not -180.0 <= anchor <= 180.0:
        raise SunOutageError("Satellite longitude must be within ±180 degrees.")

    position = values[:3]
    velocity = values[3:]
    radius = float(np.linalg.norm(position))
    if radius <= 0.0:
        raise SunOutageError("Spacecraft state position magnitude must be positive.")
    angular_momentum = np.cross(position, velocity)
    momentum_norm = float(np.linalg.norm(angular_momentum))
    if momentum_norm <= np.finfo(float).eps * radius:
        raise SunOutageError("Spacecraft state has no well-defined orbital plane.")
    momentum_hat = angular_momentum / momentum_norm
    speed_squared = float(np.dot(velocity, velocity))
    orbital_energy = 0.5 * speed_squared - MU_EARTH / radius
    if orbital_energy >= 0.0:
        raise SunOutageError("Spacecraft state must describe a bound GEO orbit.")
    semi_major_axis = -MU_EARTH / (2.0 * orbital_energy)
    if not 35_000.0 <= semi_major_axis <= 50_000.0:
        raise SunOutageError("Spacecraft state is outside the supported GEO range.")

    eccentricity_vector = (
        (speed_squared - MU_EARTH / radius) * position
        - float(np.dot(position, velocity)) * velocity
    ) / MU_EARTH
    eccentricity = float(np.linalg.norm(eccentricity_vector))
    if not 0.0 <= eccentricity < 0.1:
        raise SunOutageError("Spacecraft state eccentricity is outside the GEO range.")
    if eccentricity > 1.0e-10:
        periapsis_hat = eccentricity_vector / eccentricity
        quadrature_hat = np.cross(momentum_hat, periapsis_hat)
        true_anomaly = math.atan2(
            float(np.dot(position, quadrature_hat)),
            float(np.dot(position, periapsis_hat)),
        )
        eccentric_anomaly = math.atan2(
            math.sqrt(1.0 - eccentricity * eccentricity) * math.sin(true_anomaly),
            eccentricity + math.cos(true_anomaly),
        )
        mean_anomaly = eccentric_anomaly - eccentricity * math.sin(eccentric_anomaly)
    else:
        # Periapsis is undefined for a circular orbit.  The radius direction is
        # a source-derived nonsingular phase basis, not an invented orientation.
        eccentricity = 0.0
        periapsis_hat = position / radius
        quadrature_hat = np.cross(momentum_hat, periapsis_hat)
        mean_anomaly = 0.0
        semi_major_axis = radius

    source_epoch = epoch_utc.astimezone(timezone.utc)
    source_ecef = np.asarray(
        j2000_to_itrs_rotation_from_datetime(
            source_epoch,
            eop_enabled=eop_enabled,
        ) @ position,
        dtype=float,
    )
    source_longitude = math.atan2(source_ecef[1], source_ecef[0])
    longitude_rotation = math.atan2(
        math.sin(math.radians(anchor) - source_longitude),
        math.cos(math.radians(anchor) - source_longitude),
    )
    return GeosynchronousOrbitModel(
        epoch_utc=source_epoch,
        semi_major_axis_km=float(semi_major_axis),
        eccentricity=float(eccentricity),
        periapsis_hat_j2000=tuple(float(value) for value in periapsis_hat),
        quadrature_hat_j2000=tuple(float(value) for value in quadrature_hat),
        mean_anomaly_at_epoch_rad=float(mean_anomaly),
        ecef_longitude_rotation_rad=float(longitude_rotation),
    )


def _apparent_sun_j2000(epoch: datetime) -> np.ndarray:
    load_kernels()
    state, _light_time = spice.spkezr(
        "SUN",
        utc_to_et(epoch),
        "J2000",
        "LT+S",
        "EARTH",
    )
    return np.asarray(state[:3], dtype=float)


def sun_satellite_separation_deg(
    epoch: datetime,
    station: SunOutageStation,
    satellite_longitude_deg: float,
    *,
    satellite_orbit: GeosynchronousOrbitModel | None = None,
    satellite_position_j2000: Callable[[datetime], np.ndarray] | None = None,
    eop_enabled: bool | None = None,
) -> tuple[float, float]:
    """Return topocentric Sun/GSO separation and apparent solar diameter."""

    if not isinstance(epoch, datetime) or epoch.tzinfo is None:
        raise SunOutageError("Epoch must be timezone-aware.")
    station = _validated_station(station)
    longitude = float(satellite_longitude_deg)
    if not math.isfinite(longitude) or not -180.0 <= longitude <= 180.0:
        raise SunOutageError("Satellite longitude must be within ±180 degrees.")
    epoch = epoch.astimezone(timezone.utc)
    station_ecef = _geodetic_to_ecef(station)
    if satellite_position_j2000 is not None:
        position_j2000 = np.asarray(satellite_position_j2000(epoch), dtype=float)
        if position_j2000.shape != (3,) or not np.all(np.isfinite(position_j2000)):
            raise SunOutageError(
                "The event-time spacecraft position must be a finite J2000 three-vector."
            )
        satellite_ecef = np.asarray(
            j2000_to_itrs_rotation_from_datetime(
                epoch,
                eop_enabled=eop_enabled,
            ) @ position_j2000,
            dtype=float,
        )
    elif satellite_orbit is not None:
        satellite_ecef = satellite_orbit.position_ecef(
            epoch,
            eop_enabled=eop_enabled,
        )
    else:
        satellite_ecef = _gso_ecef(longitude)
    satellite_line = satellite_ecef - station_ecef
    satellite_distance = float(np.linalg.norm(satellite_line))
    if satellite_distance <= 0.0:
        raise SunOutageError("Invalid station-to-satellite geometry.")

    sun_j2000 = _apparent_sun_j2000(epoch)
    rotation = j2000_to_itrs_rotation_from_datetime(
        epoch,
        eop_enabled=eop_enabled,
    )
    sun_ecef = np.asarray(rotation @ sun_j2000, dtype=float)
    sun_line = sun_ecef - station_ecef
    sun_distance = float(np.linalg.norm(sun_line))
    if sun_distance <= SUN_MEAN_RADIUS_KM:
        raise SunOutageError("Invalid Earth-to-Sun geometry.")

    cosine = float(
        np.dot(satellite_line, sun_line)
        / (satellite_distance * sun_distance)
    )
    separation = math.degrees(math.acos(float(np.clip(cosine, -1.0, 1.0))))
    solar_diameter = 2.0 * math.degrees(
        math.asin(SUN_MEAN_RADIUS_KM / sun_distance)
    )
    return separation, solar_diameter


def _candidate_dates(year: int) -> tuple[date, ...]:
    dates: list[date] = []
    for centre in (date(year, 3, 20), date(year, 9, 22)):
        dates.extend(centre + timedelta(days=offset) for offset in range(-30, 31))
    return tuple(dict.fromkeys(dates))


def predict_sun_outages(
    *,
    year: int,
    station: SunOutageStation,
    satellite_longitude_deg: float,
    frequency_ghz: float,
    antenna_diameter_m: float,
    satellite_state_j2000=None,
    satellite_state_epoch_utc: datetime | None = None,
    satellite_tle_name: str | None = None,
    satellite_norad_id: int | None = None,
    satellite_station_box_half_width_deg: float | None = None,
    eop_enabled: bool | None = None,
    candidate_dates: tuple[date, ...] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> SunOutagePrediction:
    """Predict daily GSO Sun-transit risk intervals for one calendar year."""

    selected_year = int(year)
    if not 1900 <= selected_year <= 2199:
        raise SunOutageError("Year must be between 1900 and 2199.")
    station = _validated_station(station)
    beamwidth = half_power_beamwidth_deg(frequency_ghz, antenna_diameter_m)
    longitude = float(satellite_longitude_deg)
    if not math.isfinite(longitude) or not -180.0 <= longitude <= 180.0:
        raise SunOutageError("Satellite longitude must be within ±180 degrees.")
    latitude_rad = math.radians(station.latitude_deg)
    longitude_rad = math.radians(station.longitude_deg)
    up = np.array([
        math.cos(latitude_rad) * math.cos(longitude_rad),
        math.cos(latitude_rad) * math.sin(longitude_rad),
        math.sin(latitude_rad),
    ])
    if np.dot(_gso_ecef(longitude) - _geodetic_to_ecef(station), up) <= 0:
        raise SunOutageError("The selected GEO slot is below the station horizon.")
    if beamwidth > 30.0:
        raise SunOutageError(
            "The estimated 3 dB beamwidth exceeds 30 degrees; check frequency and diameter."
        )
    state_supplied = satellite_state_j2000 is not None
    epoch_supplied = satellite_state_epoch_utc is not None
    if state_supplied != epoch_supplied:
        raise SunOutageError(
            "Spacecraft state and its UTC epoch must be supplied together."
        )
    tle_supplied = bool(str(satellite_tle_name or "").strip()) or (
        satellite_norad_id is not None
    )
    if tle_supplied and state_supplied:
        raise SunOutageError(
            "Use either an event-time TLE or an isolated spacecraft state, not both."
        )
    satellite_orbit = None
    satellite_position_provider = None
    tle_periodic_fallback = None
    tle_epoch = None
    if tle_supplied:
        tle_name = str(satellite_tle_name or "").strip() or None
        norad_id = None if satellite_norad_id is None else int(satellite_norad_id)
        metadata = get_tle_metadata(tle_name, norad_id=norad_id)
        tle_epoch = metadata["tle_epoch"].astimezone(timezone.utc)
        tle_state = get_satellite_state(tle_name, tle_epoch, norad_id=norad_id)
        tle_periodic_fallback = geosynchronous_orbit_from_state(
            tle_state,
            tle_epoch,
            longitude,
            eop_enabled=eop_enabled,
        )
        station_box_half_width = (
            None
            if satellite_station_box_half_width_deg is None
            else _positive(
                satellite_station_box_half_width_deg,
                "Station-box half-width",
            )
        )

        def satellite_position_provider(epoch: datetime) -> np.ndarray:
            propagated_j2000 = np.asarray(
                get_satellite_position(tle_name, epoch, norad_id=norad_id),
                dtype=float,
            )
            if station_box_half_width is not None:
                propagated_ecef = np.asarray(
                    j2000_to_itrs_rotation_from_datetime(
                        epoch,
                        eop_enabled=eop_enabled,
                    ) @ propagated_j2000,
                    dtype=float,
                )
                propagated_longitude = math.degrees(
                    math.atan2(propagated_ecef[1], propagated_ecef[0])
                )
                longitude_difference = abs(
                    math.degrees(
                        math.atan2(
                            math.sin(math.radians(propagated_longitude - longitude)),
                            math.cos(math.radians(propagated_longitude - longitude)),
                        )
                    )
                )
            else:
                longitude_difference = 0.0
            if (
                station_box_half_width is not None
                and longitude_difference > station_box_half_width
            ):
                fallback_ecef = tle_periodic_fallback.position_ecef(
                    epoch,
                    eop_enabled=eop_enabled,
                )
                rotation = j2000_to_itrs_rotation_from_datetime(
                    epoch,
                    eop_enabled=eop_enabled,
                )
                return np.asarray(rotation.T @ fallback_ecef, dtype=float)
            return propagated_j2000
    if state_supplied:
        satellite_orbit = geosynchronous_orbit_from_state(
            satellite_state_j2000,
            satellite_state_epoch_utc,
            longitude,
            eop_enabled=eop_enabled,
        )
    dates = tuple(_candidate_dates(selected_year) if candidate_dates is None else candidate_dates)
    if not dates:
        raise SunOutageError("At least one candidate date is required.")
    if any(item.year != selected_year for item in dates):
        raise SunOutageError("Candidate dates must belong to the selected year.")

    events: list[SunOutageEvent] = []
    total = len(dates)
    for index, day in enumerate(dates):
        if cancel_check is not None and cancel_check():
            raise SunOutageCancelled("Sun-outage search cancelled.")
        midnight = datetime.combine(day, datetime_time(), tzinfo=timezone.utc)

        def geometry_at(seconds: float) -> tuple[float, float]:
            if cancel_check is not None and cancel_check():
                raise SunOutageCancelled("Sun-outage search cancelled.")
            return sun_satellite_separation_deg(
                midnight + timedelta(seconds=float(seconds)),
                station,
                satellite_longitude_deg,
                satellite_orbit=satellite_orbit,
                satellite_position_j2000=satellite_position_provider,
                eop_enabled=eop_enabled,
            )

        optimum = minimize_scalar(
            lambda seconds: geometry_at(seconds)[0],
            bounds=(0.0, 86400.0),
            method="bounded",
            options={"xatol": 0.05, "maxiter": 80},
        )
        if not optimum.success:
            raise SunOutageError(f"Could not refine the Sun transit on {day.isoformat()}.")
        peak_seconds = float(optimum.x)
        minimum_separation, solar_diameter = geometry_at(peak_seconds)
        threshold = 0.5 * (solar_diameter + beamwidth)
        if minimum_separation <= threshold:
            def boundary(seconds: float) -> float:
                separation, diameter = geometry_at(seconds)
                return separation - 0.5 * (diameter + beamwidth)

            try:
                start_seconds = brentq(
                    boundary,
                    0.0,
                    peak_seconds,
                    xtol=0.05,
                    rtol=1.0e-12,
                )
                end_seconds = brentq(
                    boundary,
                    peak_seconds,
                    86400.0,
                    xtol=0.05,
                    rtol=1.0e-12,
                )
            except ValueError as error:
                raise SunOutageError(
                    f"Could not bracket the Sun-transit contacts on {day.isoformat()}."
                ) from error
            events.append(
                SunOutageEvent(
                    start_utc=midnight + timedelta(seconds=start_seconds),
                    peak_utc=midnight + timedelta(seconds=peak_seconds),
                    end_utc=midnight + timedelta(seconds=end_seconds),
                    minimum_separation_deg=float(minimum_separation),
                    threshold_deg=float(threshold),
                    sun_angular_diameter_deg=float(solar_diameter),
                    beamwidth_3db_deg=float(beamwidth),
                )
            )
        if progress_callback is not None:
            progress_callback(int(100 * (index + 1) / total))

    if satellite_position_provider is not None:
        if station_box_half_width is not None:
            spacecraft_geometry = (
                "event-time SGP4 inside the configured station box; state-derived "
                "station-kept GEO when long-arc TLE drift leaves it"
            )
        else:
            spacecraft_geometry = "event-time SGP4 propagation from active TLE"
        method = (
            "ITU-R S.1525-1 Annex 2 geometry + station-box-guarded SGP4/TLE "
            "spacecraft position + JPL DE440 Sun"
        )
    elif satellite_orbit is None:
        spacecraft_geometry = "fixed nominal Earth-fixed GSO slot (fallback)"
        method = "ITU-R S.1525-1 Annex 2 geometry + JPL DE440 Sun"
    else:
        spacecraft_geometry = (
            "state-derived inclined/eccentric periodic GEO at sidereal rate"
        )
        method = (
            "ITU-R S.1525-1 Annex 2 geometry + audited J2000 state-derived "
            "periodic GEO + JPL DE440 Sun"
        )
    return SunOutagePrediction(
        year=selected_year,
        station=station,
        satellite_longitude_deg=float(satellite_longitude_deg),
        frequency_ghz=float(frequency_ghz),
        antenna_diameter_m=float(antenna_diameter_m),
        beamwidth_3db_deg=float(beamwidth),
        events=tuple(events),
        method=method,
        spacecraft_geometry=spacecraft_geometry,
    )


def save_sun_outage_csv(prediction: SunOutagePrediction, file_path) -> Path:
    """Export one auditable row per predicted interference-risk interval."""

    if not isinstance(prediction, SunOutagePrediction):
        raise SunOutageError("Calculate Sun-outage events before export.")
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "Station ID",
                "Station name",
                "Satellite longitude [deg E]",
                "Spacecraft geometry",
                "Frequency [GHz]",
                "Antenna diameter [m]",
                "3 dB beamwidth [deg]",
                "Start UTC",
                "Peak UTC",
                "End UTC",
                "Duration [s]",
                "Minimum separation [deg]",
                "Threshold [deg]",
                "Solar angular diameter [deg]",
                "Method",
            )
        )
        for event in prediction.events:
            writer.writerow(
                (
                    prediction.station.station_id,
                    prediction.station.name,
                    f"{prediction.satellite_longitude_deg:.8f}",
                    prediction.spacecraft_geometry,
                    f"{prediction.frequency_ghz:.6f}",
                    f"{prediction.antenna_diameter_m:.6f}",
                    f"{event.beamwidth_3db_deg:.9f}",
                    format_csv_utc(event.start_utc),
                    format_csv_utc(event.peak_utc),
                    format_csv_utc(event.end_utc),
                    f"{event.duration_seconds:.3f}",
                    f"{event.minimum_separation_deg:.9f}",
                    f"{event.threshold_deg:.9f}",
                    f"{event.sun_angular_diameter_deg:.9f}",
                    prediction.method,
                )
            )
    return path
