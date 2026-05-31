# WildlifeTracker

AI-assisted camera-trap platform for detecting, classifying, and re-identifying the **Spotted-tailed Quoll** (*Dasyurus maculatus*).

**Stack:** React + TypeScript frontend · FastAPI backend · SQLite · MegaDetector + AWC135 ML pipeline · optional MegaDescriptor re-ID gallery

This guide is a **quick start for evaluators and testers** on Windows with an NVIDIA GPU. For full step-by-step setup, see [`SETUP.md`](SETUP.md). For end-user instructions, see [`Final submssion docs/User_Manual.md`](Final%20submssion%20docs/User_Manual.md).

---

## What the application does

| Area | Features |
|------|----------|
| **Home** | Live dashboard — observation counts, species charts, camera map, recent detections |
| **Upload** | Batch folder upload with automatic collection/camera parsing; GPS required per camera folder |
| **Images** | Browse and filter camera-trap photos; view AI bounding boxes |
| **Detections** | Species distribution summary from MegaDetector + AWC135 |
| **Profiles** | Species explorer, quoll image galleries, individual profiles, manual re-ID, side-by-side comparison |
| **Reports** | Analytics, sightings map, RAI; export CSV or JSON |
| **Admin** | User roles, system metrics, re-ID backfill (admin only) |
| **Help** | In-app quick reference |

**User roles:** `reviewer`, `researcher`, `admin`. Sign-in is required to change data (upload, annotate, assign individuals). The first registered user may choose the **admin** role.

Browsing (images, detections, profiles, reports) works without logging in.

---

## Project structure

```
Project321/
├── backend/                 # FastAPI app, models, API routes, ML worker
│   ├── app/api/             # REST endpoints
│   ├── app/models/          # SQLAlchemy ORM models
│   ├── worker/pipelines/    # MegaDetector, AWC135, MegaDescriptor
│   └── tests/               # pytest suite
├── frontend/                # React + Vite UI
│   ├── src/                 # App.tsx, AdminPage.tsx, api.ts, auth.tsx
│   └── tests/e2e/           # Playwright tests
├── scripts/                 # Pipeline, import, demo, and utility scripts
├── docs/                    # Re-ID model notes
├── Final submssion docs/    # User Manual, Technical Report, marketing
├── requirements.txt
├── SETUP.md
└── README.md                # this file
```

**Not in the repository** (local / supplied separately): `node_modules/`, `storage/`, `dataset/`, `wildlife.db`, ML model weights under `C:\Users\Admin\ml_models\`.

---

## System requirements

- Windows 10/11
- NVIDIA GPU with CUDA support (tested on RTX 3080 10 GB)
- Python 3.10 (Conda recommended)
- Node.js 18+ LTS
- Git

**Optional:** Redis + Celery — only needed if you want batch jobs on a separate worker. By default, uploads are processed inside the API process.

---

## Quick install

```bash
git clone https://github.com/Noobmaster678/Project321
cd Project321

conda create -n wildlife python=3.10 -y
conda activate wildlife

pip install torch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
pip install megadetector
```

Install the AWC135 helper package:

```bash
git clone https://github.com/Australian-Wildlife-Conservancy-AWC/awc-wildlife-classifier.git C:\Users\Admin\ml_models\awc135_repo
pip install -e C:\Users\Admin\ml_models\awc135_repo
```

Download model weights to the paths defined in `backend/app/config.py`:

| File | Path |
|------|------|
| MegaDetector v5a | `C:\Users\Admin\ml_models\megadetector\md_v5a.0.0.pt` |
| AWC135 weights | `C:\Users\Admin\ml_models\awc135\awc-135-v1.pth` |
| AWC135 labels | `C:\Users\Admin\ml_models\awc135\labels.txt` |

- MegaDetector: [CameraTraps v5.0](https://github.com/microsoft/CameraTraps/releases/tag/v5.0) · [direct download](https://huggingface.co/agentmorris/megadetector/resolve/main/md_v5a.0.0.pt)
- AWC135: [awc-wildlife-classifier](https://github.com/Australian-Wildlife-Conservancy-AWC/awc-wildlife-classifier) — request weight files from the project team if not publicly available.

---

## Run the application

**Terminal 1 — backend**

```bash
conda activate wildlife
python -m backend.app.db.init_db    # optional; tables also auto-create on first API start
uvicorn backend.app.main:app --reload
```

**Terminal 2 — frontend**

```bash
cd frontend
npm install
npm run dev
```

| URL | Purpose |
|-----|---------|
| http://localhost:5173 | Web UI |
| http://localhost:8000/docs | Swagger API docs |
| http://localhost:8000/health | Health check |

---

## Upload folder format

For batch upload, use a folder layout like:

```
MySurvey/
├── Camera_A/
│   ├── IMG_001.jpg
│   └── IMG_002.jpg
└── Camera_B/
    └── IMG_003.jpg
```

When camera subfolders are detected, **latitude and longitude are required** for each camera before upload will proceed.

---

## Optional: Celery worker

If Redis is installed and you prefer distributed batch processing:

```bash
conda activate wildlife
celery -A backend.worker.celery_app worker --loglevel=info
```

If Celery is not running, the API falls back to in-process processing automatically.

---

## Optional: Re-ID gallery

Individual quoll suggestions use a MegaDescriptor gallery checkpoint. By default the app looks for:

```
storage/models/megadescriptor_l384_gallery.pt
```

Build or copy this file using `scripts/reid_megadescriptor_hf_mvp.py`. Re-ID suggestions still work manually without the gallery; AI top-5 suggestions require it.

---

## Optional: Pending Review pages

The structured review queue is disabled by default. To enable it, set before building or running the frontend:

```bash
# frontend/.env.local
VITE_ENABLE_PENDING_REVIEW=true
```

---

## Standalone ML pipeline (no web UI)

```bash
conda activate wildlife
python -m scripts.run_pipeline --limit 100 --batch-size 8
```

---

## Demo test checklist (for marking)

- [ ] Home dashboard loads at http://localhost:5173
- [ ] Register / sign in (first user can register as admin)
- [ ] Upload a camera-trap folder; progress bar completes
- [ ] Images appear under **Images** with detection boxes
- [ ] **Detections** shows species distribution
- [ ] **Profiles → Dasyurus sp | Quoll sp** shows quoll photos
- [ ] Manual re-ID: assign individual or use side-by-side compare
- [ ] **Reports** displays charts and exports CSV/JSON
- [ ] **Admin** reachable with an admin account

---

## Running tests

**Backend (from project root):**

```bash
conda activate wildlife
pip install -r requirements.txt
pytest backend/tests -q
```

**Frontend (from `frontend/`):**

```bash
npm install
npx playwright install
npm run test:e2e          # mocked API
npm run test:e2e:live     # full stack (starts backend + frontend)
```

See [`frontend/TESTING.md`](frontend/TESTING.md) for details.

---

## Configuration

Settings live in `backend/app/config.py` and can be overridden with a `.env` file in the project root (e.g. `DATABASE_URL`, `SECRET_KEY`, model paths, `BATCH_SIZE`).

Model paths, detection thresholds, and CORS origins are all configurable there.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `CUDA available: False` | Update NVIDIA driver (≥ 522.06), reinstall the CUDA PyTorch command above |
| Import errors (`sqlalchemy`, etc.) | Confirm `conda activate wildlife` and `pip install -r requirements.txt` |
| `ModuleNotFoundError: awc_helpers` | Re-run `pip install -e C:\Users\Admin\ml_models\awc135_repo` |
| Missing model file errors | Verify paths in section **Quick install** match `backend/app/config.py` |
| Upload rejected — missing coordinates | Enter lat/lon for every camera subfolder |
| `Database locked` | Only one writer to SQLite at a time; avoid multiple workers on the same DB |
| GPU out of memory | Lower `BATCH_SIZE` in `backend/app/config.py` (default 8 → 4) |

---

## Documentation

| Document | Location |
|----------|----------|
| User Manual | `Final submssion docs/User_Manual.md` |
| Technical Report | `Final submssion docs/Technical_Report.md` |
| Full setup guide | `SETUP.md` |
| Re-ID notes | `docs/REID_MODEL_RESULTS.md` |
