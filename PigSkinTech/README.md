# PigSkin AI Studio — Flet Desktop

## Current development status (November 2026)

Create the virtual environment and install dependencies from this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Run isolated regression tests (no connection to PigSkinAI):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run the isolated real-Flet render smoke test (also does not connect to
PigSkinAI):

```powershell
.\.venv\Scripts\python.exe -m tests.flet_runtime_smoke
```

Run the read-only operational audit against LocalDB:

```powershell
.\.venv\Scripts\python.exe readiness_check.py
```

The readiness audit issues only metadata/aggregate `SELECT` statements and
rolls back before closing. It does not initialize schemas or run migrations.

Before changing a database schema, create and verify a local backup. Keep
database backups outside the repository. The application still uses SQL Server
LocalDB. Do not rerun `migrate_database.py` against an existing database.

Current improvements include session revalidation on navigation, service-level
role checks for case access, hidden unpublished expert text for users, SQL-level
history pagination, a collapsible sidebar, image zoom/pan, a 24-million-pixel
input limit, and local diagnostic logs in `logs/`. Dataset figures are shown
only after a real scan. Experiment files can also contain loss, optional macro
precision/recall and a confusion matrix matched to `per_class`; run history is
held for the current desktop session only.

Support conversations enforce their rules in the service layer, not only in
the UI. A user can send the opening message plus at most two additional
messages before the first expert/admin reply. After a staff reply, the user can
continue without that pre-reply limit. Experts and admins may close a thread;
an answered thread is also closed after 30 minutes without another staff reply.
Unread badges and the open conversation refresh every five seconds.

Windows packaging has not been verified. A packaged build must include Flet,
Pillow, pyodbc, the correct ODBC driver/LocalDB prerequisites, and writable
storage for `case_images/` and `logs/`; install matching PyTorch builds only
when the AI team supplies its validated checkpoint and environment details.
`PyInstaller` and the optional `flet-cli` package are not installed in the
current virtual environment, so no distributable executable was produced.
Model weights, class maps and runtime-specific files are intentionally not
included in this repository. Inference stays unavailable until approved model
assets are provisioned locally and pass the manifest checks.

An original dark cyan/teal research command-center UI for Windows, on Flet 0.28.3.

## Running (PowerShell, inside pigskin_studio_nam)

```powershell
.\.venv\Scripts\python.exe main.py
```

The app uses Windows Authentication to connect to `(localdb)\MSSQLLocalDB`
and `PigSkinAI`. Install Microsoft ODBC Driver 17 or 18 and SQL Server LocalDB.
The existing database contains live accounts and cases. Do not run
`migrate_database.py` on it. That script is retained only for a separate,
empty database after an explicit migration plan and backup.

Connection settings can be overridden with `PIGSKIN_SQLSERVER`, `PIGSKIN_DATABASE`, and `PIGSKIN_SQL_DRIVER`. Set `PIGSKIN_SQLITE_PATH` to choose another SQLite file for the one-time migration.

## What works now
- Existing email/password accounts remain supported; passwords are stored as salted PBKDF2 hashes.
- Responsive split-panel login, registration, OTP verification and recovery screens. OTP delivery requires the separately approved LocalDB migration and explicit SMTP/SMS configuration; see [docs/AUTH_OTP_SETUP.md](docs/AUTH_OTP_SETUP.md).
- Three roles with separate workspaces:
  - **User:** submit images, view only their own history and published results, and contact support.
  - **Expert:** review submitted cases, write results, approve or return another expert's result, and access dataset/model/research-report pages. An expert cannot approve their own result.
  - **Admin:** view account/case/login metrics, manage accounts and roles, handle support, and access dataset/model/research-report pages. Admins do not get the image-analysis workspace and do not approve clinical results.
- New self-registrations are regular users only. An owner-controlled setup procedure must provision an administrator for a new installation; an admin can promote accounts to expert or admin.
- Toggle between light and dark palettes; the open page and case form values are preserved.
- Admin dashboard with account totals, successful app logins, case volume, result-review queue, and confirmed case classification metrics.
- Image picker, JPG/PNG/WEBP file verification and image preview.
- Case intake with animal/group ID, farm, lesion location, onset date, and observed signs.
- Local dataset audit (read-only): class/split counts, unreadable image files, exact SHA-256 duplicates, possible cross-split duplicate leakage, and notable class imbalance. Supports class/image and split/class/image folder layouts.
- Experiment review can load a selected JSON report from a training/evaluation run. It validates metric ranges and displays only fields present in that report; training is not run by the desktop app.
- SQL Server LocalDB case records with generated case IDs, searchable and paginated history, review status, and saved model scores when real inference runs.
- Users can delete only their own cases that have not yet been taken up by an expert; deletion requires confirmation and removes the archived image too.
- Expert result workflow: draft result → second-expert approval or return for revision → publish to the user's history with an unread-result badge.
- Support questions and replies are stored in LocalDB. They are not real-time chat.
- Model checkpoint filename and modification time recorded with each real inference for basic traceability.
- Dataset/training/model pages showing values from scanned folders and selected JSON reports; the desktop app does not train a model.
- Optional real MobileNetV2 inference when an approved checkpoint, class map,
  manifest and compatible PyTorch runtime are provisioned locally. Model
  weights and private handoff artifacts are not tracked in Git.

Original images are copied into the local `case_images/` archive when an inspection is saved. The history view can reopen archived images; deleting an eligible record removes its archived copy but never deletes the source image selected by the user. Each inspection currently stores one image. A detected checkpoint and class file do not prove that the model is compatible; the first inference must load the weights successfully. Softmax scores are displayed as model scores, not calibrated disease probabilities, and results require veterinary review.

Accounts, inspection records, support conversations, and successful login events are stored in the local SQL Server LocalDB database; this desktop app does not provide remote synchronization, multi-device collaboration, or live website-visit analytics. OTP-based account recovery is available only after provider configuration and the separately approved migration. Keep the database, OTP pepper and image archive on a trusted device and back them up together. Existing inspection records from before accounts were added are visible to experts and admins, but are not assigned to a regular user's account. The admin disease percentage uses only second-expert-approved results classified as healthy or condition; inconclusive results are excluded.

## Optional model runtime

The application checks the model/class hashes and checkpoint metadata before
inference. It uses torch/torchvision from the Studio process when available,
or an isolated interpreter configured in `models/runtime.json`. To configure
another machine after receiving approved model assets:

```powershell
$env:PIGSKIN_AI_PYTHON='C:\path\to\python.exe'
.\.venv\Scripts\python.exe main.py
```

That interpreter must provide compatible `torch`, `torchvision` and Pillow.
Run the model smoke test before opening real cases:

```powershell
.\.venv\Scripts\python.exe -m tests.model_runtime_smoke
```

Softmax is not calibrated diagnostic probability. Every output remains an AI
suggestion requiring expert review.

## Loading experiment metrics
On the **Huấn luyện** page, choose a JSON report exported by the training/evaluation workflow. The app expects:

```json
{
  "run_id": "run identifier",
  "architecture": "model architecture",
  "best_epoch": 1,
  "source": "evaluation source",
  "metrics": {
    "validation_macro_f1": 0.0,
    "test_macro_f1": 0.0,
    "test_accuracy": 0.0
  },
  "per_class": [
    {"class_name": "class name", "precision": 0.0, "recall": 0.0, "f1": 0.0}
  ]
}
```

Scores must be fractions between `0` and `1`; unavailable metrics can be omitted. The app validates and displays only the supplied report values. It does not infer a report from checkpoint weights or train a model.

The UI does not create fake diagnoses. It is a research aid and is not a veterinary diagnosis tool. The supplied dataset/run statistics come from the user-provided screenshots and must be cross-checked with the final research files.
