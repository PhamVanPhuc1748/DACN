# PigSkin AI Studio — Flet Desktop

A desktop research UI for pig-skin health records and image review, built with Flet 0.28.3.

The UI supports Light and Dark palettes, role-based navigation (Admin, Expert/Vet, Farm User), and direct model inference.

## Running (PowerShell, inside PigSkinTech)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## What works now
- Toggle between light and dark palettes; the open page and case form values are preserved.
- Role-based views: Admin, Expert, User.
- Dashboard, dataset, and training views read the latest completed run's `config.json`, `final_metrics.json`, and manifest; absent files show as unavailable rather than sample values.
- Image picker, JPG/PNG/WEBP file verification and image preview.
- Case intake with animal/group ID, farm, lesion location, onset date, and observed signs.
- SQLite case records with generated case IDs, searchable history, review status, and saved top-5 model scores.
- In the image-analysis page, choose between bundled MobileNetV2 and EfficientNet-B0 checkpoints. The app selects the best validation macro-F1 run per architecture from the shared v4 manifest.
- Real inference uses the selected checkpoint and records its architecture/run identity with the case. The worker also supports MobileNetV3-Large checkpoints for other workflows.
- The app uses the training environment's Python when the lightweight Flet environment has no Torch installed. Inference runs outside the UI thread, and the saved record includes the run/checkpoint identity.
- Page, image-preview, and result changes use short fade transitions; inference shows an indeterminate progress bar.

Original images are copied into the local `case_images/` archive when an inspection is saved. The history view can reopen archived images; deleting a record removes its archived copy but never deletes the source image selected by the user. Each inspection currently stores one image. A detected checkpoint and class file do not prove that the model is compatible; the first inference must load the weights successfully. Softmax scores are displayed as model scores, not calibrated disease probabilities, and results require veterinary review.

## Selecting the model and connecting training runs

The bundled model checkpoints are in `models/runs/20261103_125653` (MobileNetV2) and
`models/runs/20261103_125004` (EfficientNet-B0). The image-analysis page lets the user
choose one of these architectures. For each supported architecture, the app displays the
complete run with the highest validation macro-F1 among runs matching the v4 manifest hash.
Complete runs contain `best_model.pt`, `config.json`, `final_metrics.json`, and
`best_validation.json`.

The app also discovers complete runs under `E:\code\PigSkinResearchStudio\ml_workspace\runs`.
The checkpoint carries the architecture, ordered class labels, image size, and normalization
used during training. The app runs `services/inference_worker.py` using the training
studio's `.venv` when Torch is not installed in the app environment.

To use a different training studio folder, set `PIGSKIN_RESEARCH_ROOT` before launching
the app. For example:

```powershell
$env:PIGSKIN_RESEARCH_ROOT = 'D:\Research\PigSkinResearchStudio'
..\run_app.bat
```

The manifest statistics are counted from the CSV and checked against its recorded SHA-256.
The displayed training metrics come from that run's `final_metrics.json`; the app does not
substitute hand-entered example values when those files are missing.

The UI does not create fake diagnoses. It is a research aid and is not a veterinary diagnosis tool. Softmax scores are model scores, not calibrated disease probabilities; have a veterinarian review predictions.
