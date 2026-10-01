interface Props {
  text?: string
}

const DEFAULT = 'Trust Score is a risk indicator, not proof of authenticity or fraud.'

export default function Disclaimer({ text }: Props) {
  return <p className="text-xs text-muted">{text?.trim() || DEFAULT}</p>
}
