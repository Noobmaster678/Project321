# WildlifeTracker — User Manual

**AI-assisted camera-trap platform for detecting, classifying and re-identifying the Spotted-tailed Quoll (*Dasyurus maculatus*).**

---

## About this manual

This manual explains how to operate the WildlifeTracker web application from a user's point of view. It is written for the people who actually use the system day to day — wildlife ecologists, research assistants and image reviewers — and assumes no software background. Technical and installation details live in the separate **Technical Report**; this document is about *using* the product.

It is organised as:

1. **Who the system is for** — target users and what each can do.
2. **Quick-start** — the three things most users need on day one.
3. **Step-by-step procedures** — each task, in order, with the exact buttons to click.
4. **Reference** — keyboard shortcuts, roles, glossary and troubleshooting.

> Throughout this manual, **bold** text refers to a label or button you will see on screen.

---

## 1. Who the system is for

WildlifeTracker is used by conservation teams who run camera-trap surveys and need to find quolls in tens of thousands of photos without reviewing every frame by hand. The platform uses two AI models — **MegaDetector** (finds animals) and **AWC135** (identifies the species) — then helps a human confirm the result and, for quolls, work out *which individual animal* it is from its unique spot pattern.

### User roles

The features available to you depend on the role attached to your account:

| Role | Typical user | Can do |
|------|--------------|--------|
| **Reviewer** | Research assistant / volunteer | Browse images, view detections and reports, confirm/correct detections, assign quolls to known individuals. |
| **Researcher** | Ecologist / project lead | Everything a Reviewer can do, **plus** create new individual profiles (upload requires sign-in; field teams should use Researcher or Admin accounts). |
| **Admin** | System administrator | Everything above, **plus** manage user accounts and roles, view system analytics and run model maintenance from the **Admin** page. |

Anyone (even without logging in) can browse images, detections, profiles and reports. Logging in is only required to **change data** — confirming detections, assigning individuals, uploading, or creating profiles.

---

## 2. Quick-start

### 2.1 Home dashboard
1. Open the application (your administrator will give you the address, e.g. `http://localhost:5173`).
2. The **Home** page shows live summary cards: total observations, active species, known individuals, and cameras.
3. Scroll for species abundance, activity-by-time charts, a camera map, and recent detections. The dashboard refreshes automatically every few seconds.

### 2.2 Sign in
1. Open the application in your browser (your administrator will give you the address, e.g. `http://localhost:5173`).
2. Click **👤 Sign in** (top-right).
3. Enter your email and password, then **Sign In**.
   - No account yet? Click **Register**, fill in your name, email and password, choose your role, and submit.
4. Your name and role appear top-right once you are signed in. Use the **👤 menu → Sign out** to log out.

### 2.3 Find quoll photos
1. Click **Profiles** in the top menu.
2. Select **Dasyurus sp | Quoll sp** (the quoll group).
3. Click **Images** to see every quoll photo in the survey.

### 2.4 Open and review a photo
1. Click any thumbnail to open the full image.
2. The green boxes are the AI's detections. Toggle them with the **Boxes** checkbox.
3. Use **← Prev / Next →** (or the **left/right arrow keys**) to flip through photos, and **Esc** to close.

That is enough to start reviewing. The full procedures below cover uploading, identification and reporting.

---

## 3. Step-by-step procedures

### 3.1 Browsing images

**Goal: locate the photos you want to work on.**

1. Click **Images** in the top menu to open the image browser.
2. Narrow the list using the filters at the top:
   - **Processed / Pending** — whether the AI has finished analysing the photo.
   - **Has animal / Empty** — MegaDetector's verdict.
   - **Species** — filter to a single species.
   - **Camera** — restrict to one camera location.
   - **Search** — type part of a filename.
3. Photos are grouped by camera folder and sorted by capture time by default. Use the **sort** control to change the order.
4. Click a thumbnail to open it. Use the **Prev / Next** buttons or **arrow keys** to move through the set.

### 3.2 Uploading a new camera-trap batch *(sign-in required; Researcher / Admin)*

**Goal: bring a folder of new photos into the system for AI processing.**

1. Sign in, then click **Upload**.
2. Drag a camera-trap folder onto the drop zone, **or** click to choose a folder. The system reads the folder structure to work out camera names automatically.
   - Expected layout: `CollectionName/CameraFolder/image.jpg` (collection → camera subfolders → images).
3. Give the batch a **Collection name** (the survey or trip name). If one is detected from the folder, it is filled in for you.
4. Enter the **latitude and longitude** for each detected camera folder. These are **required** when the upload contains camera subfolders — the form will not submit until every camera has valid coordinates (−90…90 for latitude, −180…180 for longitude).
5. Click **Upload & Process** and leave the page open. A **progress bar** shows images processed vs. total.
6. When the job completes, the new images appear under **Images** and, once processed, under the relevant species in **Profiles**.

> Large folders are processed in the background — you can navigate away and the job continues. Processing runs in the API server by default; a separate Celery worker is optional for larger deployments.

### 3.3 Confirming and correcting a detection *(sign-in required)*

**Goal: tell the system whether the AI got the species right.**

1. Open a photo (see 3.1) and click a detection box, or click a detection chip below the image, to **focus** it. The focused box turns blue.
2. Check the species and confidence shown on the box label.
3. If the AI is correct, no action is needed — it is already recorded. If it is wrong, use the review controls to enter the **correct species** and save. Your correction is stored as an annotation against that detection and can be flagged to help retrain the model.

### 3.4 Identifying which quoll it is (manual re-ID) *(sign-in required)*

Every Spotted-tailed Quoll has a unique pattern of white spots. WildlifeTracker helps you decide which known individual a photo shows.

1. Open a quoll photo from **Profiles → Dasyurus sp | Quoll sp → Images**.
2. **Focus** the quoll detection (click its box). The **Manual re-ID** panel appears.
3. Review the **AI suggestions (Top 5)** — the system lists the most visually similar known individuals with a similarity score. If one is clearly correct, click it to assign the photo to that individual.
4. If you prefer to assign by hand, type the individual's ID (e.g. `02Q2`) into **Assign to existing ID** and click **Assign**.
5. To remove an assignment, click **Unassign**.

> **Tip:** Before confirming, use the **Compare side-by-side** tool (3.5) to check the spot pattern carefully.

### 3.5 Comparing a quoll side-by-side ⭐ *new*

**Goal: confirm an identification by matching spot patterns at high zoom.**

1. With a quoll photo open and a detection focused, find the **Reference comparison** row in the Manual re-ID panel.
2. Choose a known individual from the drop-down (e.g. `02Q2`).
3. Click **⇆ Compare side-by-side**. A large two-pane view opens:
   - **Left (TARGET)** — the quoll you are identifying.
   - **Right (REFERENCE)** — confirmed photos of the chosen individual.
4. Inspect the markings:
   - Drag the **Zoom** slider (1×–5×) — *both* panes magnify together for a fair comparison.
   - **Hover the mouse** over either pane to magnify exactly the area under the cursor, so you can sweep across the flanks and tail.
   - Use the **thumbnail strip** at the bottom, the **← →** buttons, or the **left/right arrow keys** to flip through the individual's reference photos.
   - Switch the target between **Crop** (the cut-out animal) and **Full frame** (the whole photo).
5. Press **Esc** or **Close** to return. If the patterns match, assign the individual as in step 3.4.

**Comparison shortcuts:** `← / →` change reference photo · `+ / −` zoom in/out · `Esc` close.

### 3.6 Creating a new individual profile *(Researcher / Admin)*

**Goal: register a quoll that has not been seen before.**

1. In the Manual re-ID panel, click **Create new profile…**.
2. Enter a new **ID** (following your project's naming convention, e.g. `09Q3`) and an optional nickname.
3. Choose two clear reference detections — set one as **LEFT ref** and one as **RIGHT ref** (typically a left-side and right-side view). You can navigate other photos while the dialog is open to find good shots.
4. Click **Create profile + assign**. The new individual is created and the current detection is assigned to it.

### 3.7 Assigning many photos at once *(sign-in required)*

**Goal: assign a whole page of photos to one individual quickly.**

1. On a species **Images** page, click **Select images**.
2. Tick the photos you want (or **Select all on page**).
3. Enter or pick the target **Profile ID** in the bar that appears, and click **Assign to …**.
4. A summary confirms how many detections were assigned. Use **Unassigned only** to focus on photos still needing identification.

### 3.8 Viewing an individual's history

1. Go to **Profiles → Dasyurus sp | Quoll sp → individuals**.
2. Click an individual to see its photo gallery, first/last seen dates, total sightings, and a movement timeline/map.

### 3.9 Generating and exporting reports

**Goal: produce summary statistics and data extracts for analysis.**

1. Click **Reports**.
2. Set the filters you need: **date range**, **location/camera**, **species** or a specific **individual**.
3. The page shows species distribution, detection counts, activity by hour and month, identified-quolls-over-time, a sightings map, and Relative Abundance Index (RAI) figures.
4. To export, choose **CSV Data** (for spreadsheets) or **JSON Data** (for further processing), then click **Export Report**. The file downloads to your computer.

### 3.10 Viewing detection statistics

**Goal: see how many animals of each species the AI has found across the survey.**

1. Click **Detections** in the top menu.
2. Review the summary cards: total detections, species found, and quoll detections.
3. Scroll the **Species Distribution** list to compare counts and percentages. Quoll rows are highlighted.

### 3.11 Using in-app Help

1. Click **Help** in the top menu (or the **❓** icon).
2. The page shows a quick-reference card for each common task and a keyboard-shortcut summary.
3. Use it alongside this manual for day-to-day reminders.

### 3.12 Pending Review queue *(optional — when enabled by administrator)*

When the **Pending Review** menu item is visible, it provides a structured workflow for:

- **Verify quoll detections** — confirm species labels on unreviewed quoll crops.
- **Low-confidence detections** — review uncertain classifications.
- **Check empty images** — spot-check frames marked as having no animal.
- **Assign individuals** — link verified quoll detections to known profiles.

Open **Pending Review**, pick a category card, and work through the queue. This feature requires the administrator to enable `VITE_ENABLE_PENDING_REVIEW=true` at build time.

### 3.13 Administering the system *(Admin only)*

1. Click **Admin** (visible only to administrators).
2. **Manage users:** view all accounts and change a user's role (reviewer / researcher / admin).
3. **Monitor the system:** view platform analytics and processing metrics.
4. **Model maintenance:** run re-ID backfill and related maintenance tasks.

---

## 4. Reference

### 4.1 Keyboard shortcuts

| Where | Key | Action |
|-------|-----|--------|
| Image viewer | `←` / `→` | Previous / next photo |
| Image viewer | `Esc` | Close the viewer |
| Side-by-side compare | `←` / `→` | Previous / next reference photo |
| Side-by-side compare | `+` / `−` | Zoom in / out |
| Side-by-side compare | `Esc` | Close the comparison |

### 4.2 Glossary

- **Detection** — a box drawn by MegaDetector around something it thinks is an animal.
- **Classification** — the species label AWC135 assigns to a detection, with a confidence score.
- **Annotation** — a human's confirmation or correction of a detection (and any individual assignment).
- **Individual / profile** — a single named animal (e.g. `02Q2`) that photos can be assigned to.
- **Re-ID (re-identification)** — deciding which known individual a new photo shows.
- **Collection** — a named batch of photos, usually one survey or field trip.
- **RAI (Relative Abundance Index)** — independent detection events per 100 trap-nights, a standard camera-trap activity measure.

### 4.3 Troubleshooting

| Problem | What to do |
|---------|------------|
| **"Login required"** message | Sign in — the action you tried changes data and needs an account. |
| **Upload / Create profile not available** | Upload needs sign-in. **Create profile** needs the **Researcher** or **Admin** role. Ask an administrator to upgrade your account. |
| **Upload blocked — missing coordinates** | When your folder has camera subfolders, enter latitude and longitude for every camera before uploading. |
| **Photo still says "Pending"** | The AI has not finished processing it yet. Check back after the upload job completes. |
| **No AI suggestions for a quoll** | The re-ID model needs a usable crop and a reference gallery. You can still assign the individual manually (3.4). |
| **Compare button is greyed out** | Pick an individual in the **Reference comparison** drop-down first; the button enables once that individual has reference photos. |
| **Signed out unexpectedly** | Your session expired. Simply sign in again. |

---

*WildlifeTracker — CSIT321 Project. See the Technical Report for architecture, data dictionaries and installation.*
