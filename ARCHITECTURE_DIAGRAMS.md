# Architecture Diagrams & Patterns

This document provides visual representations of the current vs. proposed architecture.

## Current Architecture Problems

### Backend: Everything in Services

```
┌─────────────────────────────────────────────────────────────┐
│                         main.py (248 lines)                  │
│  All routes mixed together, no separation by domain          │
│                                                              │
│  POST /upload │ GET /jobs/{id} │ GET /history │ DELETE /... │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│                    services/ (Doing Everything)                │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  history_service.py (644 lines)                         │  │
│  │  ❌ File I/O + Business Logic + Calculations + API prep │  │
│  │                                                          │  │
│  │  • save_job_snapshot() - persistence                    │  │
│  │  • apply_page_edits() - business logic                  │  │
│  │  • _compute_confidence_stats() - calculation            │  │
│  │  • get_timewindow_metrics() - queries                   │  │
│  │  • delete_job() - file operations                       │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  vision_service.py (427 lines)                          │  │
│  │  ❌ Prompts + API calls + Parsing all mixed             │  │
│  │                                                          │  │
│  │  • PROMPT_TEMPLATE - configuration                      │  │
│  │  • call_vision_model() - API call                       │  │
│  │  • _parse_fields() - parsing logic                      │  │
│  │  • _validate_response() - validation                    │  │
│  └─────────────────────────────────────────────────────────┘  │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  File System   │
                    │  (backend_data)│
                    └────────────────┘

PROBLEMS:
1. No clear boundaries
2. Hard to test (everything coupled)
3. Changes ripple everywhere
4. No reusability
5. Difficult to understand data flow
```

### Frontend: Type-Based Chaos

```
┌──────────────────────────────────────────────────────────────┐
│                     DashboardPage.tsx (632 lines)             │
│  ❌ Charts + Filters + Mutations + State all in one file     │
│                                                               │
│  • State management (filters, sorting)                       │
│  • Data fetching (metrics, jobs, low confidence)             │
│  • Chart rendering (pie, bar, line charts)                   │
│  • User interactions (delete, navigate, filter)              │
│  • Business logic (sorting, filtering calculations)          │
└───────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                  components/ (By Type, Not Feature)           │
│                                                               │
│  pdf/                results/              common/           │
│  ├── PdfViewer      ├── ResultsPanel      ├── ConfidenceBadge│
│  └── Thumbnails     ├── FieldsTab         └── StatusIndicator│
│                     └── TablesTab                             │
│                                                               │
│  ❌ Hard to find related code                                │
│  ❌ Not clear what features exist                            │
└───────────────────────────────────────────────────────────────┘

                              ▼
                    ┌──────────────────┐
                    │  mockApi.ts      │
                    │  (All API calls) │
                    └──────────────────┘

PROBLEMS:
1. Large, unfocused components
2. Type-based organization hides features
3. Business logic in components
4. Hard to reuse code
5. Confusing state management
```

---

## Proposed Clean Architecture

### Backend: Layered Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          API LAYER                               │
│  (HTTP Routes, Schemas, Dependencies)                           │
│                                                                  │
│  main.py (30 lines)                                             │
│  └── Includes all routers                                       │
│                                                                  │
│  api/v1/routers/                                                │
│  ├── jobs.py         ← Job processing routes                    │
│  ├── history.py      ← History & metrics routes                 │
│  └── uploads.py      ← Upload routes                            │
│                                                                  │
│  api/v1/schemas/                                                │
│  ├── job_schemas.py                                             │
│  ├── history_schemas.py                                         │
│  └── common_schemas.py                                          │
└──────────────────────────────┬───────────────────────────────────┘
                               │ Uses
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                           │
│  (Use Cases, Commands, Queries)                                 │
│                                                                  │
│  commands/                    queries/                          │
│  ├── ProcessDocument          ├── GetJobStatus                  │
│  ├── SaveEdits                ├── GetPageData                   │
│  ├── DeleteJob                ├── ListJobs                      │
│  └── UploadDocument           └── GetMetrics                    │
│                                                                  │
│  ✓ Each use case is focused and testable                       │
│  ✓ Orchestrates domain logic                                   │
│  ✓ No infrastructure dependencies                              │
└──────────────────────────────┬───────────────────────────────────┘
                               │ Uses
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DOMAIN LAYER                              │
│  (Business Logic, Entities, Value Objects)                      │
│                                                                  │
│  entities/                                                      │
│  ├── ExtractionJob     ← Core business object                   │
│  ├── PageExtraction                                             │
│  ├── FieldExtraction                                            │
│  └── TableExtraction                                            │
│                                                                  │
│  value_objects/                                                 │
│  ├── Confidence        ← Immutable, self-validating             │
│  ├── BoundingBox                                                │
│  └── JobStatus                                                  │
│                                                                  │
│  services/                                                      │
│  ├── ConfidenceCalculator  ← Pure business logic                │
│  ├── FieldAggregator                                            │
│  ├── TableGrouper                                               │
│  └── CanonicalMapper                                            │
│                                                                  │
│  repositories/ (Interfaces only)                                │
│  ├── JobRepository                                              │
│  └── PageRepository                                             │
│                                                                  │
│  ✓ No dependencies on infrastructure                           │
│  ✓ Pure business logic                                         │
│  ✓ Easy to unit test                                           │
└──────────────────────────────┬───────────────────────────────────┘
                               │ Implemented by
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                          │
│  (External Services, Persistence, APIs)                         │
│                                                                  │
│  persistence/                                                   │
│  ├── FileJobRepository     ← Implements domain interface        │
│  └── FilePageRepository                                         │
│                                                                  │
│  vision/                                                        │
│  ├── AzureVisionClient     ← External API wrapper               │
│  ├── VisionPromptBuilder                                        │
│  └── VisionResponseParser                                       │
│                                                                  │
│  pdf/                                                           │
│  ├── PdfRenderer                                                │
│  ├── ImageProcessor                                             │
│  └── AutoRotator                                                │
│                                                                  │
│  mapping/                                                       │
│  └── AzureMappingClient                                         │
│                                                                  │
│  ✓ All external dependencies isolated here                     │
│  ✓ Easy to swap implementations                                │
│  ✓ Can mock for testing                                        │
└──────────────────────────────┬───────────────────────────────────┘
                               │ Stores to
                               ▼
                         ┌─────────────┐
                         │ File System │
                         │   Database  │
                         │ External API│
                         └─────────────┘

DEPENDENCY FLOW: API → Application → Domain ← Infrastructure
                                       ▲
                                       │
                           No dependencies upward!
```

### Frontend: Feature-Based Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         App.tsx                                  │
│                      (Router Setup)                              │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├─────────────────────────────────────────────────────┐
             │                                                     │
             ▼                                                     ▼
┌────────────────────────────┐                    ┌────────────────────────────┐
│  DASHBOARD FEATURE         │                    │  WORKSPACE FEATURE         │
│                            │                    │                            │
│  DashboardPage (~100 lines)│                    │  WorkspacePage (~150 lines)│
│  Uses:                     │                    │  Uses:                     │
│  • DashboardMetrics        │                    │  • PdfViewer               │
│  • JobsTable               │                    │  • ResultsPanel            │
│  • ConfidenceHistogram     │                    │  • ResizablePanels         │
│  • LowConfidenceList       │                    │                            │
│  • FilterBar               │                    │  components/               │
│                            │                    │  ├── pdf-viewer/           │
│  hooks/                    │                    │  │   ├── PdfViewer.tsx     │
│  ├── useDashboardMetrics   │                    │  │   └── Thumbnails.tsx    │
│  ├── useJobsList           │                    │  └── results-panel/        │
│  └── useJobFilters         │                    │      ├── ResultsPanel.tsx  │
│                            │                    │      ├── FieldsTab.tsx     │
│  api/                      │                    │      └── TablesTab.tsx     │
│  └── dashboardApi.ts       │                    │                            │
│                            │                    │  hooks/                    │
│  ✓ Everything dashboard-   │                    │  ├── usePageData           │
│    related in one place    │                    │  ├── useFieldEditing       │
│  ✓ Easy to find code       │                    │  └── useCanonicalData      │
│  ✓ Focused components      │                    │                            │
└────────────┬───────────────┘                    │  api/                      │
             │                                    │  └── workspaceApi.ts       │
             │                                    │                            │
             │                                    │  state/                    │
             │                                    │  └── viewerStore.ts        │
             │                                    │                            │
             │                                    │  ✓ All workspace logic     │
             │                                    │    in one feature module   │
             │                                    └────────────┬───────────────┘
             │                                                 │
             └─────────────────┬───────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    CORE (Shared)     │
                    │                      │
                    │  api/                │
                    │  └── client.ts       │
                    │                      │
                    │  types/              │
                    │  ├── job.types.ts    │
                    │  └── common.types.ts │
                    │                      │
                    │  utils/              │
                    │  └── formatters.ts   │
                    │                      │
                    │  constants/          │
                    │  └── app.constants.ts│
                    └──────────────────────┘

BENEFITS:
1. Clear feature boundaries
2. Easy to find related code
3. Smaller, focused components
4. Reusable core utilities
5. Scalable structure
```

---

## Request Flow Examples

### Example 1: Get Job Status

#### Current Flow (Messy)

```
Frontend                Backend
   │                       │
   │  GET /jobs/{id}/status│
   ├──────────────────────>│
   │                       │
   │                   main.py (248 lines)
   │                       │ get_job(job_id)
   │                       │
   │                       ▼
   │                   store.job_store  (global dict)
   │                       │
   │                       │ if not found, try load_job_from_snapshot()
   │                       ▼
   │                   history_service.py (644 lines)
   │                       │
   │                       │ reads file system directly
   │                       │ parses JSON manually
   │                       │ reconstructs object
   │                       │
   │                       ▼
   │                   Returns ExtractionJob
   │                       │
   │                   Transform to JobStatusSchema
   │                       │
   │<──────────────────────┤
   │                       │
```

**Problems:**
- Logic scattered across 3 files
- Global state (job_store)
- Direct file system access in service
- Hard to test without file system

#### Proposed Flow (Clean)

```
Frontend                                    Backend
   │                                           │
   │  GET /api/v1/jobs/{id}/status            │
   ├──────────────────────────────────────────>│
   │                                           │
   │                                    API Layer
   │                                    routers/jobs.py
   │                                           │
   │                                           │ GetJobStatusHandler.handle()
   │                                           ▼
   │                                    Application Layer
   │                                    queries/get_job_status.py
   │                                           │
   │                                           │ job_repository.find_by_id()
   │                                           ▼
   │                                    Domain Layer
   │                                    repositories/job_repository.py (interface)
   │                                           │
   │                                           ▼
   │                                    Infrastructure Layer
   │                                    persistence/file_job_repository.py
   │                                           │
   │                                           │ Reads file
   │                                           │ Deserializes to domain entity
   │                                           │
   │                                           ▼
   │                                    Returns ExtractionJob (domain entity)
   │                                           │
   │                                           │ Maps to DTO
   │<──────────────────────────────────────────┤
   │                                           │
```

**Benefits:**
- Clear separation of concerns
- Each layer testable independently
- Easy to swap repository implementation
- Business logic in domain, not scattered

### Example 2: Save Field Edits

#### Current Flow

```
Frontend                                Backend
   │                                       │
   │  POST /history/jobs/{id}/edits       │
   ├─────────────────────────────────────>│
   │  { page: 1, fields: [...] }          │
   │                                       │
   │                                   main.py
   │                                       │ apply_page_edits()
   │                                       ▼
   │                                   history_service.py (644 lines)
   │                                       │
   │                                       │ • Find job in store or load from file
   │                                       │ • Update field values
   │                                       │ • Recalculate confidence
   │                                       │ • Save to file
   │                                       │ • Update aggregates
   │                                       │ • All in one giant function (100+ lines)
   │                                       │
   │<──────────────────────────────────────┤
   │                                       │
```

**Problems:**
- All logic in one 100+ line function
- Can't test without file system
- Confidence calculation mixed with persistence
- Hard to understand what happens

#### Proposed Flow

```
Frontend                                          Backend
   │                                                 │
   │  POST /api/v1/history/jobs/{id}/edits          │
   ├────────────────────────────────────────────────>│
   │  { page: 1, fields: [...] }                    │
   │                                                 │
   │                                          API Layer
   │                                          routers/history.py
   │                                                 │
   │                                                 │ SaveEditsHandler.handle()
   │                                                 ▼
   │                                          Application Layer
   │                                          commands/save_edits.py
   │                                                 │
   │                                                 │ 1. Load job
   │                                                 ▼
   │                                          job_repository.find_by_id()
   │                                                 │
   │                                                 │ 2. Apply edits
   │                                                 ▼
   │                                          Domain Layer
   │                                          job.apply_field_edits()
   │                                                 │
   │                                                 │ 3. Recalculate confidence
   │                                                 ▼
   │                                          confidence_calculator.recalculate()
   │                                                 │
   │                                                 │ 4. Save
   │                                                 ▼
   │                                          job_repository.save(job)
   │                                                 │
   │<────────────────────────────────────────────────┤
   │                                                 │
```

**Benefits:**
- Each step is a focused function
- Can test business logic without persistence
- Easy to add pre/post save hooks
- Clear separation: what vs. how

---

## Testing Architecture

### Backend Testing Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    TESTING PYRAMID                           │
│                                                              │
│                       ╱╲                                     │
│                      ╱  ╲   E2E Tests (Few)                 │
│                     ╱────╲  Full API + File System          │
│                    ╱      ╲                                  │
│                   ╱────────╲ Integration Tests (Some)        │
│                  ╱          ╲ Multiple layers together       │
│                 ╱────────────╲                               │
│                ╱              ╱ Unit Tests (Many)            │
│               ╱──────────────╱  Individual classes           │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Unit Tests (Fast, Many):
  ├── Domain entities
  │   ├── test_confidence.py
  │   ├── test_bounding_box.py
  │   └── test_field_extraction.py
  │
  ├── Domain services
  │   ├── test_confidence_calculator.py
  │   └── test_field_aggregator.py
  │
  └── Application use cases
      ├── test_get_job_status.py (mock repository)
      └── test_save_edits.py (mock repository)

Integration Tests (Medium speed, Some):
  ├── Repository implementations
  │   └── test_file_job_repository.py (real file system)
  │
  ├── Use cases with real repositories
  │   └── test_save_edits_integration.py
  │
  └── API routes
      └── test_jobs_router.py (TestClient)

E2E Tests (Slow, Few):
  └── test_upload_and_process.py (full workflow)
```

### Frontend Testing Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    TESTING PYRAMID                           │
│                                                              │
│                       ╱╲                                     │
│                      ╱  ╲   E2E Tests (Playwright)          │
│                     ╱────╲  Full user workflows             │
│                    ╱      ╲                                  │
│                   ╱────────╲ Integration Tests               │
│                  ╱          ╲ React Query + Components      │
│                 ╱────────────╲                               │
│                ╱              ╱ Unit Tests                   │
│               ╱──────────────╱  Components + Hooks          │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Unit Tests (Fast, Many):
  ├── Components
  │   ├── DashboardMetrics.test.tsx
  │   ├── JobsTable.test.tsx
  │   └── ConfidenceBadge.test.tsx
  │
  ├── Hooks
  │   ├── useFieldEditing.test.ts
  │   └── useDashboardData.test.ts
  │
  └── Utils
      └── formatters.test.ts

Integration Tests (Medium, Some):
  ├── Feature modules
  │   ├── DashboardPage.test.tsx (with mocked API)
  │   └── WorkspacePage.test.tsx (with mocked API)
  │
  └── API clients
      └── dashboardApi.test.ts (MSW)

E2E Tests (Slow, Few):
  ├── test_upload_workflow.spec.ts
  ├── test_edit_fields.spec.ts
  └── test_dashboard_navigation.spec.ts
```

---

## Migration Pattern: Strangler Fig

We use the "Strangler Fig" pattern to gradually replace old code:

```
Week 1: Both old and new code exist
┌─────────────────────────────────────┐
│         Old System (90%)            │
│                                     │
│  ┌─────────────────┐                │
│  │  New System     │                │
│  │  (10%)          │                │
│  │                 │                │
│  │  • Domain layer │                │
│  └─────────────────┘                │
│                                     │
└─────────────────────────────────────┘

Week 2: New code growing
┌─────────────────────────────────────┐
│      Old System (70%)               │
│                                     │
│  ┌──────────────────────┐           │
│  │  New System (30%)    │           │
│  │                      │           │
│  │  • Domain layer      │           │
│  │  • Application layer │           │
│  │  • 2 use cases       │           │
│  └──────────────────────┘           │
│                                     │
└─────────────────────────────────────┘

Week 3: New code dominant
┌─────────────────────────────────────┐
│  ┌──────────────────────────────┐   │
│  │  New System (70%)            │   │
│  │                              │   │
│  │  • All layers                │   │
│  │  • Most use cases            │   │
│  │                              │   │
│  │  ┌────────────┐              │   │
│  │  │ Old (30%)  │              │   │
│  │  │            │              │   │
│  │  └────────────┘              │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘

Week 5: Old code removed
┌─────────────────────────────────────┐
│                                     │
│      New System (100%)              │
│                                     │
│      Clean Architecture             │
│                                     │
└─────────────────────────────────────┘
```

**Key Principles:**
1. New code alongside old code
2. Gradually move routes to new implementation
3. Always keep tests passing
4. Remove old code only when fully replaced

---

## Folder Structure Comparison

### Backend

```
BEFORE                          AFTER
backend/                        backend/
├── main.py (248 lines)        ├── api/
├── services/                  │   └── v1/
│   ├── history_service.py     │       ├── routers/
│   │   (644 lines)            │       │   ├── jobs.py (~80 lines)
│   ├── vision_service.py      │       │   ├── history.py (~100 lines)
│   │   (427 lines)            │       │   └── uploads.py (~50 lines)
│   └── ...                    │       └── schemas/
├── models/                    │           ├── job_schemas.py
│   └── job.py                 │           ├── history_schemas.py
├── api/                       │           └── common_schemas.py
│   └── schemas.py             │
└── repositories/              ├── application/
    └── snapshot_repository.py │   ├── commands/
                               │   │   ├── process_document.py
                               │   │   └── save_edits.py
                               │   └── queries/
                               │       ├── get_job_status.py
                               │       └── list_jobs.py
                               │
                               ├── domain/
                               │   ├── entities/
                               │   │   ├── extraction_job.py
                               │   │   ├── page_extraction.py
                               │   │   └── field_extraction.py
                               │   ├── value_objects/
                               │   │   ├── confidence.py
                               │   │   └── bounding_box.py
                               │   ├── services/
                               │   │   ├── confidence_calculator.py
                               │   │   └── field_aggregator.py
                               │   └── repositories/
                               │       └── job_repository.py (interface)
                               │
                               ├── infrastructure/
                               │   ├── persistence/
                               │   │   └── file_job_repository.py
                               │   ├── vision/
                               │   │   ├── azure_vision_client.py
                               │   │   └── vision_response_parser.py
                               │   └── pdf/
                               │       ├── pdf_renderer.py
                               │       └── auto_rotator.py
                               │
                               └── main.py (~30 lines)
```

### Frontend

```
BEFORE                          AFTER
src/                            src/
├── pages/                      ├── features/
│   ├── DashboardPage.tsx       │   ├── dashboard/
│   │   (632 lines)             │   │   ├── components/
│   └── WorkspacePage.tsx       │   │   │   ├── DashboardMetrics.tsx
│       (309 lines)             │   │   │   ├── JobsTable.tsx
├── components/                 │   │   │   └── ConfidenceHistogram.tsx
│   ├── pdf/                    │   │   ├── hooks/
│   ├── results/                │   │   │   └── useDashboardData.ts
│   ├── common/                 │   │   ├── api/
│   ├── header/                 │   │   │   └── dashboardApi.ts
│   └── layout/                 │   │   └── DashboardPage.tsx (~100 lines)
├── services/                   │   │
│   └── mockApi.ts              │   ├── workspace/
├── hooks/                      │   │   ├── components/
├── state/                      │   │   │   ├── pdf-viewer/
└── types/                      │   │   │   └── results-panel/
                                │   │   ├── hooks/
                                │   │   │   ├── usePageData.ts
                                │   │   │   └── useFieldEditing.ts
                                │   │   ├── api/
                                │   │   │   └── workspaceApi.ts
                                │   │   ├── state/
                                │   │   │   └── viewerStore.ts
                                │   │   └── WorkspacePage.tsx (~150 lines)
                                │   │
                                │   └── shared/
                                │       └── components/
                                │
                                ├── core/
                                │   ├── api/
                                │   │   └── client.ts
                                │   ├── types/
                                │   ├── utils/
                                │   └── constants/
                                │
                                ├── App.tsx
                                └── main.tsx
```

---

## Key Patterns Used

### 1. Clean Architecture (Backend)

**Layers:**
- API: HTTP concerns only
- Application: Use case orchestration
- Domain: Business logic
- Infrastructure: External systems

**Rules:**
- Dependencies point inward
- Domain has no external dependencies
- Outer layers depend on inner layers

### 2. Command Query Separation (Backend)

**Commands:** Write operations
- ProcessDocumentCommand
- SaveEditsCommand
- DeleteJobCommand

**Queries:** Read operations
- GetJobStatusQuery
- ListJobsQuery
- GetMetricsQuery

### 3. Repository Pattern (Backend)

**Interface in domain:**
```python
class JobRepository(ABC):
    @abstractmethod
    def save(self, job: ExtractionJob) -> None
    @abstractmethod
    def find_by_id(self, job_id: str) -> Optional[ExtractionJob]
```

**Implementation in infrastructure:**
```python
class FileJobRepository(JobRepository):
    def save(self, job: ExtractionJob) -> None:
        # File system specific code
```

### 4. Feature Modules (Frontend)

Each feature has:
- `components/` - UI components
- `hooks/` - Business logic
- `api/` - API calls
- `types/` - TypeScript types
- `FeaturePage.tsx` - Main page

### 5. Custom Hooks (Frontend)

Extract business logic from components:
```typescript
const useFieldEditing = (jobId, pageNumber) => {
  // State management
  // Business logic
  // API calls
  
  return { drafts, save, isEditing }
}
```

---

## Metrics & Success Criteria

### Code Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Largest file (backend) | 644 lines | <200 lines | ✓ |
| Largest file (frontend) | 632 lines | <200 lines | ✓ |
| Files > 300 lines | 5 | 0 | ✓ |
| Test coverage (backend) | ~30% | >70% | ✓ |
| Test coverage (frontend) | ~20% | >70% | ✓ |
| Circular dependencies | Unknown | 0 | ✓ |

### Architecture Metrics

| Metric | Before | After |
|--------|--------|-------|
| Clear layer separation | ❌ | ✓ |
| Domain logic testable without DB/HTTP | ❌ | ✓ |
| Feature-based organization | ❌ | ✓ |
| Single Responsibility Principle | ❌ | ✓ |
| Dependency Inversion Principle | ❌ | ✓ |

### Developer Experience

| Metric | Before | After |
|--------|--------|-------|
| Time to find feature code | 5-10 min | <1 min |
| Time to add new field type | 2 hours | 30 min |
| Time to understand module | 1 hour | 10 min |
| New developer onboarding | 1 day | 1 hour |
| Test execution time | 30s | 5s |

---

## Conclusion

This refactoring transforms a messy, hard-to-maintain codebase into a clean, modular, well-architected application. The key principles are:

1. **Separation of Concerns** - Each module has one responsibility
2. **Layered Architecture** - Clear boundaries between layers
3. **Feature-Based Organization** - Related code stays together
4. **Testability** - Business logic testable in isolation
5. **Incremental Migration** - No big bang rewrite

The result is a codebase that's easier to understand, easier to test, easier to change, and easier to extend.
