"""Subprocess-based backend adapter for the Image-Compression-Project codec.

The external codec lives at::

    ~/Coding_Projects/Image-Compression-Project/compression.py

We invoke it exactly as the user's CLI documents::

    python compression.py compress_huff  <in>.png <out>.icj --quality N
    python compression.py decompress_huff <in>.icj <out>.png
    python compression.py compress        <in>.png <out>.npz --quality N
    python compression.py decompress      <in>.npz <out>.png

The actual codec does all the work. This module's responsibilities are:

* **Path resolution** \u2014 find ``compression.py`` via an env var, an explicit
  override, or a list of default locations so the UI can surface a clear
  error when the backend is missing.
* **Synchronous wrapper** \u2014 :func:`run_codec` invokes the backend and
  returns a typed :class:`CodecResult` instead of raising.
* **Asynchronous wrapper** \u2014 :class:`CompressorWorker` is a ``QThread`` that
  runs a job off the UI thread and emits ``finished`` / ``failed`` signals.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QThread, Signal


# ---- Path resolution ------------------------------------------------------


#: Environment variable name that, if set, forces a specific script path.
ENV_OVERRIDE = "KEVIN_COMPRESSOR_SCRIPT"


def _default_candidates() -> list[Path]:
    """Ordered list of default search locations for ``compression.py``."""
    home = Path.home()
    return [
        home / "Coding_Projects" / "Image-Compression-Project" / "compression.py",
        # Next to OpenKev, in case the project is checked out side-by-side.
        Path(__file__).resolve().parents[3] / "Image-Compression-Project" / "compression.py",
    ]


def resolve_script_path(override: str | os.PathLike | None = None) -> Path:
    """Return the path to the external ``compression.py``.

    Priority (first match wins):

    1. Explicit ``override`` argument
    2. ``$KEVIN_COMPRESSOR_SCRIPT`` environment variable
    3. Known default locations (see :func:`_default_candidates`)

    Raises :class:`FileNotFoundError` with a descriptive message if no
    candidate exists so the UI can show an actionable error.
    """
    if override is not None:
        path = Path(override).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Compressor script not found at override: {path}")
        return path

    env_val = os.environ.get(ENV_OVERRIDE)
    if env_val:
        path = Path(env_val).expanduser()
        if not path.is_file():
            raise FileNotFoundError(
                f"{ENV_OVERRIDE}={env_val!r} but that path is not a file."
            )
        return path

    checked: list[str] = []
    for candidate in _default_candidates():
        if candidate.is_file():
            return candidate
        checked.append(str(candidate))

    raise FileNotFoundError(
        "Could not locate compression.py. Set the "
        f"{ENV_OVERRIDE} environment variable, or place the script at one of: "
        + ", ".join(checked)
    )


# ---- Commands / result types ---------------------------------------------


class Command(Enum):
    """Subcommands exposed by the external codec.

    NOTE: this is intentionally a plain Enum, NOT ``(str, Enum)``. Mixing
    ``str`` in makes each member *also* a ``str``, which PySide6 silently
    unwraps when the enum is stored as ``QComboBox`` user data — retrieval
    then returns a bare string and ``cmd.value`` blows up. Keeping the enum
    as a plain Python object prevents that round-trip.
    """

    COMPRESS_HUFF = "compress_huff"
    DECOMPRESS_HUFF = "decompress_huff"
    COMPRESS_NPZ = "compress"
    DECOMPRESS_NPZ = "decompress"


#: Commands that accept a ``--quality`` argument.
_QUALITY_COMMANDS = {Command.COMPRESS_HUFF, Command.COMPRESS_NPZ}


@dataclass(frozen=True)
class CodecJob:
    """A single backend invocation."""

    command: Command
    input_path: str
    output_path: str
    quality: int | None = None

    def argv(self) -> list[str]:
        """Return the positional argv (sans Python + script) for this job."""
        argv = [self.command.value, self.input_path, self.output_path]
        if self.command in _QUALITY_COMMANDS:
            q = clamp_quality(self.quality if self.quality is not None else 50)
            argv.extend(["--quality", str(q)])
        return argv


@dataclass(frozen=True)
class CodecResult:
    """Outcome of a backend invocation."""

    success: bool
    returncode: int
    stdout: str
    stderr: str

    @property
    def error_message(self) -> str:
        """Human-readable message suitable for a dialog."""
        if self.success:
            return ""
        return (
            self.stderr.strip()
            or self.stdout.strip()
            or f"Compressor exited with code {self.returncode}"
        )


def clamp_quality(q: int) -> int:
    """Clamp a quality value to the backend's accepted ``[1, 100]`` range."""
    if q < 1:
        return 1
    if q > 100:
        return 100
    return int(q)


# ---- Synchronous runner ---------------------------------------------------


def run_codec(
    job: CodecJob,
    *,
    script_path: str | os.PathLike | None = None,
    python_executable: str | None = None,
    timeout: float | None = None,
) -> CodecResult:
    """Run ``job`` synchronously and return its outcome.

    Does NOT raise for codec failures \u2014 callers should inspect
    :attr:`CodecResult.success`. It WILL raise :class:`FileNotFoundError`
    if the backend script cannot be located, because that's a configuration
    problem, not a runtime codec problem.
    """
    script = resolve_script_path(script_path)
    interpreter = python_executable or sys.executable
    argv = [interpreter, str(script), *job.argv()]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CodecResult(
            success=False,
            returncode=-1,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + f"\nTimed out after {timeout}s",
        )
    return CodecResult(
        success=completed.returncode == 0,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def format_invocation(job: CodecJob, script_path: str | os.PathLike | None = None) -> str:
    """Return a shell-quoted command string for display / debugging."""
    script = resolve_script_path(script_path)
    argv = [sys.executable, str(script), *job.argv()]
    return " ".join(shlex.quote(a) for a in argv)


# ---- QThread worker -------------------------------------------------------


class CompressorWorker(QThread):
    """Runs a single :class:`CodecJob` off the UI thread."""

    #: Emitted on successful completion with the :class:`CodecResult`.
    finished_ok = Signal(object)
    #: Emitted on failure (non-zero return or FileNotFoundError) with a message.
    failed = Signal(str)

    def __init__(
        self,
        job: CodecJob,
        *,
        script_path: str | os.PathLike | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._job = job
        self._script_override = script_path

    def run(self) -> None:  # noqa: D401 \u2014 QThread override
        try:
            result = run_codec(self._job, script_path=self._script_override)
        except FileNotFoundError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # pragma: no cover \u2014 defensive
            self.failed.emit(f"Unexpected backend error: {exc!r}")
            return
        if result.success:
            self.finished_ok.emit(result)
        else:
            self.failed.emit(result.error_message)
