from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .audio import (
    build_export_segment_commands,
    build_ffprobe_duration_command,
    build_waveform_image_command,
    parse_duration,
    selected_range,
)
from .engines import ENGINE_NAMES, EngineConfig, EngineStatus, validate_engine
from .jobs import Job, create_job
from .model_catalog import catalog_entries
from .model_downloader import download_model
from .paths import ensure_app_dirs
from .recording import next_recording_path
from .runner import run_command
from .transcription import transcribe_job


PRIMARY_ACTION_TEXT = "스크립트 추출"


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


def _qt_import_error_message(exc: BaseException) -> str:
    return (
        f"PySide6/Qt runtime is not available: {exc}\n"
        "Run: pip install -e . and make sure Qt runtime libraries are installed."
    )


def _model_status_text(engine_name: str, ready: bool) -> str:
    return f"모델: {engine_name} 준비됨" if ready else "모델 설정 필요"


def _engine_status_text(status: EngineStatus) -> str:
    if status.ok:
        return "준비됨"
    if status.message == "Choose runner file":
        return "Runner 파일 선택 필요"
    if status.message == "Choose model path":
        return "모델 선택 필요"
    return status.message


def _open_path_command(platform: str, path: str | Path) -> list[str]:
    value = str(path)
    if platform.startswith("win"):
        return ["explorer", value]
    if platform == "darwin":
        return ["open", value]
    return ["xdg-open", value]


def _open_path(path: str | Path) -> None:
    subprocess.Popen(_open_path_command(sys.platform, path))  # noqa: S603 - local file manager command.


APP_STYLESHEET = """
QWidget {
    background: #f7f8fa;
    color: #202124;
    font-size: 12px;
}
QLabel#title {
    font-size: 20px;
    font-weight: 700;
}
QGroupBox {
    background: #ffffff;
    border: 1px solid #d7dbe2;
    border-radius: 6px;
    margin-top: 12px;
    padding: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    font-weight: 600;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #c8ced8;
    border-radius: 5px;
    padding: 6px 12px;
}
QPushButton:hover {
    background: #eef4ff;
    border-color: #8ab4ff;
}
QPushButton:disabled {
    background: #eef0f3;
    color: #8b95a1;
}
QPushButton#primaryAction {
    background: #2563eb;
    color: #ffffff;
    border: 1px solid #1d4ed8;
    border-radius: 6px;
    font-size: 18px;
    font-weight: 700;
    padding: 14px 42px;
}
QPushButton#primaryAction:hover {
    background: #1d4ed8;
}
QPlainTextEdit, QTableWidget, QComboBox, QDoubleSpinBox, QSpinBox {
    background: #ffffff;
    border: 1px solid #c8ced8;
    border-radius: 4px;
    padding: 4px;
}
QLabel#waveform {
    background: #ffffff;
    border: 1px dashed #b7bfcc;
    border-radius: 6px;
    color: #667085;
}
"""


def run() -> int:
    try:
        from PySide6.QtCore import QObject, QThread, QTimer, Qt, QUrl, Signal
        from PySide6.QtGui import QPixmap
        from PySide6.QtMultimedia import (
            QAudioInput,
            QAudioOutput,
            QMediaCaptureSession,
            QMediaFormat,
            QMediaPlayer,
            QMediaRecorder,
        )
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QApplication,
            QComboBox,
            QDialog,
            QDoubleSpinBox,
            QFileDialog,
            QGridLayout,
            QGroupBox,
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
    except ImportError as exc:
        print(_qt_import_error_message(exc), file=sys.stderr)
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

    class ModelDownloadWorker(QObject):
        log = Signal(str)
        failed = Signal(str)
        finished = Signal(str, str)

        def __init__(self, engine_id: str) -> None:
            super().__init__()
            self.engine_id = engine_id

        def run(self) -> None:
            try:
                entry = next(item for item in catalog_entries() if item.engine_id == self.engine_id)
                self.log.emit(f"{entry.name}: 모델 다운로드 시작")
                path = download_model(ensure_app_dirs(), entry)
                self.finished.emit(self.engine_id, str(path))
            except Exception as exc:  # noqa: BLE001 - show download errors in the UI.
                self.failed.emit(str(exc))

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.config = _load_config()
            self.input_path: Path | None = None
            self.total_duration = 0.0
            self.job_thread: QThread | None = None
            self.job_worker: JobWorker | None = None
            self.download_thread: QThread | None = None
            self.download_worker: ModelDownloadWorker | None = None
            self.recording_path: Path | None = None
            self.recording_finishing = False
            self.last_transcript_path: Path | None = None
            self.setWindowTitle("Meet Note Gen")
            self.resize(1080, 720)

            self.audio_output = QAudioOutput()
            self.player = QMediaPlayer()
            self.player.setAudioOutput(self.audio_output)
            self.capture_session = QMediaCaptureSession()
            self.audio_input = QAudioInput()
            self.recorder = QMediaRecorder()
            media_format = QMediaFormat(QMediaFormat.FileFormat.Mpeg4Audio)
            media_format.setAudioCodec(QMediaFormat.AudioCodec.AAC)
            self.recorder.setMediaFormat(media_format)
            self.recorder.setQuality(QMediaRecorder.Quality.HighQuality)
            self.capture_session.setAudioInput(self.audio_input)
            self.capture_session.setRecorder(self.recorder)

            root = QWidget()
            layout = QVBoxLayout(root)

            header = QHBoxLayout()
            title = QLabel("Meet Note Gen")
            title.setObjectName("title")
            self.model_settings_button = QPushButton("모델 설정")
            header.addWidget(title)
            header.addStretch(1)
            header.addWidget(self.model_settings_button)
            layout.addLayout(header)

            input_box = QGroupBox("음성 파일")
            input_layout = QVBoxLayout(input_box)
            input_actions = QHBoxLayout()
            self.open_button = QPushButton("음성 파일 선택")
            self.record_button = QPushButton("녹음 시작")
            self.stop_record_button = QPushButton("녹음 종료")
            self.stop_record_button.setEnabled(False)
            input_actions.addWidget(self.open_button)
            input_actions.addWidget(self.record_button)
            input_actions.addWidget(self.stop_record_button)
            input_actions.addStretch(1)
            input_layout.addLayout(input_actions)
            self.file_label = QLabel("파일을 선택하거나 창에 끌어다 놓으세요.")
            self.file_label.setAccessibleName("Selected audio file")
            self.file_meta_label = QLabel("길이: -")
            self.model_status_label = QLabel(_model_status_text(ENGINE_NAMES["qwen3"], False))
            status_row = QHBoxLayout()
            status_row.addWidget(self.file_label)
            status_row.addStretch(1)
            status_row.addWidget(self.file_meta_label)
            status_row.addWidget(self.model_status_label)
            input_layout.addLayout(status_row)
            layout.addWidget(input_box)

            self.waveform = QLabel("음성 파일을 선택하거나 여기에 끌어다 놓으세요.")
            self.waveform.setAlignment(Qt.AlignCenter)
            self.waveform.setAccessibleName("Waveform preview")
            self.waveform.setObjectName("waveform")
            self.waveform.setMinimumHeight(170)
            self.waveform.setScaledContents(True)
            layout.addWidget(self.waveform)

            playback_row = QHBoxLayout()
            self.play_button = QPushButton("재생")
            self.stop_button = QPushButton("정지")
            self.export_button = QPushButton("구간 내보내기")
            self.play_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.export_button.setEnabled(False)
            self.record_button.setToolTip("Record from the default microphone.")
            self.stop_record_button.setToolTip("Stop recording, load it, and transcribe if the selected model is ready.")
            self.play_button.setToolTip("Play the opened audio.")
            self.stop_button.setToolTip("Stop playback.")
            self.export_button.setToolTip("Export the selected range as split WAV segments.")
            playback_row.addWidget(self.play_button)
            playback_row.addWidget(self.stop_button)
            playback_row.addWidget(self.export_button)
            playback_row.addStretch(1)
            layout.addLayout(playback_row)

            self.advanced_box = QGroupBox("고급 옵션")
            self.advanced_box.setCheckable(True)
            self.advanced_box.setChecked(False)
            advanced_layout = QVBoxLayout(self.advanced_box)
            self.advanced_content = QWidget()
            advanced_content_layout = QVBoxLayout(self.advanced_content)
            controls = QHBoxLayout()
            controls.addWidget(QLabel("자르기"))
            self.start_spin = self.time_spin()
            self.end_spin = self.time_spin()
            self.cut_last_spin = self.time_spin()
            self.set_start_button = QPushButton("시작 지정")
            self.set_end_button = QPushButton("끝 지정")
            self.cut_last_button = QPushButton("끝에서 자르기")
            for widget in (self.start_spin, self.end_spin, self.cut_last_spin, self.set_start_button, self.set_end_button, self.cut_last_button):
                widget.setEnabled(False)
            controls.addWidget(QLabel("시작"))
            controls.addWidget(self.start_spin)
            controls.addWidget(self.set_start_button)
            controls.addWidget(QLabel("끝"))
            controls.addWidget(self.end_spin)
            controls.addWidget(self.set_end_button)
            controls.addWidget(QLabel("끝부분"))
            controls.addWidget(self.cut_last_spin)
            controls.addWidget(self.cut_last_button)
            controls.addStretch(1)
            controls.addWidget(QLabel("균등 분할"))
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
            advanced_content_layout.addLayout(controls)

            job_row = QHBoxLayout()
            self.chunk_combo = QComboBox()
            self.chunk_combo.setAccessibleName("Chunk size")
            for minutes in (3, 5, 10, 15, 20):
                self.chunk_combo.addItem(f"{minutes} min", minutes * 60)
            self.chunk_combo.setCurrentText("10 min")
            self.compare_button = QPushButton("모델 비교")
            self.resume_button = QPushButton("작업 이어하기")
            self.stop_job_button = QPushButton("작업 중지")
            self.compare_button.setEnabled(False)
            self.compare_button.setToolTip("준비된 모든 모델로 같은 음성을 비교합니다.")
            self.stop_job_button.setEnabled(False)
            self.progress = QProgressBar()
            self.progress.setRange(0, 0)
            self.progress.setVisible(False)
            chunk_label = QLabel("Chunk")
            chunk_label.setBuddy(self.chunk_combo)
            job_row.addWidget(chunk_label)
            job_row.addWidget(self.chunk_combo)
            job_row.addStretch(1)
            job_row.addWidget(self.compare_button)
            job_row.addWidget(self.resume_button)
            job_row.addWidget(self.stop_job_button)
            advanced_content_layout.addLayout(job_row)
            advanced_layout.addWidget(self.advanced_content)
            self.advanced_content.setVisible(False)
            layout.addWidget(self.advanced_box)

            primary_row = QHBoxLayout()
            primary_row.addStretch(1)
            self.transcribe_button = QPushButton(PRIMARY_ACTION_TEXT)
            self.transcribe_button.setObjectName("primaryAction")
            self.transcribe_button.setEnabled(False)
            self.transcribe_button.setToolTip("선택한 음성 파일에서 스크립트를 추출합니다.")
            primary_row.addWidget(self.transcribe_button)
            primary_row.addWidget(self.progress)
            primary_row.addStretch(1)
            layout.addLayout(primary_row)

            result_box = QGroupBox("결과")
            result_layout = QVBoxLayout(result_box)
            self.result_preview = QPlainTextEdit()
            self.result_preview.setReadOnly(True)
            self.result_preview.setPlaceholderText("추출된 스크립트가 여기에 표시됩니다.")
            self.result_preview.setAccessibleName("Transcript preview")
            result_layout.addWidget(self.result_preview)
            result_actions = QHBoxLayout()
            self.open_txt_button = QPushButton("TXT 열기")
            self.open_json_button = QPushButton("JSON 열기")
            self.open_folder_button = QPushButton("결과 폴더 열기")
            for widget in (self.open_txt_button, self.open_json_button, self.open_folder_button):
                widget.setEnabled(False)
                result_actions.addWidget(widget)
            result_actions.addStretch(1)
            result_layout.addLayout(result_actions)
            layout.addWidget(result_box)

            self.log = QPlainTextEdit()
            self.log.setReadOnly(True)
            self.log.setAccessibleName("Detailed job log")
            self.log.setMaximumHeight(96)
            self.log.setPlaceholderText("상세 로그")
            layout.addWidget(self.log)
            self.setCentralWidget(root)
            self.setAcceptDrops(True)

            self.open_button.clicked.connect(self.open_file)
            self.model_settings_button.clicked.connect(self.show_model_settings)
            self.record_button.clicked.connect(self.start_recording)
            self.stop_record_button.clicked.connect(self.stop_recording)
            self.recorder.recorderStateChanged.connect(self.recording_state_changed)
            self.recorder.errorOccurred.connect(self.recording_error)
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
            self.open_txt_button.clicked.connect(self.open_transcript)
            self.open_json_button.clicked.connect(self.open_transcript_json)
            self.open_folder_button.clicked.connect(self.open_result_folder)
            self.advanced_box.toggled.connect(self.advanced_content.setVisible)
            self.refresh_engines()
            QTimer.singleShot(0, self.show_model_settings_if_needed)

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
                "음성 파일 선택",
                "",
                "Audio Files (*.mp3 *.wav *.m4a *.flac *.aac);;All Files (*)",
            )
            if not path:
                return
            self.load_audio(Path(path), auto_transcribe=False)

        def load_audio(self, path: Path, auto_transcribe: bool) -> None:
            self.input_path = path
            self.last_transcript_path = None
            self.player.setSource(QUrl.fromLocalFile(str(self.input_path)))
            self.play_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.file_label.setText(f"선택된 파일: {self.input_path.name}")
            self.file_label.setToolTip(str(self.input_path))
            self.result_preview.clear()
            for widget in (self.open_txt_button, self.open_json_button, self.open_folder_button):
                widget.setEnabled(False)
            self.log.appendPlainText(f"Opened: {self.input_path}")
            self.probe_duration()
            self.render_waveform_preview()
            self.update_action_state()
            if auto_transcribe:
                self.transcribe_recording_if_ready()

        def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override.
            if event.mimeData().hasUrls():
                event.acceptProposedAction()

        def dropEvent(self, event) -> None:  # noqa: N802 - Qt override.
            urls = event.mimeData().urls()
            if urls:
                self.load_audio(Path(urls[0].toLocalFile()), auto_transcribe=False)

        def start_recording(self) -> None:
            self.player.stop()
            self.recording_path = next_recording_path(ensure_app_dirs())
            self.recording_path.parent.mkdir(parents=True, exist_ok=True)
            self.recording_finishing = False
            self.recorder.setOutputLocation(QUrl.fromLocalFile(str(self.recording_path)))
            self.recorder.record()
            self.update_action_state()
            self.log.appendPlainText(f"Recording: {self.recording_path}")

        def stop_recording(self) -> None:
            self.recording_finishing = True
            self.stop_record_button.setEnabled(False)
            self.recorder.stop()

        def recording_state_changed(self, state) -> None:
            if state != QMediaRecorder.RecorderState.StoppedState:
                self.update_action_state()
                return
            self.update_action_state()
            if not self.recording_finishing or self.recording_path is None:
                return
            path = self.recording_path
            self.recording_path = None
            self.recording_finishing = False
            if not path.exists():
                self.log.appendPlainText("Recording stopped, but no output file was written.")
                return
            self.log.appendPlainText(f"Recording saved: {path}")
            self.load_audio(path, auto_transcribe=True)

        def recording_error(self, _error, message: str) -> None:
            if message:
                self.log.appendPlainText(f"Recording failed: {message}")
            self.recording_path = None
            self.recording_finishing = False
            self.update_action_state()

        def transcribe_recording_if_ready(self) -> None:
            config = self.selected_engine_config()
            if config is None:
                self.log.appendPlainText("Recording loaded. Choose a ready model to transcribe.")
                return
            self.log.appendPlainText(f"Auto transcribing recording with {ENGINE_NAMES[config.engine_id]}.")
            self.start_job([config])

        def probe_duration(self) -> None:
            if self.input_path is None:
                return
            self.total_duration = 0
            self.set_editing_enabled(False)
            result = run_command(
                build_ffprobe_duration_command(self.input_path),
                ensure_app_dirs(),
            )
            if result.returncode != 0:
                self.log.appendPlainText("Could not read duration. Check ffprobe in PATH.")
                return
            try:
                self.total_duration = parse_duration(result.stdout)
            except ValueError as exc:
                self.log.appendPlainText(str(exc))
                self.file_meta_label.setText("길이: 확인 실패")
                return
            self.start_spin.setValue(0)
            self.end_spin.setValue(self.total_duration)
            self.set_editing_enabled(True)
            self.file_meta_label.setText(f"길이: {self.total_duration:.1f}초")
            self.log.appendPlainText(f"Duration: {self.total_duration:.1f} sec")

        def render_waveform_preview(self) -> None:
            if self.input_path is None:
                return
            output_path = ensure_app_dirs() / "waveform-preview.png"
            command = build_waveform_image_command(self.input_path, output_path, 1600, 220)
            result = run_command(command, ensure_app_dirs())
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
                    result = run_command(command, ensure_app_dirs())
                    if result.returncode != 0:
                        raise RuntimeError(result.stderr.strip() or "ffmpeg export failed")
            except Exception as exc:  # noqa: BLE001 - show actionable UI error.
                QMessageBox.warning(self, "Export failed", str(exc))
                self.log.appendPlainText(f"Export failed: {exc}")
                return
            self.log.appendPlainText(f"Exported {len(commands)} segment(s) to {output_dir}")

        def refresh_engines(self) -> None:
            config = self.selected_engine_config()
            if config is None:
                self.model_status_label.setText(_model_status_text(ENGINE_NAMES["qwen3"], False))
            else:
                self.model_status_label.setText(_model_status_text(ENGINE_NAMES[config.engine_id], True))
            self.update_action_state()

        def show_model_settings_if_needed(self) -> None:
            if not self.ready_engine_configs():
                self.show_model_settings()

        def show_model_settings(self) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle("모델 설정")
            dialog.resize(980, 360)
            layout = QVBoxLayout(dialog)
            intro = QLabel("추천 모델을 준비한 뒤 음성 파일에서 스크립트를 추출할 수 있습니다.")
            layout.addWidget(intro)
            table = QTableWidget(len(catalog_entries()), 4)
            table.setHorizontalHeaderLabels(["모델", "상태", "설명", "작업"])
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.horizontalHeader().setStretchLastSection(True)
            layout.addWidget(table)

            def set_selected(engine_id: str) -> None:
                self.config["selected_engine_id"] = engine_id
                _save_config(self.config)
                self.refresh_engines()
                refresh_table()

            def refresh_table() -> None:
                selected_config = self.selected_engine_config()
                selected = selected_config.engine_id if selected_config is not None else self.config.get("selected_engine_id", "qwen3")
                for row, catalog in enumerate(catalog_entries()):
                    config = self.engine_config(catalog.engine_id)
                    status = validate_engine(config)
                    status_text = "사용 중" if status.ok and selected == catalog.engine_id else _engine_status_text(status)
                    table.setItem(row, 0, self.read_only_item(catalog.name))
                    table.setItem(row, 1, self.read_only_item(status_text))
                    table.setItem(row, 2, self.read_only_item(catalog.summary))
                    action = QWidget()
                    buttons = QGridLayout(action)
                    buttons.setContentsMargins(0, 0, 0, 0)
                    use_button = QPushButton("사용")
                    download_button = QPushButton("모델 다운로드")
                    runner_button = QPushButton(catalog.runner_label)
                    model_button = QPushButton(catalog.model_label)
                    use_button.setEnabled(status.ok)
                    use_button.clicked.connect(lambda _=False, key=catalog.engine_id: set_selected(key))
                    download_button.setEnabled(self.download_thread is None)
                    download_button.clicked.connect(lambda _=False, key=catalog.engine_id: self.start_model_download(key))
                    runner_button.clicked.connect(lambda _=False, key=catalog.engine_id: (self.choose_executable(key), refresh_table()))
                    model_button.clicked.connect(lambda _=False, key=catalog.engine_id: (self.choose_model(key), refresh_table()))
                    buttons.addWidget(use_button, 0, 0)
                    buttons.addWidget(download_button, 0, 1)
                    buttons.addWidget(runner_button, 0, 2)
                    buttons.addWidget(model_button, 0, 3)
                    table.setCellWidget(row, 3, action)

            refresh_table()
            close_button = QPushButton("닫기")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button)
            dialog.exec()
            self.refresh_engines()

        def start_model_download(self, engine_id: str) -> None:
            if self.download_thread is not None:
                QMessageBox.information(self, "다운로드 중", "이미 모델 다운로드가 진행 중입니다.")
                return
            self.download_thread = QThread()
            self.download_worker = ModelDownloadWorker(engine_id)
            self.download_worker.moveToThread(self.download_thread)
            self.download_thread.started.connect(self.download_worker.run)
            self.download_worker.log.connect(self.log.appendPlainText)
            self.download_worker.failed.connect(self.model_download_failed)
            self.download_worker.finished.connect(self.model_download_finished)
            self.download_worker.failed.connect(self.download_thread.quit)
            self.download_worker.finished.connect(self.download_thread.quit)
            self.download_thread.finished.connect(self.download_worker.deleteLater)
            self.download_thread.finished.connect(self.download_thread.deleteLater)
            self.download_thread.finished.connect(self.clear_model_download)
            self.download_thread.start()

        def model_download_failed(self, message: str) -> None:
            self.log.appendPlainText(f"모델 다운로드 실패: {message}")
            QMessageBox.warning(self, "모델 다운로드 실패", message)

        def model_download_finished(self, engine_id: str, path: str) -> None:
            self.config.setdefault("engines", {}).setdefault(engine_id, {})["model_path"] = path
            self.config["selected_engine_id"] = engine_id
            _save_config(self.config)
            self.log.appendPlainText(f"모델 다운로드 완료: {path}")
            self.refresh_engines()
            status = validate_engine(self.engine_config(engine_id))
            if status.ok:
                QMessageBox.information(self, "모델 다운로드 완료", "모델이 준비됐습니다.")
            else:
                QMessageBox.information(self, "모델 다운로드 완료", f"모델은 저장했습니다. {_engine_status_text(status)} 단계가 남았습니다.")

        def clear_model_download(self) -> None:
            self.download_worker = None
            self.download_thread = None

        def read_only_item(self, text: str, tooltip: str = "") -> QTableWidgetItem:
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if tooltip:
                item.setToolTip(tooltip)
            return item

        def choose_executable(self, engine_id: str) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Choose runner file")
            if path:
                self.config.setdefault("engines", {}).setdefault(engine_id, {})["executable"] = path
                _save_config(self.config)
                self.refresh_engines()

        def choose_model(self, engine_id: str) -> None:
            if engine_id == "whisper":
                path, _ = QFileDialog.getOpenFileName(self, "Choose Whisper model")
            else:
                path = QFileDialog.getExistingDirectory(self, "Choose model folder")
            if path:
                self.config.setdefault("engines", {}).setdefault(engine_id, {})["model_path"] = path
                _save_config(self.config)
                self.refresh_engines()

        def engine_config(self, engine_id: str) -> EngineConfig:
            entry = self.config.setdefault("engines", {}).setdefault(engine_id, {})
            return EngineConfig(engine_id, Path(entry.get("executable", "")), Path(entry.get("model_path", "")))

        def ready_engine_configs(self) -> list[EngineConfig]:
            configs = [self.engine_config(engine_id) for engine_id in ENGINE_NAMES]
            return [config for config in configs if validate_engine(config).ok]

        def selected_engine_config(self) -> EngineConfig | None:
            selected = self.config.get("selected_engine_id", "qwen3")
            candidates = [self.engine_config(selected), *self.ready_engine_configs()]
            for config in candidates:
                if validate_engine(config).ok:
                    return config
            return None

        def update_action_state(self) -> None:
            has_input = self.input_path is not None and self.total_duration > 0
            ready = self.ready_engine_configs()
            recording = self.recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState
            idle = not recording and self.job_thread is None
            self.open_button.setEnabled(idle)
            self.record_button.setEnabled(idle)
            self.stop_record_button.setEnabled(recording)
            self.export_button.setEnabled(has_input and idle)
            self.transcribe_button.setEnabled(has_input and idle)
            self.compare_button.setEnabled(has_input and len(ready) >= 2 and idle)
            self.resume_button.setEnabled(idle)

        def transcribe_selected(self) -> None:
            config = self.selected_engine_config()
            if config is None:
                QMessageBox.information(self, "모델 설정 필요", "스크립트 추출 전에 사용할 모델을 준비하세요.")
                self.show_model_settings()
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
            self.update_action_state()
            self.job_thread.start()

        def stop_job(self) -> None:
            if self.job_worker is not None:
                self.job_worker.stop()
                self.log.appendPlainText("Stop requested. Waiting for current command to finish.")

        def job_failed(self, message: str) -> None:
            self.log.appendPlainText(f"Job failed: {message}")

        def job_finished(self, outputs: str) -> None:
            self.log.appendPlainText(f"Transcript written:\n{outputs}")
            paths = [Path(line.strip()) for line in outputs.splitlines() if line.strip()]
            if not paths:
                return
            self.last_transcript_path = paths[0]
            if self.last_transcript_path.exists():
                self.result_preview.setPlainText(self.last_transcript_path.read_text(encoding="utf-8", errors="replace"))
                self.open_txt_button.setEnabled(True)
                self.open_json_button.setEnabled(self.last_transcript_path.with_suffix(".json").exists())
                self.open_folder_button.setEnabled(True)

        def open_transcript(self) -> None:
            if self.last_transcript_path is not None:
                _open_path(self.last_transcript_path)

        def open_transcript_json(self) -> None:
            if self.last_transcript_path is not None:
                _open_path(self.last_transcript_path.with_suffix(".json"))

        def open_result_folder(self) -> None:
            if self.last_transcript_path is not None:
                _open_path(self.last_transcript_path.parent)

        def clear_job(self) -> None:
            self.job_worker = None
            self.job_thread = None
            self.progress.setVisible(False)
            self.stop_job_button.setEnabled(False)
            self.update_action_state()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()
    return app.exec()
