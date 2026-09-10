# Changelog

## 2.54.0

- Set the protected Sun-outage link preset to 10.7 GHz and 2.0 m, with an
  explicit checkbox required before operators can edit either physical input.
- Evaluate TLE spacecraft positions with SGP4 at Sun-transit search and contact
  epochs while propagation remains inside the profile's physical station box;
  preserve source-derived station-kept GEO motion if long-arc TLE drift leaves
  that configured control region.
- Warn when a prediction season is far from the active TLE epoch and recommend
  historical event-date orbit data; reference schedule times still never feed
  back into propagation or boundary detection.

## 2.53.0

- Use the active spacecraft's audited J2000 state to carry its measured
  inclination, eccentricity and orbital phase into Sun-outage geometry.
- Constrain isolated-state extrapolation to the physical sidereal rate instead
  of free-drifting it across a season; keep the fixed nominal GEO slot only as
  an explicitly labelled fallback when no valid state exists.
- Export the spacecraft-geometry mode with each Sun-outage schedule so a state-
  derived result cannot be confused with a fixed-slot calculation.
- Preserve the operator schedules as comparison-only observations. No timing
  offset, beamwidth constant or reference-derived calibration is applied.

## 2.52.0

- Separate Sun-outage centre timing from contact-window duration by comparing
  the model peak with the immutable reference-window midpoint.
- Show signed per-event duration differences as percentages and a duration
  MAPE summary without fitting any model constant.
- Mark boundary and duration comparisons as non-like-for-like when the source
  schedule omits frequency, antenna diameter, beamwidth, link margin and event
  threshold, preventing those configuration differences from being presented
  as calibrated model accuracy.

## 2.51.0

- Bundle the supplied 2026 AZ1/AZ2 operator Sun-outage schedules and load them
  automatically, so error metrics no longer depend on a manual import step.
- Match the application names `Azerspace-1` and `Azerspace-2 (IS-38)` to their
  AZ1/AZ2 reference records while keeping each original source timestamp.

## 2.50.0

- Added matched-event Sun-outage error metrics from imported operator TXT/XLSX
  references: start, end and duration MAE/bias plus the maximum contact-boundary
  error, shown in both seconds and minutes.
- Added per-event reference/model durations and signed `model − reference`
  timing errors without modifying or calibrating the model from the reference.
- Display the spacecraft attached to every reference and label a schedule whose
  identity is inherited from an explicitly identified companion source.

## 2.47.1

- Ignore a queued Matplotlib redraw after its Qt graph widget has closed.

## 2.47.0

- Added signed shared admin packages for authorized team computers already
  enrolled with the same verification key. The package still requires its
  password and the signing private key remains outside the application.

## 2.46.3

- Resolve Sun-outage longitude from the selected spacecraft's reference or
  state epoch instead of a shared station-keeping default. Display provenance
  and reject unavailable or ambiguous slots.

## 2.46.2

- Restore Admin Access and Credits to the bottom of the Settings navigation.

## 2.46.1

- Reject below-horizon GEO slots and explicitly empty Sun-transit searches.
- Invalidate Sun-outage results when inputs or session profiles change, and
  discard late results after logout or cancellation.
- Keep numerical precision fields readable in the Azerbaijani Settings page.

## 2.46.0

- Added an Eclipse-module `SUN OUTAGE` workspace using ITU-R S.1525-1
  antenna-beam geometry, WGS-84 ground stations and the JPL DE440 apparent
  Sun direction.
- Added UTC and Baku-time yearly risk windows, refined start/peak/end contacts,
  minimum angular separation, duration and CSV export.
- Admin ground-station coordinates remain memory-only and are available to the
  calculation only while the signed package is unlocked; Public Mode uses
  explicitly synthetic stations.

## 2.45.0 — 2026-09-04

- Added a graph-local Full Screen control to the Perturbation page.
- Full Screen hides the complete application shell and leaves only the live graph visible; Escape restores the exact previous window state.
- Added matching Normal, Retro, English, and Azerbaijani presentation.

## 2.44.1 — 2026-09-04

- Anchored Perturbation prediction to the selected spacecraft state and epoch instead of the default TLE.
- Applied the active profile's effective area, mass, and CP consistently to both live and predicted SRP.
- Kept Perturbation controls permanently visible and made the graph fill the remaining page without whole-page scrolling.

## 2.44.0 — 2026-09-04

- Moved the expensive past/future Perturbation prediction off the Qt GUI thread without changing its numerical model, settings, sampling, or outputs.
- Added live prediction progress and safe cancellation while keeping the application responsive.
- Reorganized Perturbation controls into compact filter/action rows and made the graph fit common laptop work areas.
- Added Azerbaijani text for the new background-calculation states.

## 2.43.5 — 2026-09-01

- Renamed the distributable repository folder and desktop launcher to Orbital Perturbation Analyzer branding.
- Removed the last obsolete product-path reference while preserving the scientific Moon perturbation module and labels.

## 2.43.4 — 2026-09-01

- Removed the built-in synthetic LEO profile from the public spacecraft catalogue.
- Migrates a previously selected retired LEO profile safely to the synthetic GEO profile.
- Corrected remaining GEO reference/SRP labels that still said LEO.

## 2.43.3 — 2026-09-01

- Simplified Admin Access to password-only unlock when external device provisioning and the encrypted package are ready.
- Hid private package paths and setup controls during normal admin use.
- Added explicit UI confirmation that private content remains outside the shareable application folder.

## 2.43.2 — 2026-09-01

- Temporarily removed the unfinished Orbit Determination workspace from the visible application shell and Retro navigation.
- Preserved the isolated OD engine for a future reviewed reintroduction.
- Safely redirects a previously saved OD module selection to Propagation.

## 2.43.1 — 2026-09-01

- Restored the established generic OPA orbit emblem and mission banner artwork.
- Kept the Windows XP-inspired Retro header compact and artwork-free.
- Stabilized the Windows per-user application-data path used by configuration and admin packages.

## 2.43.0 — 2026-08-31

- Extended signed admin packages with validated in-memory Eclipse and Orbit Determination datasets.
- Added automatic discovery of the installed device-bound admin package so unlock requires only the password after provisioning.
- Kept all private session data volatile and cleared it on logout or restart.

## 2.42.0 — 2026-08-31

- Converted the distributable application to a synthetic-only Public Mode.
- Added device-bound, signed and encrypted data-only Admin extensions.
- Moved settings, TLE cache, logs, diagnostics, profiles, and exports outside the repository.
- Added atomic configuration migration and full restart restoration.
- Added responsive Settings layout, Azerbaijani Admin UI, release scans, CI, and headless visual QA.
- Replaced unverified artwork with an original code-drawn header and repository-native SVG mark.
- Added real Windows DPAPI integration coverage and a machine-independent Windows launcher.

Historical private release notes are intentionally not included in the public distribution.
