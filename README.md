# Meet Note Gen

Windows Python desktop app for long Korean meeting audio.

## Run

Install `uv` and `ffmpeg` first:

```powershell
winget install -e --id astral-sh.uv
winget install -e --id Gyan.FFmpeg
```

Then run from the project folder:

```powershell
uv venv --python 3.12
uv pip install -e .
uv run python -m meet_note_gen
```

## External Tools

- Install `ffmpeg` and make it available in `PATH`.
- `ffprobe` must also be available; it ships with normal ffmpeg builds.
- Install or select paths for:
  - Qwen3-ASR 0.6B runner and model.
  - SenseVoiceSmall INT8 runner/model through sherpa-onnx.
  - Whisper.cpp `whisper-cli.exe` and `large-v3-turbo-q5` model.

Models are not bundled in the app. Use `모델 설정` to open download pages, then choose the runner executable and model path.

## Current Features

- Open audio files or drag them into the window.
- Record from the default microphone, then load and transcribe the recording automatically when the selected engine is ready.
- Generate an ffmpeg waveform preview.
- Play and stop audio through Qt Multimedia.
- Extract a script from the selected audio with one primary button.
- Preview the transcript and open TXT/JSON/result folder after completion.
- Set trim start/end from the current playback position or numeric seconds.
- Cut a duration from the end.
- Export the selected range as 1 or more WAV segments.
- Split the selected range into 2, 3, 4, 5, or custom N segments.
- Configure/download model links in a separate model settings window.
- Compare every ready engine from advanced options.
- Save chunk TXT/JSON plus merged transcript TXT/JSON.
- Resume an existing job folder and skip completed chunks.
