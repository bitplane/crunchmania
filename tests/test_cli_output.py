import errno
import os
import stat
import subprocess
import sys

import pytest

from crunchmania import pack, unpack
from crunchmania.cli import main


@pytest.mark.parametrize("command", ["pack", "unpack"])
@pytest.mark.parametrize("explicit", [False, True])
def test_existing_output_requires_force(tmp_path, capsys, command, explicit):
    data = b"valuable source contents"
    source = tmp_path / ("input.bin" if command == "pack" else "input.crm")
    original = data if command == "pack" else pack(data)
    source.write_bytes(original)
    output = tmp_path / "chosen.bin" if explicit else source.with_suffix(".crm" if command == "pack" else "")
    output.write_bytes(b"previous contents")
    argv = [command, str(source)] + ([str(output)] if explicit else [])
    assert main(argv) == 1
    assert "--force" in capsys.readouterr().err
    assert output.read_bytes() == b"previous contents"
    assert source.read_bytes() == original
    assert main(argv + ["--force"]) == 0
    assert (unpack(output.read_bytes()) if command == "pack" else output.read_bytes()) == data


def test_same_input_and_output_rejected(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"original")
    assert main(["pack", str(source), str(source)]) == 1
    assert source.read_bytes() == b"original"


def test_empty_pack_does_not_create_output(tmp_path, capsys):
    source = tmp_path / "empty"
    source.touch()
    assert main(["pack", str(source)]) == 1
    assert "empty input" in capsys.readouterr().err
    assert not source.with_suffix(".crm").exists()


def test_cli_output_limit(tmp_path, capsys):
    source = tmp_path / "input.crm"
    source.write_bytes(pack(b"hello"))
    assert main(["unpack", str(source), "--max-output-size", "4"]) == 1
    assert "output limit" in capsys.readouterr().err
    assert not source.with_suffix("").exists()
    assert main(["unpack", str(source), "--max-output-size", "5"]) == 0
    assert source.with_suffix("").read_bytes() == b"hello"


@pytest.mark.parametrize("force", [False, True])
def test_failed_write_does_not_publish_partial_output(tmp_path, monkeypatch, capsys, force):
    import errno
    import os

    source = tmp_path / "input.bin"
    source.write_bytes(b"hello")
    output = source.with_suffix(".crm")
    if force:
        output.write_bytes(b"previous archive")

    def full_disk(*args):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(os, "fsync", full_disk)
    assert main(["pack", str(source)] + (["--force"] if force else [])) == 1
    assert "No space left" in capsys.readouterr().err
    if force:
        assert output.read_bytes() == b"previous archive"
    else:
        assert not output.exists()
    assert not list(tmp_path.glob(".crunchmania-*"))


def test_cli_unlimited_output(tmp_path):
    source = tmp_path / "input.crm"
    source.write_bytes(pack(b"hello"))
    assert main(["unpack", str(source), "--max-output-size", "0"]) == 0
    assert source.with_suffix("").read_bytes() == b"hello"


@pytest.mark.parametrize("value", ["-1", "invalid"])
def test_cli_invalid_output_limit(tmp_path, capsys, value):
    with pytest.raises(SystemExit) as error:
        main(["unpack", str(tmp_path / "input.crm"), "--max-output-size", value])
    assert error.value.code == 2
    message = capsys.readouterr().err
    assert "--max-output-size" in message
    assert "_output_limit" not in message
    assert ("nonnegative" if value == "-1" else "integer number of bytes") in message


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")
def test_new_output_respects_umask(tmp_path):
    source = tmp_path / "input.bin"
    source.write_bytes(b"hello")
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import os,sys; from crunchmania.cli import main; os.umask(0o027); raise SystemExit(main(sys.argv[1:]))",
            "pack",
            str(source),
        ],
        capture_output=True,
        check=True,
    )
    assert stat.S_IMODE(source.with_suffix(".crm").stat().st_mode) == 0o640


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")
@pytest.mark.parametrize("mode", [0o640, 0o755])
def test_force_preserves_existing_permissions(tmp_path, mode):
    source = tmp_path / "input.bin"
    source.write_bytes(b"hello")
    output = source.with_suffix(".crm")
    output.write_bytes(b"old")
    output.chmod(mode)
    assert main(["pack", str(source), "--force"]) == 0
    assert stat.S_IMODE(output.stat().st_mode) == mode


@pytest.mark.parametrize("error_code", [errno.EPERM, errno.ENOTSUP, errno.ENOSYS])
def test_output_on_filesystem_without_hardlinks(tmp_path, monkeypatch, error_code):
    source = tmp_path / "input.bin"
    source.write_bytes(b"hello")

    def unsupported(*args):
        raise OSError(error_code, "hard links unavailable")

    monkeypatch.setattr(os, "link", unsupported)
    assert main(["pack", str(source)]) == 0
    output = source.with_suffix(".crm")
    assert unpack(output.read_bytes()) == b"hello"
    previous = output.read_bytes()
    assert main(["pack", str(source)]) == 1
    assert output.read_bytes() == previous
    assert not list(tmp_path.glob(".crunchmania-*"))


def test_failed_fallback_publish_removes_reservation(tmp_path, monkeypatch):
    source = tmp_path / "input.bin"
    source.write_bytes(b"hello")

    def unsupported(*args):
        raise OSError(errno.ENOTSUP, "hard links unavailable")

    def failed_replace(*args):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(os, "link", unsupported)
    monkeypatch.setattr(os, "replace", failed_replace)
    assert main(["pack", str(source)]) == 1
    assert not source.with_suffix(".crm").exists()
    assert not list(tmp_path.glob(".crunchmania-*"))
