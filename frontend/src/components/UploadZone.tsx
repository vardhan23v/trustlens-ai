import { useRef, useState } from 'react'
import type { MediaType } from '../types/report'
import { fmtBytes } from '../utils/format'

interface Props {
  file: File | null
  /** Object URL of `file`, or a demo image URL when no file is set. */
  previewUrl: string | null
  onFile: (file: File | null) => void
  disabled?: boolean
}

const IMAGE_MB = 10
const MEDIA_MB = 18
const ACCEPT =
  'image/jpeg,image/png,image/webp,.mp4,.mov,.webm,.mp3,.wav,.m4a,.ogg,video/mp4,video/quicktime,video/webm,audio/mpeg,audio/wav,audio/mp4,audio/ogg'

/** Kind from the browser's type or the extension. The server re-checks the file's own bytes. */
export function mediaTypeOf(f: File): MediaType | null {
  if (/^image\/(jpeg|png|webp)$/.test(f.type) || /\.(jpe?g|png|webp)$/i.test(f.name)) return 'image'
  if (f.type.startsWith('video/') || /\.(mp4|mov|webm)$/i.test(f.name)) return 'video'
  if (f.type.startsWith('audio/') || /\.(mp3|wav|m4a|ogg)$/i.test(f.name)) return 'audio'
  return null
}

/** Same check for a chosen, dropped or pasted file. Returns an error message, or null when acceptable. */
export function validateFile(f: File): string | null {
  const kind = mediaTypeOf(f)
  if (!kind) return 'Unsupported file. Upload an image (JPG, PNG, WebP), a video (MP4, MOV, WebM) or audio (MP3, WAV, M4A, OGG).'
  const cap = kind === 'image' ? IMAGE_MB : MEDIA_MB
  if (f.size > cap * 1024 * 1024) return `This ${kind} is ${fmtBytes(f.size)}. The limit is ${cap} MB.`
  return null
}

const KINDS: { kind: MediaType; label: string; formats: string }[] = [
  { kind: 'image', label: 'Image', formats: `JPG, PNG, WebP · ${IMAGE_MB} MB` },
  { kind: 'video', label: 'Video', formats: `MP4, MOV, WebM · ${MEDIA_MB} MB` },
  { kind: 'audio', label: 'Audio', formats: `MP3, WAV, M4A, OGG · ${MEDIA_MB} MB` },
]

function KindIcon({ kind }: { kind: MediaType }) {
  const common = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, className: 'size-5', 'aria-hidden': true } as const
  if (kind === 'image')
    return (
      <svg {...common}>
        <rect x="3.5" y="5" width="17" height="14" rx="2" />
        <path d="M4 16l4.5-4.5 4 4 3-3 4.5 4.5" strokeLinejoin="round" />
        <circle cx="9" cy="9.5" r="1.3" />
      </svg>
    )
  if (kind === 'video')
    return (
      <svg {...common}>
        <rect x="3" y="6" width="13" height="12" rx="2" />
        <path d="M16 10.5l5-3v9l-5-3" strokeLinejoin="round" />
      </svg>
    )
  return (
    <svg {...common}>
      <path d="M5 10v4M9 6v12M13 9v6M17 4v16M21 10v4" strokeLinecap="round" />
    </svg>
  )
}

/** One upload area for all three media kinds, with an inline preview or player. */
export default function UploadZone({ file, previewUrl, onFile, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const accept = (f: File | undefined) => {
    if (!f) return
    const problem = validateFile(f)
    if (problem) {
      setError(problem)
      return
    }
    setError(null)
    onFile(f)
  }

  const open = () => {
    if (!disabled) inputRef.current?.click()
  }
  const kind = file ? mediaTypeOf(file) : previewUrl ? 'image' : null

  return (
    <div>
      <div
        id="upload-dropzone"
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label="Upload media file: drag and drop image, video, or audio, or press Enter to browse files."
        aria-disabled={disabled}
        onClick={open}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            open()
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
        className={`scan-host ${dragging ? 'scan-loop' : ''} flex min-h-48 cursor-pointer flex-col items-center justify-center gap-4 rounded-xl border border-dashed p-5 text-center transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
          dragging ? 'border-accent bg-accent/10' : 'border-border bg-bg/60 hover:border-accent-soft'
        } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
      >
        {previewUrl && kind ? (
          <div className="flex w-full flex-col items-center gap-4 sm:flex-row sm:text-left">
            {kind === 'image' ? (
              <img
                src={previewUrl}
                alt="Selected image preview"
                className="max-h-40 w-auto max-w-full rounded-lg border border-border object-contain sm:max-w-56"
              />
            ) : kind === 'video' ? (
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
              <p className="truncate font-mono text-sm text-text">{file ? file.name : 'Demo image'}</p>
              <p className="mt-1 text-xs text-muted">
                <span className="mr-2 rounded-full border border-accent-soft px-2 py-px text-[11px] font-medium uppercase tracking-wide text-accent">
                  {kind}
                </span>
                {file ? fmtBytes(file.size) : 'Loaded from the demo set'} · click or drop to replace
              </p>
            </div>
          </div>
        ) : (
          <>
            <p className="text-sm text-text">
              Drop a file here, or <span className="text-accent underline underline-offset-2">browse</span>
              <span className="mt-1 block text-xs text-muted">You can also paste a copied image (Ctrl / ⌘ + V) or drop a file anywhere on the page.</span>
            </p>
            <ul className="grid w-full max-w-xl gap-2 sm:grid-cols-3">
              {KINDS.map((k) => (
                <li key={k.kind} className="rounded-lg border border-border bg-surface-2/60 px-3 py-2.5 transition-[border-color,transform] duration-200 hover:-translate-y-0.5 hover:border-accent">
                  <p className="flex items-center justify-center gap-2 text-sm font-medium text-text">
                    <span className="text-accent">
                      <KindIcon kind={k.kind} />
                    </span>
                    {k.label}
                  </p>
                  <p className="mt-1 text-[11px] text-muted">{k.formats}</p>
                </li>
              ))}
            </ul>
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
    </div>
  )
}
