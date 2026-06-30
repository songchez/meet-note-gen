# Meet Note Gen

Windows Python desktop app for long Korean meeting audio.

## Run

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python -m meet_note_gen
```

## External Tools

- Install `ffmpeg` and make it available in `PATH`.
- Install or select paths for:
  - Qwen3-ASR 0.6B runner and model.
  - SenseVoiceSmall INT8 runner/model through sherpa-onnx.
  - Whisper.cpp `whisper-cli.exe` and `large-v3-turbo-q5` model.

Models are not bundled in the app. Use the app's model table to point to existing folders or install them when download support is added.
