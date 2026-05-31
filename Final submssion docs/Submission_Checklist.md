# Final Submission Checklist — WildlifeTracker

Use this checklist before submitting to subject coordinators and publishing on the project site.

## Required documentation

| Item | File / location | Status |
| :--- | :--- | :--- |
| User manual | `User_Manual.md` | ✅ Present |
| Technical report | `Technical_Report.md` | ✅ Present |
| Group meeting agendas and minutes | `Group_Meeting_Agendas_and_Minutes.md` | ⚠️ Template — **fill in actual meeting records** |
| Project marketing | `Wildlife Tracker marketing report.docx` | ✅ Present |
| Design progress (earlier assignment) | `Design Progress Documentation (Assignment 4).pdf` | ✅ Present |
| Source code | Repository root (`backend/`, `frontend/`, `scripts/`) | ✅ In repo |
| Installation guide | `SETUP.md`, `README.md` (also summarised in Technical Report §6) | ✅ In repo |

## Executable / binaries

| Item | Notes |
| :--- | :--- |
| Runnable prototype | Backend (FastAPI) + frontend (Vite) — see Technical Report §6 |
| ML model weights | Not in repo — provide on USB or separate download if too large for Moodle |
| Demo data (optional) | Sample images or pre-seeded database if evaluators cannot upload |

## Optional (if required by supervisor)

| Item | Notes |
| :--- | :--- |
| Peer and self-assessment | Attach when coordinator provides form |
| List of actual work completed | Per-member contribution summary |
| Individual reflections | One per group member if requested |

## Pre-submission verification

- [ ] All group members have contributed to code and/or documentation (document in meeting minutes)
- [ ] User Manual steps match the running application (navigation labels, upload rules, re-ID workflow)
- [ ] Technical Report installation paths match `backend/app/config.py`
- [ ] Meeting minutes completed with real dates, attendees, and decisions
- [ ] Marketing report reviewed for consistency with final product name (**WildlifeTracker**)
- [ ] Copy of all docs uploaded to project site / Moodle as required
- [ ] Smoke test passed: login → upload → detections → profiles → reports → admin

## Known documentation notes

- **Pending Review** pages are optional and only appear when `VITE_ENABLE_PENDING_REVIEW=true` is set at frontend build time.
- **Celery + Redis** are optional for local evaluation; batch upload processes in the API process by default.
- **AWC135 model weights** may need to be supplied separately if not publicly downloadable.
