from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .engines import ENGINE_NAMES, EngineConfig, validate_engine
from .paths import ensure_app_dirs
from .audio import build_waveform_image_command


def _config_path() -> Path:
    return ensure_app_dirs() / "config.json"


def _load_config() -> dict:
    path = _config_path()
    if not path.exists():
        return {"engines": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_config(config: dict) -> None:
    _config_path().write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def _display_path(value: str | Path) -> tuple[str, str]:
    text = str(value)
    if not text or text == ".":
        return "", ""
    path = Path(text)
    if len(text) <= 48:
        return text, text
    parent = path.parent.name
    label = f"…/{parent}/{path.name}" if parent else f"…/{path.name}"
    return label, text


def run() -> int:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QApplication,
            QComboBox,
            QFileDialog,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QPushButton,
            QPlainTextEdit,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        print("PySide6 is not installed. Run: pip install -e .", file=sys.stderr)
        return 1

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.config = _load_config()
            self.input_path: Path | None = None
            self.setWindowTitle("Meet Note Gen")
            self.resize(960, 620)

            root = QWidget()
            layout = QVBoxLayout(root)

            toolbar = QHBoxLayout()
            self.open_button = QPushButton("Open Audio")
            self.play_button = QPushButton("Play")
            self.stop_button = QPushButton("Stop Playback")
            self.export_button = QPushButton("Export Segments")
            self.play_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.export_button.setEnabled(False)
            self.play_button.setToolTip("Wire audio output to enable playback.")
            self.stop_button.setToolTip("Wire audio output to enable playback.")
            self.export_button.setToolTip("Wire segment export to enable this.")
            self.model_combo = QComboBox()
            self.model_combo.setAccessibleName("ASR model")
            for engine_id, name in ENGINE_NAMES.items():
                self.model_combo.addItem(name, engine_id)
            toolbar.addWidget(self.open_button)
            toolbar.addWidget(self.play_button)
            toolbar.addWidget(self.stop_button)
            toolbar.addWidget(self.export_button)
            toolbar.addStretch(1)
            model_label = QLabel("Model")
            model_label.setBuddy(self.model_combo)
            toolbar.addWidget(model_label)
            toolbar.addWidget(self.model_combo)
            layout.addLayout(toolbar)

            self.waveform = QLabel("Open an audio file to generate a waveform preview.")
            self.waveform.setAlignment(Qt.AlignCenter)
            self.waveform.setAccessibleName("Waveform preview")
            self.waveform.setMinimumHeight(180)
            self.waveform.setStyleSheet("border: 1px solid #888; background: #111; color: #ddd;")
            self.waveform.setScaledContents(True)
            layout.addWidget(self.waveform)

            controls = QHBoxLayout()
            controls.addWidget(QLabel("Trim"))
            for text in ("Set Start", "Set End", "Cut Last"):
                button = QPushButton(text)
                button.setEnabled(False)
                button.setToolTip("Wire waveform range editing to enable this.")
                controls.addWidget(button)
            controls.addStretch(1)
            controls.addWidget(QLabel("Split"))
            for text in ("2", "3", "4", "5", "Custom"):
                button = QPushButton(text)
                button.setEnabled(False)
                button.setToolTip("Wire segment export to enable this.")
                controls.addWidget(button)
            layout.addLayout(controls)

            self.engine_table = QTableWidget(len(ENGINE_NAMES), 5)
            self.engine_table.setAccessibleName("Engine setup table")
            self.engine_table.setHorizontalHeaderLabels(["Engine", "Status", "Runner", "Model", "Action"])
            self.engine_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.engine_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.engine_table.horizontalHeader().setStretchLastSection(True)
            layout.addWidget(self.engine_table)

            job_row = QHBoxLayout()
            self.chunk_combo = QComboBox()
            self.chunk_combo.setAccessibleName("Chunk size")
            for minutes in (3, 5, 10, 15, 20):
                self.chunk_combo.addItem(f"{minutes} min", minutes * 60)
            self.chunk_combo.setCurrentText("10 min")
            self.transcribe_button = QPushButton("Transcribe")
            self.compare_button = QPushButton("Compare Models")
            self.stop_job_button = QPushButton("Stop Job")
            self.transcribe_button.setEnabled(False)
            self.compare_button.setEnabled(False)
            self.transcribe_button.setToolTip("Wire job execution to enable this.")
            self.compare_button.setToolTip("Wire job execution to enable this.")
            self.stop_job_button.setEnabled(False)
            chunk_label = QLabel("Chunk size")
            chunk_label.setBuddy(self.chunk_combo)
            job_row.addWidget(chunk_label)
            job_row.addWidget(self.chunk_combo)
            job_row.addStretch(1)
            job_row.addWidget(self.transcribe_button)
            job_row.addWidget(self.compare_button)
            job_row.addWidget(self.stop_job_button)
            layout.addLayout(job_row)

            self.log = QPlainTextEdit()
            self.log.setReadOnly(True)
            self.log.setAccessibleName("Job log")
            layout.addWidget(self.log)
            self.setCentralWidget(root)

            self.open_button.clicked.connect(self.open_file)
            self.refresh_engines()

        def open_file(self) -> None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open audio",
                "",
                "Audio Files (*.mp3 *.wav *.m4a *.flac *.aac);;All Files (*)",
            )
            if not path:
                return
            self.input_path = Path(path)
            self.log.appendPlainText(f"Opened: {self.input_path}")
            self.render_waveform_preview()

        def render_waveform_preview(self) -> None:
            if self.input_path is None:
                return
            output_path = ensure_app_dirs() / "waveform-preview.png"
            command = build_waveform_image_command(self.input_path, output_path, 1600, 220)
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                self.waveform.setText(str(self.input_path))
                self.log.appendPlainText("Waveform preview failed. Check ffmpeg in PATH.")
                if result.stderr:
                    self.log.appendPlainText(result.stderr.strip())
                return
            pixmap = QPixmap(str(output_path))
            if pixmap.isNull():
                self.waveform.setText(str(self.input_path))
                self.log.appendPlainText("Waveform preview image could not be loaded.")
                return
            self.waveform.setPixmap(pixmap)
            self.log.appendPlainText("Waveform preview ready.")

        def refresh_engines(self) -> None:
            for row, (engine_id, name) in enumerate(ENGINE_NAMES.items()):
                entry = self.config.setdefault("engines", {}).setdefault(engine_id, {})
                executable = Path(entry.get("executable", ""))
                model_path = Path(entry.get("model_path", ""))
                status = validate_engine(EngineConfig(engine_id, executable, model_path))
                self.engine_table.setItem(row, 0, self.read_only_item(name))
                self.engine_table.setItem(row, 1, self.read_only_item(status.message))
                exe_label, exe_tip = _display_path(executable)
                model_label, model_tip = _display_path(model_path)
                self.engine_table.setItem(row, 2, self.read_only_item(exe_label, exe_tip))
                self.engine_table.setItem(row, 3, self.read_only_item(model_label, model_tip))
                action = QWidget()
                buttons = QGridLayout(action)
                buttons.setContentsMargins(0, 0, 0, 0)
                exe_button = QPushButton("Choose Runner File")
                model_button = QPushButton("Choose Model")
                exe_button.clicked.connect(lambda _=False, key=engine_id: self.choose_executable(key))
                model_button.clicked.connect(lambda _=False, key=engine_id: self.choose_model(key))
                buttons.addWidget(exe_button, 0, 0)
                buttons.addWidget(model_button, 0, 1)
                self.engine_table.setCellWidget(row, 4, action)

        def read_only_item(self, text: str, tooltip: str = "") -> QTableWidgetItem:
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if tooltip:
                item.setToolTip(tooltip)
            return item

        def choose_executable(self, engine_id: str) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Choose runner file")
            if path:
                self.config["engines"][engine_id]["executable"] = path
                _save_config(self.config)
                self.refresh_engines()

        def choose_model(self, engine_id: str) -> None:
            if engine_id == "whisper":
                path, _ = QFileDialog.getOpenFileName(self, "Choose Whisper model")
            else:
                path = QFileDialog.getExistingDirectory(self, "Choose model folder")
            if path:
                self.config["engines"][engine_id]["model_path"] = path
                _save_config(self.config)
                self.refresh_engines()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
