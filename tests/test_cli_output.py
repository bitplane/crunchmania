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
