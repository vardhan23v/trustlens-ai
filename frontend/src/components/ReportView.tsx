import type { TrustReport } from '../types/report'
import { sortSignals } from '../utils/format'
import AgentsFootnote from './AgentsFootnote'
import AssessmentPanel from './AssessmentPanel'
import Caveats from './Caveats'
import DeductionTable from './DeductionTable'
import Disclaimer from './Disclaimer'
import ElaCompare from './ElaCompare'
import EvidenceList from './EvidenceList'
import ExtractedPanel from './ExtractedPanel'
import ModeBanner from './ModeBanner'
import PdfButton from './PdfButton'
import RecommendationBox from './RecommendationBox'
import RiskBadge from './RiskBadge'
import SignalCard from './SignalCard'
import TrustGauge from './TrustGauge'

interface Props {
  report: TrustReport
  /** Object URL of the uploaded file or the demo image URL (image input only). */
  originalUrl: string | null
}

function MutedList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div>
      <h3 className="section-title mb-1.5">{title}</h3>
      <ul className="list-disc space-y-1 pl-5 text-sm text-muted marker:text-border">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

export default function ReportView({ report, originalUrl }: Props) {
  const signals = sortSignals(report.signals ?? [])
  const whatToVerify = report.what_to_verify ?? []
  const inconsistencies = report.inconsistencies ?? []
  const notes = report.notes ?? []
  const ela = report.ela

  return (
    <section aria-label="Trust Report" className="space-y-6">
      {report.analysis_intent && <AssessmentPanel report={report} />}
      <div className="card animate-fade-up grid gap-6 p-4 sm:p-6 md:grid-cols-[auto_1fr] md:gap-8">
        <div className="flex justify-center md:items-start">
          <TrustGauge score={report.trust_score} risk={report.risk_level} />
        </div>
        <div className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-start gap-x-4 gap-y-3">
            <RiskBadge
              hasSignals={report.signals.length > 0}
              risk={report.risk_level}
              verdict={report.verdict}
              assessment={report.overall_assessment}
            />
            <div className="pt-1">
              <ModeBanner analysisMode={report.analysis_mode} geminiError={report.gemini_error} />
            </div>
          </div>
          <RecommendationBox text={report.recommendation} />
          {whatToVerify.length > 0 && (
            <div>
              <h3 className="section-title mb-1.5">What to verify</h3>
              <ul className="space-y-1.5 text-sm text-text">
                {whatToVerify.map((item, i) => (
                  <li key={i} className="flex gap-2">
                    <span aria-hidden="true" className="mt-px text-accent">
                      ☐
                    </span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {(report.confidence_boosters ?? []).length > 0 && (
            <div>
              <h3 className="section-title mb-1.5">What would increase confidence?</h3>
              <ul className="list-disc space-y-1 pl-5 text-sm text-text marker:text-accent-soft">
                {report.confidence_boosters.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}
          <Caveats caveats={report.caveats ?? []} />
          <PdfButton report={report} />
        </div>
      </div>

      {report.input_type === 'image' && ela && (
        <ElaCompare
          originalUrl={originalUrl}
          heatmapB64={ela.heatmap_b64}
          region={ela.region}
          status={ela.status}
          width={ela.width}
          height={ela.height}
        />
      )}

      <div className={signals.length === 0 && report.verdict ? 'hidden' : undefined}>
        <h2 className="section-title mb-3">
          Signals <span className="font-mono text-text">({signals.length})</span>
        </h2>
        {signals.length > 0 ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {signals.map((s, i) => (
              <SignalCard key={`${s.key}-${i}`} signal={s} index={i} />
            ))}
          </div>
        ) : (
          <p className="card p-4 text-sm text-muted">
            No risk signals were raised by the rule checks or Gemini. This does not verify the content as authentic.
          </p>
        )}
      </div>

      {(inconsistencies.length > 0 || notes.length > 0) && (
        <div className="grid gap-4 px-1 sm:grid-cols-2">
          <MutedList title="Inconsistencies noted" items={inconsistencies} />
          <MutedList title="Notes" items={notes} />
        </div>
      )}

      <DeductionTable signals={signals} breakdown={report.score_breakdown ?? []} score={report.trust_score} />

      <EvidenceList evidence={report.evidence ?? []} />

      {report.extracted && <ExtractedPanel extracted={report.extracted} />}

      <footer className="space-y-1 border-t border-border px-1 pt-4">
        <AgentsFootnote agentsUsed={report.agents_used ?? []} />
        <Disclaimer text={report.disclaimer} />
      </footer>
    </section>
  )
}
