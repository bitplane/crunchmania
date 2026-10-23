import errno
import os
from pathlib import Path

import pytest

from crunchmania import pack
from crunchmania.cli import main


@pytest.mark.parametrize("command", ["pack", "unpack", "info", "scan"])
def test_missing_input_is_friendly(tmp_path, capsys, command):
    assert main([command, str(tmp_path / "missing")]) == 1
    error = capsys.readouterr().err
    assert error.startswith("error:")
    assert "Traceback" not in error


@pytest.mark.parametrize("command", ["pack", "unpack"])
def test_unwritable_output_is_friendly(tmp_path, capsys, monkeypatch, command):
    source = tmp_path / "source"
    source.write_bytes(b"hello" if command == "pack" else pack(b"hello"))

    def denied(*args):
        raise PermissionError(errno.EACCES, "permission denied")

    monkeypatch.setattr(os, "link", denied)
    assert main([command, str(source)]) == 1
    assert "permission denied" in capsys.readouterr().err


def test_corrupt_stream_is_friendly(tmp_path, capsys):
    source = tmp_path / "bad.crm"
    source.write_bytes(bytes.fromhex("43724d2100000000011700000007bffc8300000000"))
    assert main(["unpack", str(source)]) == 1
    assert "ended unexpectedly" in capsys.readouterr().err
    assert not source.with_suffix("").exists()


def test_memory_error_is_friendly(tmp_path, capsys, monkeypatch):
    def fail(*args):
        raise MemoryError

    monkeypatch.setattr(Path, "read_bytes", fail)
    assert main(["scan", str(tmp_path / "file")]) == 1
    assert "insufficient memory" in capsys.readouterr().err
