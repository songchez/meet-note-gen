# Meet Note Gen Design

## Goal

Build a Windows Python desktop app for long Korean meeting audio:

- Open large audio files, including 500 MB+ and 3 hour+ recordings.
- Record from the default microphone and transcribe immediately after recording stops.
- Show waveform, play audio, trim front/back/end ranges, and split evenly.
- Transcribe with locally installed ASR engines.
- Let the user install or point to model folders instead of bundling models in the app.
- Save partial results so long jobs can resume after failure.

Target laptop:

- AMD Ryzen 7 PRO 8840U
- Radeon 780M integrated GPU
- Windows

The app should assume CPU-first execution. GPU/Vulkan/DirectML acceleration is allowed per engine when the engine supports it, but it is not required for correctness.

## Non-Goals

- No cloud API in the MVP.
- No dynamic plugin system in the MVP.
- No automatic merging of multiple model outputs in the MVP.
- No bundled ASR model files in the app installer.
- No dependency on CUDA or NVIDIA-only tooling.

## Architecture

```text
+--------------------------------------------------+
| Meet Note Gen Windows App                        |
|                                                  |
|  PySide6 GUI                                     |
|    - file open                                   |
|    - recording                                   |
|    - waveform                                    |
|    - playback                                    |
|    - trim/split controls                         |
|    - model manager                               |
|    - job progress                                |
|                                                  |
|  Core                                            |
|    - ffmpeg audio prep                           |
|    - chunk planner                               |
|    - job state                                   |
|    - engine runner                               |
|    - result writer                               |
|                                                  |
|  Installed Engines                               |
|    - Qwen3-ASR 0.6B                              |
|    - SenseVoiceSmall INT8                        |
|    - Whisper large-v3-turbo Q5                   |
+--------------------------------------------------+
```

The app owns audio preparation, UI, job state, and file output. Each ASR model is handled through an external executable or installed engine path. Python does not embed large PyTorch/Transformers runtimes for the MVP.

## Install Layout

```text
%LOCALAPPDATA%\MeetNoteGen\
  config.json
  engines\
    qwen3-asr\
    sensevoice\
    whisper\
  models\
    qwen3-asr-0.6b\
    sensevoice-small\
    whisper-large-v3-turbo-q5\
  jobs\
    <job-id>\
      input.json
      chunks\
      results\
      state.json
  output\
  recordings\
```

The app installer includes the GUI and Python runtime dependencies only. The model manager can:

- Download known engine/model packages.
- Let the user choose an existing engine/model folder.
- Validate required files before running.

## Engines

### 1. Qwen3-ASR 0.6B

Default engine.

Use for normal Korean meeting transcription when available. Prefer a CLI-style runner so the desktop app can call it as a subprocess and capture output.

Expected role:

- Best first try for Korean meeting notes.
- CPU-first.
- Chunked long-file transcription.

### 2. SenseVoiceSmall INT8

Fast fallback and comparison engine.

Use through sherpa-onnx or another ONNX-based runner. Keep it as the lightweight backup when Qwen install/runtime is not working.

Expected role:

- Quick transcription.
- Lower install/runtime risk.
- Useful for comparing model quality.

### 3. Whisper large-v3-turbo Q5

Stable fallback and subtitle-oriented engine.

Use through whisper.cpp. Prefer quantized `large-v3-turbo-q5` by default. Smaller Whisper models can be added later only if real testing shows the default is too slow.

Expected role:

- Reliable multilingual fallback.
- Better timestamp/SRT path than the other engines.
- Optional Vulkan/GPU acceleration if the local whisper.cpp build supports it.

## Audio Flow

```text
input audio or recorded audio
  |
  v
ffmpeg probe
  |
  v
user trim/split choices
  |
  v
ffmpeg normalize to 16 kHz mono wav
  |
  v
10 minute chunks by default
  |
  v
selected ASR engine
  |
  v
chunk result files
  |
  v
merged TXT / JSON / optional SRT
```

Default chunk size is 10 minutes. The app can expose 3, 5, 10, 15, and 20 minute chunk choices. Ten minutes is the default because it limits failure cost and keeps memory predictable on the target laptop.

## Editing Features

MVP editing controls:

- Open audio file.
- Record from the default microphone.
- Load a completed recording automatically and start transcription when the selected engine is ready.
- Display waveform overview.
- Play, pause, seek.
- Trim front.
- Trim back.
- Cut from end by duration.
- Keep selected range.
- Split evenly into 2, 3, 4, 5, or custom N parts.
- Export edited audio segments.

The app does not need a destructive waveform editor. All edits can be stored as time ranges and applied through ffmpeg when exporting or transcribing.

## UI Sketch

```text
+--------------------------------------------------------------+
| [Open] [Record] [Stop Rec] [Play] [Stop] [Export]            |
| Model: [Qwen3-ASR 0.6B v]                                    |
+--------------------------------------------------------------+
| 00:00:00                                             03:12:44 |
| ~~~~~~~^^^^^^~~~~~~~^^^^~~~~~~^^^^^^~~~~~~~~~~~~~^^^^^^~~~~~~ |
|        | trim start                         trim end |        |
+--------------------------------------------------------------+
| Trim: [Set Start] [Set End] [Cut Last: ____ min]              |
| Split: [2] [3] [4] [5] [N: ___] [Create Segments]             |
+--------------------------------------------------------------+
| Engines                                                      |
| Qwen3-ASR 0.6B        [Installed/Missing] [Install] [Folder]  |
| SenseVoiceSmall INT8  [Installed/Missing] [Install] [Folder]  |
| Whisper Turbo Q5      [Installed/Missing] [Install] [Folder]  |
+--------------------------------------------------------------+
| Job                                                          |
| Chunk size: [10 min v]  [Transcribe] [Compare Models] [Stop] |
| chunk_001 done                                               |
| chunk_002 running                                            |
+--------------------------------------------------------------+
```

## Job State

Each transcription creates a job folder with:

- Input file path and detected metadata.
- Selected trim range.
- Chunk size and generated chunk list.
- Selected engine or comparison engine list.
- Per-chunk status.
- Per-engine result files.

The app writes each chunk result immediately. If the app closes or an engine fails, rerunning the job skips completed chunks unless the user chooses to overwrite.

## Outputs

Minimum outputs:

- `transcript.txt`
- `transcript.json`
- `chunks/<engine>/<chunk>.txt`
- `chunks/<engine>/<chunk>.json`

Optional output:

- `transcript.srt` for Whisper when timestamps are available.

For Qwen3-ASR and SenseVoice, SRT should not be promised unless the selected runner returns reliable timestamps.

## Error Handling

Validate before starting:

- Input file exists.
- ffmpeg is available.
- Selected engine executable exists.
- Selected model folder has required files.
- Output folder is writable.
- Enough disk space exists for temporary WAV chunks.

During jobs:

- Stop on repeated engine failure for the same chunk.
- Keep completed chunk outputs.
- Show the engine command and error text in a details panel.
- Allow resume, retry failed chunk, or switch engine.

## Testing

Keep tests small:

- Unit check for even split time calculation.
- Unit check for trim range validation.
- Unit check for job resume skipping completed chunks.
- Smoke check that ffmpeg command generation is correct.

Manual checks on Windows:

- Install each engine through model manager.
- Transcribe a 3-5 minute Korean sample with each engine.
- Record a short microphone sample and verify it auto-starts transcription when a selected engine is ready.
- Transcribe a long file by chunking and resuming after stopping.
- Export trimmed and evenly split audio.

## Implementation Order

1. App skeleton with PySide6.
2. ffmpeg probe, trim, normalize, chunk, and split.
3. Job folder and resume state.
4. Model manager with manual folder selection.
5. Whisper.cpp runner.
6. SenseVoice/sherpa-onnx runner.
7. Qwen3-ASR runner.
8. Download helpers for known models.
9. Compare models mode.

Manual folder selection comes before download automation because it is smaller and unblocks engine testing sooner.

## References

- Qwen3-ASR 0.6B: https://huggingface.co/Qwen/Qwen3-ASR-0.6B-hf
- SenseVoiceSmall: https://huggingface.co/FunAudioLLM/SenseVoiceSmall
- sherpa-onnx SenseVoice: https://k2-fsa.github.io/sherpa/onnx/sense-voice/index.html
- Whisper large-v3-turbo: https://huggingface.co/openai/whisper-large-v3-turbo
- whisper.cpp: https://github.com/ggml-org/whisper.cpp
- whisper.cpp model files: https://huggingface.co/ggerganov/whisper.cpp
