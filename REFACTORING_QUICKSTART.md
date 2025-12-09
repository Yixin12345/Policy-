# Refactoring Quick Start Guide

This guide helps you get started with the refactoring immediately. Read this first, then refer to the detailed plan and checklist.

**Status (Nov 20, 2025):** Legacy bridge QA confirmed classification/table data delivery, and workspace PdfViewer now displays "Page Category" badges that mirror backend hints. Day 19 work focuses on expanding manual QA and planning the frontend feature-module split.

## TL;DR - What's Wrong?

**Backend Problems:**
- `history_service.py`: 644 lines doing everything (persistence + calculation + API logic)
- `vision_service.py`: 427 lines mixing prompts, API calls, and parsing
- `main.py`: 248 lines with all API routes in one file
- No clear separation between business logic and infrastructure

**Frontend Problems:**
- `DashboardPage.tsx`: 632 lines with charts, filters, state, and mutations
- Components organized by type (pdf/, results/) not by feature
- `mockApi.ts`: misleading name for the actual API client
- Business logic scattered across components and hooks

**Result:** Hard to find code, hard to make changes, hard to test.

---

## The Solution in 3 Sentences

1. **Backend**: Adopt Clean Architecture with Domain → Application → Infrastructure → API layers
2. **Frontend**: Use feature-based organization with Dashboard, Workspace, Upload modules
3. **Migration**: Incremental refactoring over 5 weeks, one module at a time

---

## Before & After Comparison

### Backend Structure

**Before (Current):**
```
backend/
├── main.py (248 lines - all routes)
├── services/
│   ├── history_service.py (644 lines - does everything)
│   ├── vision_service.py (427 lines - mixed concerns)
│   └── ...
├── models/
│   └── job.py (all models in one file)
└── api/
    └── schemas.py (all schemas in one file)
```

**After (Target):**
```
backend/
├── api/
│   └── v1/
│       ├── routers/
│       │   ├── jobs.py (job routes only)
│       │   ├── history.py (history routes only)
│       │   └── uploads.py (upload routes only)
│       └── schemas/ (organized by domain)
├── application/
│   ├── commands/ (write operations)
│   │   ├── process_document.py
│   │   └── save_edits.py
│   └── queries/ (read operations)
│       ├── get_job_status.py
│       └── list_jobs.py
├── domain/
│   ├── entities/ (business objects)
│   │   ├── extraction_job.py
│   │   └── field_extraction.py
│   ├── services/ (business logic)
│   │   └── confidence_calculator.py
│   └── repositories/ (interfaces)
│       └── job_repository.py
└── infrastructure/
    ├── persistence/ (file storage)
    │   └── file_job_repository.py
    └── vision/ (external APIs)
        └── azure_vision_client.py
```

### Frontend Structure

**Before (Current):**
```
src/
├── pages/
│   ├── DashboardPage.tsx (632 lines)
│   └── WorkspacePage.tsx (309 lines)
├── components/
│   ├── pdf/ (type-based grouping)
│   ├── results/ (type-based grouping)
│   └── common/
├── services/
│   └── mockApi.ts (all API calls)
└── hooks/ (generic hooks)
```

**After (Target):**
```
src/
├── features/
│   ├── dashboard/
│   │   ├── components/
│   │   │   ├── DashboardMetrics.tsx
│   │   │   ├── JobsTable.tsx
│   │   │   └── ConfidenceHistogram.tsx
│   │   ├── hooks/
│   │   │   └── useDashboardData.ts
│   │   ├── api/
│   │   │   └── dashboardApi.ts
│   │   └── DashboardPage.tsx (~100 lines)
│   │
│   ├── workspace/
│   │   ├── components/
│   │   │   ├── pdf-viewer/
│   │   │   └── results-panel/
│   │   ├── hooks/
│   │   │   ├── usePageData.ts
│   │   │   └── useFieldEditing.ts
│   │   ├── api/
│   │   │   └── workspaceApi.ts
│   │   └── WorkspacePage.tsx (~150 lines)
│   │
│   └── upload/
│       └── ... (similar structure)
│
└── core/
    ├── api/
    │   └── client.ts (base API client)
    ├── types/
    └── utils/
```

---

## Start Here: 3 Quick Wins (2 Hours)

These provide immediate value and demonstrate the refactoring approach:

### Quick Win 1: Split Backend Schemas (30 min)

**Why:** `schemas.py` has all Pydantic models in one file. Splitting improves organization.

**How:**
```bash
cd backend/api
mkdir schemas
touch schemas/__init__.py
touch schemas/job_schemas.py
touch schemas/history_schemas.py
touch schemas/common_schemas.py
```

Move schemas to appropriate files:
- Job-related → `job_schemas.py`
- History-related → `history_schemas.py`
- Shared types → `common_schemas.py`

Update `main.py` imports.

**Verify:** `python -m pytest backend/tests/`

### Quick Win 2: Rename mockApi.ts (5 min)

**Why:** Name is misleading - it's the real API client.

**How:**
```bash
cd src/services
mv mockApi.ts apiClient.ts
```

Update imports in all files:
```bash
# Find all files that import mockApi
grep -r "from '../services/mockApi" src/
grep -r "from './services/mockApi" src/

# Replace manually or use:
find src -type f -name "*.tsx" -o -name "*.ts" | xargs sed -i '' 's/mockApi/apiClient/g'
```

**Verify:** `npm run build`

### Quick Win 3: Extract ConfidenceBadge Constants (15 min)

**Why:** CHART_COLORS, STATUS_LABELS scattered across components.

**How:**
```bash
mkdir -p src/core/constants
touch src/core/constants/app.constants.ts
```

Create `app.constants.ts`:
```typescript
export const CHART_COLORS = ['#6366F1', '#0EA5E9', '#22C55E', '#F97316', '#EC4899'] as const

export const STATUS_LABELS: Record<string, string> = {
  queued: 'Queued',
  running: 'In Progress',
  completed: 'Completed',
  partial: 'Partial',
  error: 'Error'
}

export const STATUS_BADGE_CLASS: Record<string, string> = {
  queued: 'bg-amber-100 text-amber-700 border border-amber-200',
  running: 'bg-sky-100 text-sky-700 border border-sky-200',
  completed: 'bg-emerald-100 text-emerald-700 border border-emerald-200',
  partial: 'bg-indigo-100 text-indigo-700 border border-indigo-200',
  error: 'bg-rose-100 text-rose-700 border border-rose-200'
}

export const CONFIDENCE_BUCKET_LABELS = ['0-0.2', '0.2-0.4', '0.4-0.6', '0.6-0.8', '0.8-<1.0', '1.0'] as const
```

Import in DashboardPage.tsx:
```typescript
import { CHART_COLORS, STATUS_LABELS, STATUS_BADGE_CLASS, CONFIDENCE_BUCKET_LABELS } from '@/core/constants/app.constants'
```

**Verify:** `npm run dev` and check dashboard loads

---

## Week 1 Focus: Backend Domain Layer

The most critical change is establishing the domain layer. This provides the foundation for everything else.

### Day 1-2: Create Confidence Value Object

**Why it matters:** Confidence calculation is scattered across 4+ files. Centralizing it:
- Makes logic reusable
- Easier to test
- Single source of truth

**Step-by-step:**

1. **Create the file:**
```bash
mkdir -p backend/domain/value_objects
touch backend/domain/value_objects/__init__.py
touch backend/domain/value_objects/confidence.py
```

2. **Implement Confidence class:**
```python
# backend/domain/value_objects/confidence.py
from dataclasses import dataclass
from typing import Any, Tuple

@dataclass(frozen=True)
class Confidence:
    """Immutable confidence value between 0 and 1."""
    value: float
    
    def __post_init__(self):
        if not 0 <= self.value <= 1:
            object.__setattr__(self, 'value', max(0.0, min(1.0, self.value)))
    
    @classmethod
    def from_raw(cls, raw_value: Any) -> 'Confidence':
        """Create Confidence from any value, coercing to valid range."""
        try:
            value = float(raw_value)
            return cls(value)
        except (TypeError, ValueError):
            return cls(0.0)
    
    def is_low(self, threshold: float = 0.4) -> bool:
        """Check if confidence is below threshold."""
        return self.value <= threshold
    
    def bucket_index(self, bounds: Tuple[float, ...] = (0.2, 0.4, 0.6, 0.8, 1.0)) -> int:
        """Get bucket index for histogram."""
        for idx, bound in enumerate(bounds):
            if self.value <= bound:
                return idx
        return len(bounds)
    
    def __str__(self) -> str:
        return f"{self.value:.2f}"
    
    def __float__(self) -> float:
        return self.value
```

3. **Write tests:**
```python
# backend/tests/unit/domain/value_objects/test_confidence.py
import pytest
from backend.domain.value_objects.confidence import Confidence

def test_confidence_valid_value():
    conf = Confidence(0.8)
    assert conf.value == 0.8

def test_confidence_clamps_high():
    conf = Confidence(1.5)
    assert conf.value == 1.0

def test_confidence_clamps_low():
    conf = Confidence(-0.5)
    assert conf.value == 0.0

def test_confidence_from_raw_string():
    conf = Confidence.from_raw("0.75")
    assert conf.value == 0.75

def test_confidence_from_raw_invalid():
    conf = Confidence.from_raw("invalid")
    assert conf.value == 0.0

def test_is_low():
    assert Confidence(0.3).is_low()
    assert not Confidence(0.6).is_low()

def test_bucket_index():
    assert Confidence(0.1).bucket_index() == 0
    assert Confidence(0.3).bucket_index() == 1
    assert Confidence(0.5).bucket_index() == 2
    assert Confidence(1.0).bucket_index() == 4
```

4. **Run tests:**
```bash
pytest backend/tests/unit/domain/value_objects/test_confidence.py -v
```

5. **Use it in one place:**

Replace confidence logic in `history_service.py`:
```python
# OLD:
def _normalise_confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def _clamp_confidence(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value

# NEW:
from ..domain.value_objects.confidence import Confidence

# Use: Confidence.from_raw(value).value
```

**Success metrics:**
- [ ] Tests pass
- [ ] Confidence calculation centralized
- [ ] Code is more readable

### Day 3-5: Create Domain Entities

Follow similar pattern for:
- `BoundingBox` value object
- `JobStatus` value object
- `FieldExtraction` entity
- `TableExtraction` entity
- `PageExtraction` entity

---

## Week 2 Focus: Use Cases

Break down monolithic services into focused use cases.

### Example: GetJobStatus Query

**Before (in main.py):**
```python
@app.get("/api/jobs/{job_id}/status")
def get_job_status(job_id: str):
    job = get_job(job_id)  # Global function
    if not job:
        raise HTTPException(status_code=404)
    # ... 20 lines of transformation logic
    return JobStatusSchema(...)
```

**After:**

1. **Create query:**
```python
# backend/application/queries/get_job_status.py
from dataclasses import dataclass

@dataclass
class GetJobStatusQuery:
    job_id: str

class GetJobStatusHandler:
    def __init__(self, job_repository):
        self.job_repository = job_repository
    
    def handle(self, query: GetJobStatusQuery):
        job = self.job_repository.find_by_id(query.job_id)
        if not job:
            raise JobNotFoundException(query.job_id)
        
        return {
            'jobId': job.job_id,
            'totalPages': job.total_pages,
            'processedPages': job.processed_pages,
            'state': job.status.state,
            # ... other fields
        }
```

2. **Use in route:**
```python
# backend/api/v1/routers/jobs.py
@router.get("/{job_id}/status")
def get_job_status(
    job_id: str,
    handler: GetJobStatusHandler = Depends(get_job_status_handler)
):
    query = GetJobStatusQuery(job_id=job_id)
    try:
        return handler.handle(query)
    except JobNotFoundException:
        raise HTTPException(status_code=404, detail="Job not found")
```

**Benefits:**
- Handler is testable without HTTP
- Business logic separated from HTTP concerns
- Easy to add caching, logging, etc.

---

## Week 3-4 Focus: Frontend Features

Break down large pages into feature modules.

### Example: Dashboard Feature

**Before:** DashboardPage.tsx has everything (632 lines)

**After:** Break into focused components

1. **Create structure:**
```bash
mkdir -p src/features/dashboard/components
mkdir -p src/features/dashboard/hooks
mkdir -p src/features/dashboard/api
```

2. **Extract MetricsCard component:**
```typescript
// src/features/dashboard/components/DashboardMetrics.tsx
import type { DashboardMetrics } from '../types'

type Props = {
  metrics: DashboardMetrics
}

export const DashboardMetrics = ({ metrics }: Props) => (
  <div className="grid grid-cols-4 gap-4">
    <MetricCard label="Total Jobs" value={metrics.totalJobs} />
    <MetricCard label="Completed" value={metrics.completedJobs} />
    <MetricCard label="In Progress" value={metrics.runningJobs} />
    <MetricCard label="Failed" value={metrics.failedJobs} />
  </div>
)

const MetricCard = ({ label, value }: { label: string; value: number }) => (
  <div className="bg-white rounded-lg shadow p-4">
    <div className="text-sm text-gray-600">{label}</div>
    <div className="text-2xl font-bold">{value}</div>
  </div>
)
```

3. **Extract custom hook:**
```typescript
// src/features/dashboard/hooks/useDashboardData.ts
import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '../api/dashboardApi'

export const useDashboardData = () => {
  const metricsQuery = useQuery({
    queryKey: ['dashboard', 'metrics'],
    queryFn: dashboardApi.getMetrics
  })
  
  const jobsQuery = useQuery({
    queryKey: ['dashboard', 'jobs'],
    queryFn: dashboardApi.listJobs
  })
  
  return {
    metrics: metricsQuery.data,
    jobs: jobsQuery.data ?? [],
    isLoading: metricsQuery.isLoading || jobsQuery.isLoading
  }
}
```

4. **Simplified page:**
```typescript
// src/features/dashboard/DashboardPage.tsx
import { DashboardMetrics } from './components/DashboardMetrics'
import { JobsTable } from './components/JobsTable'
import { useDashboardData } from './hooks/useDashboardData'

export const DashboardPage = () => {
  const { metrics, jobs, isLoading } = useDashboardData()
  
  if (isLoading) return <LoadingSpinner />
  
  return (
    <AppShell>
      <DashboardMetrics metrics={metrics} />
      <JobsTable jobs={jobs} />
    </AppShell>
  )
}
```

**Result:** 632 lines → ~50 lines main page + focused components

---

## Testing Strategy

### Unit Tests (Fast, Many)

Test individual functions/classes without dependencies:

```python
# Backend
def test_confidence_calculation():
    calc = ConfidenceCalculator()
    result = calc.bucket_index(Confidence(0.3))
    assert result == 1

# Frontend
test('DashboardMetrics renders total jobs', () => {
  const metrics = { totalJobs: 42, ... }
  render(<DashboardMetrics metrics={metrics} />)
  expect(screen.getByText('42')).toBeInTheDocument()
})
```

### Integration Tests (Slower, Fewer)

Test multiple components working together:

```python
# Backend
def test_save_edits_updates_job(test_db):
    handler = SaveEditsHandler(job_repository, confidence_calculator)
    command = SaveEditsCommand(...)
    result = handler.handle(command)
    
    # Verify job was updated in repository
    job = job_repository.find_by_id(job_id)
    assert job.pages[0].fields[0].value == "updated value"
```

### E2E Tests (Slowest, Critical Paths)

Test full user workflows:

```typescript
test('user can edit field and save', async () => {
  render(<WorkspacePage />)
  
  await user.click(screen.getByText('Edit'))
  await user.type(screen.getByLabelText('Field value'), 'new value')
  await user.click(screen.getByText('Save'))
  
  expect(await screen.findByText('Saved successfully')).toBeVisible()
})
```

---

## Common Pitfalls to Avoid

### 1. Big Bang Refactoring
❌ **Don't:** Refactor everything at once  
✅ **Do:** One module at a time, keep tests passing

### 2. Changing Functionality
❌ **Don't:** Fix bugs or add features during refactoring  
✅ **Do:** Pure structural changes only

### 3. Skipping Tests
❌ **Don't:** "I'll write tests later"  
✅ **Do:** Write tests before refactoring, keep them green

### 4. Premature Abstraction
❌ **Don't:** Create complex abstractions for hypothetical needs  
✅ **Do:** Extract patterns you see repeated 3+ times

### 5. Analysis Paralysis
❌ **Don't:** Spend weeks planning perfect architecture  
✅ **Do:** Start with quick wins, iterate

---

## Daily Workflow

1. **Morning (30 min)**
   - Review checklist
   - Pick 1-2 tasks for the day
   - Create branch: `git checkout -b refactor/task-name`

2. **Work (6 hours)**
   - Implement changes
   - Write tests
   - Keep tests passing
   - Commit frequently: `git commit -m "Extract ConfidenceCalculator"`

3. **Afternoon (1 hour)**
   - Review changes
   - Run full test suite
   - Update checklist
   - Push: `git push origin refactor/task-name`

4. **End of day (30 min)**
   - Demo progress (if working with team)
   - Document any blockers
   - Plan next day's tasks

---

## Getting Help

### When Stuck

1. **Check the detailed plan**: `REFACTORING_PLAN.md`
2. **Check the checklist**: `REFACTORING_CHECKLIST.md`
3. **Review architecture**: Look at similar patterns in the codebase
4. **Simplify**: Break the task into smaller pieces

### Red Flags

**Stop and ask for help if:**
- Tests are failing for > 30 minutes
- You're changing > 500 lines at once
- You're creating > 5 new files for one feature
- You don't understand why code exists

---

## Success Checklist

After completing refactoring, you should be able to:

- [ ] Find all code related to a feature in one place
- [ ] Add a new field type without touching 10+ files
- [ ] Test business logic without starting the server
- [ ] Understand what each module does from its name
- [ ] Onboard a new developer in < 1 hour

---

## Next Steps

1. **Read this guide** ✓
2. **Do the 3 quick wins** (2 hours)
3. **Review the detailed plan** (`REFACTORING_PLAN.md`)
4. **Start Week 1** from the checklist
5. **Commit early, commit often**

Good luck! The codebase will thank you. 🚀
