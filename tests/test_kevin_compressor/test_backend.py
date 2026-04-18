"""Tests for apps/KevinCompressor/backend.py.

The end-to-end round-trip test actually invokes the external compressor
via subprocess, so it's skipped cleanly when the backend or its sample
assets are unavailable.
"""

from __future__ import annotations

import os
import shutil

import pytest

from apps.KevinCompressor.backend import (
    CodecJob, Command, ENV_OVERRIDE, clamp_quality, format_invocation,
    resolve_script_path, run_codec,
)


# ---- Path resolution ------------------------------------------------------


class TestResolveScriptPath:
    def test_explicit_override_wins(self, tmp_path, monkeypatch):
        fake = tmp_path / "compression.py"
        fake.write_text("# stub", encoding="utf-8")
        monkeypatch.setenv(ENV_OVERRIDE, "/nope/nonexistent")
        resolved = resolve_script_path(fake)
        assert resolved == fake

    def test_override_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_script_path(tmp_path / "does-not-exist.py")

    def test_env_var_used_when_no_override(self, tmp_path, monkeypatch):
        fake = tmp_path / "compression.py"
        fake.write_text("# stub", encoding="utf-8")
        monkeypatch.setenv(ENV_OVERRIDE, str(fake))
        resolved = resolve_script_path()
        assert resolved == fake

    def test_env_var_bad_path_raises(self, monkeypatch):
        monkeypatch.setenv(ENV_OVERRIDE, "/definitely/not/a/real/path.py")
        with pytest.raises(FileNotFoundError):
            resolve_script_path()

    def test_missing_everywhere_raises_with_guidance(self, monkeypatch, tmp_path):
        monkeypatch.delenv(ENV_OVERRIDE, raising=False)
        # Stub out every default search location so the real on-disk backend
        # (which DOES exist in this dev environment) isn't found.
        from apps.KevinCompressor import backend as backend_mod
        monkeypatch.setattr(
            backend_mod,
            "_default_candidates",
            lambda: [tmp_path / "nope1.py", tmp_path / "nope2.py"],
        )
        with pytest.raises(FileNotFoundError) as excinfo:
            resolve_script_path()
        msg = str(excinfo.value)
        assert ENV_OVERRIDE in msg
        assert "compression.py" in msg


# ---- Quality clamping -----------------------------------------------------


class TestClampQuality:
    @pytest.mark.parametrize("inp,expected", [
        (-5, 1), (0, 1), (1, 1), (50, 50), (100, 100), (101, 100), (9999, 100),
    ])
    def test_clamping(self, inp, expected):
        assert clamp_quality(inp) == expected


# ---- CodecJob argv --------------------------------------------------------


class TestCommandEnum:
    """Regression guard for the PySide6 QVariant unwrapping bug.

    When ``Command`` was declared as ``class Command(str, Enum)``, storing a
    member as ``QComboBox`` user data silently round-tripped through a
    ``QString`` and came back as a bare ``str``, so ``cmd.value`` raised
    ``AttributeError``. Keeping the enum as a plain :class:`Enum` plus a
    ``Command(raw)`` normalization step on retrieval prevents that.
    """

    def test_is_not_a_str_subclass(self):
        # If someone re-introduces ``(str, Enum)`` they'll trip this.
        assert not isinstance(Command.COMPRESS_HUFF, str)

    def test_value_lookup_round_trip(self):
        # Enables the defensive ``Command(raw)`` call in the UI.
        assert Command("compress") is Command.COMPRESS_NPZ
        assert Command("compress_huff") is Command.COMPRESS_HUFF
        assert Command("decompress") is Command.DECOMPRESS_NPZ
        assert Command("decompress_huff") is Command.DECOMPRESS_HUFF

    def test_qcombobox_round_trip_survives(self):
        """Actually stuff a Command through a real QComboBox and read it back.

        With ``(str, Enum)`` this round-trip was lossy. With plain ``Enum``
        the object comes back unchanged.
        """
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QApplication, QComboBox
        app = QApplication.instance() or QApplication([])
        combo = QComboBox()
        combo.addItem("A", Command.COMPRESS_HUFF)
        combo.addItem("B", Command.COMPRESS_NPZ)
        combo.setCurrentIndex(1)
        raw = combo.currentData()
        # Either we get the enum back directly, OR Qt hands back the value
        # and our defensive Command(raw) call must reconstruct it.
        if isinstance(raw, Command):
            assert raw is Command.COMPRESS_NPZ
        else:
            assert Command(raw) is Command.COMPRESS_NPZ
        combo.deleteLater()


class TestCodecJobArgv:
    def test_compress_huff_includes_quality(self):
        job = CodecJob(Command.COMPRESS_HUFF, "in.png", "out.icj", quality=75)
        argv = job.argv()
        assert argv[:3] == ["compress_huff", "in.png", "out.icj"]
        assert "--quality" in argv and argv[argv.index("--quality") + 1] == "75"

    def test_decompress_does_not_include_quality(self):
        job = CodecJob(Command.DECOMPRESS_HUFF, "in.icj", "out.png")
        argv = job.argv()
        assert argv == ["decompress_huff", "in.icj", "out.png"]

    def test_quality_defaults_to_50_when_none(self):
        job = CodecJob(Command.COMPRESS_HUFF, "a", "b", quality=None)
        assert "50" in job.argv()

    def test_quality_is_clamped_in_argv(self):
        job = CodecJob(Command.COMPRESS_NPZ, "a", "b", quality=500)
        assert "100" in job.argv()


# ---- format_invocation (only runs when backend is available) -------------


def _backend_available() -> bool:
    try:
        resolve_script_path()
    except FileNotFoundError:
        return False
    return True


@pytest.mark.skipif(not _backend_available(), reason="External compressor not installed")
class TestFormatInvocation:
    def test_round_trip_shape(self):
        job = CodecJob(Command.COMPRESS_HUFF, "foo.png", "bar.icj", quality=42)
        cmd = format_invocation(job)
        assert "compression.py" in cmd
        assert "compress_huff" in cmd
        assert "--quality" in cmd
        assert "42" in cmd


# ---- End-to-end round trip (only runs when backend + sample image exist) -


def _find_sample_image() -> str | None:
    try:
        script = resolve_script_path()
    except FileNotFoundError:
        return None
    candidate = script.parent / "dog.png"
    return str(candidate) if candidate.is_file() else None


SAMPLE_IMAGE = _find_sample_image()


@pytest.mark.skipif(
    SAMPLE_IMAGE is None,
    reason="External compressor and sample image not available",
)
class TestRoundTrip:
    def test_compress_huff_then_decompress_huff_produces_image(self, tmp_path):
        compressed = tmp_path / "out.icj"
        restored = tmp_path / "restored.png"

        r1 = run_codec(
            CodecJob(Command.COMPRESS_HUFF, SAMPLE_IMAGE, str(compressed), quality=50),
            timeout=60,
        )
        assert r1.success, r1.error_message
        assert compressed.is_file() and compressed.stat().st_size > 0

        r2 = run_codec(
            CodecJob(Command.DECOMPRESS_HUFF, str(compressed), str(restored)),
            timeout=60,
        )
        assert r2.success, r2.error_message
        assert restored.is_file() and restored.stat().st_size > 0

    def test_failure_surfaces_error_message(self, tmp_path):
        # Point at a non-existent input to trigger a non-zero exit.
        bad = tmp_path / "missing.png"
        out = tmp_path / "out.icj"
        result = run_codec(
            CodecJob(Command.COMPRESS_HUFF, str(bad), str(out), quality=50),
            timeout=20,
        )
        assert result.success is False
        assert result.error_message  # has something meaningful
