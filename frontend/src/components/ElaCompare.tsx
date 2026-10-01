import type { ReactNode } from 'react'
import type { ElaStatus } from '../types/report'

interface Props {
  originalUrl: string | null
  heatmapB64: string | null
  region: number[] | null
  status: ElaStatus
  /** Original image size in pixels — used to scale the region overlay. */
  width: number | null
  height: number | null
}

const CAPTION = 'ELA highlights compression differences; not proof of editing'

function RegionBox({ region, width, height }: { region: number[] | null; width: number | null; height: number | null }) {
  if (!region || region.length !== 4 || !width || !height) return null
  const [x, y, w, h] = region
  if (w <= 0 || h <= 0) return null
  const pct = (n: number, total: number) => `${Math.max(0, Math.min(100, (n / total) * 100))}%`
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute rounded-sm border-2 border-accent shadow-[0_0_0_1px_rgba(11,15,23,0.9)]"
      style={{ left: pct(x, width), top: pct(y, height), width: pct(w, width), height: pct(h, height) }}
    />
  )
}

function Pane({ label, children }: { label: string; children: ReactNode }) {
  return (
    <figure className="min-w-0">
      <figcaption className="mb-2 text-xs font-medium uppercase tracking-wider text-muted">{label}</figcaption>
      <div className="flex justify-center rounded-lg border border-border bg-bg p-2">{children}</div>
    </figure>
  )
}

export default function ElaCompare({ originalUrl, heatmapB64, region, status, width, height }: Props) {
  const hasHeatmap = status === 'ok' && !!heatmapB64
  if (!originalUrl && !hasHeatmap && status !== 'not_applicable_lossless') return null

  const original = originalUrl && (
    <Pane label="Original">
      <div className="relative inline-block">
        <img src={originalUrl} alt="Original uploaded image" className="block max-h-[28rem] w-auto max-w-full" />
        {hasHeatmap && <RegionBox region={region} width={width} height={height} />}
      </div>
    </Pane>
  )

  return (
    <section aria-label="Error level analysis" className="card animate-fade-up p-4 sm:p-6">
      <h2 className="section-title mb-4">Image forensics · Error Level Analysis</h2>
      {hasHeatmap ? (
        <>
          <div className={`grid gap-4 ${originalUrl ? 'md:grid-cols-2' : ''}`}>
            {original}
            <Pane label="ELA heatmap">
              <div className="relative inline-block">
                <img
                  src={`data:image/png;base64,${heatmapB64}`}
                  alt="Error level analysis heatmap of the image"
                  className="block max-h-[28rem] w-auto max-w-full"
                />
                <RegionBox region={region} width={width} height={height} />
              </div>
            </Pane>
          </div>
          {region && region.length === 4 && (
            <p className="mt-3 flex items-center gap-2 text-xs text-muted">
              <span aria-hidden="true" className="inline-block h-3 w-4 rounded-sm border-2 border-accent" />
              Outlined area: region with the strongest compression difference
            </p>
          )}
          <p className="mt-2 text-xs text-muted">{CAPTION}</p>
        </>
      ) : (
        <>
          {originalUrl && <div className="grid gap-4 md:grid-cols-2">{original}</div>}
          <p className="mt-3 text-sm text-muted">
            {status === 'not_applicable_lossless'
              ? 'ELA not applicable to lossless images (PNG)'
              : status === 'error'
                ? 'ELA could not be computed for this image'
                : 'ELA not available for this image'}
          </p>
        </>
      )}
    </section>
  )
}
