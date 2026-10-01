import { useRef, useState } from 'react'
import type { DragEvent, KeyboardEvent } from 'react'
import { fmtBytes } from '../utils/format'

const ACCEPT = ['image/jpeg', 'image/png', 'image/webp']
const MAX_BYTES = 10 * 1024 * 1024

interface Props {
  file: File | null
  /** Preview URL: object URL of `file`, or a demo image URL when no file is set. */
  previewUrl: string | null
  onFile: (file: File | null) => void
  disabled?: boolean
}

export default function DropZone({ file, previewUrl, onFile, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const accept = (f: File | undefined) => {
    if (!f) return
    if (!ACCEPT.includes(f.type)) {
      setError('Unsupported file type. Use a JPG, PNG or WebP image.')
      return
    }
    if (f.size > MAX_BYTES) {
      setError(`Image is ${fmtBytes(f.size)}. The limit is 10 MB.`)
      return
    }
    setError(null)
    onFile(f)
  }

  const open = () => {
    if (!disabled) inputRef.current?.click()
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (!disabled) accept(e.dataTransfer.files?.[0])
  }

  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      open()
    }
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label="Upload an image: drag and drop, or press Enter to choose a file. JPG, PNG or WebP up to 10 MB."
        aria-disabled={disabled}
        onClick={open}
        onKeyDown={onKey}
        onDragOver={(e) => {
          e.preventDefault()
          if (!disabled) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`scan-host ${dragging ? 'scan-loop' : ''} flex min-h-44 cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed p-5 text-center transition-colors ${
          dragging ? 'border-accent bg-accent/10' : 'border-border bg-bg/60 hover:border-accent-soft'
        } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
      >
        {previewUrl ? (
          <div className="flex w-full flex-col items-center gap-4 sm:flex-row sm:text-left">
            <img
              src={previewUrl}
              alt="Selected image preview"
              className="max-h-40 w-auto max-w-full rounded-lg border border-border object-contain sm:max-w-56"
            />
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-sm text-text">{file ? file.name : 'Demo image'}</p>
              <p className="mt-1 text-xs text-muted">
                {file ? fmtBytes(file.size) : 'Loaded from the demo set'} · click or drop to replace
              </p>
            </div>
          </div>
        ) : (
          <>
            <svg viewBox="0 0 24 24" fill="none" className="size-8 text-accent" aria-hidden="true">
              <path
                d="M12 16V5m0 0-4 4m4-4 4 4M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3"
                stroke="currentColor"
                strokeWidth="1.600"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <p className="text-sm text-text">
              Drop a screenshot or image here, or <span className="text-accent underline underline-offset-2">browse</span>
            </p>
            <p className="text-xs text-muted">JPG, PNG or WebP · up to 10 MB</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT.join(',')}
          className="hidden"
          tabIndex={-1}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => {
            accept(e.target.files?.[0])
            e.target.value = ''
          }}
        />
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-risk-high">
          {error}
        </p>
      )}
    </div>
  )
}
