interface Props {
  caveats: string[]
}

export default function Caveats({ caveats }: Props) {
  if (caveats.length === 0) return null
  return (
    <div>
      <h3 className="section-title mb-1.5">What this analysis cannot tell you</h3>
      <ul className="list-disc space-y-1 pl-5 text-sm text-muted marker:text-border">
        {caveats.map((c, i) => (
          <li key={i}>{c}</li>
        ))}
      </ul>
    </div>
  )
}
