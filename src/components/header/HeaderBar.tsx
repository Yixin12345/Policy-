import UploadDropzone from '../common/UploadDropzone'
import StatusIndicator from '../common/StatusIndicator'
import type { JobStatus } from '../../types/extraction'

type HeaderBarProps = {
  onFileSelected: (file: File) => void
  isUploading: boolean
  status?: JobStatus
  statusOverrideLabel?: string
  statusOverrideColor?: string
  onGoToHistory?: () => void
  onExportJson?: () => void
  onExportExcel?: () => void
  isExporting?: boolean
  isExportingExcel?: boolean
}

const HeaderBar = ({
  onFileSelected,
  isUploading,
  status,
  statusOverrideLabel,
  statusOverrideColor,
  onGoToHistory,
  onExportJson,
  onExportExcel,
  isExporting = false,
  isExportingExcel = false
}: HeaderBarProps) => {
  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-3">
          <img
            src="/synechron-logo.png"
            alt="Synechron logo"
            className="h-8 w-auto"
          />
          <span className="text-lg font-semibold text-brand-600">Recon AI 2.0</span>
        </div>
        <StatusIndicator status={status} isLoading={isUploading} overrideLabel={statusOverrideLabel} overrideColor={statusOverrideColor} />
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onGoToHistory}
          className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:border-brand-300 hover:text-brand-600"
        >
          View History
        </button>
        <button
          type="button"
          disabled={!status || !onExportJson || isExporting}
          onClick={onExportJson}
          className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:border-brand-300 hover:text-brand-600 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-300"
        >
          {isExporting ? 'Exporting…' : 'Export JSON'}
        </button>
        <button
          type="button"
          disabled={!status || !onExportExcel || isExportingExcel}
          onClick={onExportExcel}
          className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:border-brand-300 hover:text-brand-600 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-300"
        >
          {isExportingExcel ? 'Exporting…' : 'Export Excel'}
        </button>
        <UploadDropzone onFileSelected={onFileSelected} isUploading={isUploading} />
      </div>
    </header>
  )
}

export default HeaderBar
