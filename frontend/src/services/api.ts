import type { Demo, Health, InputType, Intent, TrustReport } from '../types/report'
import mockReport from '../mocks/scam_sms.json'
import { sleep } from '../utils/format'

// Same-origin only. The frontend never talks to Gemini directly.
const API = '/api'

export class ApiError extends Error {}

export interface AnalyzeRequest {
  mode: InputType
  text?: string
  file?: File | null
  demoId?: string | null
  /** Image uploads: what to verify. */
  intent?: Intent | null
}

/** Dev aid: `?mock=1` returns the bundled sample report instead of calling the API. */
export function isMock(): boolean {
  return new URLSearchParams(window.location.search).get('mock') === '1'
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `Request failed (${res.status}). Is the backend running?`
    try {
      const body: unknown = await res.json()
      const detail = (body as { detail?: unknown } | null)?.detail
      if (typeof detail === 'string' && detail) msg = detail
      else if (Array.isArray(detail)) {
        const parts = detail
          .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : ''))
          .filter(Boolean)
        if (parts.length) msg = parts.join('; ')
      }
    } catch {
      // non-JSON error body — keep the generic message
    }
    throw new ApiError(msg)
  }
  return (await res.json()) as T
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API}${path}`, init)
  } catch {
    throw new ApiError('Could not reach the TrustLens backend. Check that it is running and try again.')
  }
  return parse<T>(res)
}

function postJson<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export function getHealth(): Promise<Health> {
  return request<Health>('/health')
}

export async function getDemos(): Promise<Demo[]> {
  if (isMock()) {
    const m = mockReport as unknown as TrustReport
    return [{ id: 'scam_sms', label: 'Scam SMS', input_type: 'text', text: m.extracted.extracted_text, image_url: null }]
  }
  const demos = await request<Demo[]>('/demos')
  return Array.isArray(demos) ? demos : []
}

export function analyzeImage(file: File, intent: Intent): Promise<TrustReport> {
  const form = new FormData()
  form.append('file', file)
  form.append('analysis_mode', intent)
  return request<TrustReport>('/analyze/image', { method: 'POST', body: form })
}

export function analyzeText(text: string): Promise<TrustReport> {
  return postJson<TrustReport>('/analyze/text', { text })
}

export function analyzeClaim(text: string): Promise<TrustReport> {
  return postJson<TrustReport>('/analyze/claim', { text })
}

export function analyzeDemo(id: string): Promise<TrustReport> {
  return postJson<TrustReport>(`/analyze/demo/${encodeURIComponent(id)}`)
}

/** Builds the PDF on the backend from the analysis already on screen (nothing is re-analysed) and saves it. */
export async function downloadPdfReport(report: TrustReport): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${API}/report/pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ report }),
    })
  } catch {
    throw new ApiError('PDF generation is temporarily unavailable. Your TrustLens analysis is still available.')
  }
  if (!res.ok) await parse<never>(res)
  const blob = await res.blob()
  const stamp = new Date().toISOString().slice(0, 19).replace(/[-:]/g, '').replace('T', '_')
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `TrustLens_Report_${stamp}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

export async function analyze(req: AnalyzeRequest): Promise<TrustReport> {
  if (isMock()) {
    await sleep(2000)
    return mockReport as unknown as TrustReport
  }
  if (req.demoId) return analyzeDemo(req.demoId)
  if (req.mode === 'image') {
    if (!req.file) throw new ApiError('Choose an image to analyze.')
    return analyzeImage(req.file, req.intent ?? 'artifact_authenticity')
  }
  const text = (req.text ?? '').trim()
  if (!text) throw new ApiError('Enter some text to analyze.')
  return req.mode === 'claim' ? analyzeClaim(text) : analyzeText(text)
}
