import { splitFirstSentence } from '../utils/format'

interface Props {
  text: string
}

export default function RecommendationBox({ text }: Props) {
  if (!text.trim()) return null
  const [first, rest] = splitFirstSentence(text)
  return (
    <div className="rounded-xl border border-border bg-surface-2 p-4">
      <h3 className="section-title mb-1.5">Recommendation</h3>
      <p className="text-[15px] leading-relaxed text-text">
        <strong className="font-semibold">{first}</strong>
        {rest && <> {rest}</>}
      </p>
    </div>
  )
}
