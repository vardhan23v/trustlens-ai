interface Props {
  value: string
  onChange: (value: string) => void
  placeholder: string
  label: string
  disabled?: boolean
}

export default function TextArea({ value, onChange, placeholder, label, disabled }: Props) {
  return (
    <textarea
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      rows={7}
      spellCheck={false}
      className="block min-h-44 w-full resize-y rounded-xl border border-border bg-bg/60 p-4 text-sm leading-relaxed text-text placeholder:text-muted/70 focus:border-accent-soft focus:outline-none focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-60"
    />
  )
}
