# Admin extensions

Admin extensions are optional data-only additions to the public application. They do not add executable Python, shell commands, archive members, paths, or dynamic imports.

## Security flow

1. On the authorized Windows account, run `python scripts/enroll_admin_device.py --verification-key <public-key-file>`.
2. The application creates a random device ID and device secret. Windows DPAPI protects the secret for the current user; the unprotected secret is not written to disk.
3. On an offline provisioning system, create the signed package using the external signing private key, exported enrollment descriptor, private content JSON, and a password entered through a hidden prompt.
4. Install the signed package at the application's standard per-user admin location outside the repository. Settings → `ADMIN ACCESS` then shows readiness without exposing the path; the authorized user enters only the password and unlocks. If provisioning is missing, the panel reveals the generic device/package setup controls.
5. The application checks package version and device/key identity, verifies Ed25519 signature, derives a key with Argon2id from password plus device secret, authenticates/decrypts with AES-256-GCM, then validates the strict content schema.
6. Profiles, references, and informational module descriptors are installed only in memory. Logout or application exit removes them and returns to the public profile.

Signature verification happens before DPAPI unprotect and decryption. Re-enrolling creates a new device identity and invalidates packages created for the previous enrollment.

## Shared team package

For an authorized colleague who must not send a device descriptor back to the
provisioner, create a shared package with
`scripts/build_shared_admin_package.py`. The colleague first enrolls using the
same public verification key, then selects the resulting `.opa-admin` package
in Settings → Admin Access and enters its password. The shared package can be
opened by any enrolled Windows user/device with that verification key and the
password, so distribute it only to the intended team. It remains signed and
authenticated before its data is loaded. The private signing key stays on the
provisioning computer.

The standard enrollment and encrypted package live under the operating system's per-user application-data directory, never under the source/application folder. Zipping or copying the repository therefore does not include private content. The UI does not display or persist those external paths.

## External-only secrets

The following must remain outside this repository and outside its working tree:

- Ed25519 signing private key;
- per-device enrollment file/descriptor;
- admin passwords;
- built `.opa-admin` packages;
- private content JSON and any source datasets;
- real operator names or values.

The public verification key may be distributed to an authorized user, but it is not bundled by default. Never pass passwords as command-line arguments or environment variables.

## Synthetic verification workflow

`examples/admin_content.synthetic.example.json` is fictional. To exercise the workflow without private content:

```powershell
python scripts/generate_admin_signing_key.py --output-directory C:\external\opa-provisioning
python scripts/enroll_admin_device.py --verification-key C:\external\opa-provisioning\admin_signing_public.pub --export-descriptor C:\external\opa-provisioning\device.json
python scripts/build_admin_package.py --content examples\admin_content.synthetic.example.json --private-key C:\external\opa-provisioning\admin_signing_private.key --enrollment C:\external\opa-provisioning\device.json --output C:\external\opa-provisioning\synthetic.opa-admin
```

The scripts reject output secrets placed inside the repository. Use a strong unique password at the hidden prompt. The example package contains no real spacecraft or operator data.

## Package evolution

Unknown schema versions, unknown keys, oversized arrays, non-finite numbers, duplicate JSON keys, path-like fields, and executable module descriptors are rejected. Introduce a new explicit schema/version for future changes; do not silently accept incompatible payloads.
