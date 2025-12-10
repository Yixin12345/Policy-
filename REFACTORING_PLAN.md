# Document OCR - Comprehensive Refactoring Plan

**Generated**: 2025-11-19  
**Status**: In Progress  
**Priority**: High

## Executive Summary

This document provides a detailed analysis and refactoring plan for the Document OCR application. The current codebase suffers from poor separation of concerns, large monolithic files, and unclear architectural boundaries, making it difficult to maintain and extend.

**Key Metrics:**
- Backend: 22 Python files, largest service: 644 lines
- Frontend: 28 TypeScript files, largest page: 632 lines
- Main API file: 248 lines (all routes in one file)
- No clear domain boundaries or layered architecture

**Latest Progress (Nov 20, 2025):** Legacy bridge verified end-to-end with document classification/table data flowing to v1 job endpoints, integration suite re-run (3 API tests green), and workspace PdfViewer updated to display "Page Category" badges that mirror backend hints.

---

## 1. Current Architecture Analysis

### 1.1 Backend Issues

#### Critical Problems

1. **Massive Service Files**
   - `history_service.py`: 644 lines with 20+ functions
   - `vision_service.py`: 427 lines mixing prompts, API calls, parsing
   - Functions doing unrelated tasks (persistence, calculation, API calls)

2. **No Layered Architecture**
   - Services directly access file system
   - Business logic mixed with infrastructure
   - No clear separation between domain and application layers

3. **Monolithic API Router**
   - `main.py`: 248 lines with all routes
   - No versioning strategy
   - Routes for different resources mixed together

4. **Weak Repository Pattern**
   - Only one repository (`snapshot_repository.py`)
   - Services doing direct file I/O
   - No abstraction over data access

5. **Configuration Issues**
   - Settings accessed globally
   - No dependency injection
   - Hard-coded paths and constants scattered

#### File Structure Problems

```
backend/
├── main.py                    # ❌ All routes in one file (248 lines)
├── services/
│   ├── history_service.py     # ❌ 644 lines, 20+ functions
│   ├── vision_service.py      # ❌ 427 lines, mixed responsibilities
│   ├── mapping_service.py     # ❌ 8KB, prompt templates mixed with logic
│   ├── job_runner.py          # ✓ Reasonable
│   └── ...
├── api/
│   ├── schemas.py             # ❌ All Pydantic models in one file
│   └── __init__.py
├── repositories/
│   └── snapshot_repository.py # ❌ Only one repository
└── models/
    └── job.py                 # ❌ All domain models in one file
```

### 1.2 Frontend Issues

#### Critical Problems

1. **Large Page Components**
   - `DashboardPage.tsx`: 632 lines (charts, filters, mutations all in one)
   - `WorkspacePage.tsx`: 309 lines
   - `ResultsPanel.tsx`: 302 lines

2. **Type-Based Organization**
   - Components grouped by type (pdf/, results/, common/)
   - Not by features or business domains
   - Hard to locate related functionality

3. **Unclear Service Layer**
   - `mockApi.ts` - misleading name (it's the real API client)
   - All API calls in one 205-line file
   - No separation by domain

4. **State Management Confusion**
   - Mix of Zustand and React Query
   - Unclear when to use which
   - Global store doing too much

5. **Hook Organization**
   - `useHistoryData.ts` and `useExtractionData.ts`
   - Hooks don't align with features
   - Business logic leaking into hooks

#### File Structure Problems

```
src/
├── pages/
│   ├── DashboardPage.tsx      # ❌ 632 lines
│   └── WorkspacePage.tsx      # ❌ 309 lines
├── components/
│   ├── pdf/                   # ⚠️ Type-based grouping
│   ├── results/               # ⚠️ Type-based grouping
│   ├── common/
│   ├── header/
│   └── layout/
├── services/
│   └── mockApi.ts             # ❌ Misleading name, all APIs here
├── hooks/                     # ⚠️ Not feature-aligned
├── state/                     # ⚠️ Global store
└── types/
    └── extraction.ts          # ❌ All types in one file
```

### 1.3 Cross-Cutting Issues

1. **No Clear Domain Boundaries**
   - OCR extraction, document classification, table processing, canonical mapping all intermingled
   - Difficult to understand what each module does
   - Changes ripple across multiple files

2. **Inconsistent Naming**
   - Backend: snake_case
   - Frontend: camelCase
   - No clear naming conventions for layers

3. **Limited Testing**
   - Only `App.test.tsx` visible
   - No test organization
   - No clear testing strategy

4. **Documentation Gaps**
   - README is comprehensive but architecture is unclear
   - No ADRs (Architecture Decision Records)
   - No component documentation

---

## 2. Proposed Architecture

### 2.1 Backend Clean Architecture

```
backend/
├── api/                          # Presentation Layer
│   ├── v1/
│   │   ├── routers/
│   │   │   ├── jobs.py          # Job processing routes
│   │   │   ├── history.py       # History & metrics routes
│   │   │   ├── uploads.py       # Upload routes
│   │   │   └── health.py        # Health check routes
│   │   ├── dependencies.py      # DI container & dependencies
│   │   └── schemas/
│   │       ├── job_schemas.py
│   │       ├── history_schemas.py
│   │       ├── upload_schemas.py
│   │       └── common_schemas.py
│   └── main.py                  # App initialization only
│
├── application/                 # Application Layer (Use Cases)
│   ├── commands/                # Write operations
│   │   ├── process_document.py
│   │   ├── save_edits.py
│   │   ├── delete_job.py
│   │   └── upload_document.py
│   ├── queries/                 # Read operations
│   │   ├── get_job_status.py
│   │   ├── get_page_data.py
│   │   ├── get_metrics.py
│   │   ├── get_low_confidence.py
│   │   └── list_jobs.py
│   └── dto/                     # Data Transfer Objects
│       └── ...
│
├── domain/                      # Domain Layer (Business Logic)
│   ├── entities/
│   │   ├── extraction_job.py
│   │   ├── page_extraction.py
│   │   ├── field_extraction.py
│   │   ├── table_extraction.py
│   │   └── canonical_bundle.py
│   ├── value_objects/
│   │   ├── bounding_box.py
│   │   ├── confidence.py
│   │   ├── job_status.py
│   │   └── document_type.py
│   ├── services/                # Domain Services
│   │   ├── confidence_calculator.py
│   │   ├── document_classifier.py
│   │   ├── field_aggregator.py
│   │   ├── table_grouper.py
│   │   └── canonical_mapper.py
│   ├── repositories/            # Repository Interfaces
│   │   ├── job_repository.py
│   │   ├── page_repository.py
│   │   └── snapshot_repository.py
│   └── exceptions/
│       └── domain_exceptions.py
│
├── infrastructure/              # Infrastructure Layer
│   ├── persistence/
│   │   ├── file_job_repository.py
│   │   ├── file_page_repository.py
│   │   └── file_snapshot_repository.py
│   ├── vision/
│   │   ├── azure_vision_client.py
│   │   ├── vision_prompt_builder.py
│   │   └── vision_response_parser.py
│   ├── pdf/
│   │   ├── pdf_renderer.py
│   │   ├── image_processor.py
│   │   └── auto_rotator.py
│   ├── mapping/
│   │   ├── azure_mapping_client.py
│   │   └── canonical_transformer.py
│   └── config/
│       ├── settings.py
│       └── dependencies.py
│
├── shared/                      # Shared utilities
│   ├── logging.py
│   ├── serializers.py
│   └── constants.py
│
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

### 2.2 Frontend Feature-Based Architecture

```
src/
├── features/                    # Feature modules
│   ├── dashboard/
│   │   ├── components/
│   │   │   ├── DashboardMetrics.tsx
│   │   │   ├── JobsTable.tsx
│   │   │   ├── ConfidenceHistogram.tsx
│   │   │   ├── LowConfidenceList.tsx
│   │   │   ├── FilterBar.tsx
│   │   │   └── StatusChart.tsx
│   │   ├── hooks/
│   │   │   ├── useDashboardMetrics.ts
│   │   │   ├── useJobsList.ts
│   │   │   └── useJobFilters.ts
│   │   ├── api/
│   │   │   └── dashboardApi.ts
│   │   ├── types/
│   │   │   └── dashboard.types.ts
│   │   └── DashboardPage.tsx
│   │
│   ├── workspace/
│   │   ├── components/
│   │   │   ├── pdf-viewer/
│   │   │   │   ├── PdfViewer.tsx
│   │   │   │   ├── PageThumbnails.tsx
│   │   │   │   └── PageControls.tsx
│   │   │   ├── results-panel/
│   │   │   │   ├── ResultsPanel.tsx
│   │   │   │   ├── FieldsTab.tsx
│   │   │   │   ├── TablesTab.tsx
│   │   │   │   ├── CanonicalTab.tsx
│   │   │   │   ├── RawTab.tsx
│   │   │   │   └── SummaryTab.tsx
│   │   │   ├── ResizablePanels.tsx
│   │   │   └── WorkspaceHeader.tsx
│   │   ├── hooks/
│   │   │   ├── usePageData.ts
│   │   │   ├── useFieldEditing.ts
│   │   │   ├── useTableEditing.ts
│   │   │   └── useCanonicalData.ts
│   │   ├── api/
│   │   │   └── workspaceApi.ts
│   │   ├── state/
│   │   │   └── viewerStore.ts
│   │   ├── types/
│   │   │   └── workspace.types.ts
│   │   └── WorkspacePage.tsx
│   │
│   ├── upload/
│   │   ├── components/
│   │   │   └── UploadDropzone.tsx
│   │   ├── hooks/
│   │   │   └── useDocumentUpload.ts
│   │   ├── api/
│   │   │   └── uploadApi.ts
│   │   └── types/
│   │       └── upload.types.ts
│   │
│   └── shared/                  # Shared feature components
│       ├── components/
│       │   ├── StatusIndicator.tsx
│       │   ├── ConfidenceBadge.tsx
│       │   └── AppShell.tsx
│       └── hooks/
│
├── core/                        # Core application infrastructure
│   ├── api/
│   │   ├── client.ts           # Base API client
│   │   ├── interceptors.ts
│   │   └── types.ts
│   ├── config/
│   │   └── env.ts
│   ├── types/
│   │   ├── common.types.ts
│   │   ├── extraction.types.ts
│   │   └── api.types.ts
│   ├── utils/
│   │   ├── formatters.ts
│   │   └── validators.ts
│   └── constants/
│       └── app.constants.ts
│
├── router/
│   └── AppRouter.tsx
│
├── App.tsx
└── main.tsx
```

---

## 3. Detailed Refactoring Steps

### Phase 1: Backend Foundation (Week 1-2)

#### Step 1.1: Create Domain Layer
**Priority: CRITICAL**

1. **Extract Domain Entities**
   ```python
   # backend/domain/entities/extraction_job.py
   from dataclasses import dataclass
   from typing import List, Optional
   from datetime import datetime
   from ..value_objects.job_status import JobStatus
   from .page_extraction import PageExtraction
   
   @dataclass
   class ExtractionJob:
       job_id: str
       pdf_path: Path
       status: JobStatus
       pages: List[PageExtraction]
       document_type: Optional[str]
       canonical: Optional[dict]
       # ... other fields
   ```

2. **Create Value Objects**
   ```python
   # backend/domain/value_objects/confidence.py
   from dataclasses import dataclass
   
   @dataclass(frozen=True)
   class Confidence:
       value: float
       
       def __post_init__(self):
           if not 0 <= self.value <= 1:
               raise ValueError("Confidence must be between 0 and 1")
       
       @classmethod
       def from_raw(cls, raw_value) -> 'Confidence':
           try:
               value = float(raw_value)
               return cls(max(0.0, min(1.0, value)))
           except (TypeError, ValueError):
               return cls(0.0)
       
       def is_low(self, threshold: float = 0.4) -> bool:
           return self.value <= threshold
       
       def bucket_index(self, bounds: tuple) -> int:
           for idx, bound in enumerate(bounds):
               if self.value <= bound:
                   return idx
           return len(bounds)
   ```

3. **Define Repository Interfaces**
   ```python
   # backend/domain/repositories/job_repository.py
   from abc import ABC, abstractmethod
   from typing import Optional, List
   from ..entities.extraction_job import ExtractionJob
   
   class JobRepository(ABC):
       @abstractmethod
       def save(self, job: ExtractionJob) -> None:
           pass
       
       @abstractmethod
       def find_by_id(self, job_id: str) -> Optional[ExtractionJob]:
           pass
       
       @abstractmethod
       def find_all(self) -> List[ExtractionJob]:
           pass
       
       @abstractmethod
       def delete(self, job_id: str) -> bool:
           pass
   ```

#### Step 1.2: Implement Application Layer Use Cases
**Priority: CRITICAL**

1. **Command Pattern for Write Operations**
   ```python
   # backend/application/commands/save_edits.py
   from dataclasses import dataclass
   from typing import List
   
   @dataclass
   class SaveEditsCommand:
       job_id: str
       page_number: int
       field_updates: List[dict]
       table_cell_updates: List[dict]
   
   class SaveEditsHandler:
       def __init__(self, job_repository, confidence_calculator):
           self.job_repository = job_repository
           self.confidence_calculator = confidence_calculator
       
       def handle(self, command: SaveEditsCommand):
           job = self.job_repository.find_by_id(command.job_id)
           if not job:
               raise JobNotFoundException(command.job_id)
           
           page = job.get_page(command.page_number)
           page.apply_field_updates(command.field_updates)
           page.apply_table_updates(command.table_cell_updates)
           
           # Recalculate confidence
           job.recalculate_confidence(self.confidence_calculator)
           
           self.job_repository.save(job)
           return job
   ```

2. **Query Pattern for Read Operations**
   ```python
   # backend/application/queries/get_metrics.py
   from dataclasses import dataclass
   from datetime import datetime, timedelta
   
   @dataclass
   class GetMetricsQuery:
       start_date: datetime
       end_date: datetime
   
   class GetMetricsHandler:
       def __init__(self, job_repository, metrics_calculator):
           self.job_repository = job_repository
           self.metrics_calculator = metrics_calculator
       
       def handle(self, query: GetMetricsQuery):
           jobs = self.job_repository.find_in_date_range(
               query.start_date, 
               query.end_date
           )
           return self.metrics_calculator.calculate(jobs)
   ```

#### Step 1.3: Split Service Files
**Priority: CRITICAL**

**Break down `history_service.py` (644 lines):**

1. Extract confidence calculation → `domain/services/confidence_calculator.py`
2. Extract snapshot logic → `infrastructure/persistence/file_snapshot_repository.py`
3. Extract metrics calculation → `domain/services/metrics_calculator.py`
4. Extract edit application → `application/commands/save_edits.py`
5. Extract job queries → `application/queries/`

**Break down `vision_service.py` (427 lines):**

1. Extract Azure client → `infrastructure/vision/azure_vision_client.py`
2. Extract prompts → `infrastructure/vision/vision_prompts.py`
3. Extract parsing → `infrastructure/vision/vision_response_parser.py`
4. Extract use case → `application/commands/extract_page.py`

#### Step 1.4: Reorganize API Routes
**Priority: HIGH**

1. **Split main.py into routers**
   ```python
   # backend/api/v1/routers/jobs.py
   from fastapi import APIRouter, HTTPException, Depends
   from ....application.queries.get_job_status import GetJobStatusQuery, GetJobStatusHandler
   
   router = APIRouter(prefix="/jobs", tags=["jobs"])
   
   @router.get("/{job_id}/status")
   async def get_job_status(
       job_id: str,
       handler: GetJobStatusHandler = Depends()
   ):
       query = GetJobStatusQuery(job_id=job_id)
       try:
           return handler.handle(query)
       except JobNotFoundException:
           raise HTTPException(status_code=404, detail="Job not found")
   ```

2. **Setup dependency injection**
   ```python
   # backend/api/v1/dependencies.py
   from typing import Generator
   from ...infrastructure.persistence.file_job_repository import FileJobRepository
   from ...application.queries.get_job_status import GetJobStatusHandler
   
   def get_job_repository() -> FileJobRepository:
       return FileJobRepository(base_path=Path("backend_data"))
   
   def get_job_status_handler(
       repo: FileJobRepository = Depends(get_job_repository)
   ) -> GetJobStatusHandler:
       return GetJobStatusHandler(repo)
   ```

#### Step 1.5: Implement Infrastructure Layer
**Priority: HIGH**

1. **File-based repositories**
   ```python
   # backend/infrastructure/persistence/file_job_repository.py
   from pathlib import Path
   from typing import Optional, List
   from ...domain.repositories.job_repository import JobRepository
   from ...domain.entities.extraction_job import ExtractionJob
   
   class FileJobRepository(JobRepository):
       def __init__(self, base_path: Path):
           self.base_path = base_path
           self.base_path.mkdir(exist_ok=True)
       
       def save(self, job: ExtractionJob) -> None:
           job_dir = self.base_path / job.job_id
           job_dir.mkdir(exist_ok=True)
           # Serialize and save
       
       def find_by_id(self, job_id: str) -> Optional[ExtractionJob]:
           # Load and deserialize
           pass
   ```

2. **Vision service client**
   ```python
   # backend/infrastructure/vision/azure_vision_client.py
   from openai import OpenAI
   from typing import Dict, Any
   
   class AzureVisionClient:
       def __init__(self, api_key: str, endpoint: str, model: str):
           self.client = OpenAI(api_key=api_key, base_url=endpoint)
           self.model = model
       
       def analyze_image(self, image_data: str, prompt: str) -> Dict[str, Any]:
           response = self.client.chat.completions.create(
               model=self.model,
               messages=[{
                   "role": "user",
                   "content": [
                       {"type": "text", "text": prompt},
                       {"type": "image_url", "image_url": {"url": image_data}}
                   ]
               }]
           )
           return response
   ```

---

### Phase 2: Frontend Restructuring (Week 3-4)

#### Step 2.1: Create Feature Modules
**Priority: HIGH**

1. **Dashboard Feature**
   ```typescript
   // src/features/dashboard/DashboardPage.tsx
   import { DashboardMetrics } from './components/DashboardMetrics'
   import { JobsTable } from './components/JobsTable'
   import { ConfidenceHistogram } from './components/ConfidenceHistogram'
   import { useDashboardData } from './hooks/useDashboardData'
   
   export const DashboardPage = () => {
     const { metrics, jobs, isLoading } = useDashboardData()
     
     return (
       <AppShell>
         <DashboardMetrics metrics={metrics} />
         <ConfidenceHistogram jobs={jobs} />
         <JobsTable jobs={jobs} isLoading={isLoading} />
       </AppShell>
     )
   }
   ```

2. **Break down large components**
   ```typescript
   // src/features/dashboard/components/DashboardMetrics.tsx
   import type { DashboardMetrics } from '../types/dashboard.types'
   
   type Props = {
     metrics: DashboardMetrics
   }
   
   export const DashboardMetrics = ({ metrics }: Props) => {
     return (
       <div className="grid grid-cols-4 gap-4">
         <MetricCard 
           label="Total Jobs" 
           value={metrics.totalJobs} 
         />
         <MetricCard 
           label="Completed" 
           value={metrics.completedJobs} 
         />
         {/* More metrics */}
       </div>
     )
   }
   ```

#### Step 2.2: Organize API Clients by Feature
**Priority: MEDIUM**

1. **Feature-specific API clients**
   ```typescript
   // src/features/dashboard/api/dashboardApi.ts
   import { apiClient } from '@/core/api/client'
   import type { DashboardMetrics, JobSummary } from '../types/dashboard.types'
   
   export const dashboardApi = {
     async getMetrics(): Promise<DashboardMetrics> {
       return apiClient.get('/api/history/metrics')
     },
     
     async listJobs(): Promise<JobSummary[]> {
       const response = await apiClient.get('/api/history/jobs')
       return response.jobs
     },
     
     async deleteJob(jobId: string): Promise<void> {
       return apiClient.delete(`/api/history/jobs/${jobId}`)
     }
   }
   ```

2. **Base API client**
   ```typescript
   // src/core/api/client.ts
   const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
   
   class ApiClient {
     private baseUrl: string
     
     constructor(baseUrl: string) {
       this.baseUrl = baseUrl
     }
     
     async get<T>(path: string): Promise<T> {
       const response = await fetch(this.buildUrl(path))
       return this.handleResponse<T>(response)
     }
     
     async post<T>(path: string, body: unknown): Promise<T> {
       const response = await fetch(this.buildUrl(path), {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify(body)
       })
       return this.handleResponse<T>(response)
     }
     
     // ... delete, put, etc.
   }
   
   export const apiClient = new ApiClient(API_BASE_URL)
   ```

#### Step 2.3: Refactor State Management
**Priority: MEDIUM**

1. **Feature-specific stores**
   ```typescript
   // src/features/workspace/state/viewerStore.ts
   import { create } from 'zustand'
   
   type ViewerState = {
     jobId: string | null
     currentPage: number
     selectedTab: string
     setJobId: (jobId: string, totalPages?: number) => void
     setCurrentPage: (page: number) => void
     setSelectedTab: (tab: string) => void
   }
   
   export const useViewerStore = create<ViewerState>((set) => ({
     jobId: null,
     currentPage: 1,
     selectedTab: 'fields',
     setJobId: (jobId, totalPages) => set({ jobId, currentPage: 1 }),
     setCurrentPage: (page) => set({ currentPage: page }),
     setSelectedTab: (tab) => set({ selectedTab: tab })
   }))
   ```

2. **Custom hooks for business logic**
   ```typescript
   // src/features/workspace/hooks/useFieldEditing.ts
   import { useState, useCallback } from 'react'
   import { useMutation } from '@tanstack/react-query'
   import { workspaceApi } from '../api/workspaceApi'
   import type { FieldUpdate } from '../types/workspace.types'
   
   export const useFieldEditing = (jobId: string, pageNumber: number) => {
     const [drafts, setDrafts] = useState<Record<string, string>>({})
     const [isEditing, setIsEditing] = useState(false)
     
     const saveMutation = useMutation({
       mutationFn: (updates: FieldUpdate[]) => 
         workspaceApi.saveEdits(jobId, pageNumber, updates),
       onSuccess: () => {
         setDrafts({})
         setIsEditing(false)
       }
     })
     
     const updateField = useCallback((fieldId: string, value: string) => {
       setDrafts(prev => ({ ...prev, [fieldId]: value }))
     }, [])
     
     return {
       drafts,
       isEditing,
       setIsEditing,
       updateField,
       save: saveMutation.mutate,
       isSaving: saveMutation.isPending
     }
   }
   ```

---

### Phase 3: Testing & Documentation (Week 5)

#### Step 3.1: Setup Test Infrastructure
**Priority: MEDIUM**

1. **Backend unit tests**
   ```python
   # backend/tests/unit/domain/services/test_confidence_calculator.py
   import pytest
   from backend.domain.services.confidence_calculator import ConfidenceCalculator
   from backend.domain.value_objects.confidence import Confidence
   
   def test_calculate_buckets():
       calculator = ConfidenceCalculator()
       confidences = [
           Confidence(0.1), Confidence(0.3), 
           Confidence(0.5), Confidence(0.9)
       ]
       
       buckets = calculator.calculate_buckets(confidences)
       
       assert buckets[0] == 1  # 0.1 in first bucket
       assert buckets[1] == 1  # 0.3 in second bucket
   ```

2. **Frontend component tests**
   ```typescript
   // src/features/dashboard/components/DashboardMetrics.test.tsx
   import { render, screen } from '@testing-library/react'
   import { DashboardMetrics } from './DashboardMetrics'
   
   describe('DashboardMetrics', () => {
     it('displays total jobs count', () => {
       const metrics = {
         totalJobs: 42,
         completedJobs: 30,
         // ... other fields
       }
       
       render(<DashboardMetrics metrics={metrics} />)
       
       expect(screen.getByText('42')).toBeInTheDocument()
     })
   })
   ```

#### Step 3.2: Add Documentation
**Priority: LOW**

1. **Architecture Decision Records**
   ```markdown
   # ADR-001: Clean Architecture for Backend
   
   ## Status
   Accepted
   
   ## Context
   The backend codebase has grown to be difficult to maintain with services
   exceeding 600 lines and mixed responsibilities.
   
   ## Decision
   Adopt Clean Architecture with clear separation between:
   - Domain (entities, value objects, repositories)
   - Application (use cases, DTOs)
   - Infrastructure (persistence, external services)
   - API (routes, schemas)
   
   ## Consequences
   - More files but better organization
   - Easier to test individual components
   - Clear dependency direction
   ```

2. **API documentation**
   - Enable automatic OpenAPI/Swagger docs in FastAPI
   - Add docstrings to all route handlers
   - Document all request/response schemas

---

## 4. Migration Strategy

### 4.1 Parallel Development Approach

**Goal**: Refactor incrementally without breaking existing functionality.

#### Backend Migration

1. **Create new structure alongside old**
   ```
   backend/
   ├── legacy/           # Move old code here
   │   └── services/
   ├── domain/           # New clean architecture
   ├── application/
   └── infrastructure/
   ```

2. **Implement one use case at a time**
   - Start with `GetJobStatus` query
   - Implement domain entities, repository, query handler
   - Create new route in new router
   - Test thoroughly
   - Switch frontend to use new route
   - Mark old route as deprecated

3. **Gradual migration order**
   ```
   Week 1: Setup foundation
   - Domain entities
   - Repository interfaces
   - First repository implementation
   
   Week 2: First use cases
   - GetJobStatus query
   - GetPageData query
   - ListJobs query
   
   Week 3: Write operations
   - SaveEdits command
   - ProcessDocument command
   
   Week 4: Complex operations
   - Metrics calculation
   - Low confidence queries
   
   Week 5: Cleanup
   - Remove legacy code
   - Update tests
   ```

#### Frontend Migration

1. **Create feature modules one at a time**
   ```
   src/
   ├── legacy/           # Move old pages here
   │   ├── DashboardPage.tsx
   │   └── WorkspacePage.tsx
   ├── features/         # New feature-based structure
   │   └── dashboard/    # Migrate dashboard first
   ```

2. **Migration order**
   ```
   Week 1: Setup
   - Create core/ infrastructure
   - Setup base API client
   - Create feature structure
   
   Week 2: Dashboard feature
   - Break down DashboardPage
   - Create dashboard components
   - Migrate dashboard API calls
   
   Week 3: Workspace feature
   - Break down WorkspacePage
   - Create workspace components
   - Migrate workspace API calls
   
   Week 4: Upload feature
   - Extract upload logic
   - Create upload components
   
   Week 5: Cleanup
   - Remove legacy/
   - Update routing
   ```

### 4.2 Testing During Migration

1. **Keep existing tests passing**
   - Don't delete tests when refactoring
   - Adapt tests to new structure
   - Add new tests for new components

2. **Integration tests**
   - Test that old and new implementations produce same results
   - Create integration tests between layers

3. **End-to-end tests**
   - Add basic E2E tests before refactoring
   - Ensure E2E tests pass throughout migration

---

## 5. Success Metrics

### Code Quality Metrics

- [ ] No file > 300 lines
- [ ] No function > 50 lines
- [ ] Test coverage > 70%
- [ ] All linter warnings resolved
- [ ] No circular dependencies

### Architecture Metrics

- [ ] Clear separation of concerns (domain, application, infrastructure)
- [ ] All external dependencies in infrastructure layer
- [ ] No domain logic in API routes
- [ ] Repository pattern fully implemented
- [ ] All use cases follow command/query pattern

### Developer Experience Metrics

- [ ] New feature can be added in single module
- [ ] Tests can run in < 5 seconds
- [ ] Build time < 30 seconds
- [ ] Clear documentation for all layers
- [ ] New developers can understand structure in < 1 hour

---

## 6. Quick Wins (Do First)

These changes provide immediate value with minimal risk:

### Backend Quick Wins

1. **Rename and organize constants** (30 min)
   - Move all constants to `shared/constants.py`
   - Group by domain (CONFIDENCE_*, SNAPSHOT_*, etc.)

2. **Split schemas.py** (1 hour)
   - Create `api/schemas/job_schemas.py`
   - Create `api/schemas/history_schemas.py`
   - Create `api/schemas/common_schemas.py`

3. **Extract confidence logic** (2 hours)
   - Create `domain/value_objects/confidence.py`
   - Replace all confidence calculation with value object
   - Immediate readability improvement

4. **Create router for history** (2 hours)
   - Extract history routes from main.py
   - Create `api/v1/routers/history.py`
   - Reduces main.py size by ~60 lines

### Frontend Quick Wins

1. **Rename mockApi.ts** (5 min)
   - Rename to `apiClient.ts`
   - Update imports

2. **Extract constants** (30 min)
   - Create `core/constants/app.constants.ts`
   - Move CHART_COLORS, STATUS_LABELS, etc.

3. **Split types file** (1 hour)
   - Create `core/types/job.types.ts`
   - Create `core/types/extraction.types.ts`
   - Create `core/types/canonical.types.ts`

4. **Extract MetricCard component** (1 hour)
   - Create `features/dashboard/components/MetricCard.tsx`
   - Immediate reusability

---

## 7. Risk Assessment

### High Risk Changes

1. **Database/persistence changes**
   - **Risk**: Data loss or corruption
   - **Mitigation**: Backup all data, implement migration script, test thoroughly

2. **Vision service refactoring**
   - **Risk**: Breaking OCR extraction
   - **Mitigation**: Keep old implementation, A/B test, gradual rollout

3. **State management changes**
   - **Risk**: UI bugs, lost state
   - **Mitigation**: Comprehensive UI tests, manual testing

### Medium Risk Changes

1. **API route reorganization**
   - **Risk**: Breaking frontend
   - **Mitigation**: Version API, deprecate old routes gradually

2. **Component splitting**
   - **Risk**: Props drilling, performance issues
   - **Mitigation**: Use React Context where appropriate, profile performance

### Low Risk Changes

1. **File/folder reorganization**
   - Easy to revert
   - Can be done incrementally

2. **Constant extraction**
   - Minimal impact
   - Easy to test

3. **Type splitting**
   - Compile-time safety
   - Easy to verify

---

## 8. Timeline

### Conservative Estimate (5 weeks, 1 developer)

| Week | Backend | Frontend |
|------|---------|----------|
| 1 | Domain layer, repository interfaces | Core infrastructure, feature structure |
| 2 | Application use cases, first migrations | Dashboard feature migration |
| 3 | Infrastructure implementations | Workspace feature migration |
| 4 | Complete service migrations | Upload feature, state cleanup |
| 5 | Testing, documentation, cleanup | Testing, documentation, cleanup |

### Aggressive Estimate (3 weeks, 2 developers)

| Week | Backend Developer | Frontend Developer |
|------|-------------------|-------------------|
| 1 | Domain + Application layer | Core + Dashboard feature |
| 2 | Infrastructure + API routes | Workspace + Upload features |
| 3 | Testing + Documentation | Testing + Documentation |

---

## 9. Next Steps

### Immediate Actions (This Week)

1. **Get stakeholder approval** for refactoring plan
2. **Create refactoring branch** from main
3. **Implement quick wins** to demonstrate value
4. **Setup project board** to track progress
5. **Schedule daily standups** for refactoring work

### Phase 1 Kickoff (Next Week)

1. **Backend**: Create domain entities and value objects
2. **Frontend**: Setup core infrastructure and feature folders
3. **Both**: Write first set of tests for new structure
4. **Documentation**: Start ADR document for key decisions

### Checkpoints

- **End of Week 1**: Domain layer complete, core infrastructure ready
- **End of Week 2**: First use case migrated, first feature migrated
- **End of Week 3**: 50% migration complete
- **End of Week 4**: 90% migration complete
- **End of Week 5**: 100% complete, legacy code removed

---

## 10. Conclusion

This refactoring plan provides a clear path from the current messy, hard-to-maintain codebase to a clean, modular, well-architected application. The phased approach minimizes risk while delivering incremental value.

**Key Principles:**
- Incremental migration over big-bang rewrite
- Test coverage maintained throughout
- Business functionality never broken
- Clear separation of concerns at all layers
- Feature-based organization for easier development

**Expected Outcomes:**
- 50% reduction in average file size
- 2x faster feature development
- 3x easier onboarding for new developers
- 70%+ test coverage
- Clear, maintainable architecture

The investment in refactoring will pay dividends in reduced bugs, faster feature delivery, and improved developer satisfaction.
