# WildlifeTracker — Technical Report

**CSIT321 Final Project · Wildlife AI Detection System**

This document accompanies the WildlifeTracker product and covers system requirements, design, testing, closeout, and installation. It is intended for supervisors, subject coordinators, and technical evaluators.

| Section | Contents |
| :--- | :--- |
| 1 | Final system requirements (scope and iteration management) |
| 2 | Project summary and requirements traceability |
| 3 | System design (architecture, data dictionaries) |
| 4 | System testing |
| 5 | Project closeout (lessons learned, acceptance, transition) |
| 6 | Installation process |

---

# **1. Final System Requirements**

## **1.1 Introduction**

The Wildlife AI Detection System was developed to support ecologists and wildlife researchers in managing and analysing large volumes of camera trap data through artificial intelligence and modern web technologies. The system evolved iteratively throughout the project lifecycle, with functionality continuously refined based on supervisor feedback, technical limitations, and implementation progress.

The final implementation focuses on providing an integrated platform capable of wildlife image upload, automated species detection, human-assisted review workflows, species exploration, reporting, and administrative management.

## **1.2 Functional Requirements**

The table below lists the core functional requirements for the delivered WildlifeTracker platform and their implementation status.

| ID | Requirement | Implementation | Status |
| :--- | :--- | :--- | :--- |
| FR-01 | User registration, login, logout and role-based access (reviewer / researcher / admin) | `/api/auth`, JWT sessions, React auth context | Complete |
| FR-02 | Batch upload of camera-trap image folders with automatic collection and camera parsing | `/api/images/upload-batch`, Upload page | Complete |
| FR-03 | Automated wildlife detection (localise animals in images) | MegaDetector v5a pipeline | Complete |
| FR-04 | Automated species classification on detected crops | AWC135 classifier | Complete |
| FR-05 | Image browser with filters (processed, has animal, species, camera, search) | Images page, `/api/images` | Complete |
| FR-06 | Detection summary and species distribution view | Detections page, `/api/stats/species` | Complete |
| FR-07 | Species explorer with per-species image galleries | Profiles pages, `/api/individuals` | Complete |
| FR-08 | Known individual profiles, sightings, and timeline | Individuals tables, profile pages | Complete |
| FR-09 | Human-in-the-loop re-ID: AI top-5 suggestions and manual assignment | `/api/reid`, Manual re-ID panel | Complete |
| FR-10 | Side-by-side spot-pattern comparison (target vs reference) | Compare modal in image viewer | Complete |
| FR-11 | Human review: confirm, correct, annotate detections | `/api/annotations`, annotation UI | Complete |
| FR-12 | Dashboard analytics (counts, maps, activity charts) | Home page, `/api/stats`, `/api/reports` | Complete |
| FR-13 | Reporting and CSV/JSON export | Reports page, `/api/reports`, `/api/exports` | Complete |
| FR-14 | Admin: user management, system metrics, re-ID backfill | Admin page, `/api/admin` | Complete |
| FR-15 | Structured review queue (verify quolls, low confidence, empty check) | Pending Review pages (optional feature flag) | Partial |
| FR-16 | Fully automated individual recognition without human review | MegaDescriptor gallery + auto-assign | Partial |
| FR-17 | Automated model retraining from user corrections | Correction tables, export pipeline | Partial |

## **1.3 Non-Functional Requirements**

### **1.3.1 Performance**

The platform was designed to process thousands of camera trap images efficiently. Batch jobs run asynchronously in the background: when Redis and Celery are available, work is dispatched to Celery workers; otherwise the FastAPI process processes images locally using the same pipeline (see `backend/app/api/images.py`). FastAPI endpoints remain non-blocking throughout.

### **1.3.2 Scalability**

The architecture separates frontend, backend, database, and AI processing components to support future scalability and deployment expansion.

### **1.3.3 Usability**

The user interface prioritises simplicity, readability, and ease of navigation for both technical and non-technical users.

### **1.3.4 Maintainability**

The project follows a modular architecture that separates frontend rendering, backend APIs, database management, and machine learning workflows into independent components.

# **Project Summary**

## **Overview**

The Wildlife AI Detection System successfully achieved the primary objectives outlined in the original project proposal by implementing an integrated wildlife monitoring platform capable of supporting automated wildlife detection and ecological data management.

The final system combines a React and TypeScript frontend, a FastAPI backend, SQL database persistence, asynchronous processing, and AI-based wildlife detection models into a unified platform architecture.

## **Achievement of Original Requirements**

The implemented system satisfies the major functional requirements originally proposed during earlier project stages.

Key implemented features include:

* Batch image upload with automatic camera detection  
* Automated wildlife detection and classification  
* Detection review and annotation workflows  
* Dynamic species explorer and individual animal tracking  
* Dashboard analytics and reporting  
* Authentication and administrative management  
* Human-in-the-loop feedback workflows

The project also exceeded several initial requirements by implementing additional features such as review queues, annotation correction workflows, role-based administration, and dynamic frontend rendering systems.

## **Iterative Development and Scope Management**

The system underwent continuous iterative refinement throughout development. Supervisor feedback from previous assignments contributed to improvements in architecture clarity, workflow organisation, and frontend usability.

Several implementation decisions evolved during development:

### **AI Model Changes**

Initially, the project team attempted to train a custom wildlife detection model. However, the resulting detection performance was not sufficiently reliable for large-scale wildlife monitoring tasks.

To improve system accuracy and implementation stability, the project transitioned to a multi-stage AI pipeline using MegaDetector and AWC135 classification models.

### **Frontend Development Adjustments**

Frontend pages such as the Species Explorer were initially developed using mock data structures before backend APIs were fully implemented. This allowed frontend and backend development to proceed concurrently while maintaining development progress.

### **Workflow Improvements**

The upload workflow was redesigned to support automatic folder parsing and camera detection, significantly improving usability for researchers handling large camera trap datasets.

## **Current Project State**

At the current stage, the system successfully demonstrates a working minimum viable product capable of supporting end-to-end wildlife monitoring workflows.

The platform currently supports:

* Wildlife image upload  
* AI detection and classification  
* Species exploration  
* Detection review and annotation  
* Manual and AI-assisted individual re-identification  
* Side-by-side comparison of a target quoll against a known individual  
* Database persistence  
* Dashboard analytics  
* Authentication and access control

Individual re-identification is implemented as a human-in-the-loop workflow: the system proposes the most visually similar known individuals and provides a side-by-side comparison tool, while a reviewer makes the final assignment. Fully automated, unsupervised individual recognition and full production-deployment containerisation remain future development goals.

## **Requirements Traceability Matrix**

| Original Requirement | Implementation | Status |
| :---: | :---: | :---: |
| Upload camera trap images | Upload module | Complete |
| AI wildlife detection | MegaDetector | Complete |
| Species classification | AWC135 Classifier | Complete |
| Species Explorer | Dynamic Species Explorer | Complete |
| Individual animal tracking | Individuals & Sightings | Complete (human-in-the-loop) |
| Individual re-ID assistance | AI Top-5 suggestions + side-by-side comparison | Complete |
| Human review workflow | Annotation System | Complete |
| Dashboard analytics | Dashboard Module | Complete |
| User authentication | Login System | Complete |
| AI retraining support | Correction Workflow | Partial |

The project requirements evolved throughout development as the team gained a better understanding of both the available wildlife data and the limitations of automated identification. While the original vision aimed to fully automate both species classification and individual animal identification, testing revealed that the available image data was not sufficiently consistent to reliably distinguish individual animals across all observations. Factors such as varying camera angles, lighting conditions, partial visibility, and limited identifying features reduced the accuracy of fully automated individual recognition.

As a result, the project scope was adjusted to prioritise reliable species-level classification while adopting a human-in-the-loop approach for individual animal management. The final system automatically groups images by species and provides supervisors with tools to manually assign observations to individual animal profiles. To support this workflow, the system also generates recommendations by comparing new observations against existing individual profiles and identifying the most visually similar matches. This approach improved reliability while still reducing the manual workload required for wildlife monitoring and individual tracking.

# **System Design**

## **3.1 System Architecture**

The Wildlife AI Detection System follows a modular client-server architecture consisting of four primary components:

1. Frontend Application  
2. Backend API  
3. AI Processing Pipeline  
4. Database Layer

The architecture separates user interaction, backend processing, machine learning tasks, and persistent storage into independent modules to improve maintainability and scalability.

![][image1]

Figure 3.1 illustrates the overall architecture of the Wildlife AI Detection System. Users interact with the React frontend, which communicates with the FastAPI backend through REST API requests. The backend manages database operations and orchestrates AI processing: when Celery and Redis are available, batch jobs run on worker processes; otherwise the same pipeline runs in-process within the API server. Wildlife images are processed using MegaDetector and the AWC135 classifier, with detection results stored in the database for later review and analysis. 

## **3.2 Frontend Architecture**

The frontend was developed using:

* React 18  
* TypeScript  
* Vite  
* React Router  
* Leaflet  
* Recharts

The frontend provides:

* Dashboard visualisation  
* Upload workflows  
* Detection viewing  
* Species explorer  
* Review dashboard  
* Reporting pages  
* Administrative interfaces

React was selected due to its component-based architecture and ability to efficiently manage dynamic user interfaces. TypeScript was chosen to improve maintainability through static type checking and improved development tooling. Vite provides fast build times and development performance, while React Router enables efficient navigation within the single-page application architecture.

## **3.3 Backend Architecture**

The backend was implemented using FastAPI and Python.

The backend responsibilities include:

* Authentication and authorization  
* Image upload handling  
* API endpoint management  
* Database communication  
* AI task orchestration  
* Report generation  
* Annotation management

FastAPI was selected due to its high performance, asynchronous request handling, automatic API documentation generation, and compatibility with Python-based machine learning libraries. The framework allows efficient communication between the frontend, database layer, and AI processing pipeline.

## **3.4 AI Processing Pipeline**

The AI detection workflow operates through multiple stages:

1. MegaDetector detects wildlife within uploaded images  
2. Detected regions are cropped from images  
3. AWC135 classifier predicts species labels  
4. Detection results are stored in the database

Initial project development focused on training a custom wildlife detection model. However, testing results indicated insufficient accuracy and reliability for large-scale deployment. The project therefore adopted a multi-stage AI pipeline using MegaDetector for wildlife localisation and the AWC135 classifier for species recognition. This approach provided significantly improved performance while reducing development complexity.

## **3.5 Database Design**

The database layer of the Wildlife AI Detection System uses SQLAlchemy ORM with SQLite during development and PostgreSQL compatibility for future deployment. SQLAlchemy allows the system to define database structures through Python model classes while still maintaining relational database behaviour such as primary keys, foreign keys, and table relationships.

The database was designed to support the full wildlife monitoring workflow, including image upload, AI detection, human review, individual animal tracking, processing jobs, and model version management.

**Figure 3.5: Entity Relationship Diagram of the Wildlife AI Detection System![][image2]**

The Entity Relationship Diagram shows the relationship between the main data entities used by the system. Collections and cameras are linked to uploaded images, allowing each image to be traced back to its original field deployment and camera trap location. Each image can contain multiple AI detections, and each detection stores the predicted species, confidence score, bounding box coordinates, crop path, and review status.

The annotations table stores human review records linked to detections. This allows reviewers to confirm correct predictions, correct species labels, add notes, and flag records for retraining. The missed detection corrections table stores cases where the AI model failed to detect an animal, allowing users to draw a bounding box and provide correction data for future model improvement.

The sightings table acts as a bridge between detections, images, and known individual animals. This allows the system to track repeated appearances of the same animal across different camera trap images. The individuals table stores known animal profiles, including species, name, first seen date, last seen date, and total sighting count. The reference left and reference right detection fields are used to store representative detection images for identifying individual animals from different visible sides.

Processing jobs are linked to users and are used to track asynchronous batch image processing. The model versions table stores information about AI model versions, including model type, path, validation accuracy, and whether the model is active. Although the model versions table is not directly connected to another table in the ERD, it provides important support for AI model tracking and future retraining workflows.

### **3.5.1 Database Table Summary**

| Table | Purpose |
| ----- | ----- |
|   Users | Stores user accounts, authentication details, roles, and account status. |
| Collections | Stores survey or deployment collection information such as collection name, number, date, and folder path. |
| Cameras | Stores camera trap metadata such as camera name, number, side, GPS location, and elevation. |
| Images | Stores uploaded wildlife image metadata, including file path, camera link, collection link, processing status, and capture information. |
| Detections | Stores AI-generated wildlife detection results, including bounding box coordinates, predicted species, confidence score, crop path, and review status. |
| Annotations | Stores human review and correction records linked to AI detections. |
| Individuals | Stores known individual animal profiles, including species, name, first/last seen dates, sighting count, reference detection IDs, profile text, and notes. |
| Sightings | Links individual animals to specific images and detections, supporting animal tracking across multiple observations. |
| Deployments | Stores camera deployment information such as start date, end date, location, elevation, bait used, and trap nights. |
| Missed Detection Corrections | Stores user-submitted corrections for animals missed by the AI model. |
| Processing Jobs | Tracks asynchronous image processing batches, including progress, status, failures, and creator information. |
| Model Versions | Stores AI model registry information such as model name, type, path, training samples, validation accuracy, and active status. |
| Re-ID Suggestion Feedback | Stores reviewer feedback on AI re-ID suggestions (accept/reject) to support future model improvement. |

## **3.6 Data Dictionaries**

The following data dictionaries describe the main database tables used by the system. These fields represent the key data required to support image processing, AI detection, review workflows, and individual animal tracking.

### **3.6.1 Images Table**

| Field | Description |
| :---- | :---- |
| id | Unique identifier for each uploaded image. |
| filename | Original image file name. |
| file\_path | Storage path of the uploaded image. |
| camera\_id | Foreign key linking the image to the camera that captured it. |
| collection\_id | Foreign key linking the image to the collection or survey folder. |
| captured\_at | Date and time when the image was captured. |
| width | Image width in pixels. |
| height | Image height in pixels. |
| file\_size | Size of the uploaded image file. |
| processed | Indicates whether the image has been processed by the AI pipeline. |
| has\_animal | Indicates whether an animal was detected in the image. |
| thumbnail\_path | Path to the generated thumbnail image. |
| event\_id | Identifier used to group related images into an event. |
| temperature\_c | Temperature metadata recorded by the camera, if available. |
| trigger\_mode | Camera trigger mode metadata, if available. |

### **3.6.2 Detections Table**

| Field | Description |
| :---- | :---- |
| id | Unique identifier for each detection record. |
| image\_id | Foreign key linking the detection to the image where it was found. |
| bbox\_x | X-coordinate of the detection bounding box. |
| bbox\_y | Y-coordinate of the detection bounding box. |
| bbox\_w | Width of the detection bounding box. |
| bbox\_h | Height of the detection bounding box. |
| detection\_conf | Confidence score from the animal detection model. |
| category | General detection category, such as animal or empty. |
| species | Predicted wildlife species. |
| class\_confidence | Confidence score from the species classification model. |
| model\_version | Version of the AI model used for the detection. |
| crop\_path | Path to the cropped detected animal image. |
| review\_status | Human review status of the detection. |
| created\_at | Date and time when the detection record was created. |

### 

### **3.6.3 Individuals Table**

| Field | Description |
| :---- | :---- |
| id | Unique database identifier for each individual animal record. |
| individual\_id | Human-readable individual animal identifiers, such as Quoll-001. |
| species | Species of the individual animal. |
| name | Optional name assigned to the individual animal. |
| first\_seen | Date when the individual animal was first recorded. |
| last\_seen | Date when the individual animal was most recently recorded. |
| total\_sightings | Total number of sightings linked to the individual. |
| ref\_left\_detection\_id | Foreign key to a reference detection showing the left-side or identifying view of the animal. |
| ref\_right\_detection\_id | Foreign key to a reference detection showing the right-side or identifying view of the animal. |
| profile\_lead | Optional overview text displayed on the individual profile. |
| notes | Optional ecologist notes stored on the profile. |

### **3.6.4 Sightings Table**

| Field | Description |
| :---- | :---- |
| id | Unique identifier for each sighting record. |
| individual\_id | Foreign key linking the sighting to a known individual animal. |
| image\_id | Foreign key linking the sighting to the image where the animal appeared. |
| detection\_id | Foreign key linking the sighting to the AI detection record. |
| identified\_by | User or process that identified the animal. |
| source | Indicates whether the sighting was generated by AI, manual review, or another process. |

### **3.6.5 Annotations Table**

| Field | Description |
| :---- | :---- |
| id | Unique identifier for each annotation record. |
| detection\_id | Foreign key linking the annotation to a detection. |
| annotator | User who reviewed or annotated the detection. |
| corrected\_species | Corrected species label provided by the reviewer, if required. |
| is\_correct | Indicates whether the original AI prediction was correct. |
| notes | Additional reviewer comments. |
| individual\_id | Optional reference to a known individual animal. |
| flag\_retraining | Indicates whether the annotation should be used for future model retraining. |
| created\_at | Date and time when the annotation was created. |

## **3.7 Frontend–Backend Communication Design**![][image3]

The frontend communicates with the backend through REST API endpoints and asynchronous JSON requests. This communication design allows the frontend interface to remain separate from backend processing logic, improving maintainability and allowing both parts of the system to be developed independently.

The general communication flow is as follows:

1. A user performs an action on the frontend, such as uploading images, viewing detections, reviewing an annotation, or opening the species explorer.  
2. The frontend sends an API request to the backend using an appropriate REST endpoint.  
3. The backend validates the request and performs the required operation.  
4. The backend queries or updates the database using SQLAlchemy ORM.  
5. The backend returns a JSON response containing the requested data or operation result.  
6. The frontend receives the response and dynamically updates the user interface.

For example, when a user uploads a collection of camera trap images, the frontend sends the image files and folder metadata to the backend. The backend creates the required collection, camera, image, and processing job records, then dispatches the AI processing workflow. As the AI pipeline processes images, the frontend can request progress updates and display the current processing status to the user.

This design supports modular development, efficient data communication, and a responsive user experience even when large image processing tasks are being performed in the background.

# **4\. System Testing**

## **4.1 Functional Testing**

| Test Case | Expected Result | Outcome |
| ----- | ----- | ----- |
| User Login | User authenticated | Pass |
| Upload Images | Images uploaded | Pass |
| Run Detection | Animals detected | Pass |
| Open Species Explorer | Species displayed | Pass |
| Create Annotation | Annotation saved | Pass |
| Generate Dashboard | Statistics displayed | Pass |

## **4.2 Integration Testing**

Integration testing covered frontend ↔ backend ↔ database ↔ AI communication.

**Frontend ↔ Backend:** The React/TypeScript frontend communicates with the FastAPI backend via RESTful endpoints. Backend tests confirm that multipart image payloads and JSON metadata are parsed, validated (via Pydantic schemas), and persisted correctly.

**Backend ↔ Database:** Automated tests in `backend/tests/` cover auth, images, detections, annotations, reports, stats, admin, and pipeline verification modules (65+ test cases across eight test files). Tests verify CRUD operations and relationships among Collections, Cameras, Images, Detections, Annotations, and Individuals in SQLite.

**Database ↔ AI pipeline:** Pipeline verification tests confirm that MegaDetector and AWC135 outputs are parsed correctly and that bounding boxes, species classifications, and confidence scores are stored in the Detections table. End-to-end Playwright tests in `frontend/tests/e2e/` validate key UI workflows against a mocked or live API.

## **4.3 User Acceptance Testing**

UAT focused on evaluating the system against the practical needs of wildlife ecologists. Throughout the iterative development cycle, regular demonstrations were provided to the project supervisor, and their feedback drove several key improvements:

* **Workflow Refinement:** Initial designs required manual intervention between detection and classification. Supervisor feedback highlighted the need for bulk automation, which led to a fully automated end-to-end pipeline.  
* **Data Export Utility:** Researchers required accessible data outputs for external analysis. The system was iteratively updated to include robust CSV and JSON export functionalities (/api/exports), allowing users to easily extract annotation and statistical data.  
* **UI/UX Adjustments:** The frontend species explorer and dashboard were refined to support large datasets (thousands of images) and to ensure that pagination and filtering could be performed intuitively without overwhelming the browser.

# **5\. Project Closeout**

### **5.1 Lessons Learned**

* **Importance of iterative development:** Initially, processing machine learning (ML) tasks synchronously resulted in API timeouts and a poor user experience. Iteratively evolving the architecture to an asynchronous model (incorporating Redis and Celery) was essential to decouple the high-speed web interface from resource-intensive, long-running ML inference processes.  
* **Challenges of AI training:** A critical discovery was that processing every camera-trap image directly through the species classification model consumed massive computational resources. We learned that chaining models—using an object detection model (MegaDetector) first to filter out 70–90% of empty images before passing image crops to the species identification model (AWC135 classifier)—drastically reduced processing time and storage overhead.  
* **Frontend/backend integration:** Managing asynchronous state between a disconnected user interface (UI) and background processing workers proved challenging. Implementing a robust polling mechanism in which the React-based UI continuously queried the backend service for job progress updates was necessary to keep users informed during bulk uploads.  
* **Database design:** While aiosqlite enabled rapid ML pipeline prototyping, we learned that SQLite experiences write-lock issues when multiple Celery workers execute simultaneous database operations. Preparing the Object Relational Mapper (ORM) for deployment on a robust relational database management system (such as PostgreSQL) is necessary for scaling.


### **5.2 Post-Project Review**

* **What Worked Well:** The highly modular architecture (separating the Vite/React UI, FastAPI routing, and Celery ML workers) is the system's greatest success. It prevents heavy machine learning workloads from crashing the web server. Furthermore, the successful integration of the AWC135 PyTorch model allows for highly accurate Spotted-tailed quoll detection.  
* **Areas for Improvement:** The system currently relies on SQLite, which limits horizontal scaling of the ML workers. Finalizing the database migration to PostgreSQL (via asyncpg and psycopg) is the primary technical debt to address. Additionally, more robust error handling and automatic retries for failed Celery tasks would improve system resilience.

### **5.3 Project Acceptance**

The final delivered system successfully meets all core functional requirements outlined in the initial project scope. The platform provides an integrated web environment capable of bulk wildlife image uploading, automated species detection and classification, human-assisted review workflows, and statistical reporting.

### **5.4 Transition Plan**

**Future development:**

* **Cloud deployment:** Containerizing the frontend, backend, and worker nodes using Docker, orchestrated via Kubernetes, to allow the system to scale dynamically in cloud environments (AWS/Azure). Image storage will transition from local directories to scalable Object Storage (S3/MinIO).   
* **Additional species models:** Expanding the classifier's weights and category mapping to detect a broader taxonomy of native Australian species beyond the current focus.   
* **Automated re-identification:** Fully integrating the experimental MegaDescriptor pipeline. This will utilize FAISS vector search and cosine similarity on cropped animal embeddings to automatically match and track individual animals across different camera deployments.   
* **Automated retraining:**Implementing a data feedback loop where user corrections (tracked in the database via `missed_correction` and `reid_suggestion_feedback` tables) are compiled nightly to fine-tune and retrain the ML models, continuously improving accuracy. 

# **6. Installation Process**

This section describes how to run WildlifeTracker locally for development and evaluator testing. Full step-by-step instructions with verification commands are also in the repository root files `SETUP.md` and `README.md`.

## **6.1 System Prerequisites**

| Component | Requirement |
| :--- | :--- |
| Operating system | Windows 10 or 11 (primary development target) |
| Hardware | NVIDIA GPU with CUDA support (tested on RTX 3080 10 GB); 32 GB RAM recommended for large batches |
| Python | 3.10 (Miniconda recommended) |
| Node.js | 18+ LTS |
| Git | Latest |
| NVIDIA driver | ≥ 522.06 (CUDA 11.8 compatible) |
| Redis + Celery | **Optional** — batch upload falls back to in-process processing when Celery is not running |

## **6.2 Environment and Backend Setup**

Use a dedicated Conda environment to avoid dependency conflicts.

**1. Clone the repository and create the environment**

```bash
git clone https://github.com/Noobmaster678/Project321
cd Project321
conda create -n wildlife python=3.10 -y
conda activate wildlife
```

**2. Install GPU-accelerated PyTorch (CUDA 11.8)**

```bash
pip install torch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cu118
```

**3. Install backend dependencies**

```bash
pip install -r requirements.txt
pip install megadetector
```

**4. Download model weights to the paths expected by `backend/app/config.py`**

| File | Required path |
| :--- | :--- |
| MegaDetector v5a weights | `C:\Users\Admin\ml_models\megadetector\md_v5a.0.0.pt` |
| AWC135 classifier weights | `C:\Users\Admin\ml_models\awc135\awc-135-v1.pth` |
| AWC135 label list | `C:\Users\Admin\ml_models\awc135\labels.txt` |

Download MegaDetector from [Microsoft CameraTraps v5.0](https://github.com/microsoft/CameraTraps/releases/tag/v5.0) or [Hugging Face](https://huggingface.co/agentmorris/megadetector/resolve/main/md_v5a.0.0.pt). AWC135 weights may need to be obtained from the project supervisor if not publicly available.

**5. Install the AWC classifier helper package**

```bash
git clone https://github.com/Australian-Wildlife-Conservancy-AWC/awc-wildlife-classifier.git C:\Users\Admin\ml_models\awc135_repo
pip install -e C:\Users\Admin\ml_models\awc135_repo
```

**6. Initialise the database**

```bash
python -m backend.app.db.init_db
```

## **6.3 Running the Application**

**Terminal 1 — Backend API**

```bash
conda activate wildlife
uvicorn backend.app.main:app --reload
```

- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

**Terminal 2 — Frontend**

```bash
cd frontend
npm install
npm run dev
```

- Application UI: `http://localhost:5173`

**Optional Terminal 3 — Celery worker (for distributed batch processing)**

Only needed if Redis is installed and you want ML jobs on a separate worker process:

```bash
conda activate wildlife
celery -A backend.worker.celery_app worker --loglevel=info
```

If Celery is not running, uploaded batches are still processed automatically by the API process.

**Optional — standalone ML batch script (no web UI)**

```bash
python -m scripts.run_pipeline --limit 100 --batch-size 8
```

## **6.4 Evaluator Smoke Test**

1. Open `http://localhost:5173` — Home dashboard loads with statistics.
2. Register or log in — session appears in the top-right user menu.
3. Upload a camera-trap folder via **Upload** (sign-in required).
4. Confirm job progress completes and images appear under **Images**.
5. Open **Profiles → Dasyurus sp | Quoll sp → Images** and review detections.
6. Open **Reports** and export CSV or JSON.
7. Log in as an admin account and open **Admin** for user management and re-ID backfill.

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,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>