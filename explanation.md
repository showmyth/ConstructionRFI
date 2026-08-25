# Construction RFI Project Explanation

This project is an ingestion and processing pipeline for construction-related files such as images, PDFs, and audio. The high-level goal is:

1. Accept a file through an API.
2. Validate and store it safely on disk.
3. Record metadata about the asset in a database.
4. Queue the asset for background processing.
5. Run extraction logic (OCR, transcription, or object detection).
6. Persist extracted text and chunked content for downstream use.

The system is built around a small asynchronous service architecture with:

- a FastAPI HTTP layer for uploads and health checks,
- a Celery-based background worker for heavy processing,
- SQLAlchemy models for persistent storage,
- a set of service modules for OCR, speech transcription, vision detection, cleaning, and chunking.

---

## 1. Overall Architecture

### A. API layer
The API layer is located in the `apps/api` package.

It exposes:

- `/health` for a simple health check.
- `/upload` for accepting a file upload.
- `/job/{job_id}` as a placeholder endpoint for status lookup.

The upload route is the main entry point for user submissions.

### B. Worker layer
The worker layer is located in `apps/worker/main.py`.

It defines a Celery app and a task named `process_asset_task`. This task is responsible for taking a queued asset and running the actual extraction pipeline.

### C. Services layer
The `services/` package contains the core business logic:

- `services.ingestion`: file validation, hashing, temp storage, final storage
- `services.ocr`: OCR extraction for images and PDFs
- `services.speech`: audio transcription using Whisper
- `services.vision`: object detection for images
- `services.cleaning`: text normalization and cleanup
- `services.chunking`: splitting text into chunks for later retrieval or indexing

### D. Persistence layer
The `storage/database` package contains:

- SQLAlchemy engine setup
- ORM models such as `Asset`, `ExtractedContent`, `ContentChunk`, and `AssetOutput`

The database is used to track the lifecycle of each uploaded asset.

---

## 2. End-to-End Flow

The typical workflow is:

1. A user uploads a file to the API.
2. The API validates the file type and stores it in a temporary location.
3. A hash is computed for the file.
4. The file is moved to a final storage location (`storage/raw/images` or `storage/raw/pdfs`).
5. A database row is created for the asset with status `PENDING`.
6. A Celery task is enqueued with metadata about the asset.
7. The worker receives the task, loads the asset from the database, and processes it.
8. Depending on the content type, the worker:
   - runs OCR for images/PDFs,
   - transcribes audio,
   - optionally runs vision detection on images.
9. The extracted text is cleaned.
10. The extracted content is stored in the database.
11. The text is split into chunks and stored as chunk records.
12. The asset status is updated to `READY` or `FAILED`.

---

## 3. Main Files and Their Responsibilities

### `apps/api/main.py`
This is the FastAPI application entry point.

Responsibilities:
- create the FastAPI app,
- expose `/health`,
- include the upload router,
- provide a simple `/job/{job_id}` placeholder endpoint.

### `apps/api/routes/upload.py`
This file implements the upload endpoint.

Responsibilities:
- accept uploaded files from the client,
- invoke ingestion logic,
- create a database entry for the asset,
- move the file into its final storage location,
- queue a Celery worker task.

### `apps/worker/main.py`
This is the background worker implementation.

Responsibilities:
- initialize the Celery app,
- define the `process_asset_task` Celery task,
- convert a payload into a `WorkerInput` object,
- run the async processing pipeline,
- update database records with processed output.

### `services/ingestion/pipeline.py`
This file contains the main ingestion workflow for uploaded files.

Responsibilities:
- save the uploaded file to a temporary path,
- detect the MIME type,
- validate whether the file is supported,
- compute a SHA-256 hash,
- prepare the final storage location,
- return an `IngestionResult` object for downstream use.

### `services/ingestion/storage.py`
This file manages storage paths.

Responsibilities:
- define the base directories for raw and temporary storage,
- create directories if they do not exist,
- save uploaded content to disk.

### `services/ingestion/check_filetype.py`
This file detects the MIME type of a file.

Responsibilities:
- inspect the file using `python-magic`,
- return a standardized MIME string.

### `services/ingestion/hashing.py`
This file computes a checksum for the uploaded file.

Responsibilities:
- generate the SHA-256 hash of the file bytes.

### `services/ocr/recognition.py`
This file conducts OCR extraction for image and PDF assets.

Responsibilities:
- detect whether the input is an image or PDF,
- use Tesseract for image OCR,
- use `pdfplumber` for PDF text extraction,
- return structured extraction data.

### `services/speech/whisper.py`
This file transcribes audio using Whisper.

Responsibilities:
- load a Whisper model,
- run transcription on the provided audio file,
- return a result containing text and segments.

### `services/vision/detector.py`
This file performs object detection on images.

Responsibilities:
- lazily load an RF-DETR model,
- run inference over the input image,
- return a dictionary of detected objects and bounding boxes.

### `services/cleaning/cleaner.py`
This file normalizes and cleans extracted text.

Responsibilities:
- remove control characters,
- normalize newlines and spacing,
- fix line breaks that were split by hyphenation,
- produce cleaner plain text.

### `services/chunking/chunker.py`
This file splits content into manageable chunks.

Responsibilities:
- create paragraph-based chunks for plain text,
- create page-section chunks for PDFs,
- create transcript-based chunks for audio segments.

---

## 4. Main Functions and Their Contracts

Below is a detailed explanation of the most important functions.

### `health_check()`
Location: `apps/api/main.py`

Purpose:
- returns a simple status response to confirm the API is alive.

Input:
- no arguments.

Return type:
- `dict[str, str]`

Example return:
```python
{"status": "ok"}
```

---

### `upload(file: UploadFile = File(...), db: AsyncSession = Depends(get_db))`
Location: `apps/api/routes/upload.py`

Purpose:
- receives an uploaded file from the client,
- validates it,
- stores it,
- records it in the database,
- queues background processing.

Input:
- `file`: an `UploadFile` object from FastAPI.
- `db`: an asynchronous SQLAlchemy session.

Expected file types:
- image MIME types such as `image/png`, `image/jpeg`, `image/webp`
- `application/pdf`

Return type:
- a dictionary containing:
  - `id`: asset identifier,
  - `status`: current processing state,
  - `message`: human-readable status message.

Possible failure modes:
- unsupported file type -> HTTP 400
- duplicate asset -> HTTP 409
- unexpected error -> HTTP 500

---

### `ingest_file(upload_file: UploadFile) -> IngestionResult`
Location: `services/ingestion/pipeline.py`

Purpose:
- prepares the uploaded file for persistence and downstream processing.

Input:
- `upload_file`: a FastAPI `UploadFile`.

Return type:
- `IngestionResult` (a Pydantic model)

Returned fields:
- `filename: str | None`
- `temp_path: str`
- `final_path: str`
- `sha256: str`
- `content_type: str`

Behavior:
- creates a temporary file path using a UUID,
- writes the uploaded bytes to disk,
- detects the MIME type,
- validates supported types,
- computes a hash,
- prepares the final destination path.

---

### `save_temp_file(upload_file, destination: Path) -> None`
Location: `services/ingestion/storage.py`

Purpose:
- writes the uploaded file buffer to disk.

Input:
- `upload_file`: any file-like object with a `.file` stream.
- `destination`: a `Path` object pointing at the target file location.

Return type:
- `None`

---

### `detect_mime_type(path: Path) -> str`
Location: `services/ingestion/check_filetype.py`

Purpose:
- identifies the MIME type of the file.

Input:
- `path`: a filesystem path to the file.

Return type:
- `str`

Expected output examples:
- `image/png`
- `image/jpeg`
- `application/pdf`

---

### `sha256_file(path: Path) -> str`
Location: `services/ingestion/hashing.py`

Purpose:
- computes the file hash used to deduplicate assets.

Input:
- `path`: path to the file.

Return type:
- `str`

---

### `extract_from_media(media_path: Path) -> dict[str, Any]`
Location: `services/ocr/recognition.py`

Purpose:
- extract text from images and PDFs via OCR and PDF parsing.

Input:
- `media_path`: a `Path` pointing to an image or PDF.

Return type:
- `dict[str, Any]`

Returned structure:
- for images:
  - `text`: OCR text
  - `source`: `tesseract`
  - `metadata`: empty dict
- for PDFs:
  - `text`: joined text from all pages
  - `pages`: number of pages
  - `source`: `pdfplumber`
  - `metadata`: empty dict

Expected input type:
- a real file path that exists on disk.

---

### `transcribe_audio(audio_path: Path) -> dict[str, Any]`
Location: `services/speech/whisper.py`

Purpose:
- convert an audio file into text using Whisper.

Input:
- `audio_path`: a `Path` pointing to an audio file.

Return type:
- `dict[str, Any]`

Returned structure:
- `text`: transcribed text
- `language`: detected language
- `segments`: transcript segments
- `source`: `openai-whisper`

---

### `run_detection(image_path: str | Path, confidence_threshold: float = 0.5) -> dict`
Location: `services/vision/detector.py`

Purpose:
- run object detection over an image.

Input:
- `image_path`: path to an image file.
- `confidence_threshold`: a float controlling detection sensitivity.

Return type:
- `dict`

Returned structure:
- `model_used`: name of the model
- `objects`: list of detected objects

Each object contains:
- `type`: label/class name
- `confidence`: confidence score
- `bounding_box`: `[x1, y1, x2, y2]`

---

### `clean_extracted_text(text: str) -> str`
Location: `services/cleaning/cleaner.py`

Purpose:
- normalize OCR or transcription output into more usable plain text.

Input:
- `text`: raw extracted text, usually as a string.

Return type:
- `str`

Behavior:
- normalizes newline endings,
- removes control characters,
- collapses repeated spaces,
- removes broken hyphenation across line breaks,
- reduces excessive paragraph spacing.

---

### `build_chunks(extracted_content: dict[str, Any], asset_content_type: str) -> list[ChunkPayload]`
Location: `services/chunking/chunker.py`

Purpose:
- split extracted text into chunk objects suitable for downstream search or retrieval.

Input:
- `extracted_content`: a dictionary containing text and metadata,
- `asset_content_type`: the MIME type of the source asset.

Return type:
- `list[ChunkPayload]`

Behavior:
- for audio: use audio transcript segments,
- for PDFs: split by paragraph/page sections,
- otherwise: split plain text into paragraph chunks.

---

### `process_asset_async(worker_input: WorkerInput)`
Location: `apps/worker/main.py`

Purpose:
- the core asynchronous processing function for an asset.

Input:
- `worker_input`: a `WorkerInput` Pydantic model.

Return type:
- `str | None`

Behavior:
- loads the asset from the database,
- updates its status to `PROCESSING`,
- chooses the appropriate processor based on content type,
- stores extracted text and metadata,
- creates chunk records,
- marks the asset as `READY` or `FAILED`.

---

### `process_asset_task(payload: dict)`
Location: `apps/worker/main.py`

Purpose:
- Celery wrapper for the async processing pipeline.

Input:
- `payload`: a dictionary that can be validated into `WorkerInput`.

Return type:
- none directly; it runs the async pipeline and may raise on failure.

Behavior:
- validates the payload into `WorkerInput`,
- calls `asyncio.run(process_asset_async(...))`.

---

## 5. The Main Data Contracts

### `WorkerInput`
Defined in `packages/shared_schemas/worker_input.py`

Fields:
- `asset_id: str`
- `worker_type: WorkerType`
- `stored_path: str`
- `content_type: str`
- `correlation_id: str`
- `created_at: datetime`
- `retry_count: int = 0`
- `metadata: Optional[dict] = None`

This is the payload that is passed to the worker task from the API.

### `IngestionResult`
Defined in `packages/shared_schemas/ingestion.py`

Fields:
- `filename: str | None`
- `temp_path: str`
- `final_path: str`
- `sha256: str`
- `content_type: str`

This is the output of the ingestion pipeline and is used by the upload route.

### Database Models

#### `Asset`
Represents a file that has been uploaded and queued for processing.

Fields include:
- `id`
- `sha256`
- `original_filename`
- `stored_path`
- `content_type`
- `processing_status`
- `created_at`

#### `ExtractedContent`
Stores the output of OCR/transcription for an asset.

Fields include:
- `asset_id`
- `extracted_text`
- `content_type`
- `extraction_metadata`

#### `ContentChunk`
Stores chunked text pieces derived from the extracted content.

Fields include:
- `asset_id`
- `extracted_content_id`
- `chunk_idx`
- `chunk_type`
- `text`
- `chunk_metadata`

#### `AssetOutput`
Stores structured outputs such as object-detection results.

Fields include:
- `asset_id`
- `output_type`
- `output_content`

---

## 6. What the Project Is Doing Conceptually

At a conceptual level, the project is a document-processing pipeline for construction-related media. It is designed to turn uploaded files into machine-readable text and structured data that can later be used for search, summarization, QA, or analysis.

In short:
- file upload -> storage -> processing -> extraction -> persistence.

The architecture is intentionally simple and modular, with each service focused on one responsibility.

---

## 7. Notes About the Current Implementation

A few implementation details are worth knowing:

- The worker currently expects image/PDF/audio content and routes accordingly.
- The upload route creates a Celery task using the worker task name `apps.worker.main.process_asset_task`.
- The worker uses asynchronous SQLAlchemy operations inside a Celery task.
- The detection service currently loads a model from a local path such as `/ml-cache/ultralytics/rtdetr-l.pt`.
- Some imports appear duplicated in the worker module, which suggests the code is still being evolved and cleaned up.

---

## 8. Summary

The project works as a document ingestion and extraction pipeline:

- FastAPI accepts an upload.
- Files are validated and stored.
- Their metadata is recorded in the database.
- Celery workers process them in the background.
- OCR, speech transcription, and vision detection produce text and structured outputs.
- The results are cleaned, chunked, and persisted.

If you want to understand the code quickly, the most important path to follow is:

`/upload -> ingest_file -> database insert -> Celery task -> process_asset_async -> extraction -> clean -> chunk -> save to DB`
