# PigSkin AI Studio — Flet Desktop

An original dark cyan/teal research command-center UI for Windows, on Flet 0.28.3.

## Running (PowerShell, inside PigSkinTech)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## What works now
- Toggle between light and dark palettes; the open page and case form values are preserved.
- Dashboard with 2017-image split, documented model metrics, real SQLite inspection count.
- Image picker, JPG/PNG/WEBP file verification and image preview.
- Case intake with animal/group ID, farm, lesion location, onset date, and observed signs.
- SQLite case records with generated case IDs, searchable history, review status, and saved top-5 model scores.
- Model checkpoint filename and modification time recorded with each real inference for basic traceability.
- Dataset/training/model pages showing DOCUMENTED statistics, clearly not live training.
- Optional **real** MobileNetV2 inference, **only** with a compatible checkpoint and correctly ordered class names.

Original images are copied into the local `case_images/` archive when an inspection is saved. The history view can reopen archived images; deleting a record removes its archived copy but never deletes the source image selected by the user. Each inspection currently stores one image. A detected checkpoint and class file do not prove that the model is compatible; the first inference must load the weights successfully. Softmax scores are displayed as model scores, not calibrated disease probabilities, and results require veterinary review.

## Connecting model weights
1. Confirm the AI team trained **torchvision.models.mobilenet_v2** with `classifier[1]=Linear(last_channel,num_classes)` and an ImageNet-normalized `Resize(256)->CenterCrop(224)` preprocessing pipeline. Otherwise adjust `services/inference.py` to match their exact training procedure.
2. Put the true PyTorch state dict in `models/best.pth`, not the `.example` file. Supported: raw state_dict or dict containing `model_state_dict`/`state_dict`.
3. Put the exact ordered list of all class names in `models/classes.json` (e.g. `["healthy", ...]`); **do not use invented class maps**. Ensure length matches trained output classes.
4. Install matching `torch` and `torchvision` builds via official PyTorch instructions appropriate to the system (CPU is fine). Then restart app.
5. Test several independently labeled images and compare results to your group's evaluation script before reporting AI performance.

The UI does not create fake diagnoses. It is a research aid and is not a veterinary diagnosis tool. The supplied dataset/run statistics come from the user-provided screenshots and must be cross-checked with the final research files.

## Integration into DACN repo
Copy this folder to `D:\DACN\PigSkinTech` **after backing up the current Flet work**. Do not overwrite the entire DACN repository. Work on branch `devN`; `.venv`, local database and model weight files are excluded from git.
