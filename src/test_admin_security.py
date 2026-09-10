import json
from pathlib import Path
import secrets
import sys
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from admin_security import (
    AdminSecurityError,
    AdminSessionManager,
    CONTENT_SCHEMA,
    WindowsDpapiProtector,
    build_shared_access_package,
    build_signed_package,
    enroll_device,
)


class MemoryProtector:
    def __init__(self, binding=b"device-a"):
        self.binding = binding

    def protect(self, data):
        return self.binding + b"\0" + bytes(data)

    def unprotect(self, data):
        prefix = self.binding + b"\0"
        if not bytes(data).startswith(prefix):
            raise AdminSecurityError("This user/device is not enrolled.")
        return bytes(data)[len(prefix):]


def synthetic_content():
    return {
        "schema": CONTENT_SCHEMA,
        "profiles": [
            {
                "profile_id": "admin-synthetic-demo",
                "display_name": "ADMIN SYNTHETIC DEMO",
                "built_in": False,
                "orbit_source": "cartesian",
                "epoch_utc": "2031-01-01T00:00:00+00:00",
                "state_j2000": [7100.0, 0.0, 0.0, 0.0, 7.4, 1.0],
                "source_description": "SYNTHETIC/DEMO admin package test",
                "mass_kg": 600.0,
                "effective_area_m2": 9.0,
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
        ],
        "reference_datasets": [
            {
                "id": "admin-synthetic-reference",
                "label": "ADMIN SYNTHETIC REFERENCE",
                "epoch_utc": "2031-01-01T00:00:00+00:00",
                "step_seconds": 60.0,
                "source_frame": "J2000/ICRF",
                "scenarios": [
                    {
                        "name": "SYNTHETIC EARTH",
                        "include_moon": False,
                        "include_srp": False,
                        "states": [
                            [7100.0, 0.0, 0.0, 0.0, 7.4, 1.0],
                            [7099.9, 444.0, 60.0, -0.46, 7.38, 0.99],
                        ],
                    }
                ],
            }
        ],
        "eclipse_reference_datasets": [
            {
                "id": "admin-synthetic-eclipse",
                "label": "ADMIN SYNTHETIC ECLIPSE",
                "satellite": "SYNTHETIC/DEMO SPACECRAFT",
                "nominal_longitude_deg": 0.0,
                "coverage_start_utc": "2031-01-01T00:00:00+00:00",
                "coverage_end_utc": "2031-01-01T02:00:00+00:00",
                "events": [
                    {
                        "event_number": 1,
                        "shadow_body": "EARTH",
                        "penumbra_entry_utc": "2031-01-01T00:20:00+00:00",
                        "umbra_entry_utc": "2031-01-01T00:25:00+00:00",
                        "center_utc": "2031-01-01T00:30:00+00:00",
                        "umbra_exit_utc": "2031-01-01T00:35:00+00:00",
                        "penumbra_exit_utc": "2031-01-01T00:40:00+00:00",
                        "total_duration_seconds": 1200.0,
                        "minimum_sunlight_fraction": 0.0,
                    }
                ],
            }
        ],
        "orbit_determination_datasets": [
            {
                "id": "admin-synthetic-od",
                "display_name": "ADMIN SYNTHETIC ORBIT DETERMINATION",
                "frame_note": "SYNTHETIC/DEMO J2000 training dataset",
                "spacecraft_mass_kg": 600.0,
                "cp_scale_factor": 1.0,
                "stations": [
                    {
                        "station_id": "DEMO-STATION",
                        "name": "SYNTHETIC GROUND STATION",
                        "latitude_deg": 40.0,
                        "longitude_deg": 50.0,
                        "height_km": 0.1,
                        "temperature_c": 20.0,
                        "pressure_mbar": 1013.25,
                        "humidity_percent": 40.0,
                        "biases": {"Range": 0.0, "Azimuth": 0.0, "Elevation": 0.0},
                        "noises": {"Range": 0.1, "Azimuth": 0.01, "Elevation": 0.01},
                        "range_ambiguity_km": 0.0,
                    }
                ],
                "measurements": [
                    {
                        "measurement_id": 1,
                        "quality_factor": 1,
                        "station_id": "DEMO-STATION",
                        "type": "Range",
                        "epoch_utc": "2031-01-01T00:00:00+00:00",
                        "value": 42000.0,
                    }
                ],
                "reference_orbit": [
                    {
                        "epoch_utc": "2031-01-01T00:00:00+00:00",
                        "elements": [42164.0, 0.001, 0.1, 0.0, 0.0, 0.0],
                        "cp_scale_factor": 1.0,
                        "discontinuity": False,
                    }
                ],
            }
        ],
        "admin_modules": [
            {
                "id": "synthetic-admin-workspace",
                "label": "SYNTHETIC ADMIN WORKSPACE",
                "description": "Fictional data-only extension used by security tests.",
            }
        ],
    }


class AdminSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.enrollment_path = self.root / "enrollment.json"
        self.package_path = self.root / "demo.opa-admin"
        self.protector = MemoryProtector()
        self.password = secrets.token_urlsafe(24)
        self.signing_key = Ed25519PrivateKey.generate()
        verification_key = self.signing_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        self.enrollment = enroll_device(
            verification_key,
            enrollment_path=self.enrollment_path,
            protector=self.protector,
        )
        self.package_path.write_bytes(
            build_signed_package(
                synthetic_content(),
                self.password,
                self.enrollment,
                self.signing_key,
                protector=self.protector,
            )
        )

    def tearDown(self):
        self.temp.cleanup()

    def manager(self, protector=None):
        return AdminSessionManager(
            enrollment_path=self.enrollment_path,
            protector=protector or self.protector,
        )

    def test_enrolled_device_password_and_signature_unlock(self):
        manager = self.manager()
        content = manager.unlock(
            self.package_path, self.password
        )
        self.assertTrue(manager.unlocked)
        self.assertEqual(content.profiles[0].profile_id, "admin-synthetic-demo")
        self.assertEqual(
            content.reference_datasets[0]["id"], "admin-synthetic-reference"
        )
        self.assertEqual(
            content.eclipse_reference_datasets[0]["id"],
            "admin-synthetic-eclipse",
        )
        self.assertEqual(
            content.orbit_determination_datasets[0]["id"],
            "admin-synthetic-od",
        )
        self.assertEqual(content.admin_modules[0].module_id, "synthetic-admin-workspace")
        manager.logout()
        self.assertFalse(manager.unlocked)
        self.assertIsNone(manager.content)

    def test_wrong_password_is_rejected(self):
        with self.assertRaisesRegex(AdminSecurityError, "unlock failed"):
            self.manager().unlock(self.package_path, secrets.token_urlsafe(24))

    def test_unenrolled_device_secret_is_rejected(self):
        with self.assertRaisesRegex(AdminSecurityError, "not enrolled"):
            self.manager(MemoryProtector(b"device-b")).unlock(
                self.package_path, self.password
            )

    def test_package_for_another_device_is_rejected(self):
        second_path = self.root / "second-enrollment.json"
        second = enroll_device(
            self.signing_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw),
            enrollment_path=second_path,
            protector=self.protector,
        )
        foreign_package = self.root / "foreign.opa-admin"
        foreign_package.write_bytes(
            build_signed_package(
                synthetic_content(),
                self.password,
                second,
                self.signing_key,
                protector=self.protector,
            )
        )
        with self.assertRaisesRegex(AdminSecurityError, "not authorized"):
            self.manager().unlock(foreign_package, self.password)

    def test_tampering_and_fake_signature_are_rejected_before_decryption(self):
        envelope = json.loads(self.package_path.read_text(encoding="utf-8"))
        ciphertext = envelope["aead"]["ciphertext"]
        replacement = "B" if ciphertext.startswith("A") else "A"
        envelope["aead"]["ciphertext"] = replacement + ciphertext[1:]
        tampered = self.root / "tampered.opa-admin"
        tampered.write_text(json.dumps(envelope), encoding="utf-8")
        with self.assertRaisesRegex(AdminSecurityError, "signature verification"):
            self.manager().unlock(tampered, self.password)

    def test_unknown_path_or_executable_fields_are_rejected(self):
        content = synthetic_content()
        content["admin_modules"][0]["path"] = "../private.py"
        with self.assertRaisesRegex(AdminSecurityError, "schema"):
            build_signed_package(
                content,
                self.password,
                self.enrollment,
                self.signing_key,
                protector=self.protector,
            )

    def test_plaintext_is_not_written_beside_package(self):
        self.manager().unlock(self.package_path, self.password)
        files = {item.name for item in self.root.iterdir() if item.is_file()}
        self.assertEqual(files, {"enrollment.json", "demo.opa-admin"})

    def test_shared_team_package_opens_for_second_enrolled_device(self):
        shared_path = self.root / "team.opa-admin"
        shared_path.write_bytes(
            build_shared_access_package(
                synthetic_content(),
                self.password,
                self.enrollment.verification_key,
                self.signing_key,
            )
        )
        second_path = self.root / "second-enrollment.json"
        enroll_device(
            self.enrollment.verification_key,
            enrollment_path=second_path,
            protector=MemoryProtector(b"device-b"),
        )
        second_manager = AdminSessionManager(
            enrollment_path=second_path,
            protector=MemoryProtector(b"device-b"),
        )
        content = second_manager.unlock(shared_path, self.password)
        self.assertEqual(content.profiles[0].profile_id, "admin-synthetic-demo")
        with self.assertRaisesRegex(AdminSecurityError, "unlock failed"):
            self.manager().unlock(shared_path, secrets.token_urlsafe(24))

    def test_shared_team_package_requires_its_signing_key_enrollment(self):
        shared_path = self.root / "team.opa-admin"
        shared_path.write_bytes(
            build_shared_access_package(
                synthetic_content(),
                self.password,
                self.enrollment.verification_key,
                self.signing_key,
            )
        )
        other_signing_key = Ed25519PrivateKey.generate()
        wrong_key_path = self.root / "wrong-key-enrollment.json"
        enroll_device(
            other_signing_key.public_key().public_bytes(
                Encoding.Raw, PublicFormat.Raw
            ),
            enrollment_path=wrong_key_path,
            protector=MemoryProtector(b"device-c"),
        )
        manager = AdminSessionManager(
            enrollment_path=wrong_key_path,
            protector=MemoryProtector(b"device-c"),
        )
        with self.assertRaisesRegex(AdminSecurityError, "authorized"):
            manager.unlock(shared_path, self.password)

    def test_shared_team_package_rejects_mismatched_signing_key(self):
        with self.assertRaisesRegex(AdminSecurityError, "does not match"):
            build_shared_access_package(
                synthetic_content(),
                self.password,
                self.enrollment.verification_key,
                Ed25519PrivateKey.generate(),
            )


@unittest.skipUnless(sys.platform == "win32", "Windows DPAPI is required")
class WindowsDpapiIntegrationTests(unittest.TestCase):
    def test_real_dpapi_enrollment_and_unlock_roundtrip(self):
        with tempfile.TemporaryDirectory(prefix="opa-dpapi-test-") as directory:
            root = Path(directory)
            enrollment_path = root / "enrollment.json"
            package_path = root / "demo.opa-admin"
            protector = WindowsDpapiProtector()
            signing_key = Ed25519PrivateKey.generate()
            verification_key = signing_key.public_key().public_bytes(
                Encoding.Raw, PublicFormat.Raw
            )
            enrollment = enroll_device(
                verification_key,
                enrollment_path=enrollment_path,
                protector=protector,
            )
            password = secrets.token_urlsafe(24)
            package_path.write_bytes(
                build_signed_package(
                    synthetic_content(),
                    password,
                    enrollment,
                    signing_key,
                    protector=protector,
                )
            )

            manager = AdminSessionManager(
                enrollment_path=enrollment_path,
                protector=protector,
            )
            content = manager.unlock(package_path, password)
            self.assertTrue(manager.unlocked)
            self.assertEqual(content.profiles[0].profile_id, "admin-synthetic-demo")
            manager.logout()
            self.assertFalse(manager.unlocked)


if __name__ == "__main__":
    unittest.main()
