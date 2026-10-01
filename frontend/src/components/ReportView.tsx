import type { TrustReport } from '../types/report'
import { sortSignals } from '../utils/format'
import AgentsFootnote from './AgentsFootnote'
import AssessmentPanel from './AssessmentPanel'
import Caveats from './Caveats'
import ClaimBreakdown from './ClaimBreakdown'
import DeductionTable from './DeductionTable'
import Disclaimer from './Disclaimer'
import ElaCompare from './ElaCompare'
import EvidenceList from './EvidenceList'
import ExtractedPanel from './ExtractedPanel'
import ModeBanner from './ModeBanner'
import PdfButton from './PdfButton'
import PipelinePanel from './PipelinePanel'
import SectionNav from './SectionNav'
import type { Section } from './SectionNav'
import { useCountUp } from '../hooks/useCountUp'
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
  const changeFactors = (report.change_factors ?? []).length > 0 ? report.change_factors : (report.confidence_boosters ?? [])
  const news = report.mode === 'news_claim'
  // A clean 100 would read as "trusted". With no findings and no positive assessment there is nothing to score.
  const undecided = ['INCONCLUSIVE', 'NOT_ASSESSED', 'UNVERIFIED', 'EVIDENCE_UNAVAILABLE'].includes(report.overall_assessment?.state ?? '')
  const unscored = !!report.mode && (report.signals ?? []).length === 0 && (!!report.gemini_error || undecided)
  const shownSignals = useCountUp(signals.length)
  const hasPipeline =
    (report.stages ?? []).length > 0 || (report.specialist_models ?? []).length > 0 || Object.keys(report.media_metadata ?? {}).length > 0
  const sections: Section[] = [
    { id: 'rep-assessment', label: 'Assessment' },
    { id: 'rep-summary', label: 'Summary' },
    ...(news && ((report.claims ?? []).length > 0 || (report.evidence ?? []).length > 0) ? [{ id: 'rep-evidence', label: 'Evidence' }] : []),
    { id: 'rep-findings', label: 'Findings' },
    { id: 'rep-score', label: 'Score' },
    ...(hasPipeline ? [{ id: 'rep-pipeline', label: 'Pipeline' }] : []),
  ]

  return (
    <section aria-label="Trust Report" className="space-y-6">
      <SectionNav sections={sections} />
      <div id="rep-assessment" className="scroll-mt-32">
        <AssessmentPanel report={report} />
      </div>
      <div id="rep-summary" className="card card-glow animate-fade-up grid scroll-mt-32 gap-6 p-4 sm:p-6 md:grid-cols-[auto_1fr] md:gap-8">
        <div className="flex justify-center md:items-start">
          <div className="max-w-[15rem] text-center">
            {unscored ? (
              <div className="grid size-[180px] place-items-center rounded-full border-[12px] border-border text-center">
                <p className="px-4 text-sm font-semibold text-muted">
                  Not scored
                  <span className="mt-1 block text-[11px] font-normal">
                    {report.gemini_error ? 'the examination did not complete' : 'nothing decisive was found either way'}
                  </span>
                </p>
              </div>
            ) : (
              <TrustGauge score={report.trust_score} risk={report.risk_level} />
            )}
            {report.score_scope && <p className="mt-2 text-[11px] leading-snug text-muted">{report.score_scope}</p>}
          </div>
        </div>
        <div className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-start gap-x-4 gap-y-3">
            <RiskBadge
              hasSignals={report.signals.length > 0}
              risk={report.risk_level}
              verdict={report.mode ? null : report.verdict}
              assessment={report.mode ? report.overall_assessment : report.verdict ? null : report.overall_assessment}
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
          {changeFactors.length > 0 && (
            <div>
              <h3 className="section-title mb-1.5">
                {report.mode === 'ai_generated' ? 'What would increase confidence?' : 'What would change the assessment?'}
              </h3>
              <ul className="list-disc space-y-1 pl-5 text-sm text-text marker:text-accent-soft">
                {changeFactors.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}
          <Caveats caveats={report.caveats ?? []} />
          <PdfButton report={report} />
        </div>
      </div>

      {(report.input_type === 'image' || report.media_type === 'image') && ela && (
        <ElaCompare
          originalUrl={originalUrl}
          heatmapB64={ela.heatmap_b64}
          region={ela.region}
          status={ela.status}
          width={ela.width}
          height={ela.height}
        />
      )}

      {news && (
        <div id="rep-evidence" className="scroll-mt-32 space-y-6">
          <ClaimBreakdown claims={report.claims ?? []} timeline={report.timeline ?? []} article={report.article ?? null} />
          <EvidenceList evidence={report.evidence ?? []} />
        </div>
      )}

      <div id="rep-findings" className={`scroll-mt-32 ${signals.length === 0 && report.verdict ? 'hidden' : ''}`}>
        <h2 className="section-title mb-3">
          {news ? 'Media and content findings' : 'Synthetic-media findings'} <span className="font-mono text-text">({shownSignals})</span>
        </h2>
        {signals.length > 0 ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {signals.map((s, i) => (
              <SignalCard key={`${s.key}-${i}`} signal={s} index={i} />
            ))}
          </div>
        ) : (
          <p className="card p-4 text-sm text-muted">
            No indicators were raised by the deterministic checks or Gemini. That is an absence of evidence, not proof
            that the media is authentic.
          </p>
        )}
      </div>

      {(inconsistencies.length > 0 || notes.length > 0) && (
        <div className="grid gap-4 px-1 sm:grid-cols-2">
          <MutedList title="Inconsistencies noted" items={inconsistencies} />
          <MutedList title="Notes" items={notes} />
        </div>
      )}

      <div id="rep-score" className="scroll-mt-32">
        <DeductionTable signals={signals} breakdown={report.score_breakdown ?? []} score={report.trust_score} />
      </div>

      <div id="rep-pipeline" className="scroll-mt-32">
        <PipelinePanel report={report} />
      </div>

      {report.extracted && <ExtractedPanel extracted={report.extracted} />}

      <footer className="space-y-1 border-t border-border px-1 pt-4">
        <AgentsFootnote agentsUsed={report.agents_used ?? []} />
        <Disclaimer text={report.disclaimer} />
      </footer>
    </section>
  )
}
