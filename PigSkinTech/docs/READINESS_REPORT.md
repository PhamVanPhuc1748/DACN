# PigSkin AI Studio readiness report

Date: 2026-11-03 (Asia/Saigon)

## Verified

- Exact project interpreter: Python 3.10.5 from `..\.venv`.
- Runtime dependency set imports correctly: Flet 0.28.3, Pillow and pyodbc.
- All Python sources compile and all 58 isolated regression tests pass.
- A real hidden Flet process reaches the initial rendered page without opening
  LocalDB.
- Importing `main` does not connect to or initialize LocalDB.
- The read-only LocalDB audit found the required columns, valid roles/states,
  no duplicate account emails, no checked orphan rows and no missing archived
  image among the paths stored by the inspected records.
- Service authorization protects user-owned cases and support threads. Expert
  results require a different expert for approval.
- Support message limits, staff close permission, 30-minute answered-thread
  expiry and unread refresh are implemented and regression-tested.
- The selected MobileNetV2 checkpoint, class order, hashes and exact training
  preprocessing are verified. A real ten-class inference smoke test passes via
  an isolated Python 3.10.5 PyTorch runtime.
- Missing, changed or invalid model assets keep inference unavailable instead
  of producing fabricated scores.
- Startup/database failures render a recoverable error instead of leaving a
  blank desktop page.

Final read-only LocalDB snapshot: 3 users, 13 login events, 10 inspections,
2 support threads and 5 support messages. All nine reported integrity-error
counts were zero; one active admin remains. Two stored image paths were checked,
with zero missing files and zero paths outside the archive. These values match
the pre-fix audit, confirming that this audit did not alter application data.

## Operational cautions

- `migrate_database.py` was not run. Do not run it against the existing
  `PigSkinAI` database without a separate approved migration plan and backup.
- The snapshot at
  `C:\Users\ADMIN\Documents\PigSkinBackups\20261103_152116_979` was not
  modified.
- `readiness_check.py` is intentionally read-only. Keep it that way for future
  handoff checks.

## Not yet verified

- Exact reproduction with the original Python 3.11, torch 2.5.1 and
  torchvision 0.20.1 training environment: that `.venv` was intentionally not
  included in the handoff. The checkpoint does strict-load and reproduces its
  201-image test metrics in the available isolated runtime.
- A packaged Windows executable: PyInstaller and the optional Flet CLI package
  are absent, so packaging and installer behavior were not tested.
- Full manual visual/interaction coverage on 1366x768 and 1920x1080 displays,
  including OS file-picker behavior and long real-world text/data sets.
- Multi-machine/remote synchronization, email recovery and server-grade
  concurrency are outside this LocalDB desktop application's scope.

## Commands

```powershell
..\.venv\Scripts\python.exe -m compileall -q .
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
..\.venv\Scripts\python.exe -m tests.model_runtime_smoke
..\.venv\Scripts\python.exe -m tests.flet_runtime_smoke
..\.venv\Scripts\python.exe -m pip check
..\.venv\Scripts\python.exe readiness_check.py
```
