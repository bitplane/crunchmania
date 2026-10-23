import hashlib
import json
import subprocess

import pytest

from crunchmania import unpack

from .conftest import ALL_FILES, DATA_DIR, ancient_decompress


@pytest.mark.parametrize("filename", ALL_FILES)
def test_reference_digest(filename):
    digests = json.loads((DATA_DIR / "sha256.json").read_text())
    assert hashlib.sha256(unpack((DATA_DIR / filename).read_bytes())).hexdigest() == digests[filename]


def test_reference_rejection_is_a_failure(monkeypatch, tmp_path):
    def reject(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, b"", b"invalid stream")

    monkeypatch.setattr(subprocess, "run", reject)
    with pytest.raises(pytest.fail.Exception, match="invalid stream"):
        ancient_decompress("generated.crm", tmp_path)
