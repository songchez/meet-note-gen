from __future__ import annotations

import json
import sys
from pathlib import Path

from .engines import ENGINE_NAMES, EngineConfig, validate_engine
from .paths import ensure_app_dirs


def _config_path() -> Path:
    return ensure_app_dirs() / "config.json"


def _load_config() -> dict:
    path = _config_path()
    if not path.exists():
        return {"engines": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_config(config: dict) -> None:
    _config_path().write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def run() -> int:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
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
            self.open_button = QPushButton("Open")
            self.play_button = QPushButton("Play")
            self.stop_button = QPushButton("Stop")
            self.export_button = QPushButton("Export")
            self.play_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.export_button.setEnabled(False)
            self.model_combo = QComboBox()
            for engine_id, name in ENGINE_NAMES.items():
                self.model_combo.addItem(name, engine_id)
            toolbar.addWidget(self.open_button)
            toolbar.addWidget(self.play_button)
            toolbar.addWidget(self.stop_button)
            toolbar.addWidget(self.export_button)
            toolbar.addStretch(1)
            toolbar.addWidget(QLabel("Model"))
            toolbar.addWidget(self.model_combo)
            layout.addLayout(toolbar)

            self.waveform = QLabel("Open an audio file to prepare chunks.")
            self.waveform.setAlignment(Qt.AlignCenter)
            self.waveform.setMinimumHeight(160)
            self.waveform.setStyleSheet("border: 1px solid #999;")
            layout.addWidget(self.waveform)

            controls = QHBoxLayout()
            controls.addWidget(QLabel("Trim"))
            controls.addWidget(QPushButton("Set Start"))
            controls.addWidget(QPushButton("Set End"))
            controls.addWidget(QPushButton("Cut Last"))
            controls.addStretch(1)
            controls.addWidget(QLabel("Split"))
            for text in ("2", "3", "4", "5", "N"):
                controls.addWidget(QPushButton(text))
            layout.addLayout(controls)

            self.engine_table = QTableWidget(len(ENGINE_NAMES), 5)
            self.engine_table.setHorizontalHeaderLabels(["Engine", "Status", "Executable", "Model", "Action"])
            self.engine_table.horizontalHeader().setStretchLastSection(True)
            layout.addWidget(self.engine_table)

            job_row = QHBoxLayout()
            self.chunk_combo = QComboBox()
            for minutes in (3, 5, 10, 15, 20):
                self.chunk_combo.addItem(f"{minutes} min", minutes * 60)
            self.chunk_combo.setCurrentText("10 min")
            self.transcribe_button = QPushButton("Transcribe")
            self.compare_button = QPushButton("Compare Models")
            self.stop_job_button = QPushButton("Stop")
            self.stop_job_button.setEnabled(False)
            job_row.addWidget(QLabel("Chunk size"))
            job_row.addWidget(self.chunk_combo)
            job_row.addStretch(1)
            job_row.addWidget(self.transcribe_button)
            job_row.addWidget(self.compare_button)
            job_row.addWidget(self.stop_job_button)
            layout.addLayout(job_row)

            self.log = QPlainTextEdit()
            self.log.setReadOnly(True)
            layout.addWidget(self.log)
            self.setCentralWidget(root)

            self.open_button.clicked.connect(self.open_file)
            self.transcribe_button.clicked.connect(self.not_wired)
            self.compare_button.clicked.connect(self.not_wired)
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
            self.waveform.setText(str(self.input_path))
            self.export_button.setEnabled(True)
            self.log.appendPlainText(f"Opened: {self.input_path}")

        def not_wired(self) -> None:
            self.log.appendPlainText("Job execution will be wired after engine smoke tests.")

        def refresh_engines(self) -> None:
            for row, (engine_id, name) in enumerate(ENGINE_NAMES.items()):
                entry = self.config.setdefault("engines", {}).setdefault(engine_id, {})
                executable = Path(entry.get("executable", ""))
                model_path = Path(entry.get("model_path", ""))
                status = validate_engine(EngineConfig(engine_id, executable, model_path))
                self.engine_table.setItem(row, 0, QTableWidgetItem(name))
                self.engine_table.setItem(row, 1, QTableWidgetItem(status.message))
                self.engine_table.setItem(row, 2, QTableWidgetItem(str(executable) if str(executable) != "." else ""))
                self.engine_table.setItem(row, 3, QTableWidgetItem(str(model_path) if str(model_path) != "." else ""))
                action = QWidget()
                buttons = QGridLayout(action)
                buttons.setContentsMargins(0, 0, 0, 0)
                exe_button = QPushButton("Set exe")
                model_button = QPushButton("Set model")
                exe_button.clicked.connect(lambda _=False, key=engine_id: self.choose_executable(key))
                model_button.clicked.connect(lambda _=False, key=engine_id: self.choose_model(key))
                buttons.addWidget(exe_button, 0, 0)
                buttons.addWidget(model_button, 0, 1)
                self.engine_table.setCellWidget(row, 4, action)

        def choose_executable(self, engine_id: str) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Select engine executable")
            if path:
                self.config["engines"][engine_id]["executable"] = path
                _save_config(self.config)
                self.refresh_engines()

        def choose_model(self, engine_id: str) -> None:
            if engine_id == "whisper":
                path, _ = QFileDialog.getOpenFileName(self, "Select Whisper model")
            else:
                path = QFileDialog.getExistingDirectory(self, "Select model folder")
            if path:
                self.config["engines"][engine_id]["model_path"] = path
                _save_config(self.config)
                self.refresh_engines()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
