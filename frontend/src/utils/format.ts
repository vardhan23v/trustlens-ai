import type { Category, Severity, Signal } from '../types/report'

export const SEVERITY_ORDER: Record<Severity, number> = { high: 0, medium: 1, low: 2 }
export const SEVERITY_ICON: Record<Severity, string> = { high: '🔴', medium: '🟠', low: '🟡' }
export const SEVERITY_LABEL: Record<Severity, string> = { high: 'High', medium: 'Medium', low: 'Low' }

export const CATEGORY_LABEL: Record<Category, string> = {
  image_forensics: 'Image forensics',
  url_domain: 'URL & domain',
  message_content: 'Message content',
  claim_evidence: 'Claim evidence',
}

const AGENT_LABEL: Record<string, string> = {
  extractor: 'Extractor',
  analyst: 'Trust Signal Analyst',
  claim_verifier: 'Claim Verifier',
  vision: 'Gemini Vision',
}

export function normSeverity(s: string): Severity {
  return s === 'high' || s === 'medium' || s === 'low' ? s : 'medium'
}

/** high → medium → low, larger penalty first within a severity. */
export function sortSignals(signals: Signal[]): Signal[] {
  return [...signals].sort(
    (a, b) =>
      SEVERITY_ORDER[normSeverity(a.severity)] - SEVERITY_ORDER[normSeverity(b.severity)] ||
      b.penalty - a.penalty,
  )
}

export function agentName(id: string): string {
  return AGENT_LABEL[id] ?? id.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export function categoryLabel(c: string): string {
  return CATEGORY_LABEL[c as Category] ?? c.replace(/_/g, ' ')
}

/** Splits "First sentence. Rest of text" → ["First sentence.", "Rest of text"]. */
export function splitFirstSentence(text: string): [string, string] {
  const t = text.trim()
  const m = t.match(/^(.+?[.!?])(\s+)(.*)$/s)
  if (!m) return [t, '']
  return [m[1], m[3]]
}

/** 20 → "20", 7.5 → "7.5" */
export function fmtNum(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1)
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export function isHttpUrl(url: string): boolean {
  return /^https?:\/\//i.test(url.trim())
}

export function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
