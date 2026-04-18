"""Kevin Compressor — image compression module for OpenKev.

UI responsibilities only. All actual encoding/decoding work is delegated to
the external ``compression.py`` backend via :mod:`apps.KevinCompressor.backend`.

Layout
------
The module is a :class:`KevModule` with two inner tabs:

* **Compress** — pick an input image, pick an output file, choose a format
  (ICJ Huffman or NPZ), set a quality factor, see a live preview of the
  input image, run the job, then see the reconstructed preview next to it.
* **Decompress** — pick a compressed file (ICJ or NPZ), pick an output image,
  run the job, see the reconstructed preview.

Every job runs on a :class:`CompressorWorker` thread so the UI stays
responsive. The backend is **grayscale-only** — we surface that clearly in
the UI, and the preview panes always display images as grayscale to match.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSizePolicy,
    QSlider, QStatusBar, QTabWidget, QVBoxLayout, QWidget,
)

from apps.KevinCompressor.backend import (
    CodecJob, Command, CompressorWorker, clamp_quality, resolve_script_path,
)
from apps.kev_module import KevModule


IMAGE_EXTS = "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.tif *.webp"
IMAGE_FILTER = f"Images ({IMAGE_EXTS})"
ICJ_FILTER = "Kev Compressed Image (*.icj)"
NPZ_FILTER = "NumPy Compressed (*.npz)"
PNG_FILTER = "PNG Image (*.png)"
PREVIEW_MAX_PX = 420


#: Map from a compress command to the matching decompress command so the
#: pipeline can round-trip a single format selection end-to-end.
_DECOMPRESS_FOR = {
    Command.COMPRESS_HUFF: Command.DECOMPRESS_HUFF,
    Command.COMPRESS_NPZ: Command.DECOMPRESS_NPZ,
}

#: Extension used for the intermediate compressed file, keyed by command.
_INTERMEDIATE_EXT = {
    Command.COMPRESS_HUFF: ".icj",
    Command.COMPRESS_NPZ: ".npz",
}


# ---- Shared building blocks ----------------------------------------------


class _FilePicker(QWidget):
    """A QLineEdit + Browse button with a configurable mode (open/save + filter)."""

    changed = Signal(str)

    def __init__(
        self,
        *,
        label: str,
        mode: str,  # "open" or "save"
        file_filter: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._filter = file_filter

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(label)
        self._label.setFixedWidth(100)
        self._edit = QLineEdit()
        self._edit.setPlaceholderText("(no file selected)")
        self._edit.textChanged.connect(self.changed)
        self._browse = QPushButton("Browse…")
        self._browse.clicked.connect(self._open_dialog)

        layout.addWidget(self._label)
        layout.addWidget(self._edit, 1)
        layout.addWidget(self._browse)

    def path(self) -> str:
        return self._edit.text().strip()

    def set_path(self, path: str) -> None:
        self._edit.setText(path)

    def _open_dialog(self) -> None:
        if self._mode == "open":
            path, _ = QFileDialog.getOpenFileName(self, "Select file", "", self._filter)
        else:
            path, _ = QFileDialog.getSaveFileName(self, "Save as", "", self._filter)
        if path:
            self._edit.setText(path)


class _ImagePreview(QLabel):
    """Grayscale-friendly image preview pane with an empty placeholder state."""

    def __init__(self, caption: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._caption = caption
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(PREVIEW_MAX_PX // 2, PREVIEW_MAX_PX // 2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QLabel { background: #fafafa; color: #888; }")
        self.clear_preview()

    def clear_preview(self) -> None:
        self.setText(f"{self._caption}\n(no image)")
        self._current_path: str | None = None

    def set_image(self, path: str) -> None:
        self._current_path = path
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.setText(f"{self._caption}\n(preview unavailable)")
            return
        scaled = pixmap.scaled(
            PREVIEW_MAX_PX, PREVIEW_MAX_PX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)


# ---- Mode tabs -----------------------------------------------------------


class _CompressTab(QWidget):
    """Full compress -> decompress pipeline that lands on a user-visible PNG.

    Pressing **Compress** runs the codec in two stages back-to-back:

    1. Compress the chosen input image into a temporary intermediate file
       (``<output>.icj`` or ``<output>.npz``, sibling to the output PNG).
    2. Decompress that intermediate back into the user's chosen ``.png``.

    After the pipeline completes, the intermediate is deleted (or kept if
    the user ticks "Keep compressed intermediate"). The output preview
    shows the final PNG — the real lossy result at the chosen quality.
    """

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Pipeline state. ``_worker`` is non-None while any stage is running.
        self._worker: CompressorWorker | None = None
        self._intermediate_path: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ---- Settings ----
        settings = QGroupBox("Settings")
        form = QFormLayout(settings)

        self._input_picker = _FilePicker(
            label="Input image:", mode="open", file_filter=IMAGE_FILTER,
        )
        self._input_picker.changed.connect(self._on_input_changed)

        self._output_picker = _FilePicker(
            label="Output PNG:", mode="save", file_filter=PNG_FILTER,
        )

        self._format_combo = QComboBox()
        self._format_combo.addItem("ICJ (Huffman)", Command.COMPRESS_HUFF)
        self._format_combo.addItem("NPZ (raw coefficients)", Command.COMPRESS_NPZ)

        self._quality_slider = QSlider(Qt.Orientation.Horizontal)
        self._quality_slider.setRange(1, 100)
        self._quality_slider.setValue(50)
        self._quality_slider.setTickInterval(10)
        self._quality_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._quality_value = QLabel("50")
        self._quality_value.setFixedWidth(32)
        self._quality_slider.valueChanged.connect(
            lambda v: self._quality_value.setText(str(v))
        )
        quality_row = QHBoxLayout()
        quality_row.addWidget(self._quality_slider, 1)
        quality_row.addWidget(self._quality_value)

        self._keep_intermediate = QCheckBox(
            "Keep compressed intermediate (.icj / .npz) next to the PNG"
        )

        form.addRow(self._input_picker)
        form.addRow(self._output_picker)
        form.addRow("Format:", self._format_combo)
        form.addRow("Quality:", _wrap(quality_row))
        form.addRow(self._keep_intermediate)
        layout.addWidget(settings)

        # ---- Previews ----
        previews = QHBoxLayout()
        self._input_preview = _ImagePreview("Input")
        self._output_preview = _ImagePreview("Reconstructed PNG")
        previews.addWidget(self._input_preview)
        previews.addWidget(self._output_preview)
        layout.addLayout(previews, 1)

        # ---- Action row ----
        actions = QHBoxLayout()
        self._run_button = QPushButton("Compress")
        self._run_button.clicked.connect(self._run_pipeline)
        actions.addStretch()
        actions.addWidget(self._run_button)
        layout.addLayout(actions)

    # ---- small helpers --------------------------------------------------

    def _on_input_changed(self, path: str) -> None:
        path = path.strip()
        if path and os.path.isfile(path):
            self._input_preview.set_image(path)
        else:
            self._input_preview.clear_preview()

    def _current_compress_command(self) -> Command:
        # See backend.Command docstring for why this normalization exists.
        raw = self._format_combo.currentData()
        if isinstance(raw, Command):
            return raw
        return Command(raw)

    def _pipeline_running(self) -> bool:
        return self._worker is not None

    def _cleanup_intermediate(self) -> None:
        path = self._intermediate_path
        self._intermediate_path = None
        if not path:
            return
        if self._keep_intermediate.isChecked():
            return
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            # Non-fatal; surface in the status line so the user notices.
            self.status_message.emit(
                f"Note: could not delete intermediate {os.path.basename(path)}"
            )

    # ---- Pipeline orchestration ----------------------------------------

    def _run_pipeline(self) -> None:
        if self._pipeline_running():
            return
        in_path = self._input_picker.path()
        out_png = self._output_picker.path()
        if not in_path or not os.path.isfile(in_path):
            QMessageBox.warning(self, "Missing input", "Pick an existing input image.")
            return
        if not out_png:
            QMessageBox.warning(self, "Missing output", "Pick an output PNG path.")
            return

        # Force .png on the output so the final file is always viewable.
        if not out_png.lower().endswith(".png"):
            out_png += ".png"
            self._output_picker.set_path(out_png)

        # Intermediate sits next to the output, same base name, codec extension.
        compress_cmd = self._current_compress_command()
        root, _ = os.path.splitext(out_png)
        intermediate = root + _INTERMEDIATE_EXT[compress_cmd]
        self._intermediate_path = intermediate

        # Clear any stale reconstructed preview from a previous run.
        self._output_preview.clear_preview()

        # Stage 1 — compress into the intermediate.
        compress_job = CodecJob(
            command=compress_cmd,
            input_path=in_path,
            output_path=intermediate,
            quality=clamp_quality(self._quality_slider.value()),
        )
        self._run_button.setEnabled(False)
        self.status_message.emit(
            f"Compressing → {os.path.basename(intermediate)} "
            f"(q={compress_job.quality})…"
        )
        self._worker = self._spawn_worker(
            compress_job,
            on_success=self._on_compress_done,
            on_failure=self._on_pipeline_failure,
        )

    def _on_compress_done(self, _result) -> None:
        self._worker = None
        intermediate = self._intermediate_path
        out_png = self._output_picker.path()
        compress_cmd = self._current_compress_command()
        decomp_cmd = _DECOMPRESS_FOR[compress_cmd]

        if not intermediate or not os.path.isfile(intermediate):
            # Extremely defensive: backend reported success but no file exists.
            self._on_pipeline_failure(
                "Compression stage reported success but the intermediate "
                "file is missing."
            )
            return

        # Stage 2 — decompress into the final PNG.
        self.status_message.emit(
            f"Decompressing → {os.path.basename(out_png)}…"
        )
        decomp_job = CodecJob(
            command=decomp_cmd, input_path=intermediate, output_path=out_png,
        )
        self._worker = self._spawn_worker(
            decomp_job,
            on_success=self._on_pipeline_success,
            on_failure=self._on_pipeline_failure,
        )

    def _on_pipeline_success(self, _result) -> None:
        self._worker = None
        out_png = self._output_picker.path()

        # Preview the actual PNG we just wrote.
        if out_png and os.path.isfile(out_png):
            self._output_preview.set_image(out_png)

        intermediate = self._intermediate_path
        kept = self._keep_intermediate.isChecked()
        self._cleanup_intermediate()

        suffix = ""
        if kept and intermediate:
            suffix = f" (kept {os.path.basename(intermediate)})"
        self.status_message.emit(
            f"Compressed → {os.path.basename(out_png)}{suffix}"
        )
        self._run_button.setEnabled(True)

    def _on_pipeline_failure(self, message: str) -> None:
        self._worker = None
        self._cleanup_intermediate()
        self.status_message.emit("Compression pipeline failed")
        QMessageBox.warning(self, "Compression failed", message)
        self._run_button.setEnabled(True)

    def _spawn_worker(
        self,
        job: CodecJob,
        *,
        on_success,
        on_failure,
    ) -> CompressorWorker:
        worker = CompressorWorker(job, parent=self)
        worker.finished_ok.connect(on_success)
        worker.failed.connect(on_failure)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        return worker


class _DecompressTab(QWidget):
    """Decompress an ICJ/NPZ file back into a viewable image."""

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker: CompressorWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        settings = QGroupBox("Settings")
        form = QFormLayout(settings)
        self._input_picker = _FilePicker(
            label="Input file:", mode="open",
            file_filter=f"Kev Compressed (*.icj *.npz);;{ICJ_FILTER};;{NPZ_FILTER}",
        )
        self._output_picker = _FilePicker(
            label="Output image:", mode="save",
            file_filter="PNG Image (*.png)",
        )
        form.addRow(self._input_picker)
        form.addRow(self._output_picker)
        layout.addWidget(settings)

        self._preview = _ImagePreview("Decoded output")
        layout.addWidget(self._preview, 1)

        actions = QHBoxLayout()
        self._run_button = QPushButton("Decompress")
        self._run_button.clicked.connect(self._run)
        actions.addStretch()
        actions.addWidget(self._run_button)
        layout.addLayout(actions)

    def _run(self) -> None:
        if self._worker is not None:
            return
        in_path = self._input_picker.path()
        out_path = self._output_picker.path()
        if not in_path or not os.path.isfile(in_path):
            QMessageBox.warning(self, "Missing input", "Pick an existing compressed file.")
            return
        if not out_path:
            QMessageBox.warning(self, "Missing output", "Pick an output image path.")
            return
        ext = os.path.splitext(in_path)[1].lower()
        if ext == ".icj":
            command = Command.DECOMPRESS_HUFF
        elif ext == ".npz":
            command = Command.DECOMPRESS_NPZ
        else:
            QMessageBox.warning(
                self, "Unknown format",
                "Input must be an .icj or .npz file (pick one from the dialog).",
            )
            return
        if not out_path.lower().endswith(".png"):
            out_path += ".png"
            self._output_picker.set_path(out_path)

        job = CodecJob(command=command, input_path=in_path, output_path=out_path)
        self._run_button.setEnabled(False)
        self.status_message.emit(f"Decompressing ({command.value})…")
        worker = CompressorWorker(job, parent=self)
        worker.finished_ok.connect(lambda _r: self._on_success())
        worker.failed.connect(self._on_failure)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_success(self) -> None:
        self._run_button.setEnabled(True)
        self._worker = None
        out = self._output_picker.path()
        if out and os.path.isfile(out):
            self._preview.set_image(out)
        self.status_message.emit(f"Decompressed → {os.path.basename(out)}")

    def _on_failure(self, message: str) -> None:
        self._run_button.setEnabled(True)
        self._worker = None
        self.status_message.emit("Decompression failed")
        QMessageBox.warning(self, "Decompression failed", message)


# ---- Module ---------------------------------------------------------------


class KevinCompressor(KevModule):
    """Image compression front-end delegating to the external codec."""

    app_name = "Kevin Compressor"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_banner())

        self._tabs = QTabWidget()
        self._compress_tab = _CompressTab(self)
        self._decompress_tab = _DecompressTab(self)
        self._compress_tab.status_message.connect(self._set_status)
        self._decompress_tab.status_message.connect(self._set_status)
        self._tabs.addTab(self._compress_tab, "Compress")
        self._tabs.addTab(self._decompress_tab, "Decompress")
        layout.addWidget(self._tabs, 1)

        self._status = QStatusBar()
        layout.addWidget(self._status)
        self._set_status(self._initial_status())

    # ---- KevModule interface -------------------------------------------

    @property
    def open_files(self) -> list[str]:
        return []  # Compressor is stateless from a document perspective.

    def focus_file(self, filepath: str) -> None:  # noqa: ARG002
        return None

    # ---- UI helpers -----------------------------------------------------

    def _build_banner(self) -> QWidget:
        banner = QFrame()
        banner.setFrameShape(QFrame.Shape.StyledPanel)
        banner.setStyleSheet(
            "QFrame { background: #eef4ff; border: 1px solid #c6d7f5; }"
        )
        row = QHBoxLayout(banner)
        row.setContentsMargins(10, 6, 10, 6)
        label = QLabel(
            "Kevin Compressor · DCT + quantization codec (grayscale only)"
        )
        label.setStyleSheet("color: #333; font-weight: bold;")
        row.addWidget(label)
        row.addStretch()
        return banner

    def _set_status(self, msg: str) -> None:
        self._status.showMessage(msg)

    def _initial_status(self) -> str:
        try:
            path = resolve_script_path()
            return f"Backend ready: {path}"
        except FileNotFoundError as exc:
            return str(exc)


# ---- Tiny layout helper ---------------------------------------------------


def _wrap(layout) -> QWidget:
    """Wrap a QLayout in an anonymous QWidget so it can be added to a QFormLayout."""
    w = QWidget()
    w.setLayout(layout)
    return w
