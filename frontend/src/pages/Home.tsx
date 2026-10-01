import { useCallback, useEffect, useRef, useState } from 'react'
import Backdrop from '../components/Backdrop'
import ErrorCard from '../components/ErrorCard'
import Header from '../components/Header'
import Hero from '../components/Hero'
import InputPanel from '../components/InputPanel'
import ReportView from '../components/ReportView'
import StageProgress from '../components/StageProgress'
import { mediaTypeOf } from '../components/UploadZone'
import { analyze, getDemos, getHealth } from '../services/api'
import type { Demo, Health, MediaType, Mode, TrustReport } from '../types/report'
import { useRevealAll } from '../hooks/useReveal'
import { prefersReducedMotion } from '../utils/format'

type Phase = 'idle' | 'analyzing' | 'result' | 'error'

interface RunRequest {
  mode: Mode
  file?: File | null
  text?: string
  demoId?: string | null
  mediaType: MediaType
  /** Image shown as "original" next to the compression map (image input only). */
  imageUrl?: string | null
}

export default function Home() {
  // The user first chooses what they are verifying; the choice stays on screen.
  const [mode, setMode] = useState<Mode | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  // Text is an alternative to a file: entering one clears the other.
  const [text, setText] = useState('')
  // The demo currently loaded; cleared as soon as the user picks a file or changes mode.
  const [demoId, setDemoId] = useState<string | null>(null)

  const [demos, setDemos] = useState<Demo[]>([])
  const [health, setHealth] = useState<Health | null>(null)

  const [phase, setPhase] = useState<Phase>('idle')
  const [running, setRunning] = useState<{ mode: Mode; mediaType: MediaType } | null>(null)
  const [report, setReport] = useState<TrustReport | null>(null)
  const [reportImageUrl, setReportImageUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [announce, setAnnounce] = useState('')

  const runId = useRef(0)
  const objectUrls = useRef<string[]>([])
  const resultRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLDivElement>(null)
  useRevealAll()

  useEffect(() => {
    let alive = true
    getDemos()
      .then((d) => alive && setDemos(d))
      .catch(() => alive && setDemos([])) // backend down → no chips, no crash
    getHealth()
      .then((h) => alive && setHealth(h))
      .catch(() => undefined)
    const urls = objectUrls.current
    return () => {
      alive = false
      urls.forEach((u) => URL.revokeObjectURL(u))
    }
  }, [])

  const run = useCallback(async (req: RunRequest) => {
    const id = ++runId.current
    setPhase('analyzing')
    setRunning({ mode: req.mode, mediaType: req.mediaType })
    setError(null)
    setReport(null)
    setAnnounce('Analysis started')
    try {
      const result = await analyze(req)
      if (id !== runId.current) return
      setReport(result)
      setReportImageUrl(req.mediaType === 'image' ? (req.imageUrl ?? null) : null)
      setPhase('result')
      setAnnounce('Analysis complete')
      requestAnimationFrame(() =>
        resultRef.current?.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' }),
      )
    } catch (e) {
      if (id !== runId.current) return
      setError(e instanceof Error && e.message ? e.message : 'Something went wrong. Please try again.')
      setPhase('error')
    }
  }, [])

  const busy = phase === 'analyzing'

  const onFile = (f: File | null) => {
    setFile(f)
    setDemoId(null)
    if (f) setText('')
    if (f) {
      const url = URL.createObjectURL(f)
      objectUrls.current.push(url)
      setPreviewUrl(url)
    } else {
      setPreviewUrl(null)
    }
  }

  const onText = (value: string) => {
    setText(value)
    if (value && (file || demoId)) {
      setFile(null)
      setDemoId(null)
      setPreviewUrl(null)
    }
  }

  const onModeChange = (m: Mode | null) => {
    setMode(m)
    if (demoId) {
      setDemoId(null)
      setPreviewUrl(null)
    }
  }

  const onPickDemo = (d: Demo) => {
    if (busy) return
    setMode(d.mode)
    setDemoId(d.id)
    setFile(null)
    setText('')
    setPreviewUrl(d.image_url)
    // Auto-run: one click shows the full report.
    void run({ mode: d.mode, demoId: d.id, mediaType: 'image', imageUrl: d.image_url })
  }

  const hasText = text.trim().length > 0
  const canSubmit = !!mode && (!!file || !!demoId || hasText)

  const onSubmit = () => {
    if (busy || !mode || !canSubmit) return
    if (!file && !demoId) {
      void run({ mode, text, mediaType: 'text' })
      return
    }
    const mediaType = file ? (mediaTypeOf(file) ?? 'image') : 'image'
    void run({ mode, file, demoId, mediaType, imageUrl: previewUrl })
  }

  return (
    <div className="mx-auto min-h-screen max-w-6xl overflow-x-clip px-4 pb-16">
      <Backdrop />
      <Header />
      <Hero
        onStart={() =>
          inputRef.current?.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' })
        }
      />
      <main className="space-y-6">
        <div ref={inputRef} className="reveal reveal-zoom scroll-mt-20">
          <InputPanel
            mode={mode}
            onModeChange={onModeChange}
            onSubmit={onSubmit}
            busy={busy}
            canSubmit={canSubmit}
            file={file}
            previewUrl={previewUrl}
            onFile={onFile}
            text={text}
            onText={onText}
            demos={demos}
            activeDemoId={demoId}
            onPickDemo={onPickDemo}
            health={health}
          />
        </div>

        {phase === 'error' && error && <ErrorCard message={error} />}

        <div ref={resultRef} className="scroll-mt-20 space-y-6">
          {busy && running && <StageProgress mode={running.mode} mediaType={running.mediaType} />}
          {phase === 'result' && report && <ReportView report={report} originalUrl={reportImageUrl} />}
        </div>

        {phase === 'idle' && (
          <p className="px-1 text-sm text-muted">
            Choose a mode, then upload an image, video or audio clip, or paste text. TrustLens shows the evidence behind every
            assessment — what was found, what is missing, and how certain it is.
          </p>
        )}
      </main>
      <div aria-live="polite" role="status" className="sr-only">
        {announce}
      </div>
    </div>
  )
}
