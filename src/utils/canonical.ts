import type {
  CanonicalBundle,
  CanonicalValue,
  CanonicalValueSource,
  PageExtraction,
} from '../types/extraction'

export const isCanonicalValue = (value: unknown): value is CanonicalValue =>
  Boolean(value && typeof value === 'object' && 'value' in (value as Record<string, unknown>))

export const toCanonicalValue = (value: unknown): CanonicalValue => {
  if (value === null || value === undefined) {
    return { value: null }
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return { value }
  }
  return { value: JSON.stringify(value) }
}

export const collectCanonicalFields = (
  input: Record<string, unknown>,
  prefix = '',
  dropKeys: Set<string> = new Set(),
): Record<string, CanonicalValue | null | undefined> => {
  const result: Record<string, CanonicalValue | null | undefined> = {}
  Object.entries(input).forEach(([key, rawValue]) => {
    const shouldDrop = dropKeys.has(key)
    const label = shouldDrop ? prefix : prefix ? `${prefix}.${key}` : key
    if (isCanonicalValue(rawValue) || rawValue === null || rawValue === undefined) {
      if (label) {
        result[label] = rawValue as CanonicalValue | null | undefined
      }
    } else if (rawValue && typeof rawValue === 'object' && !Array.isArray(rawValue)) {
      Object.assign(
        result,
        collectCanonicalFields(
          rawValue as Record<string, unknown>,
          label,
          dropKeys,
        ),
      )
    } else {
      if (label) {
        result[label] = toCanonicalValue(rawValue)
      }
    }
  })
  return result
}

const containsPageRecursive = (node: unknown, pageNumber: number): boolean => {
  if (!node) {
    return false
  }
  if (Array.isArray(node)) {
    return node.some((entry) => containsPageRecursive(entry, pageNumber))
  }
  if (typeof node === 'object') {
    if (isCanonicalValue(node)) {
      const sources = (node as CanonicalValue).sources ?? []
      return sources.some((source) => source.page === pageNumber)
    }
    return Object.values(node as Record<string, unknown>).some((value) => containsPageRecursive(value, pageNumber))
  }
  return false
}

export const canonicalHasPage = (canonical: CanonicalBundle | null | undefined, pageNumber: number | null | undefined): boolean => {
  if (!canonical || !pageNumber) {
    return false
  }
  return containsPageRecursive(canonical, pageNumber)
}

export const findPagesForSources = (sources: CanonicalValueSource[] | undefined | null): number[] => {
  if (!sources) {
    return []
  }
  const pages = new Set<number>()
  sources.forEach((source) => {
    if (typeof source.page === 'number') {
      pages.add(source.page)
    }
  })
  return Array.from(pages).sort((a, b) => a - b)
}

const canonicalValueTouchesPage = (
  value: CanonicalValue | null | undefined,
  page: PageExtraction,
  fieldIds: Set<string>,
  tableIds: Set<string>,
): boolean => {
  if (!value?.sources) {
    return false
  }
  return value.sources.some((source) => {
    if (typeof source.page === 'number' && source.page === page.pageNumber) {
      return true
    }
    if (source.fieldId && fieldIds.has(source.fieldId)) {
      return true
    }
    if (source.tableId && tableIds.has(source.tableId)) {
      return true
    }
    return false
  })
}

export const canonicalTouchesPage = (canonical: CanonicalBundle | null | undefined, page: PageExtraction | undefined): boolean => {
  if (!canonical || !page) {
    return false
  }

  const fieldIds = new Set(page.fields.map((field) => field.id).filter(Boolean))
  const tableIds = new Set(page.tables.map((table) => table.id).filter(Boolean))
  let matched = false

  const walk = (node: unknown) => {
    if (matched || !node) {
      return
    }
    if (Array.isArray(node)) {
      node.forEach(walk)
      return
    }
    if (typeof node === 'object') {
      if (isCanonicalValue(node)) {
        matched = canonicalValueTouchesPage(node, page, fieldIds, tableIds)
        return
      }
      Object.values(node as Record<string, unknown>).forEach(walk)
    }
  }

  walk(canonical)
  return matched
}
