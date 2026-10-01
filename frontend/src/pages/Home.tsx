import { useCallback, useEffect, useRef, useState } from 'react'
import ErrorCard from '../components/ErrorCard'
import Header from '../components/Header'
import InputPanel from '../components/InputPanel'
import ReportView from '../components/ReportView'
import StageProgress, { HOLD_STAGE, STAGES } from '../components/StageProgress'
import { analyze, getDemos, getHealth, isMock } from '../services/api'
import type { Demo, Health, InputType, Intent, TrustReport } from '../types/report'
import { prefersReducedMotion, sleep } from '../utils/format'

type Phase = 'idle' | 'analyzing' | 'result' | 'error'

const STAGE_MS = 400

interface RunRequest {
  mode: InputType
  text?: string
  file?: File | null
  demoId?: string | null
  intent?: Intent | null
  /** Image shown as "original" in the report (image mode only). */
  imageUrl?: string | null
}

export default function Home() {
  const [mode, setMode] = useState<InputType>('image')
  const [texts, setTexts] = useState<{ text: string; claim: string }>({ text: '', claim: '' })
  // Image tab: the user first says what they want verified.
  const [intent, setIntent] = useState<Intent | null>(null)
  const [runIntent, setRunIntent] = useState<Intent | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  // The demo currently loaded into an input; cleared as soon as the user edits that input.
  const [demo, setDemo] = useState<{ id: string; mode: InputType } | null>(null)

  const [demos, setDemos] = useState<Demo[]>([])
  const [health, setHealth] = useState<Health | null>(null)

  const [phase, setPhase] = useState<Phase>('idle')
  const [stage, setStage] = useState(0)
  const [report, setReport] = useState<TrustReport | null>(null)
  const [reportImageUrl, setReportImageUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [announce, setAnnounce] = useState('')

  const runId = useRef(0)
  const objectUrls = useRef<string[]>([])
  const resultRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let alive = true
    getDemos()
      .then((d) => alive && setDemos(d))
      .catch(() => alive && setDemos([])) // backend down → no chips, no crash
    if (!isMock()) {
      getHealth()
        .then((h) => alive && setHealth(h))
        .catch(() => undefined)
    }
    const urls = objectUrls.current
    return () => {
      alive = false
      urls.forEach((u) => URL.revokeObjectURL(u))
    }
  }, [])

  const run = useCallback(async (req: RunRequest) => {
    const id = ++runId.current
    const reduced = prefersReducedMotion()
    setPhase('analyzing')
    setError(null)
    setReport(null)
    setAnnounce('')
    setStage(0)
    setRunIntent(req.mode === 'image' ? (req.intent ?? null) : null)

    // Timed walk through the stages; holds on "Gemini reasoning" until the response arrives.
    const timer = window.setInterval(() => setStage((s) => Math.min(s + 1, HOLD_STAGE)), STAGE_MS)
    try {
      const [result] = await Promise.all([analyze(req), sleep(reduced ? 0 : HOLD_STAGE * STAGE_MS + 500)])
      if (id !== runId.current) return
      window.clearInterval(timer)
      setStage(STAGES.length) // flash the remaining stages complete
      await sleep(reduced ? 0 : 450)
      if (id !== runId.current) return
      setReport(result)
      setReportImageUrl(req.mode === 'image' ? (req.imageUrl ?? null) : null)
      setPhase('result')
      setAnnounce('Analysis complete')
      requestAnimationFrame(() =>
        resultRef.current?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' }),
      )
    } catch (e) {
      if (id !== runId.current) return
      setError(e instanceof Error && e.message ? e.message : 'Something went wrong. Please try again.')
      setPhase('error')
    } finally {
      window.clearInterval(timer)
    }
  }, [])

  const busy = phase === 'analyzing'

  const onTextChange = (value: string) => {
    if (mode === 'image') return
    setTexts((t) => ({ ...t, [mode]: value }))
    if (demo?.mode === mode) setDemo(null)
  }

  const onFile = (f: File | null) => {
    setFile(f)
    if (f) {
      const url = URL.createObjectURL(f)
      objectUrls.current.push(url)
      setPreviewUrl(url)
    } else {
      setPreviewUrl(null)
    }
    if (demo?.mode === 'image') setDemo(null)
  }

  const onPickDemo = (d: Demo) => {
    if (busy) return
    setMode(d.input_type)
    setDemo({ id: d.id, mode: d.input_type })
    if (d.input_type === 'image') {
      setIntent('artifact_authenticity') // the demo notices are artifact checks
      setFile(null)
      setPreviewUrl(d.image_url)
    } else {
      const key = d.input_type
      setTexts((t) => ({ ...t, [key]: d.text ?? '' }))
    }
    // Auto-run: one click shows the full report.
    void run({
      mode: d.input_type,
      demoId: d.id,
      text: d.text ?? '',
      imageUrl: d.input_type === 'image' ? d.image_url : null,
      intent: d.input_type === 'image' ? 'artifact_authenticity' : null,
    })
  }

  const activeDemoId = demo?.mode === mode ? demo.id : null
  const currentText = mode === 'image' ? '' : texts[mode]
  const canSubmit = mode === 'image' ? !!intent && (!!file || !!activeDemoId) : currentText.trim().length > 0

  const onSubmit = () => {
    if (busy || !canSubmit) return
    if (mode === 'image') {
      void run({ mode, file, demoId: activeDemoId, imageUrl: previewUrl, intent })
    } else {
      void run({ mode, text: currentText, demoId: activeDemoId })
    }
  }

  return (
    <div className="mx-auto min-h-screen max-w-6xl px-4 pb-16">
      <Header />
      <main className="space-y-6">
        <InputPanel
          mode={mode}
          onModeChange={setMode}
          onSubmit={onSubmit}
          busy={busy}
          canSubmit={canSubmit}
          text={currentText}
          onTextChange={onTextChange}
          file={file}
          previewUrl={previewUrl}
          onFile={onFile}
          intent={intent}
          onIntentChange={(i) => {
            setIntent(i)
            if (demo?.mode === 'image') setDemo(null)
          }}
          demos={demos}
          activeDemoId={activeDemoId}
          onPickDemo={onPickDemo}
          health={health}
        />

        {phase === 'error' && error && <ErrorCard message={error} />}

        <div ref={resultRef} className="scroll-mt-4 space-y-6">
          {busy && <StageProgress stage={stage} intent={runIntent} />}
          {phase === 'result' && report && <ReportView report={report} originalUrl={reportImageUrl} />}
        </div>

        {phase === 'idle' && (
          <p className="px-1 text-sm text-muted">
            Upload a screenshot, paste a message, or enter a news claim. TrustLens shows every signal behind the score —
            what was found, where, and why it matters.
          </p>
        )}
      </main>
      <div aria-live="polite" role="status" className="sr-only">
        {announce}
      </div>
    </div>
  )
}
