# Windows packaging preparation

Packaging is prepared but has not been executed or verified. The build remains
owner-controlled and never installs dependencies automatically.

## Build prerequisites

- A dedicated Python build environment with the dependencies in
  `requirements.txt` and PyInstaller installed explicitly.
- Microsoft ODBC Driver 17 or 18 and SQL Server LocalDB installed on the target
  Windows machine.
- The target database configured through Windows Authentication.

From the application directory, run only after installing PyInstaller in the
chosen build environment:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\build_windows.ps1
```

The recipe includes the Flet runtime, login image, checkpoint, class map, model
manifest, runtime configuration and physical worker modules required by the
external Python interpreter. It intentionally excludes torch and
torchvision from the desktop executable because AI inference uses a separate
validated Python runtime.

## Portable AI runtime

The application resolves the AI interpreter in this order:

1. `PIGSKIN_AI_PYTHON`.
2. `python_executable` and `python_candidates` in `models/runtime.json`.
3. `ai_runtime\python.exe` or `ai_runtime\Scripts\python.exe` beside the EXE.

The selected interpreter must contain compatible torch, torchvision and
Pillow. A packaged deployment can therefore place a prepared virtual
environment at `ai_runtime\` beside `PigSkinAIStudio.exe` without embedding
PyTorch into the desktop executable.

## Writable application data

Source runs continue to use the project `case_images\` and `logs\` folders. A
frozen executable writes them under
`%LOCALAPPDATA%\PigSkinAIStudio\` by default. Override this location with
`PIGSKIN_DATA_DIR`. Use `PIGSKIN_MODEL_DIR` to load approved model assets from
an external `models\` directory.

Before distribution, manually verify the generated EXE on a clean Windows
machine, including Flet launch, LocalDB/ODBC access, writable storage, AI
runtime discovery and one approved model smoke test.
