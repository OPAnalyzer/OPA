"""Build a signed password-protected package for enrolled team devices."""

from __future__ import annotations

import argparse
from base64 import b64decode
from getpass import getpass
import json
from pathlib import Path
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from admin_security import (  # noqa: E402
    build_shared_access_package,
    load_verification_key_file,
)


def _outside_repository(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    try:
        path.relative_to(ROOT)
    except ValueError:
        return path
    raise argparse.ArgumentTypeError(
        "Private input and package output must stay outside the repository."
    )


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    raw = path.read_bytes()
    if len(raw) == 32:
        return Ed25519PrivateKey.from_private_bytes(raw)
    if raw.lstrip().startswith(b"-----BEGIN"):
        key = load_pem_private_key(raw, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("Signing key is not Ed25519.")
        return key
    return Ed25519PrivateKey.from_private_bytes(
        b64decode(raw.decode("ascii").strip(), validate=True)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--content", required=True, type=_outside_repository)
    parser.add_argument("--private-key", required=True, type=_outside_repository)
    parser.add_argument("--verification-key", required=True, type=_outside_repository)
    parser.add_argument("--output", required=True, type=_outside_repository)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite an existing package.")
    password = getpass("Team package password: ")
    confirmation = getpass("Confirm password: ")
    if not password or password != confirmation:
        parser.error("Passwords did not match.")
    content = json.loads(args.content.read_text(encoding="utf-8"))
    package = build_shared_access_package(
        content,
        password,
        load_verification_key_file(args.verification_key),
        _load_private_key(args.private_key),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(package)
    print("Shared signed admin package created outside the repository.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
