from __future__ import annotations

import json
import subprocess
import sys
import webbrowser
from pathlib import Path

from .audio import (
    build_export_segment_commands,
    build_ffprobe_duration_command,
    build_waveform_image_command,
    parse_duration,
    selected_range,
)
from .engines import ENGINE_HOME_PAGES, ENGINE_NAMES, EngineConfig, validate_engine
from .jobs import Job, create_job
from .paths import ensure_app_dirs
from .transcription import transcribe_job


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
        from PySide6.QtCore import QObject, QThread, Qt, QUrl, Signal
        from PySide6.QtGui import QPixmap
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QApplication,
            QComboBox,
            QDoubleSpinBox,
            QFileDialog,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QMessageBox,
            QProgressBar,
            QPushButton,
            QPlainTextEdit,
            QSpinBox,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        print("PySide6 is not installed. Run: pip install -e .", file=sys.stderr)
        return 1

    class JobWorker(QObject):
        log = Signal(str)
        failed = Signal(str)
        finished = Signal(str)

        def __init__(self, job, configs: list[EngineConfig]) -> None:
            super().__init__()
            self.job = job
            self.configs = configs
            self.stop_requested = False

        def stop(self) -> None:
            self.stop_requested = True

        def run(self) -> None:
            try:
                outputs = []
                for config in self.configs:
                    if self.stop_requested:
                        raise RuntimeError("Job stopped")
                    outputs.append(
                        transcribe_job(
                            self.job,
                            config,
                            should_stop=lambda: self.stop_requested,
                            on_log=self.log.emit,
                        )
                    )
                self.finished.emit("\n".join(str(path) for path in outputs))
            except Exception as exc:  # noqa: BLE001 - surface tool/runtime errors to the UI.
                self.failed.emit(str(exc))

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.config = _load_config()
            self.input_path: Path | None = None
            self.total_duration = 0.0
            self.job_thread: QThread | None = None
            self.job_worker: JobWorker | None = None
            self.setWindowTitle("Meet Note Gen")
            self.resize(960, 620)

            self.audio_output = QAudioOutput()
            self.player = QMediaPlayer()
            self.player.setAudioOutput(self.audio_output)

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
            self.play_button.setToolTip("Play the opened audio.")
            self.stop_button.setToolTip("Stop playback.")
            self.export_button.setToolTip("Export the selected range as split WAV segments.")
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
            self.start_spin = self.time_spin()
            self.end_spin = self.time_spin()
            self.cut_last_spin = self.time_spin()
            self.set_start_button = QPushButton("Set Start")
            self.set_end_button = QPushButton("Set End")
            self.cut_last_button = QPushButton("Cut Last")
            for widget in (self.start_spin, self.end_spin, self.cut_last_spin, self.set_start_button, self.set_end_button, self.cut_last_button):
                widget.setEnabled(False)
            controls.addWidget(QLabel("Start"))
            controls.addWidget(self.start_spin)
            controls.addWidget(self.set_start_button)
            controls.addWidget(QLabel("End"))
            controls.addWidget(self.end_spin)
            controls.addWidget(self.set_end_button)
            controls.addWidget(QLabel("Last"))
            controls.addWidget(self.cut_last_spin)
            controls.addWidget(self.cut_last_button)
            controls.addStretch(1)
            controls.addWidget(QLabel("Split"))
            self.split_spin = QSpinBox()
            self.split_spin.setRange(1, 99)
            self.split_spin.setValue(1)
            self.split_spin.setEnabled(False)
            controls.addWidget(self.split_spin)
            for text in ("2", "3", "4", "5"):
                button = QPushButton(text)
                button.setEnabled(False)
                button.clicked.connect(lambda _=False, value=int(text): self.split_spin.setValue(value))
                controls.addWidget(button)
                setattr(self, f"split_{text}_button", button)
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
            self.resume_button = QPushButton("Resume Job")
            self.stop_job_button = QPushButton("Stop Job")
            self.transcribe_button.setEnabled(False)
            self.compare_button.setEnabled(False)
            self.transcribe_button.setToolTip("Transcribe with the selected ready model.")
            self.compare_button.setToolTip("Transcribe with every ready model.")
            self.stop_job_button.setEnabled(False)
            self.progress = QProgressBar()
            self.progress.setRange(0, 0)
            self.progress.setVisible(False)
            chunk_label = QLabel("Chunk size")
            chunk_label.setBuddy(self.chunk_combo)
            job_row.addWidget(chunk_label)
            job_row.addWidget(self.chunk_combo)
            job_row.addStretch(1)
            job_row.addWidget(self.transcribe_button)
            job_row.addWidget(self.compare_button)
            job_row.addWidget(self.resume_button)
            job_row.addWidget(self.stop_job_button)
            job_row.addWidget(self.progress)
            layout.addLayout(job_row)

            self.log = QPlainTextEdit()
            self.log.setReadOnly(True)
            self.log.setAccessibleName("Job log")
            layout.addWidget(self.log)
            self.setCentralWidget(root)

            self.open_button.clicked.connect(self.open_file)
            self.model_combo.currentIndexChanged.connect(lambda _index: self.update_action_state())
            self.play_button.clicked.connect(self.player.play)
            self.stop_button.clicked.connect(self.player.stop)
            self.set_start_button.clicked.connect(self.set_start_from_player)
            self.set_end_button.clicked.connect(self.set_end_from_player)
            self.cut_last_button.clicked.connect(self.apply_cut_last)
            self.export_button.clicked.connect(self.export_segments)
            self.transcribe_button.clicked.connect(self.transcribe_selected)
            self.compare_button.clicked.connect(self.compare_models)
            self.resume_button.clicked.connect(self.resume_job)
            self.stop_job_button.clicked.connect(self.stop_job)
            self.refresh_engines()

        def time_spin(self) -> QDoubleSpinBox:
            spin = QDoubleSpinBox()
            spin.setRange(0, 24 * 60 * 60)
            spin.setDecimals(1)
            spin.setSuffix(" sec")
            return spin

        def set_editing_enabled(self, enabled: bool) -> None:
            for widget in (
                self.start_spin,
                self.end_spin,
                self.cut_last_spin,
                self.set_start_button,
                self.set_end_button,
                self.cut_last_button,
                self.split_spin,
                self.split_2_button,
                self.split_3_button,
                self.split_4_button,
                self.split_5_button,
            ):
                widget.setEnabled(enabled)

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
            self.player.setSource(QUrl.fromLocalFile(str(self.input_path)))
            self.play_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.log.appendPlainText(f"Opened: {self.input_path}")
            self.probe_duration()
            self.render_waveform_preview()
            self.update_action_state()

        def probe_duration(self) -> None:
            if self.input_path is None:
                return
            self.total_duration = 0
            self.set_editing_enabled(False)
            result = subprocess.run(
                build_ffprobe_duration_command(self.input_path),
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.log.appendPlainText("Could not read duration. Check ffprobe in PATH.")
                return
            try:
                self.total_duration = parse_duration(result.stdout)
            except ValueError as exc:
                self.log.appendPlainText(str(exc))
                return
            self.start_spin.setValue(0)
            self.end_spin.setValue(self.total_duration)
            self.set_editing_enabled(True)
            self.log.appendPlainText(f"Duration: {self.total_duration:.1f} sec")

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

        def current_range(self):
            if self.total_duration <= 0:
                raise ValueError("Open an audio file with readable duration first.")
            return selected_range(
                self.total_duration,
                self.start_spin.value(),
                self.end_spin.value(),
                self.cut_last_spin.value(),
            )

        def set_start_from_player(self) -> None:
            self.start_spin.setValue(round(self.player.position() / 1000, 1))

        def set_end_from_player(self) -> None:
            self.end_spin.setValue(round(self.player.position() / 1000, 1))

        def apply_cut_last(self) -> None:
            if self.total_duration <= 0:
                return
            self.end_spin.setValue(max(0, self.total_duration - self.cut_last_spin.value()))

        def export_segments(self) -> None:
            if self.input_path is None:
                return
            output_dir = QFileDialog.getExistingDirectory(self, "Choose export folder")
            if not output_dir:
                return
            try:
                commands = build_export_segment_commands(
                    self.input_path,
                    output_dir,
                    self.current_range(),
                    self.split_spin.value(),
                )
                for command in commands:
                    self.log.appendPlainText(f"Exporting: {Path(command[-1]).name}")
                    result = subprocess.run(command, capture_output=True, text=True, check=False)
                    if result.returncode != 0:
                        raise RuntimeError(result.stderr.strip() or "ffmpeg export failed")
            except Exception as exc:  # noqa: BLE001 - show actionable UI error.
                QMessageBox.warning(self, "Export failed", str(exc))
                self.log.appendPlainText(f"Export failed: {exc}")
                return
            self.log.appendPlainText(f"Exported {len(commands)} segment(s) to {output_dir}")

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
                page_button = QPushButton("Open Page")
                exe_button.clicked.connect(lambda _=False, key=engine_id: self.choose_executable(key))
                model_button.clicked.connect(lambda _=False, key=engine_id: self.choose_model(key))
                page_button.clicked.connect(lambda _=False, key=engine_id: webbrowser.open(ENGINE_HOME_PAGES[key]))
                buttons.addWidget(exe_button, 0, 0)
                buttons.addWidget(model_button, 0, 1)
                buttons.addWidget(page_button, 0, 2)
                self.engine_table.setCellWidget(row, 4, action)
            self.update_action_state()

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

        def engine_config(self, engine_id: str) -> EngineConfig:
            entry = self.config.setdefault("engines", {}).setdefault(engine_id, {})
            return EngineConfig(engine_id, Path(entry.get("executable", "")), Path(entry.get("model_path", "")))

        def ready_engine_configs(self) -> list[EngineConfig]:
            configs = [self.engine_config(engine_id) for engine_id in ENGINE_NAMES]
            return [config for config in configs if validate_engine(config).ok]

        def selected_engine_config(self) -> EngineConfig | None:
            config = self.engine_config(self.model_combo.currentData())
            return config if validate_engine(config).ok else None

        def update_action_state(self) -> None:
            has_input = self.input_path is not None and self.total_duration > 0
            ready = self.ready_engine_configs()
            self.export_button.setEnabled(has_input)
            self.transcribe_button.setEnabled(has_input and self.selected_engine_config() is not None and self.job_thread is None)
            self.compare_button.setEnabled(has_input and len(ready) >= 2 and self.job_thread is None)
            self.resume_button.setEnabled(self.job_thread is None)

        def transcribe_selected(self) -> None:
            config = self.selected_engine_config()
            if config is None:
                QMessageBox.warning(self, "Engine missing", "Choose runner file and model path first.")
                return
            self.start_job([config])

        def compare_models(self) -> None:
            configs = self.ready_engine_configs()
            if len(configs) < 2:
                QMessageBox.warning(self, "Engines missing", "Choose at least 2 ready engines first.")
                return
            self.start_job(configs)

        def start_job(self, configs: list[EngineConfig]) -> None:
            if self.input_path is None:
                return
            try:
                job = create_job(
                    ensure_app_dirs() / "jobs",
                    self.input_path,
                    self.current_range(),
                    self.chunk_combo.currentData(),
                    [config.engine_id for config in configs],
                )
            except Exception as exc:  # noqa: BLE001 - show validation errors to the UI.
                QMessageBox.warning(self, "Job failed", str(exc))
                return
            self.start_job_worker(job, configs)

        def resume_job(self) -> None:
            path = QFileDialog.getExistingDirectory(self, "Choose job folder", str(ensure_app_dirs() / "jobs"))
            if not path:
                return
            try:
                job = Job.load(path)
                configs = [self.engine_config(engine_id) for engine_id in job.state["engine_ids"]]
                configs = [config for config in configs if validate_engine(config).ok]
                if not configs:
                    raise ValueError("Choose runner file and model path for this job first.")
            except Exception as exc:  # noqa: BLE001 - show validation errors to the UI.
                QMessageBox.warning(self, "Resume failed", str(exc))
                return
            self.start_job_worker(job, configs)

        def start_job_worker(self, job: Job, configs: list[EngineConfig]) -> None:
            self.log.appendPlainText(f"Job: {job.root}")
            self.job_thread = QThread()
            self.job_worker = JobWorker(job, configs)
            self.job_worker.moveToThread(self.job_thread)
            self.job_thread.started.connect(self.job_worker.run)
            self.job_worker.log.connect(self.log.appendPlainText)
            self.job_worker.failed.connect(self.job_failed)
            self.job_worker.finished.connect(self.job_finished)
            self.job_worker.failed.connect(self.job_thread.quit)
            self.job_worker.finished.connect(self.job_thread.quit)
            self.job_thread.finished.connect(self.job_worker.deleteLater)
            self.job_thread.finished.connect(self.job_thread.deleteLater)
            self.job_thread.finished.connect(self.clear_job)
            self.progress.setVisible(True)
            self.stop_job_button.setEnabled(True)
            self.resume_button.setEnabled(False)
            self.transcribe_button.setEnabled(False)
            self.compare_button.setEnabled(False)
            self.job_thread.start()

        def stop_job(self) -> None:
            if self.job_worker is not None:
                self.job_worker.stop()
                self.log.appendPlainText("Stop requested. Waiting for current command to finish.")

        def job_failed(self, message: str) -> None:
            self.log.appendPlainText(f"Job failed: {message}")

        def job_finished(self, outputs: str) -> None:
            self.log.appendPlainText(f"Transcript written:\n{outputs}")

        def clear_job(self) -> None:
            self.job_worker = None
            self.job_thread = None
            self.progress.setVisible(False)
            self.stop_job_button.setEnabled(False)
            self.update_action_state()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
