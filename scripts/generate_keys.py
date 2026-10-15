"""Generate a local RSA key pair; never replace an existing key."""

import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> None:
    directory = Path(__file__).resolve().parents[1] / "src" / "certs"
    private_path = directory / "private_key.pem"
    public_path = directory / "public_key.pem"
    if private_path.exists() and public_path.exists():
        print("JWT keys already exist; kept unchanged.")
        return
    if private_path.exists() or public_path.exists():
        raise SystemExit("Only one JWT key exists. Restore the matching pair before continuing.")

    directory.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_bytes = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    descriptor = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(private_bytes)
    with public_path.open("xb") as stream:
        stream.write(public_bytes)
    print("Created src/certs/private_key.pem and src/certs/public_key.pem.")


if __name__ == "__main__":
    main()
