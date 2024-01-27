import logging
import os
import shutil
import subprocess
import sys
from typing import Optional

from pipx.constants import WINDOWS
from pipx.util import PipxError

logger = logging.getLogger(__name__)


def has_venv() -> bool:
    try:
        import venv  # noqa

        return True
    except ImportError:
        return False


class InterpreterResolutionError(PipxError):
    def __init__(self, source: str, version: str, wrap_message: bool = True):
        self.source = source
        self.version = version
        potentially_path = "/" in version
        potentially_pylauncher = "python" not in version and not potentially_path

        message = (
            f"No executable for the provided Python version '{version}' found in {source}."
            " Please make sure the provided version is "
        )
        if source == "py launcher":
            message += "listed when running `py --list`."
        if source == "PATH":
            message += "on your PATH or the file path is valid. "
            if potentially_path:
                message += "The provided version looks like a path, but no executable was found there."
            if potentially_pylauncher:
                message += (
                    "The provided version looks like a version for Python Launcher, " "but `py` was not found on PATH."
                )
        super().__init__(message, wrap_message)


def find_python_interpreter(python_version: str) -> str:
    try:
        py_executable = find_py_launcher_python(python_version)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise InterpreterResolutionError(source="py launcher", version=python_version) from e
    if not py_executable:
        path_python = shutil.which(python_version)
        if not path_python:
            raise InterpreterResolutionError(source="PATH", version=python_version)
        # If path is a symlink, don't apply realpath as that breaks venvs on unix based systems
        path_python = os.path.realpath(path_python, strict=True) if not os.path.islink(path_python) else path_python

        try:
            py_executable = subprocess.run(
                [path_python, "-c", "import sys; print(sys.executable)"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise InterpreterResolutionError(source="PATH", version=python_version) from e
    # If path is a symlink, don't apply realpath as that breaks venvs on unix based systems
    return os.path.realpath(py_executable, strict=True) if not os.path.islink(py_executable) else py_executable


# The following code was copied from https://github.com/uranusjr/pipx-standalone
# which uses the same technique to build a completely standalone pipx
# distribution.
#
# If we are running under the Windows embeddable distribution,
# venv isn't available (and we probably don't want to use the
# embeddable distribution as our applications' base Python anyway)
# so we try to locate the system Python and use that instead.


def find_py_launcher_python(python_version: Optional[str] = None) -> Optional[str]:
    py = shutil.which("py")
    if py and python_version:
        python_semver = python_version
        if python_version.startswith("python"):
            logging.warn(
                "Removing `python` from the start of the version, as pylauncher just expects the semantic version"
            )
            python_semver = python_semver.lstrip("python")
        py = subprocess.run(
            [py, f"-{python_semver}", "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    return py


def _find_default_windows_python() -> str:
    if has_venv():
        return sys.executable
    python = find_py_launcher_python() or shutil.which("python")

    if python is None:
        raise PipxError("No suitable Python found")

    # If the path contains "WindowsApps", it's the store python
    if "WindowsApps" not in python:
        return python

    # Special treatment to detect Windows Store stub.
    # https://twitter.com/zooba/status/1212454929379581952

    proc = subprocess.run([python, "-V"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    if proc.returncode != 0:
        # Cover the 9009 return code pre-emptively.
        raise PipxError("No suitable Python found")
    if not proc.stdout.strip():
        # A real Python should print version, Windows Store stub won't.
        raise PipxError("No suitable Python found")
    return python  # This executable seems to work.


def _get_sys_executable() -> str:
    if WINDOWS:
        return _find_default_windows_python()
    else:
        return sys.executable


def _get_absolute_python_interpreter(env_python: str) -> str:
    which_python = shutil.which(env_python)
    if not which_python:
        raise PipxError(f"Default python interpreter '{env_python}' is invalid.")
    return which_python


env_default_python = os.environ.get("PIPX_DEFAULT_PYTHON")

if not env_default_python:
    DEFAULT_PYTHON = _get_sys_executable()
else:
    DEFAULT_PYTHON = _get_absolute_python_interpreter(env_default_python)
