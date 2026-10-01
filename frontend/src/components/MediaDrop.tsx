import { useRef, useState } from 'react'
import { fmtBytes } from '../utils/format'

interface Props {
  file: File | null
  previewUrl: string | null
  onFile: (file: File | null) => void
  disabled?: boolean
}

const MAX_MB = 18
const ACCEPT = '.mp4,.mov,.webm,.mp3,.wav,.m4a,.ogg,video/mp4,video/quicktime,video/webm,audio/mpeg,audio/wav,audio/mp4,audio/ogg'
const EXT = /\.(mp4|mov|webm|mp3|wav|m4a|ogg)$/i

/** Upload area for the Video / Audio tab, with an inline player for the selected file. */
export default function MediaDrop({ file, previewUrl, onFile, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const accept = (f: File | undefined) => {
    if (!f) return
    if (!EXT.test(f.name) && !/^(video|audio)\//.test(f.type)) {
      setError('Unsupported file. Use MP4, MOV or WebM video, or MP3, WAV, M4A or OGG audio.')
      return
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File is larger than ${MAX_MB} MB. Trim the clip and try again.`)
      return
    }
    setError(null)
    onFile(f)
  }

  const isVideo = !!file && (file.type.startsWith('video/') || /\.(mp4|mov|webm)$/i.test(file.name))

  return (
    <div>
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label={`Upload a video or audio file: drag and drop, or press Enter to choose a file. Up to ${MAX_MB} MB.`}
        aria-disabled={disabled}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          if (!disabled) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (!disabled) accept(e.dataTransfer.files?.[0])
        }}
        className={`scan-host ${dragging ? 'scan-loop' : ''} flex min-h-44 cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed p-5 text-center transition-colors ${
          dragging ? 'border-accent bg-accent/10' : 'border-border bg-bg/60 hover:border-accent-soft'
        } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
      >
        {file && previewUrl ? (
          <div className="flex w-full flex-col items-center gap-4 sm:flex-row sm:text-left">
            {isVideo ? (
              <video
                src={previewUrl}
                controls
                onClick={(e) => e.stopPropagation()}
                className="max-h-48 w-full max-w-xs rounded-lg border border-border bg-black"
              />
            ) : (
              <audio src={previewUrl} controls onClick={(e) => e.stopPropagation()} className="w-full max-w-xs" />
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-sm text-text">{file.name}</p>
              <p className="mt-1 text-xs text-muted">{fmtBytes(file.size)} · click or drop to replace</p>
            </div>
          </div>
        ) : (
          <>
            <svg viewBox="0 0 24 24" fill="none" className="size-8 text-accent" aria-hidden="true">
              <rect x="3" y="6" width="13" height="12" rx="2" stroke="currentColor" strokeWidth="1.6" />
              <path d="M16 10.5l5-3v9l-5-3" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
            </svg>
            <p className="text-sm text-text">
              Drop a video or audio clip here, or <span className="text-accent underline underline-offset-2">browse</span>
            </p>
            <p className="text-xs text-muted">MP4, MOV, WebM · MP3, WAV, M4A, OGG · up to {MAX_MB} MB</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
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
      <p className="mt-2 text-xs text-muted">
        Gemini examines the picture, the sound and what is said. No specialist deepfake detector is run; the report says
        so.
      </p>
    </div>
  )
}
