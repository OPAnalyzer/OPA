"""Import operator-produced Sun-outage schedules as immutable references."""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


class SunOutageReferenceError(ValueError):
    """Raised when a schedule cannot be interpreted without assumptions."""


BUNDLED_SUN_OUTAGE_REFERENCE_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "sun_outage"
    / "operator_reference_2026.csv"
)


@dataclass(frozen=True)
class SunOutageReferenceEvent:
    event_id: str
    satellite: str
    station_code: str
    start_utc: datetime
    end_utc: datetime
    source_name: str
    satellite_inferred: bool = False

    @property
    def date_utc(self):
        return self.start_utc.date()

    @property
    def midpoint_utc(self):
        """Return the only centre-time observable present in source schedules."""

        return self.start_utc + (self.end_utc - self.start_utc) / 2


@dataclass(frozen=True)
class SunOutageErrorMetrics:
    """Raw timing differences for pairs matched on the same UTC date.

    The source schedules contain contact times but no link configuration.  The
    centre fields therefore compare the reference window midpoint with the
    model's geometric peak, while boundary/duration fields remain uncalibrated
    schedule differences.
    """

    matched_count: int
    start_mae_seconds: float | None
    end_mae_seconds: float | None
    duration_mae_seconds: float | None
    maximum_boundary_error_seconds: float | None
    start_bias_seconds: float | None
    end_bias_seconds: float | None
    duration_bias_seconds: float | None
    center_mae_seconds: float | None
    center_bias_seconds: float | None
    duration_mape_percent: float | None


def calculate_sun_outage_error_metrics(matched_pairs) -> SunOutageErrorMetrics:
    """Summarise model-minus-reference timing errors without tuning either input."""

    errors = []
    for reference, model in matched_pairs:
        start_error = (model.start_utc - reference.start_utc).total_seconds()
        end_error = (model.end_utc - reference.end_utc).total_seconds()
        reference_duration = (reference.end_utc - reference.start_utc).total_seconds()
        model_duration = (model.end_utc - model.start_utc).total_seconds()
        duration_error = model_duration - reference_duration
        center_error = (model.peak_utc - reference.midpoint_utc).total_seconds()
        duration_percent = 100.0 * duration_error / reference_duration
        errors.append(
            (start_error, end_error, duration_error, center_error, duration_percent)
        )

    count = len(errors)
    if not count:
        return SunOutageErrorMetrics(
            matched_count=0,
            start_mae_seconds=None,
            end_mae_seconds=None,
            duration_mae_seconds=None,
            maximum_boundary_error_seconds=None,
            start_bias_seconds=None,
            end_bias_seconds=None,
            duration_bias_seconds=None,
            center_mae_seconds=None,
            center_bias_seconds=None,
            duration_mape_percent=None,
        )

    start_errors = tuple(item[0] for item in errors)
    end_errors = tuple(item[1] for item in errors)
    duration_errors = tuple(item[2] for item in errors)
    center_errors = tuple(item[3] for item in errors)
    duration_percent_errors = tuple(item[4] for item in errors)
    return SunOutageErrorMetrics(
        matched_count=count,
        start_mae_seconds=sum(abs(value) for value in start_errors) / count,
        end_mae_seconds=sum(abs(value) for value in end_errors) / count,
        duration_mae_seconds=sum(abs(value) for value in duration_errors) / count,
        maximum_boundary_error_seconds=max(
            *(abs(value) for value in start_errors),
            *(abs(value) for value in end_errors),
        ),
        start_bias_seconds=sum(start_errors) / count,
        end_bias_seconds=sum(end_errors) / count,
        duration_bias_seconds=sum(duration_errors) / count,
        center_mae_seconds=sum(abs(value) for value in center_errors) / count,
        center_bias_seconds=sum(center_errors) / count,
        duration_mape_percent=(
            sum(abs(value) for value in duration_percent_errors) / count
        ),
    )


def sun_outage_satellite_code(value: str) -> str:
    """Return the reference code used for known Azerspace spacecraft names."""

    identity = re.sub(r"[^A-Z0-9]", "", str(value).upper())
    if identity == "AZ1" or "AZERSPACE1" in identity:
        return "AZ1"
    if identity == "AZ2" or "AZERSPACE2" in identity or "IS38" in identity:
        return "AZ2"
    return identity


def _parse_utc(value: str) -> datetime:
    text = str(value).strip()
    for pattern in (
        "%Y/%m/%d-%H:%M:%S.%f",
        "%Y/%m/%d-%H:%M:%S",
        "%d/%m/%Y-%H:%M:%S.%f",
        "%d/%m/%Y-%H:%M:%S",
    ):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    raise SunOutageReferenceError(f"Unsupported reference UTC value: {text}")


def _station_code(event_id: str, comment: str = "") -> str:
    identity = f"{event_id} {comment}".upper()
    if "BAK" in identity:
        return "BAK"
    if "NAX" in identity:
        return "NAX"
    match = re.search(r"STATCOL[_-]?([A-Z0-9]+)", identity)
    return match.group(1) if match else "UNKNOWN"


def _satellite_from_name(source_name: str) -> str:
    match = re.search(r"\bAZ\s*[-_ ]?([12])(?!\d)", source_name.upper())
    return "" if match is None else f"AZ{match.group(1)}"


def _event(event_id, start, end, comment, source_name):
    start_utc = _parse_utc(start)
    end_utc = _parse_utc(end)
    if end_utc <= start_utc:
        raise SunOutageReferenceError(
            f"Reference event {event_id} ends before it starts."
        )
    return SunOutageReferenceEvent(
        event_id=str(event_id).strip(),
        satellite=_satellite_from_name(source_name),
        station_code=_station_code(str(event_id), str(comment)),
        start_utc=start_utc,
        end_utc=end_utc,
        source_name=source_name,
    )


def _load_text(path: Path):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
    expression = re.compile(
        r"^\s*(STATCOL\S*)\s+"
        r"(\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+"
        r"(\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s*(.*)$",
        re.MULTILINE,
    )
    return tuple(
        _event(event_id, start, end, comment, path.name)
        for event_id, start, end, comment in expression.findall(text)
    )


def _xlsx_rows(path: Path):
    try:
        with zipfile.ZipFile(path) as archive:
            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = ["".join(item.itertext()) for item in root]
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as error:
        raise SunOutageReferenceError(f"Could not read {path.name}: {error}") from error
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows = []
    for row in sheet.findall(".//x:sheetData/x:row", namespace):
        values = []
        for cell in row.findall("x:c", namespace):
            coordinate = cell.get("r", "")
            letters = re.match(r"[A-Z]+", coordinate.upper())
            column = len(values)
            if letters is not None:
                column = 0
                for letter in letters.group(0):
                    column = column * 26 + ord(letter) - ord("A") + 1
                column -= 1
            kind = cell.get("t")
            value = cell.find("x:v", namespace)
            if kind == "inlineStr":
                inline = cell.find("x:is", namespace)
                parsed = "" if inline is None else "".join(inline.itertext())
            elif value is None:
                parsed = ""
            elif kind == "s":
                parsed = shared[int(value.text)]
            else:
                parsed = value.text or ""
            while len(values) <= column:
                values.append("")
            values[column] = parsed
        rows.append(values)
    return rows


def _load_xlsx(path: Path):
    events = []
    for row in _xlsx_rows(path):
        if len(row) < 3 or not str(row[0]).upper().startswith("STATCOL"):
            continue
        events.append(
            _event(row[0], row[1], row[2], row[3] if len(row) > 3 else "", path.name)
        )
    return tuple(events)


def _load_csv(path: Path):
    events = []
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as stream:
            rows = csv.DictReader(stream)
            for row in rows:
                start_utc = datetime.fromisoformat(row["start_utc"])
                end_utc = datetime.fromisoformat(row["end_utc"])
                if start_utc.tzinfo is None or end_utc.tzinfo is None:
                    raise SunOutageReferenceError(
                        f"Bundled reference contains a timezone-free UTC value: {path.name}"
                    )
                start_utc = start_utc.astimezone(timezone.utc)
                end_utc = end_utc.astimezone(timezone.utc)
                if end_utc <= start_utc:
                    raise SunOutageReferenceError(
                        f"Reference event {row['event_id']} ends before it starts."
                    )
                events.append(
                    SunOutageReferenceEvent(
                        event_id=row["event_id"].strip(),
                        satellite=sun_outage_satellite_code(row["satellite"]),
                        station_code=row["station_code"].strip().upper(),
                        start_utc=start_utc,
                        end_utc=end_utc,
                        source_name=row["source_name"].strip(),
                        satellite_inferred=(
                            row.get("satellite_inferred", "").strip().lower()
                            in {"1", "true", "yes"}
                        ),
                    )
                )
    except (KeyError, OSError, TypeError, ValueError) as error:
        if isinstance(error, SunOutageReferenceError):
            raise
        raise SunOutageReferenceError(f"Could not read {path.name}: {error}") from error
    return tuple(events)


def load_sun_outage_reference_files(paths) -> tuple[SunOutageReferenceEvent, ...]:
    """Load and merge TXT/XLSX schedules, preserving their original UTC times."""

    events = []
    for value in paths:
        path = Path(value)
        suffix = path.suffix.lower()
        if suffix in {".txt", ".dat", ".stdout"}:
            loaded = _load_text(path)
        elif suffix == ".xlsx":
            loaded = _load_xlsx(path)
        elif suffix == ".csv":
            loaded = _load_csv(path)
        else:
            raise SunOutageReferenceError(f"Unsupported reference file: {path.name}")
        if not loaded:
            raise SunOutageReferenceError(f"No Sun-outage events found in {path.name}.")
        events.extend(loaded)
    unique = {
        (event.event_id, event.start_utc, event.end_utc): event for event in events
    }
    satellites_by_suffix = {}
    for event in unique.values():
        if event.satellite:
            satellites_by_suffix.setdefault(
                Path(event.source_name).suffix.lower(), set()
            ).add(event.satellite)
    unique = {
        key: (
            replace(
                event,
                satellite=next(iter(satellites_by_suffix[suffix])),
                satellite_inferred=True,
            )
            if not event.satellite
            and len(satellites_by_suffix.get(
                suffix := Path(event.source_name).suffix.lower(), set()
            )) == 1
            else event
        )
        for key, event in unique.items()
    }
    return tuple(sorted(unique.values(), key=lambda item: item.start_utc))


def load_bundled_sun_outage_references() -> tuple[SunOutageReferenceEvent, ...]:
    """Load the immutable AZ1/AZ2 operator schedules shipped with the app."""

    return load_sun_outage_reference_files((BUNDLED_SUN_OUTAGE_REFERENCE_PATH,))
