import ConfidenceBadge from '../common/ConfidenceBadge'
import type { TableExtraction } from '../../types/extraction'

type TablesTabProps = {
  tables?: TableExtraction[]
  isLoading: boolean
  isEditing?: boolean
  getCellValue?: (table: TableExtraction, rowIndex: number, cellIndex: number) => string
  onCellChange?: (
    table: TableExtraction,
    rowIndex: number,
    cellIndex: number,
    value: string
  ) => void
}

const TablesTab = ({ tables, isLoading, isEditing = false, getCellValue, onCellChange }: TablesTabProps) => {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 2 }).map((_, index) => (
          <div
            key={index}
            className="h-32 animate-pulse rounded-lg bg-slate-100"
          />
        ))}
      </div>
    )
  }

  if (!tables || tables.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
        No tables detected on this page.
      </div>
    )
  }

  return (
    <div className="space-y-4 overflow-y-auto">
      {tables.map((table) => (
        <div
          key={table.id}
          className="rounded-lg border border-slate-200 bg-white shadow-sm"
        >
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-slate-700">
                {table.caption ?? 'Detected Table'}
              </p>
              <p className="text-xs text-slate-500">Page {table.page}</p>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-wide text-slate-400">
                {table.tableGroupId ? (
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-500">
                    Table Group {table.tableGroupId.slice(0, 6)}
                  </span>
                ) : null}
                {table.continuationOf ? (
                  <span className="rounded-full bg-amber-50 px-2 py-0.5 font-semibold text-amber-700">
                    Continuation
                  </span>
                ) : null}
                {typeof table.rowStartIndex === 'number' && table.rowStartIndex > 0 ? (
                  <span className="rounded-full bg-slate-50 px-2 py-0.5 font-semibold text-slate-500">
                    Rows {table.rowStartIndex + 1}+
                  </span>
                ) : null}
                {table.inferredHeaders ? (
                  <span className="rounded-full bg-sky-50 px-2 py-0.5 font-semibold text-sky-600">
                    Header Inferred
                  </span>
                ) : null}
              </div>
            </div>
            {table.confidence && <ConfidenceBadge score={table.confidence} />}
          </div>
          <div className="max-h-[420px] overflow-x-auto overflow-y-auto">
            <table className="min-w-[40rem] border-separate border-spacing-0 text-sm">
              <thead className="sticky top-0 bg-slate-100">
                <tr>
                  {table.columns.map((column) => (
                    <th
                      key={column.key}
                      className="border-b border-slate-200 px-3 py-2 text-left font-semibold text-slate-600"
                    >
                      <div className="flex items-center gap-2">
                        <span>{column.header}</span>
                        {column.confidence && (
                          <span className="text-xs text-slate-400">
                            {Math.round(column.confidence * 100)}%
                          </span>
                        )}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row, rowIndex) => (
                  <tr key={rowIndex} className="odd:bg-white even:bg-slate-50">
                    {row.map((cell, cellIndex) => {
                      const cellValue = getCellValue ? getCellValue(table, rowIndex, cellIndex) : cell.value
                      const rowsForTextarea = Math.min(4, Math.max(1, Math.ceil((cellValue.length || 1) / 48)))
                      return (
                        <td
                          key={`${table.id}-${rowIndex}-${cellIndex}`}
                          className="border-b border-slate-100 px-3 py-2 text-slate-700"
                        >
                          {isEditing ? (
                            <textarea
                              value={cellValue}
                              onChange={(event) => onCellChange?.(table, rowIndex, cellIndex, event.target.value)}
                              rows={rowsForTextarea}
                              className="w-full rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-700 shadow-sm focus:border-brand-400 focus:outline-none focus:ring focus:ring-brand-200"
                            />
                          ) : (
                            <div className="flex items-start justify-between gap-2">
                              <span>{cell.value}</span>
                              {cell.confidence && (
                                <span className="text-xs text-slate-400">
                                  {Math.round(cell.confidence * 100)}%
                                </span>
                              )}
                            </div>
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  )
}

export default TablesTab
