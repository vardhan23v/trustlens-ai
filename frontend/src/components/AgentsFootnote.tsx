import { agentName } from '../utils/format'

interface Props {
  agentsUsed: string[]
}

export default function AgentsFootnote({ agentsUsed }: Props) {
  if (agentsUsed.length === 0) return null
  return (
    <p className="text-xs text-muted">
      Analysed by CrewAI agents: {agentsUsed.map(agentName).join(', ')} (Gemini)
    </p>
  )
}
