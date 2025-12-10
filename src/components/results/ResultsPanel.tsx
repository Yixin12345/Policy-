import { useEffect, useMemo, useState } from 'react'
import FieldsTab from './FieldsTab'
import RawTab from './RawTab'
import ResultsTabs from './ResultsTabs'
import TablesTab from './TablesTab'
import CanonicalTab from './CanonicalTab'
import { useViewerStore } from '../../state/viewerStore'
import { useSavePageEdits } from '../../hooks/useHistoryData'
import type {
  CanonicalBundle,
  CanonicalSelectPayload,
  FieldExtraction,
  FieldUpdatePayload,
  PageClassification,
  PageExtraction,
  TableCellUpdatePayload,
  TableExtraction,
} from '../../types/extraction'
import { canonicalTouchesPage } from '../../utils/canonical'

type ResultsPanelProps = {
  pageFields?: FieldExtraction[]
  tables?: TableExtraction[]
  page?: PageExtraction
  isLoading: boolean
  canonical?: CanonicalBundle | null
  canonicalDocumentType?: string | null
  canonicalDocumentTypes?: string[]
  canonicalDocumentCategories?: string[]
  isCanonicalLoading?: boolean
  pageClassifications?: PageClassification[]
  onCanonicalSelect?: (payload: CanonicalSelectPayload | null) => void
}

const ResultsPanel = ({
  pageFields,
  tables,
  page,
  isLoading,
  canonical,
  canonicalDocumentType,
  canonicalDocumentTypes,
  canonicalDocumentCategories,
  isCanonicalLoading = false,
  pageClassifications,
  onCanonicalSelect,
}: ResultsPanelProps) => {
  const activeTab = useViewerStore((state) => state.selectedTab)
  const setActiveTab = useViewerStore((state) => state.setSelectedTab)
  const jobId = useViewerStore((state) => state.jobId)

  const [isEditing, setIsEditing] = useState(false)
  const [fieldDrafts, setFieldDrafts] = useState<Record<string, string>>({})
  const [tableDrafts, setTableDrafts] = useState<Record<string, string>>({})

  const saveMutation = useSavePageEdits(jobId)

  const pageNumber = page?.pageNumber ?? null
  const isEditableTab = activeTab === 'fields' || activeTab === 'tables'

  const canonicalTabDisabled = useMemo(() => {
    if (isCanonicalLoading) {
      return true
    }
    return !canonical
  }, [canonical, isCanonicalLoading])

  useEffect(() => {
    setFieldDrafts({})
    setTableDrafts({})
    setIsEditing(false)
  }, [pageNumber, jobId])

  useEffect(() => {
    if (!isEditableTab) {
      setIsEditing(false)
    }
  }, [isEditableTab])

  useEffect(() => {
    if (activeTab !== 'canonical') {
      onCanonicalSelect?.(null)
    }
  }, [activeTab, onCanonicalSelect])

  useEffect(() => {
    if (activeTab === 'canonical' && canonicalTabDisabled) {
      setActiveTab('fields')
      onCanonicalSelect?.(null)
    }
  }, [activeTab, canonicalTabDisabled, onCanonicalSelect, setActiveTab])

  const getFieldKey = (field: FieldExtraction, index: number) => field.id ?? `${field.name || 'field'}-${index}`
  const getCellKey = (table: TableExtraction, rowIndex: number, cellIndex: number) => `${table.id}-${rowIndex}-${cellIndex}`

  const handleFieldChange = (field: FieldExtraction, index: number, value: string) => {
    const key = getFieldKey(field, index)
    setFieldDrafts((previous) => {
      if (value === field.value) {
        const rest = { ...previous }
        delete rest[key]
        return rest
      }
      return { ...previous, [key]: value }
    })
  }

  const handleCellChange = (table: TableExtraction, rowIndex: number, cellIndex: number, value: string) => {
    const key = getCellKey(table, rowIndex, cellIndex)
    const originalValue = table.rows[rowIndex][cellIndex].value
    setTableDrafts((previous) => {
      if (value === originalValue) {
        const rest = { ...previous }
        delete rest[key]
        return rest
      }
      return { ...previous, [key]: value }
    })
  }

  const fieldPayloads = useMemo<FieldUpdatePayload[]>(() => {
    if (!pageFields) return []
    const payload: FieldUpdatePayload[] = []
    pageFields.forEach((field, index) => {
      const key = getFieldKey(field, index)
      if (!(key in fieldDrafts)) {
        return
      }
      const draftValue = fieldDrafts[key]
      if (draftValue === field.value) {
        return
      }
      payload.push({
        fieldId: field.id,
        name: field.name,
        value: draftValue,
      })
    })
    return payload
  }, [fieldDrafts, pageFields])

  const tablePayloads = useMemo<TableCellUpdatePayload[]>(() => {
    if (!tables) return []
    const payload: TableCellUpdatePayload[] = []
    tables.forEach((table) => {
      table.rows.forEach((row, rowIndex) => {
        row.forEach((cell, cellIndex) => {
          const key = getCellKey(table, rowIndex, cellIndex)
          if (!(key in tableDrafts)) {
            return
          }
          const draftValue = tableDrafts[key]
          if (draftValue === cell.value) {
            return
          }
          payload.push({
            tableId: table.id,
            row: rowIndex,
            column: cellIndex,
            value: draftValue,
          })
        })
      })
    })
    return payload
  }, [tableDrafts, tables])

  const hasChanges = fieldPayloads.length > 0 || tablePayloads.length > 0

  const handleSave = () => {
    if (!jobId || !pageNumber) {
      window.alert('Select a job before saving edits.')
      return
    }
    if (!hasChanges) {
      window.alert('No edits to save yet.')
      return
    }
    saveMutation.mutate(
      {
        page: pageNumber,
        fields: fieldPayloads,
        tableCells: tablePayloads,
      },
      {
        onSuccess: () => {
          setIsEditing(false)
          setFieldDrafts({})
          setTableDrafts({})
        },
        onError: (error) => {
          window.alert(error.message)
        },
      },
    )
  }

  const handleCancel = () => {
    setIsEditing(false)
    setFieldDrafts({})
    setTableDrafts({})
  }

  const isEditDisabled = !isEditableTab || !jobId || !pageNumber || isLoading

  const getFieldValue = (field: FieldExtraction, index: number) => {
    const key = getFieldKey(field, index)
    return fieldDrafts[key] ?? field.value
  }

  const getCellValue = (table: TableExtraction, rowIndex: number, cellIndex: number) => {
    const key = getCellKey(table, rowIndex, cellIndex)
    return tableDrafts[key] ?? table.rows[rowIndex][cellIndex].value
  }

  const derivedDocumentType = useMemo(() => {
    if (canonicalDocumentTypes && canonicalDocumentTypes.length > 0) {
      return canonicalDocumentTypes[0]
    }
    if (canonicalDocumentCategories && canonicalDocumentCategories.length > 0) {
      return canonicalDocumentCategories[0]
    }
    return canonicalDocumentType ?? null
  }, [canonicalDocumentCategories, canonicalDocumentType, canonicalDocumentTypes])

  return (
    <section className="flex h-full w-full flex-col rounded-xl border border-slate-200 bg-white shadow-sm xl:min-w-[36rem] 2xl:min-w-[44rem]">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">Results</h2>
          <p className="text-xs text-slate-500">
            Review extracted content and export when ready.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isEditableTab ? (
            isEditing ? (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleCancel}
                  className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-300 hover:text-slate-800 disabled:cursor-not-allowed disabled:text-slate-300"
                  disabled={saveMutation.isPending}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSave}
                  className="rounded-md border border-brand-500 bg-brand-500 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:border-brand-600 hover:bg-brand-600 disabled:cursor-not-allowed disabled:border-brand-200 disabled:bg-brand-200"
                  disabled={saveMutation.isPending || !hasChanges}
                >
                  {saveMutation.isPending ? 'Saving…' : 'Save edits'}
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setIsEditing(true)}
                className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-brand-300 hover:text-brand-600 disabled:cursor-not-allowed disabled:text-slate-300"
                disabled={isEditDisabled}
              >
                Edit
              </button>
            )
          ) : null}
          <ResultsTabs
            activeTab={activeTab}
            onSelect={setActiveTab}
            disabledTabs={{ canonical: canonicalTabDisabled }}
          />
        </div>
      </div>
      <div className="flex-1 overflow-hidden p-4">
        {activeTab === 'fields' && (
          <FieldsTab
            pageFields={pageFields}
            isLoading={isLoading}
            isEditing={isEditing}
            getFieldValue={getFieldValue}
            onFieldChange={handleFieldChange}
          />
        )}
        {activeTab === 'tables' && (
          <TablesTab
            tables={tables}
            isLoading={isLoading}
            isEditing={isEditing}
            getCellValue={getCellValue}
            onCellChange={handleCellChange}
          />
        )}
        {activeTab === 'canonical' && (
          <CanonicalTab
            canonical={canonical}
            documentType={derivedDocumentType}
            documentTypes={canonicalDocumentTypes}
            documentCategories={canonicalDocumentCategories}
            isLoading={isCanonicalLoading}
            pageClassifications={pageClassifications}
            onSelectValue={onCanonicalSelect}
          />
        )}
        {activeTab === 'raw' && (
          <RawTab page={page} isLoading={isLoading} />
        )}
      </div>
    </section>
  )
}

export default ResultsPanel
