import { useCallback, useEffect, useRef, useState } from 'react'
import Backdrop from '../components/Backdrop'
import CursorFx from '../components/CursorFx'
import { DropOverlay, ScrollChrome, ShortcutsHelp, Toaster, toast } from '../components/PageChrome'
import ErrorCard from '../components/ErrorCard'
import Header from '../components/Header'
import Hero from '../components/Hero'
import InputPanel from '../components/InputPanel'
import ReportView from '../components/ReportView'
import StageProgress from '../components/StageProgress'
import { mediaTypeOf, validateFile } from '../components/UploadZone'
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

  // The whole page takes the colour of the selected mode (index.css reads html[data-mode]).
  useEffect(() => {
    const root = document.documentElement
    if (mode) root.dataset.mode = mode
    else delete root.dataset.mode
  }, [mode])

  // A file dropped anywhere on the page, or an image pasted from the clipboard, goes through the same
  // validation as the upload zone.
  const [dragging, setDragging] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const live = useRef({ busy, canSubmit, onSubmit: () => {} })
  const takeFile = useCallback((f: File | undefined, how: string) => {
    if (!f) return
    const problem = validateFile(f)
    if (problem) {
      toast(problem)
      return
    }
    setFile(f)
    setDemoId(null)
    setText('')
    const url = URL.createObjectURL(f)
    objectUrls.current.push(url)
    setPreviewUrl(url)
    toast(`${how}: ${f.name || 'image'}`)
    inputRef.current?.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' })
  }, [])

  useEffect(() => {
    let depth = 0
    const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes('Files')
    const enter = (e: DragEvent) => {
      if (!hasFiles(e)) return
      depth += 1
      setDragging(true)
    }
    const leave = (e: DragEvent) => {
      if (!hasFiles(e)) return
      depth = Math.max(0, depth - 1)
      if (depth === 0) setDragging(false)
    }
    const over = (e: DragEvent) => {
      if (hasFiles(e)) e.preventDefault()
    }
    const drop = (e: DragEvent) => {
      if (!hasFiles(e)) return
      e.preventDefault()
      depth = 0
      setDragging(false)
      if (!live.current.busy) takeFile(e.dataTransfer?.files?.[0], 'Dropped')
    }
    const paste = (e: ClipboardEvent) => {
      const f = Array.from(e.clipboardData?.files ?? [])[0]
      if (!f || live.current.busy) return // plain text pastes go to the text box as usual
      e.preventDefault()
      takeFile(f, 'Pasted')
    }
    const key = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      const typing = !!t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT' || t.isContentEditable)
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'Escape') {
        setHelpOpen(false)
        if (!live.current.busy && !typing) setMode(null)
        else if (typing) t?.blur()
        return
      }
      if (typing || live.current.busy) return
      if (e.key === '1') setMode('news_claim')
      else if (e.key === '2') setMode('ai_generated')
      else if (e.key === '?') setHelpOpen((o) => !o)
      else if (e.key === 'Enter' && live.current.canSubmit && t?.tagName !== 'BUTTON') live.current.onSubmit()
    }
    window.addEventListener('dragenter', enter)
    window.addEventListener('dragleave', leave)
    window.addEventListener('dragover', over)
    window.addEventListener('drop', drop)
    window.addEventListener('paste', paste)
    window.addEventListener('keydown', key)
    return () => {
      window.removeEventListener('dragenter', enter)
      window.removeEventListener('dragleave', leave)
      window.removeEventListener('dragover', over)
      window.removeEventListener('drop', drop)
      window.removeEventListener('paste', paste)
      window.removeEventListener('keydown', key)
    }
  }, [takeFile])

  const onSubmit = () => {
    if (busy || !mode || !canSubmit) return
    if (!file && !demoId) {
      void run({ mode, text, mediaType: 'text' })
      return
    }
    const mediaType = file ? (mediaTypeOf(file) ?? 'image') : 'image'
    void run({ mode, file, demoId, mediaType, imageUrl: previewUrl })
  }

  live.current = { busy, canSubmit, onSubmit }

  return (
    <div className="mx-auto min-h-screen max-w-6xl overflow-x-clip px-4 pb-16">
      <Backdrop />
      <CursorFx />
      <ScrollChrome />
      <Toaster />
      <DropOverlay show={dragging && !busy} />
      <ShortcutsHelp open={helpOpen} onToggle={() => setHelpOpen((o) => !o)} />
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
