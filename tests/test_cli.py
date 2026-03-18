from crunchmania.cli import main

from .conftest import DATA_DIR


def test_info(capsys):
    rc = main(["info", str(DATA_DIR / "test_C1.crm")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "standard" in out
    assert "152089" in out


def test_info_lzh(capsys):
    rc = main(["info", str(DATA_DIR / "test_C1_lz.crm")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "LZH" in out


def test_unpack(tmp_path):
    output = tmp_path / "out.bin"
    rc = main(["unpack", str(DATA_DIR / "test_C1.crm"), str(output)])
    assert rc == 0
    assert output.exists()
    assert len(output.read_bytes()) == 152089


def test_unpack_default_output(tmp_path, monkeypatch):
    import shutil

    src = tmp_path / "test.crm"
    shutil.copy(DATA_DIR / "test_C1.crm", src)
    monkeypatch.chdir(tmp_path)
    rc = main(["unpack", str(src)])
    assert rc == 0
    assert (tmp_path / "test").exists()


def test_scan(capsys):
    rc = main(["scan", str(DATA_DIR / "shnock")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "CrM block(s) found" in out


def test_scan_no_data(capsys, tmp_path):
    f = tmp_path / "empty"
    f.write_bytes(b"\x00" * 100)
    rc = main(["scan", str(f)])
    assert rc == 0
    assert "no CrM data found" in capsys.readouterr().out


def test_no_command(capsys):
    rc = main([])
    assert rc == 1


def test_aliases(tmp_path):
    output = tmp_path / "out.bin"
    rc = main(["u", str(DATA_DIR / "DECK2prefs"), str(output)])
    assert rc == 0
    assert output.exists()
