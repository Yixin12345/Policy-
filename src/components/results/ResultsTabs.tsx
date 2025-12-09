import clsx from 'clsx'
import type { ResultsTab } from '../../state/viewerStore'

type ResultsTabsProps = {
  activeTab: ResultsTab
  onSelect: (tab: ResultsTab) => void
  disabledTabs?: Partial<Record<ResultsTab, boolean>>
}

const tabs: Array<{ id: ResultsTab; label: string }> = [
  { id: 'fields', label: 'Fields' },
  { id: 'tables', label: 'Tables' },
  { id: 'canonical', label: 'Canonical' },
  { id: 'raw', label: 'Raw' }
]

const ResultsTabs = ({ activeTab, onSelect, disabledTabs }: ResultsTabsProps) => {
  return (
    <div className="flex items-center gap-1 rounded-md bg-slate-100 p-1">
      {tabs.map((tab) => {
        const isDisabled = Boolean(disabledTabs?.[tab.id])
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => {
              if (!isDisabled) {
                onSelect(tab.id)
              }
            }}
            className={clsx(
              'flex-1 rounded-md px-3 py-2 text-sm font-medium transition',
              isDisabled
                ? 'cursor-not-allowed text-slate-300'
                : activeTab === tab.id
                  ? 'bg-white text-brand-600 shadow-sm'
                  : 'text-slate-600 hover:text-brand-600'
            )}
            disabled={isDisabled}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

export default ResultsTabs
