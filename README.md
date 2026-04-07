# Wildlife AI Platform - Tester Quick Start

This repository contains the current prototype submission (FastAPI backend + React frontend + MegaDetector + AWC135 pipeline).

This quick guide is for evaluators/testers on **Windows + NVIDIA GPU**.  
For full detailed setup, see `SETUP.md`.

## 1) System Requirements

- Windows 10/11
- NVIDIA GPU (CUDA-capable; tested on RTX 3080 10 GB)
- Python 3.10 (Conda recommended)
- Node.js 18+
- Git

## 2) Clone and Install

```bash
git clone <your-repo-url>
cd Project321

conda create -n wildlife python=3.10 -y
conda activate wildlife

pip install torch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
pip install megadetector
```

Install AWC helper package:

```bash
git clone https://github.com/Australian-Wildlife-Conservancy-AWC/awc-wildlife-classifier.git C:\Users\Admin\ml_models\awc135_repo
pip install -e C:\Users\Admin\ml_models\awc135_repo
```

## 3) Required Model Files (must exist at these exact paths)

The current code expects:

- `C:\Users\Admin\ml_models\megadetector\md_v5a.0.0.pt`
- `C:\Users\Admin\ml_models\awc135\awc-135-v1.pth`
- `C:\Users\Admin\ml_models\awc135\labels.txt`

These paths come from `backend/app/config.py`.

## 4) Model Download Sources

- MegaDetector v5a weights (official release):
  - https://github.com/microsoft/CameraTraps/releases/tag/v5.0
  - direct file: https://huggingface.co/agentmorris/megadetector/resolve/main/md_v5a.0.0.pt
- AWC classifier project:
  - https://github.com/Australian-Wildlife-Conservancy-AWC/awc-wildlife-classifier
  - AWC overview/news page: https://www.australianwildlife.org/australian-wildlife-classifier-awc135

If AWC weight files are not publicly downloadable in your environment, request these two files from the submitter/supervisor and place them in `C:\Users\Admin\ml_models\awc135\`.

## 5) Run the Prototype

Backend (Terminal 1):

```bash
conda activate wildlife
python -m backend.app.db.init_db
uvicorn backend.app.main:app --reload
```

Frontend (Terminal 2):

```bash
cd frontend
npm install
npm run dev
```

Open:

- Frontend: `http://localhost:5173`
- Backend API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## 6) Optional: Run ML Batch Processing Directly

```bash
conda activate wildlife
python -m scripts.run_pipeline --limit 100 --batch-size 8
```

## 7) Demo Test Checklist (for marking)

- App loads at `http://localhost:5173`
- User can register/login
- Batch upload accepts camera-trap image folders
- Job progress is visible
- Detections and review pages render data
- Reports page can export CSV/JSON
- Admin page is reachable with admin account

## 8) Troubleshooting

- `CUDA available: False`: update NVIDIA driver and reinstall CUDA-enabled torch command above
- `No module named sqlalchemy` or other import errors: confirm `conda activate wildlife` and run `pip install -r requirements.txt`
- `ModuleNotFoundError: awc_helpers`: reinstall editable AWC package
- Missing model file errors: verify exact file names and paths listed in section 3
