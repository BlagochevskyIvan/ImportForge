"""Generate a local RSA key pair; never replace an existing key."""

import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_keys(directory: Path) -> None:
    private_path = directory / "private_key.pem"
    public_path = directory / "public_key.pem"
    if private_path.exists() and public_path.exists():
        try:
            private_key = serialization.load_pem_private_key(
                private_path.read_bytes(), password=None
            )
            public_key = serialization.load_pem_public_key(public_path.read_bytes())
        except (TypeError, ValueError) as exc:
            raise SystemExit("Existing JWT keys are invalid; kept unchanged.") from exc
        if (
            not isinstance(private_key, rsa.RSAPrivateKey)
            or not isinstance(public_key, rsa.RSAPublicKey)
            or private_key.public_key().public_numbers() != public_key.public_numbers()
        ):
            raise SystemExit("Existing JWT keys do not form an RSA pair; kept unchanged.")
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
    print(f"Created {private_path} and {public_path}.")


def main() -> None:
    generate_keys(Path(__file__).resolve().parents[1] / "certs")


if __name__ == "__main__":
    main()
