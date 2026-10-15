import stat
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization

from scripts.generate_keys import generate_keys


def test_generate_matching_keys_and_preserve_them_on_repeat(tmp_path):
    directory = tmp_path / "certs"
    generate_keys(directory)
    private_path = directory / "private_key.pem"
    public_path = directory / "public_key.pem"
    before = {path: path.read_bytes() for path in (private_path, public_path)}
    private = serialization.load_pem_private_key(before[private_path], password=None)
    public = serialization.load_pem_public_key(before[public_path])
    assert private.public_key().public_numbers() == public.public_numbers()
    assert stat.S_IMODE(private_path.stat().st_mode) == 0o600
    generate_keys(directory)
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("filename", ["private_key.pem", "public_key.pem"])
def test_partial_pair_is_not_overwritten(tmp_path, filename):
    key = tmp_path / filename
    key.write_bytes(b"existing key")
    with pytest.raises(SystemExit, match="Only one JWT key exists"):
        generate_keys(tmp_path)
    assert key.read_bytes() == b"existing key"
    assert list(tmp_path.iterdir()) == [key]


def test_mismatched_pair_is_not_overwritten(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    generate_keys(first)
    generate_keys(second)
    public_path = first / "public_key.pem"
    public_path.write_bytes((second / "public_key.pem").read_bytes())
    before = {path: path.read_bytes() for path in first.iterdir()}
    with pytest.raises(SystemExit, match="do not form an RSA pair"):
        generate_keys(first)
    assert {path: path.read_bytes() for path in first.iterdir()} == before


def test_invalid_pair_is_not_overwritten(tmp_path):
    for filename in ("private_key.pem", "public_key.pem"):
        (tmp_path / filename).write_bytes(b"invalid")
    with pytest.raises(SystemExit, match="keys are invalid"):
        generate_keys(tmp_path)
    assert all(path.read_bytes() == b"invalid" for path in tmp_path.iterdir())


def test_script_uses_project_root_from_another_working_directory(tmp_path):
    root = tmp_path / "project"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "scripts" / "generate_keys.py"
    script = scripts / source.name
    script.write_bytes(source.read_bytes())
    result = subprocess.run(
        [sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert (root / "certs" / "private_key.pem").is_file()
    assert (root / "certs" / "public_key.pem").is_file()
    assert not (tmp_path / "certs").exists()
