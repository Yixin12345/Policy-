import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import clsx from 'clsx'

type UploadDropzoneProps = {
  onFileSelected: (file: File) => void
  isUploading?: boolean
}

const UploadDropzone = ({ onFileSelected, isUploading = false }: UploadDropzoneProps) => {
  const handleDrop = useCallback(
    (acceptedFiles: File[]) => {
      const [file] = acceptedFiles
      if (file) {
        onFileSelected(file)
      }
    },
    [onFileSelected]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    multiple: false,
    accept: {
      'application/pdf': ['.pdf'],
      'text/markdown': ['.md', '.mmd']
    },
    onDrop: handleDrop,
    disabled: isUploading
  })

  const label = (() => {
    if (isUploading) return 'Uploading…'
    if (isDragActive) return 'Drop PDF or Markdown to upload'
    return 'Upload PDF or Markdown'
  })()

  return (
    <div
      {...getRootProps({
        className: clsx(
          'inline-flex cursor-pointer items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-brand-400 hover:text-brand-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500',
          isUploading && 'cursor-not-allowed opacity-75'
        ),
        role: 'button',
        tabIndex: 0,
        'aria-disabled': isUploading
      })}
    >
      <input {...getInputProps()} />
      <span aria-live="polite">{label}</span>
    </div>
  )
}

export default UploadDropzone
