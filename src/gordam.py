"""Import audited GORDAM orbit-determination solution reports.

GORDAM reports use an Earth-centred inertial state, but do not label it as
J2000.  The report does give the corresponding Earth-fixed longitude at the
state epoch.  This importer uses that reported longitude and the application's
J2000-to-ITRS rotation to construct an explicitly J2000 state.  It never
substitutes a nominal GEO slot or a made-up state vector.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
import re

import numpy as np

from earth_orientation import j2000_to_itrs_rotation_from_datetime


class GordamImportError(ValueError):
    """Raised when a file does not contain a complete GORDAM solution."""


@dataclass(frozen=True)
class GordamSolution:
    """One source-derived state at the report's OD epoch."""

    satellite: str
    epoch_utc: datetime
    state_j2000: tuple[float, float, float, float, float, float]
    longitude_deg: float
    mass_kg: float | None
    cp_scale_factor: float | None
    source_name: str


_FLOAT = r"[-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?"


def _required_float(pattern: str, source: str, label: str) -> float:
    matches = list(re.finditer(pattern, source, re.IGNORECASE | re.MULTILINE))
    if not matches:
        raise GordamImportError(f"GORDAM report is missing {label}.")
    return float(matches[-1].group(1))


def _rotation_z(angle_rad: float) -> np.ndarray:
    cosine = math.cos(angle_rad)
    sine = math.sin(angle_rad)
    return np.asarray(
        ((cosine, -sine, 0.0), (sine, cosine, 0.0), (0.0, 0.0, 1.0)),
        dtype=float,
    )


def load_gordam_solution(path: str | Path) -> GordamSolution:
    """Read a detailed ``gordam.stdout`` file into a real J2000 state.

    The compact ``gordam_report2.dat`` output is intentionally rejected: it
    is useful as a summary, but it does not carry the Cartesian solution or
    the frame bridge required for a safe import.
    """

    source_path = Path(path)
    try:
        source = source_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        source = source_path.read_text(encoding="latin-1")
    except OSError as error:
        raise GordamImportError(f"Could not read GORDAM report: {error}") from error

    satellite_match = re.search(r"^\s*Satellite\s*:\s*(\S.*)$", source, re.MULTILINE)
    epoch_match = re.search(
        r"^\s*Epoch\s*:\s*Absolute Time\s+(\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2})",
        source,
        re.MULTILINE,
    )
    if satellite_match is None or epoch_match is None:
        raise GordamImportError(
            "Select the detailed GORDAM stdout report with satellite and epoch fields."
        )
    try:
        epoch = datetime.strptime(epoch_match.group(1), "%Y/%m/%d-%H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError as error:
        raise GordamImportError("GORDAM report has an invalid solution epoch.") from error

    blocks = list(
        re.finditer(
            r"POSITION,VELOCITY\s*\(KM,KM/S\)(.*?)(?=\n\s*(?:KEPLERIAN ELEMENTS|MEASUREMENT BIASES|STATISTICS)|\Z)",
            source,
            re.IGNORECASE | re.DOTALL,
        )
    )
    if not blocks:
        raise GordamImportError(
            "The detailed Cartesian solution is absent; gordam_report2.dat alone cannot be imported."
        )
    state_block = blocks[-1].group(1)
    # GORDAM prints the first axis of each group with a full label, then uses
    # abbreviated Y/Z labels on following lines.
    labels = (
        ("POSITION X", rf"^\s*POSITION X\s+({_FLOAT})"),
        ("POSITION Y", rf"^\s*(?:POSITION\s+)?Y\s+({_FLOAT})"),
        ("POSITION Z", rf"^\s*(?:POSITION\s+)?Z\s+({_FLOAT})"),
        ("VELOCITY X", rf"^\s*VELOCITY X\s+({_FLOAT})"),
        ("VELOCITY Y", rf"^\s*(?:VELOCITY\s+)?Y\s+({_FLOAT})"),
        ("VELOCITY Z", rf"^\s*(?:VELOCITY\s+)?Z\s+({_FLOAT})"),
    )
    values: list[float] = []
    remaining = state_block
    for label, pattern in labels:
        match = re.search(pattern, remaining, re.IGNORECASE | re.MULTILINE)
        if match is None:
            raise GordamImportError(f"GORDAM report is missing {label}.")
        values.append(float(match.group(1)))
        remaining = remaining[match.end():]
    state_gordam = np.asarray(values, dtype=float)
    # GORDAM prints the longitude in the Keplerian subsection immediately
    # after the Cartesian block, rather than inside that block.
    longitude_section = source[blocks[-1].end():blocks[-1].end() + 2000]
    longitude = _required_float(
        rf"^\s*LONGITUDE\s+({_FLOAT})", longitude_section, "the solved longitude"
    )
    if not (-180.0 <= longitude <= 180.0):
        raise GordamImportError("GORDAM solved longitude is outside ±180 degrees.")

    # The report gives the longitude of this state at the same epoch.  This
    # fixes the GORDAM inertial frame's Z rotation without a hand-tuned value.
    source_angle = math.atan2(state_gordam[1], state_gordam[0])
    to_itrs = _rotation_z(math.radians(longitude) - source_angle)
    j2000_to_itrs = j2000_to_itrs_rotation_from_datetime(epoch)
    state_j2000 = np.concatenate(
        (
            j2000_to_itrs.T @ (to_itrs @ state_gordam[:3]),
            j2000_to_itrs.T @ (to_itrs @ state_gordam[3:]),
        )
    )
    if not np.all(np.isfinite(state_j2000)):
        raise GordamImportError("GORDAM state conversion produced non-finite values.")

    def optional(pattern: str) -> float | None:
        matches = list(re.finditer(pattern, source, re.IGNORECASE | re.MULTILINE))
        return None if not matches else float(matches[-1].group(1))

    return GordamSolution(
        satellite=satellite_match.group(1).strip(),
        epoch_utc=epoch,
        state_j2000=tuple(float(value) for value in state_j2000),
        longitude_deg=float(longitude),
        mass_kg=optional(rf"^\s*(?:Total Mass\s*=|Spacecraft Mass \(kg\))\s*({_FLOAT})"),
        cp_scale_factor=optional(rf"^\s*CP SCALE FACTOR\s*=\s*({_FLOAT})"),
        source_name=source_path.name,
    )
