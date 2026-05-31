# WildlifeTracker — Environment Setup Guide

> **Target system:** Windows 10/11 · NVIDIA RTX 3080 (10 GB) · 32 GB RAM recommended  
> **Python:** 3.10 · **CUDA:** 11.8 · **PyTorch:** 2.1 · **Node.js:** 18+ LTS

This guide walks through a complete local install of WildlifeTracker — the CSIT321 camera-trap platform (FastAPI + React + MegaDetector + AWC135 + optional MegaDescriptor re-ID).

For a shorter evaluator guide, see [`README.md`](README.md).

---

## Prerequisites

| Software | Version | Notes |
|----------|---------|-------|
| [Miniconda](https://docs.conda.io/en/latest/miniconda.html) | Latest | Python environment management |
| [Git](https://git-scm.com/downloads) | Latest | Clone repo and AWC135 helper |
| [NVIDIA Driver](https://www.nvidia.com/Download/index.aspx) | ≥ 522.06 | CUDA 11.8 support |
| [Node.js](https://nodejs.org/) | 18+ LTS | Frontend dev server |

You do **not** need the CUDA Toolkit or cuDNN installed separately — the PyTorch wheel includes what you need.

**Optional:** [Redis](https://redis.io/) — only if running a Celery worker for distributed batch jobs. The app works without it.

---

## Step 1: Clone the repository

```bash
git clone https://github.com/Noobmaster678/Project321
cd Project321
```

---

## Step 2: Create the Conda environment

```bash
conda create -n wildlife python=3.10 -y
conda activate wildlife
```

Always activate this environment before backend or script work:

```bash
conda activate wildlife
```

---

## Step 3: Install PyTorch (CUDA 11.8)

Install PyTorch **before** other ML packages:

```bash
pip install torch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cu118
```

Verify the GPU is visible:

```bash
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'); print('VRAM GB:', round(torch.cuda.get_device_properties(0).total_mem / 1e9, 1) if torch.cuda.is_available() else 0)"
```

Expected:

```
CUDA available: True
GPU: NVIDIA GeForce RTX 3080
VRAM GB: 10.0
```

If CUDA is `False`, update your NVIDIA driver and reinstall PyTorch with the command above.

---

## Step 4: Install backend Python dependencies

From the project root:

```bash
pip install -r requirements.txt
pip install megadetector
```

Key packages installed via `requirements.txt`:

| Package | Purpose |
|---------|---------|
| FastAPI + Uvicorn | REST API server |
| SQLAlchemy + aiosqlite | Async ORM + SQLite |
| python-jose + bcrypt | JWT authentication |
| Pillow + opencv-python-headless + timm | Image processing / AWC135 |
| pandas + numpy | Data handling |
| celery + redis | Optional async workers |
| pytest + httpx | Backend tests |

---

## Step 5: Install MegaDetector

```bash
pip install megadetector
```

Download v5a weights to the path expected by `backend/app/config.py`:

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\Admin\ml_models\megadetector" | Out-Null
curl.exe -L "https://huggingface.co/agentmorris/megadetector/resolve/main/md_v5a.0.0.pt" -o "C:\Users\Admin\ml_models\megadetector\md_v5a.0.0.pt"
```

Official sources:

- https://github.com/microsoft/CameraTraps/releases/tag/v5.0
- https://huggingface.co/agentmorris/megadetector

Verify:

```bash
python -c "from megadetector.detection.run_detector import load_detector; load_detector(r'C:/Users/Admin/ml_models/megadetector/md_v5a.0.0.pt'); print('MegaDetector loaded OK')"
```

---

## Step 6: Install AWC135 classifier

Clone and install the AWC helper package:

```powershell
git clone https://github.com/Australian-Wildlife-Conservancy-AWC/awc-wildlife-classifier.git "C:\Users\Admin\ml_models\awc135_repo"
pip install -e "C:\Users\Admin\ml_models\awc135_repo"
```

Create the model folder and place weight files:

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\Admin\ml_models\awc135" | Out-Null
```

Required files:

1. `C:\Users\Admin\ml_models\awc135\awc-135-v1.pth`
2. `C:\Users\Admin\ml_models\awc135\labels.txt`

Sources:

- https://github.com/Australian-Wildlife-Conservancy-AWC/awc-wildlife-classifier
- https://www.australianwildlife.org/australian-wildlife-classifier-awc135

If weights are not publicly downloadable, request them from the project supervisor and copy them into the folder above.

Verify:

```bash
python -c "import awc_helpers; print('awc_helpers import OK')"
```

---

## Step 7: Initialise the database

```bash
python -m backend.app.db.init_db
```

This creates `wildlife.db` in the project root with all ORM tables.

> **Note:** Tables are also created automatically the first time you start the API (`uvicorn`), so this step is optional but recommended for a clean first run.

---

## Step 8: Verify installation

Run dependency and model pre-flight checks:

```bash
python -c "
import torch, fastapi, sqlalchemy
from PIL import Image
import cv2, pandas
print('PyTorch:', torch.__version__, '| CUDA:', torch.cuda.is_available())
print('FastAPI:', fastapi.__version__)
print('SQLAlchemy:', sqlalchemy.__version__)
print('Pillow, OpenCV, Pandas: OK')
"
```

```powershell
python -c "from pathlib import Path; files=[r'C:/Users/Admin/ml_models/megadetector/md_v5a.0.0.pt', r'C:/Users/Admin/ml_models/awc135/awc-135-v1.pth', r'C:/Users/Admin/ml_models/awc135/labels.txt']; print({f: Path(f).exists() for f in files})"
python -c "import megadetector; print('megadetector OK')"
python -c "import awc_helpers; print('awc_helpers OK')"
```

All model paths should report `True`.

---

## Step 9: Run the application

### 9.1 Backend API (Terminal 1)

```bash
conda activate wildlife
uvicorn backend.app.main:app --reload
```

| URL | Purpose |
|-----|---------|
| http://localhost:8000/docs | Interactive API documentation |
| http://localhost:8000/health | Health check |

The API serves uploaded images and crops from `storage/` at `/storage/...`.

### 9.2 Frontend (Terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### 9.3 First login

1. Click **Sign in → Register**.
2. The **first user** in an empty database may register with the **admin** role.
3. Subsequent admin accounts require an existing admin to create them.

---

## Step 10: Optional — Celery worker

Only needed for distributed batch processing with Redis. **Skip this for normal local evaluation** — uploads process in the API process by default.

1. Install and start Redis (e.g. Windows Redis port or WSL).
2. In a third terminal:

```bash
conda activate wildlife
celery -A backend.worker.celery_app worker --loglevel=info
```

If Celery is unavailable, `backend/app/api/images.py` automatically falls back to in-process processing.

---

## Step 11: Optional — Re-ID gallery

AI top-5 individual suggestions require a MegaDescriptor gallery checkpoint:

```
storage/models/megadescriptor_l384_gallery.pt
```

Build it with:

```bash
python -m scripts.reid_megadescriptor_hf_mvp
```

Or set a custom path via `.env`:

```
REID_GALLERY_PATH=C:/path/to/your/gallery.pt
```

Manual individual assignment works without the gallery file.

---

## Step 12: Optional — Pending Review UI

The structured review queue is hidden unless enabled at frontend build time. Create `frontend/.env.local`:

```
VITE_ENABLE_PENDING_REVIEW=true
```

Restart `npm run dev`. A **Pending Review** item appears in the navigation.

---

## Step 13: Optional — standalone ML batch script

Process images directly without the web UI:

```bash
conda activate wildlife
python -m scripts.run_pipeline --limit 100 --batch-size 8
```

Other useful scripts:

| Script | Purpose |
|--------|---------|
| `scripts/verify_pipeline.py` | Check pipeline end-to-end |
| `scripts/bulk_import.py` | Import existing image folders |
| `scripts/reset_demo.py` | Reset demo database state |
| `scripts/create_sample_upload_folder.py` | Create sample images for testing |
| `scripts/seed_sample_1_individuals_demo.py` | Seed demo individual profiles |

---

## Configuration reference

All settings are in `backend/app/config.py`. Override any value with a `.env` file in the project root:

```env
# Example .env
DATABASE_URL=sqlite+aiosqlite:///./wildlife.db
SECRET_KEY=change-me-in-production
BATCH_SIZE=8
MEGADETECTOR_MODEL_PATH=C:/Users/Admin/ml_models/megadetector/md_v5a.0.0.pt
AWC135_MODEL_PATH=C:/Users/Admin/ml_models/awc135/awc-135-v1.pth
AWC135_LABELS_PATH=C:/Users/Admin/ml_models/awc135/labels.txt
OPEN_REGISTRATION=true
```

Important defaults:

| Setting | Default | Notes |
|---------|---------|-------|
| `BATCH_SIZE` | 8 | Lower to 4 if GPU runs out of memory |
| `TARGET_SPECIES` | `"Quoll"` | Species filter for re-ID pipeline |
| `REID_AUTO_ASSIGN` | `true` | Auto-link high-confidence re-ID matches |
| `STORAGE_ROOT` | `./storage` | Uploads, crops, thumbnails, re-ID models |

---

## Running tests

### Backend (pytest)

From project root:

```bash
conda activate wildlife
pytest backend/tests -q
```

### Frontend (Playwright)

From `frontend/`:

```bash
npm install
npx playwright install
npm run test:e2e          # UI tests with mocked API
npm run test:e2e:live     # Full stack against real backend
```

See [`frontend/TESTING.md`](frontend/TESTING.md).

---

## Quick reference

| Command | Purpose |
|---------|---------|
| `conda activate wildlife` | Activate Python environment |
| `uvicorn backend.app.main:app --reload` | Start backend |
| `python -m backend.app.db.init_db` | Create database tables |
| `cd frontend && npm run dev` | Start frontend dev server |
| `cd frontend && npm run build` | Production frontend build → `frontend/dist/` |
| `pytest backend/tests -q` | Run backend tests |
| `python -m scripts.run_pipeline --limit 100` | Standalone ML batch |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `CUDA not available` | Update NVIDIA driver ≥ 522.06; reinstall PyTorch CUDA wheel |
| GPU out of memory | Set `BATCH_SIZE=4` in `config.py` or `.env` |
| `ImportError: megadetector` | `pip install megadetector` inside `wildlife` env |
| `ModuleNotFoundError: awc_helpers` | `pip install -e C:\Users\Admin\ml_models\awc135_repo` |
| Missing model file | Check exact paths in `backend/app/config.py` |
| `Database locked` | One SQLite writer at a time; don't run multiple Celery workers on same DB |
| Upload fails — coordinates | Enter latitude/longitude for every camera subfolder |
| No re-ID suggestions | Ensure `storage/models/megadescriptor_l384_gallery.pt` exists |
| Admin page access denied | Sign in with an admin-role account |
| Frontend can't reach API | Confirm backend on port 8000; check `CORS_ORIGINS` in config |

---

## Project layout

```
Project321/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint
│   │   ├── config.py            # Settings (model paths, thresholds)
│   │   ├── api/                 # auth, images, detections, annotations,
│   │   │                        # individuals, reid, reports, exports,
│   │   │                        # stats, admin
│   │   ├── models/              # SQLAlchemy tables
│   │   ├── schemas/             # Pydantic request/response models
│   │   ├── services/            # Reports, re-ID backfill
│   │   └── utils/               # Auth, EXIF, event grouping
│   ├── worker/
│   │   ├── celery_app.py        # Optional Celery (falls back if absent)
│   │   ├── tasks.py
│   │   └── pipelines/           # megadetector, awc135, megadescriptor
│   └── tests/
├── frontend/
│   ├── src/App.tsx              # Main UI (all pages)
│   ├── src/AdminPage.tsx
│   ├── src/api.ts               # API client
│   └── tests/e2e/
├── scripts/                     # Pipeline, import, demo utilities
├── docs/                        # Re-ID documentation
├── Final submssion docs/        # User Manual, Technical Report
├── storage/                     # Runtime data (created on first run, gitignored)
├── requirements.txt
├── pytest.ini
├── README.md
└── SETUP.md
```

---

## Further reading

| Document | Location |
|----------|----------|
| Evaluator quick start | `README.md` |
| User Manual | `Final submssion docs/User_Manual.md` |
| Technical Report | `Final submssion docs/Technical_Report.md` |
| Frontend testing | `frontend/TESTING.md` |
| Re-ID model results | `docs/REID_MODEL_RESULTS.md` |
