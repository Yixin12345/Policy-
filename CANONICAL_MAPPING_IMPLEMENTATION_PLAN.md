# Canonical Mapping Implementation Plan

Generated: 2025-11-20
Status: Phase 1 in progress (schema + mapper scaffold complete)
Scope: Introduce explicit canonical schema (56 fields from `RequiredFields.md`) with structured identity blocks, flattened absence details, and full UB04 coverage — replacing implicit prompt-driven mapping. No legacy code usage.

---
## 1. Goals
- Establish a single authoritative backend schema for 56 required fields.
- Support repeated identity blocks via arrays (extensible, schema‐driven).
- Preserve separate canonical keys for `totalDue` and `balanceDue`; merge their display label in UI.
- Flatten CMR absence details for simpler diffing & editing.
- Expand UB04 coverage beyond provider name/address to full field set (Boxes 1–10, 38, 42–47, 50, 53, 55 + duplicates).
- Provide deterministic pre-normalization before LLM mapping, reducing hallucination risk.
- Generate dynamic LLM prompt from schema (no hard-coded long string constants).
- Align backend & frontend representations; enforce ordering & grouping.
- Deliver robust test coverage (schema integrity, mapping correctness, UI rendering).

## 2. Non-Goals
- Changing existing extraction or vision OCR model behavior.
- Rewriting table extraction logic beyond adding canonical line item mapping.
- Introducing persistence schema migrations (all canonical mapping is computed, not stored long-term yet).
- Implementing advanced reconciliation across conflicting duplicate blocks (basic detection only in this phase).

## 3. Schema Design
### 3.1 Field Groups & Ordering
1. General Invoice (fields 1–18)
2. Continued Monthly Residence (CMR) Form (fields 21–34)
3. UB04 Form (fields 35–56)

**Ordering rule:** Canonical outputs **must** surface fields in the exact order listed above for each document type. This order is authoritative for both backend payload construction and frontend rendering, ensuring parity with `RequiredFields.md`.

### 3.2 Canonical Field Labels
- **Exact label fidelity:** Canonical schema must reuse field names verbatim (including capitalization, punctuation, and slashes) from `RequiredFields.md`. Examples: `Policy number`, `Invoice date / statement date`, `Total due / balance due`, `Select the level of care`, `Line items (Boxes 42–47)`, `Type of bill (Box 4)`.
- Persist both an internal stable identifier (e.g., enum value `POLICY_NUMBER`) **and** the exact display label string, but any serialized output consumed by the UI will include the human-readable label exactly as listed.
- Combined labels remain combined (`Total due / balance due`), while internal representation may still break into `totalDue` and `balanceDue` values for logic. Frontend merges to the combined label when rendering.
- CMR absence details flatten into individually labeled fields matching spec: `Absence departure date`, `Absence return date`, `Absence reason`, `Absence admission date`, `Absence discharge date` (exact strings added to schema list).
- UB04 line items array: maintain parent label `Line items (Boxes 42–47)` with structured entries containing sub-fields (revenue code, description, etc.) while preserving overall line item label for ordering.

### 3.3 Identity Blocks (Array Strategy)
`identityBlocks: IdentityBlock[]`
IdentityBlock model:
```
IdentityBlock {
  blockType: enum('policyHolderIdentity','providerIdentity','patientIdentity'),
  sequence: int (1-based appearance order),
  policyNumber: str | null,
  policyholderName: str | null,
  policyholderAddress: str | null,
  providerName: str | null,
  providerAddress: str | null,
  patientName: str | null,          // UB04 patient identity
  patientAddress: str | null,       // UB04 patient address
  birthDate: str | null,            // For patient blocks where available
  presentFields: str[],             // canonical field identifiers present in this block
  source: { page: int, fieldIds: str[] }
}
```
Justification: Avoid suffix proliferation (`policyNumber2`), support arbitrary future repetition, simpler iteration & diff.

### 3.4 Canonical Bundle Structure
Top-level JSON structure returned by mapper:
```
CanonicalBundle {
  schemaVersion: '1.0.0',
  generatedAt: ISO8601,
  documentCategories: string[],     // e.g. ['INVOICE','CMR','UB04'] present
  invoice: { ... },                 // object with atomic invoice fields + lineItems[]
  cmr: { ... },                     // atomic fields + absence details flattened
  ub04: { ... },                    // includes lineItems, payerNames[], etc.
  identityBlocks: IdentityBlock[],
  reasoningNotes: string[],         // optional reasoning from LLM for ambiguous mappings
  sourceMap: { canonicalKey: SourceAttribution }
}

SourceAttribution {
  page: int,
  fieldIds?: string[],
  tableId?: string,
  column?: int,
  confidenceAggregate?: number
}
```

### 3.5 Field Presence Rules
- If category applies but field absent: value = null (explicit null, not omitted).
- If category doesn't apply (e.g. UB04 fields in pure invoice doc): omit category object entirely OR include empty object with `categoryPresent: false` flag (choose former for lean JSON; test accordingly).

## 4. Backend Implementation Plan
### 4.1 Files Added / Remaining
- ✅ `backend/domain/value_objects/canonical_field.py` (Enum + metadata constants storing exact display label and stable identifier, plus group ordering index reflecting `RequiredFields.md`).
- ✅ `backend/domain/value_objects/identity_block.py` (dataclass model).
- ✅ `backend/domain/services/canonical_mapper.py` (core service enforcing ordered output, identity aggregation).
- ✅ `backend/infrastructure/mapping/prompt_builder.py` (schema-driven prompt generation).
- ✅ `backend/infrastructure/mapping/azure_mapping_client.py` (LLM call integrated with dynamic prompt + deterministic merge utilities).
- [ ] `backend/application/queries/get_canonical_mapping.py` (Query handler to expose bundle).

### 4.2 Pre-Normalization Flow
1. ✅ Gather raw extracted fields & tables per page (existing domain entities).
2. ✅ Apply name normalization dictionary (snake_case/raw label → canonical key) via mapper alias lookup.
3. ✅ Consolidate line items: detect table structures with revenue or procedure codes; transform to canonical `Line items (Boxes 42–47)` array entries while preserving sub-field detail.
4. ✅ Build identity blocks by scanning pages for contiguous field clusters; mapper now accumulates duplicate block fields per page.
5. ✅ Prepare deterministic JSON partial baseline (mapper now flattens CMR absence details and persists `sourceMap`; remaining deterministic merge rules handled during prompt builder work).
6. ✅ Invoke LLM with schema-driven prompt instructing canonical fill + ordering (requires prompt builder & client wiring).
7. ✅ Merge LLM result with deterministic partial (LLM cannot override high-confidence deterministic fields unless conflict flagged) while re-sorting final payload.

### 4.3 Prompt Design Principles
- Enumerate groups & required keys programmatically using the exact label strings pulled from `canonical_field.py`.
- Include each field's descriptive copy (sourced from `RequiredFields.md`) so the LLM understands semantic intent and document context when searching for evidence.
- Instruct array output for `identityBlocks` with required object keys.
- Explicit formatting section (strict JSON, no markdown, no comments).
- State schema version & require `schemaVersion` echo.
- Provide examples (one invoice-only, one mixed invoice + UB04) generated from schema builder (small, curated) that demonstrate correct ordering and label usage.
- Ban hallucinated fields (explicit instruction: "If not defined in schema, output null or omit as per rules; never invent keys or alter label casing.").
- Convey disjoint mapping rules: invoice fields must only be satisfied by invoice pages, CMR fields by CMR pages, and UB04 fields by UB04 pages; the LLM should ignore similarly labelled fields outside the active document type.
- Surface page-level document type hints (from classifier or user input) in the prompt so the LLM can filter where to look for each group.

### 4.4 Error Handling
- Validate LLM JSON parse; on failure fall back to deterministic partial with `llmCompletionStatus: 'FAILED_PARSE'`.
- Field-level validation errors aggregated into `reasoningNotes` if LLM returns inconsistent types (e.g., non-numeric for numeric field expected).
- Confidence override attempts flagged.

### 4.5 Performance Considerations
- Cache static prompt prefix (schema description) in memory.
- Only send page-level raw snippets for fields not confidently mapped (size reduction).
- Introduce `CANONICAL_SCHEMA_VERSION` env var to permit controlled future evolution.

## 5. Frontend Implementation Plan
### 5.1 Files to Add / Modify
- `src/features/workspace/types/canonicalSchema.ts` (Type definitions & ordered arrays of keys)
- `src/features/workspace/components/CanonicalTab.tsx` (Refactor to use groups, identity blocks array)
- `src/features/workspace/utils/formatCanonical.ts` (Formatting helpers: merge label for Total Due / Balance Due)
- `src/features/workspace/hooks/useCanonicalData.ts` (Query new endpoint `/api/v1/jobs/{id}/canonical`)

### 5.2 Rendering Rules
- Group sections in prescribed order: Invoice → CMR → UB04 → Identity Blocks, mirroring the sequence in `RequiredFields.md`.
- Render each field label exactly as provided in the spec (case-sensitive, punctuation preserved). For internal canonical values mapped to multiple data points (e.g., total vs balance due), merge them under the combined label `Total due / balance due` while preserving both values in the tooltip/detail view.
- Identity Blocks: accordion list with badge of presentFields count / possible, and nested field labels matching spec.
- Absence details inline under CMR using flattened fields labeled exactly as spec (e.g., `Absence departure date`).
- UB04 line items: table labeled `Line items (Boxes 42–47)` with dynamic columns for the sub-fields.

### 5.3 UX Enhancements (Optional Phase 2)
- Conflict highlighting (if reasoningNotes mention discrepancy).
- Toggle raw vs normalized value view.
- Inline field edit for null invoice fields (patch workflow prepared but not implemented in phase 1).

## 6. Testing Strategy
### 6.1 Backend Unit Tests
- `test_canonical_schema.py`: counts (56), group membership, identity block model validation.
- `test_canonical_mapper_pre_normalization.py`: raw → deterministic mapping (fixtures with edge cases).
- `test_canonical_mapper_identity_blocks.py`: multiple identity blocks detection.
- `test_prompt_builder.py`: prompt includes all group headings & example structure.
- `test_llm_merge_logic.py`: ensure deterministic fields not overridden incorrectly.

### 6.2 Backend Integration Tests
- Simulated extraction dataset → full canonical bundle (mock LLM returning partial JSON).
- Failure path (malformed LLM JSON) fallback behavior.

### 6.3 Frontend Tests
- `canonicalRender.test.tsx`: presence of all grouped keys, merged label behavior.
- Identity blocks dynamic rendering (2 blocks fixture).
- UB04 line items table columns.
- Snapshot test for a complete canonical bundle.

### 6.4 Non-Functional Tests
- Prompt size under threshold (assert length < configurable limit, e.g., 16k chars).
- Performance measurement: canonical mapping service execution time < 500 ms excluding LLM latency for average document.

## 7. Migration & Rollout
### 7.1 Phase 1 (Implementation)
- Add schema & mapper without exposing API.
### 7.2 Phase 2 (API Exposure)
- Introduce new endpoint `/api/v1/jobs/{jobId}/canonical`.
### 7.3 Phase 3 (UI Consumption)
- Update `CanonicalTab.tsx` to consume new endpoint.
### 7.4 Phase 4 (Deprecation)
- Remove any residual references to previous ad-hoc canonical structure (none if already refactored); confirm absence of legacy mapping service imports.

## 8. Timeline (Approx)
| Week | Deliverables | Status |
|------|--------------|--------|
| 1 | Backend schema, mapper core, prompt builder, unit tests | 95% — schema/mapper/tests + deterministic prompt + merge in place |
| 2 | LLM client integration, integration tests, API query handler | 20% — client scaffold exists; integration tests + query handler outstanding |
| 3 | Frontend types, CanonicalTab refactor, frontend tests | Pending |
| 4 | Optimization, conflict highlighting (optional), documentation, rollout | Pending |

## 9. Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM output inconsistency | Parse failures | Strict JSON instructions + robust fallback partial |
| Identity block misclassification | UX confusion | Sequence ordering + reasoningNotes for conflicts |
| UB04 line item extraction ambiguity | Data gaps | Confidence threshold + flag ambiguous items with null fields |
| Performance regression | Slower request | Cache prompt prefix & limit raw text payload sent to LLM |
| Schema drift over time | Maintenance overhead | Versioned schema (`schemaVersion`) + env-controlled upgrades |

## 10. Acceptance Criteria
- Backend returns JSON with all defined canonical keys (null or populated) for applicable categories.
- Identity blocks array present and accurately lists block types & fields.
- UB04 line items appear when UB04 classification exists; empty array otherwise if UB04 applies but no items.
- Canonical payload preserves the ordering defined in `RequiredFields.md` for each document group.
- Frontend displays grouped sections and merged total/balance label using exact field names from the specification.
- Tests: 100% pass; schema count test equals 56.
- No legacy module imports or usage.

## 11. Implementation Checklist (Derived from TODOs)
1. ✅ Create schema & identity block models.
2. ✅ Complete mapper pre-normalization (line items, absence flattening, sourceMap enrichment). Identity block detection ✅.
3. ✅ Build dynamic prompt builder & integrate with Azure client (replace static prompt, add deterministic partial merge).
4. ◻️ Add query handler & API route for canonical bundle (FastAPI dependency wiring).
5. ◻️ Frontend schema constants + hook & UI refactor (Canonical tab consumption).
6. ◻️ Expand backend unit + integration tests (prompt builder snapshots, line items, API contract).
7. ◻️ Add frontend component tests for canonical rendering.
8. ◻️ Update documentation (README canonical section, API docs).
9. ◻️ Execute review & finalize rollout.

## 12. Open Decisions (Track Prior to Coding)
- Numeric vs string formatting for amounts (currently assume raw text; may normalize to decimal strings). Decision: Keep as raw extracted text in phase 1; add normalization flag later.
- Confidence override threshold (e.g., >0.92 prevents LLM alteration). Decision: Threshold constant in schema module.
- UB04 duplicates handling (Boxes 1/2 repetition) — treat as additional identity block vs separate fields. Decision: Represent provider duplicates as additional `providerIdentity` block entries.

## 13. Future Extensions
- Field-level edit & re-validation workflow.
- Canonical diff across document revisions (version comparison).
- Anomaly detection (conflicting identity blocks) scoring.
- Automated normalization (currency formatting, date ISO parsing).

---
Prepared by: Refactored Architecture Track
Next Action: Implement canonical bundle API handler and surface schema in frontend workspace
