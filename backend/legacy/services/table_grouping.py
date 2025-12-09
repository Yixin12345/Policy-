from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Dict, List

from ...models.job import PageExtraction, TableCell, TableColumn, TableExtraction


def assign_table_groups(pages: List[PageExtraction]) -> Dict[str, List[TableExtraction]]:
  """Annotate tables that span multiple pages with shared group metadata."""
  groups: Dict[str, List[TableExtraction]] = {}
  processed: List[TableExtraction] = []

  for page in sorted(pages, key=lambda p: p.page_number):
    for table in page.tables:
      candidate = _find_continuation(processed, table)
      if candidate:
        _remove_duplicate_overlap(candidate, table)
        table.table_group_id = candidate.table_group_id
        table.continuation_of = candidate.table_group_id
        table.row_start_index = candidate.row_start_index + len(candidate.rows)
        if not _has_headers(table):
          table.columns = [_copy_column(column) for column in candidate.columns]
          table.inferred_headers = True
        else:
          table.inferred_headers = False
        groups.setdefault(table.table_group_id, []).append(table)
      else:
        group_id = uuid.uuid4().hex
        table.table_group_id = group_id
        table.continuation_of = None
        table.row_start_index = 0
        table.inferred_headers = False
        groups.setdefault(group_id, []).append(table)
      processed.append(table)

  return groups


def merge_table_segments(groups: Dict[str, List[TableExtraction]]) -> Dict[str, TableExtraction]:
  """Collapse table segments by group into logical tables with deduplicated rows."""
  merged: Dict[str, TableExtraction] = {}

  for group_id, segments in groups.items():
    ordered = sorted(segments, key=lambda tbl: (tbl.page, tbl.row_start_index))
    if not ordered:
      continue

    first = ordered[0]
    merged_rows: List[List[TableCell]] = []
    merged_columns = [_copy_column(column) for column in first.columns]
    seen_signature = None

    for segment in ordered:
      for row in segment.rows:
        signature = _row_signature(row)
        if seen_signature and signature == seen_signature:
          continue
        merged_rows.append([_copy_cell(cell) for cell in row])
        seen_signature = signature

    merged_table = TableExtraction(
      id=f"{group_id}-merged",
      page=first.page,
      caption=first.caption,
      confidence=first.confidence,
      columns=merged_columns,
      rows=merged_rows,
      bbox=first.bbox,
      normalized=first.normalized,
      table_group_id=group_id,
      continuation_of=None,
      inferred_headers=any(segment.inferred_headers for segment in ordered),
      row_start_index=0,
    )
    merged[group_id] = merged_table

  return merged


def _find_continuation(processed: List[TableExtraction], current: TableExtraction) -> TableExtraction | None:
  for candidate in reversed(processed):
    if current.page <= candidate.page:
      continue
    if current.page - candidate.page > 1:
      break
    if _is_potential_continuation(candidate, current):
      return candidate
  return None


def _is_potential_continuation(previous: TableExtraction, current: TableExtraction) -> bool:
  if current.page <= previous.page:
    return False
  if current.page - previous.page > 1:
    return False

  score = 0

  if current.page == previous.page + 1:
    score += 2

  width_ratio = _width_ratio(previous, current)
  if width_ratio is not None and 0.65 <= width_ratio <= 1.35:
    score += 1

  header_similarity = _header_similarity(previous, current)
  if header_similarity >= 0.6:
    score += 2
  elif not _has_headers(current):
    score += 1

  if previous.caption and current.caption:
    if previous.caption.strip().lower() == current.caption.strip().lower():
      score += 1

  prev_cols = len(previous.columns)
  curr_cols = len(current.columns)
  if prev_cols and curr_cols and abs(prev_cols - curr_cols) <= 1:
    score += 1
  elif prev_cols and curr_cols == 0:
    score += 1

  return score >= 3


def _has_headers(table: TableExtraction) -> bool:
  return any((column.header or "").strip() for column in table.columns)


def _header_similarity(previous: TableExtraction, current: TableExtraction) -> float:
  prev_headers = {(column.header or "").strip().lower() for column in previous.columns if (column.header or "").strip()}
  if not prev_headers:
    return 0.0
  curr_headers = {(column.header or "").strip().lower() for column in current.columns if (column.header or "").strip()}
  if not curr_headers:
    return 0.0
  matches = len(prev_headers & curr_headers)
  return matches / max(len(prev_headers), 1)


def _width_ratio(previous: TableExtraction, current: TableExtraction) -> float | None:
  if not previous.bbox or not current.bbox:
    return None
  if previous.bbox.width == 0:
    return None
  return current.bbox.width / previous.bbox.width


def _remove_duplicate_overlap(previous: TableExtraction, current: TableExtraction) -> None:
  if not previous.rows or not current.rows:
    return
  last_prev = _row_signature(previous.rows[-1])
  first_curr = _row_signature(current.rows[0])
  if last_prev == first_curr:
    current.rows.pop(0)


def _row_signature(row: List[TableCell]) -> tuple[str, ...]:
  return tuple((cell.value or "").strip() for cell in row)


def _copy_column(column: TableColumn) -> TableColumn:
  return replace(column)


def _copy_cell(cell: TableCell) -> TableCell:
  return replace(cell)
