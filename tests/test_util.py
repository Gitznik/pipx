import sys

import pytest  # type: ignore

from pipx.util import run_subprocess


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Path resolution skip if not on windows")
def test_executable_path_resolution_unix():
    cmd = ["python99.99", "-c", "import sys;"]
    try:
        run_subprocess(cmd)
    except FileNotFoundError as e:
        assert "No such file or directory: 'python99.99'" in str(e)
