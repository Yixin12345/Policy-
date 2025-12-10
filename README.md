# Recon AI 2.0

Document processing workbench featuring a Vite/React reviewer and a FastAPI orchestration backend. The app ingests PDFs or Markdown transcripts, normalises page orientation when images are available, runs vision- or text-powered extraction, and presents human-in-the-loop tools to review, edit, export, and analyse structured results.

## Core Capabilities

- **PDF ingestion pipeline** – converts pages to images, auto-rotates sideways tables using line-orientation scoring with projection-profile fallback + confidence guardrails, and persists job snapshots for replay.
- **Markdown ingestion pipeline** – splits `.md/.mmd` transcripts on `<--- Page Split --->`, calls the text LLM to recover fields/tables with bounding boxes, and generates canonical bundles directly from the raw transcript without image conversion.
- **Vision extraction** – calls the configured vision model to capture fields and tables, then aggregates canonical field values for dashboard rollups.
- **Canonical mapping** – runs aggregated OCR through the Azure OpenAI mapping service to classify document type (facility invoice, CMR, UB04) and emit canonical bundles with full LLM trace metadata.
- **Confidence analytics** – computes per-job confidence buckets, highlights low-confidence fields, and exposes histogram/watch-list data to the UI.
- **Manual review workspace** – side-by-side PDF viewer and editable results panel with inline confidence badges, edit mode, save + export flows, and mutation-driven cache invalidation.
- **Multi-page table stitching** – detects when tables span page breaks, propagates headers, deduplicates overlapping rows, and surfaces continuation metadata with merged logical tables.
- **Dashboard** – visualises throughput trends, status mix, confidence distribution, and a low-confidence watch list; supports live navigation, deletion, and new uploads.
- **JSON export** – one-click download of the current job’s structured payload, canonical bundle, mapping trace metadata, and table-group analytics.

## Tech Stack

- React 19 + TypeScript
- Vite (rolldown)
- Tailwind CSS
- TanStack React Query
- Zustand
- Vitest + Testing Library
- FastAPI + Pydantic v2
- PyMuPDF, OpenCV, NumPy for PDF rendering and orientation analysis
- OpenAI GPT‑5 (vision + text) via Azure OpenAI

## Getting Started

Install dependencies and start the dev server:

    npm install
    npm run dev

The dev server runs on http://localhost:5173 by default.

Backend environment (optional but recommended for end-to-end testing):

```
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

## Available Scripts

- `npm run dev` – start the Vite dev server
- `npm run lint` – run ESLint
- `npm run test` – run Vitest in watch mode
- `npm run test -- --run` – run the test suite once
- `npm run build` – type-check and build for production
- `npm run preview` – preview the production build locally

## Project Structure

- `src/components` – UI components (header, PDF viewer, results panel)
- `src/hooks` – React Query hooks for data fetching
- `src/state` – Zustand store for viewer controls
- `src/pages` – top-level dashboard and workspace screens
- `src/services` – API surface for the FastAPI backend
- `src/data` – sample OCR payloads used during development
- `src/types` – shared TypeScript models
- `backend/requirements.txt` – backend runtime dependencies
- `backend/services` – ingestion, history, auto-rotation, LLM mapping, and table grouping helpers

## Backend Integration

The API client in `src/services/mockApi.ts` calls the FastAPI backend exposed at `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`). Completed jobs are persisted to disk so the dashboard can surface summaries, trend metrics, and deep links back into the workspace view.

### Processing Pipeline

Markdown uploads follow a two-stage text workflow (page extraction + canonical mapping) without rendering images. PDF uploads continue to use the image-based path described below.

1. **PDF rendering** – `pdf_service.pdf_to_images` renders each page to PNG and applies `_auto_orient_image`, leveraging `choose_best_rotation` (line/edge scoring with projection fallback + confidence guardrails) to correct sideways layouts only when evidence is strong. Rotation metadata is stored per page.
2. **Vision model invocation** – `job_runner` feeds each page image to `vision_service.call_vision_model`, collects per-page document-type hints, and parses fields/tables into dataclasses.
3. **Canonical mapping** – `mapping_service.generate_canonical_bundle` aggregates OCR output and calls the Azure OpenAI text model to classify the overall document, emit canonical sections, and capture LLM trace metadata.
4. **Confidence analysis** – `history_service._compute_confidence_stats_for_job` calculates bucketed confidence counts and low-confidence totals, powering dashboard histograms and watch lists.
5. **Aggregation** – `aggregation.aggregate_fields` groups duplicate fields across pages and exposes best-value confidence stats.
6. **Table grouping** – `table_grouping.assign_table_groups` ties table segments across page breaks based on column similarity, captions, and bbox width; headers propagate when missing, duplicates are trimmed, and `merge_table_segments` produces logical tables.
7. **Snapshot persistence** – `history_service.save_job_snapshot` writes job payloads (including rotation metadata, canonical bundle, mapping trace, and table metadata) so the dashboard, canonical tab, and exports remain stable across sessions.

### Editing & Export Flow

- The workspace edit mode (in `ResultsPanel`) lets reviewers update fields or table cells; `useSavePageEdits` posts deltas to `/api/history/jobs/{jobId}/edits`.
- Backend `apply_page_edits` (history_service) updates snapshots, recomputes aggregates/confidence, and marks revised items with restored original values.
- Successful saves invalidate histogram, summary, and low-confidence queries to reflect manual fixes immediately.
- The header’s **Export JSON** button downloads the latest job detail (fields, tables, canonical bundle, mapping trace metadata, confidence stats, table groups).

## Algorithm Reference

### Auto-Rotation (`backend/utils/auto_rotate_lines.py`)

1. **Preprocessing**
    - Convert to grayscale, apply bilateral denoise, then adaptive threshold to emphasise line ink without amplifying noise.
2. **Line-ink scoring**
    - Morphological opening with long horizontal/vertical kernels extracts dominant strokes.
    - Horizontal vs. vertical ink values are normalised by image area.
3. **Edge orientation scoring**
    - Sobel gradients produce magnitude/angle maps; energy is accumulated for ~0° (vertical lines) and ~90° (horizontal lines).
4. **Projection fallback**
    - When ink/edge signals disagree or are weak, projection profiles measure text-band spacing to evaluate {0, 90, 180, 270} and rescue sparse text pages.
5. **Confidence gating**
    - Candidate scores are normalised; rotations only apply when the leading angle beats the runner-up by the configured gap and clears minimum confidence thresholds, otherwise the page is left untouched.
6. **Optional deskew**
    - After selecting the winner, small-angle deskew (≤3°) uses Hough lines to centre horizontal runs.
7. **Integration**
    - `pdf_service._auto_orient_image` runs the scorer post-render, records rotation/margin diagnostics, and overwrites the PNG only when a confident orientation is found; the applied angle is stored on `PageExtraction.rotation_applied` for downstream auditing.

### Confidence Bucketing (`backend/services/history_service.py`)

1. Coerce all confidence values to floats, clamp to [0,1].
2. Tally each field into bucket bounds `(0.2, 0.4, 0.6, 0.8, 1.0)` yielding six buckets.
3. Track low-confidence counts at or below `CONFIDENCE_LOW_THRESHOLD` (default 0.4).
4. Persist bucket arrays and counts in job summaries/snapshots.
5. Front end aggregates buckets across jobs to populate the histogram, and queries `/api/history/low-confidence` for watch-list entries.

### Table Grouping (`backend/services/table_grouping.py`)

1. **Continuation heuristic**
    - Iterate tables in page order, evaluate new tables against recent segments:
      - Same group if next page, similar bbox width ratio (0.65–1.35), matching headers (≥60% overlap) or header absent, near-equal column counts, matching captions.
    - When positive, mark `table_group_id` and flag `continuation_of`.
2. **Duplicate overlap removal**
    - If last row of previous segment matches first row of current (value signature), drop the duplicate from the continuation.
3. **Header propagation**
    - If continuation lacks headers, clone prior columns and set `inferred_headers = True` while keeping row start index offset.
4. **Row indexing**
    - Maintain `row_start_index = previous.row_start_index + len(previous.rows)` so downstream exports know absolute positions.
5. **Merged logical tables**
    - For each group, merge segments (copying cells) and skip consecutive duplicate signatures; store merged summaries under `job.metadata['mergedTables']` for exports/analytics.

### Edit Propagation (`backend/services/history_service.py`)

1. Locate target fields by id/name; preserve `original_value` the first time a value changes.
2. If manual edits revert to the original value, clear the `revised` flag and drop the stored baseline.
3. Automatically raise confidently edited fields/cells to 1.0 confidence (unless API payload overrides).
4. Table cell edits enforce row/column bounds and mutate the backing dataclass in place.
5. After edits the service recomputes aggregates, persists the snapshot, and triggers React Query invalidation chain.

## Testing

Run tests once in CI mode:

    npm run test -- --run

Vitest is configured with jsdom via `vite.config.ts` and `src/setupTests.ts`.

## Next Steps

1. Integrate a streaming vision provider or batching strategy for large PDFs.
2. Surface merged logical tables in the UI (toggle between per-page and grouped view).
3. Enhance watch-list filters (by document, date range, or owner) and add alerting hooks.
4. Extend export to additional formats (CSV, Excel) leveraging merged table data.
