type ConfidenceBadgeProps = {
  score: number
}

const formatScore = (score: number) => {
  const percent = Math.round(score * 100)
  return `${percent}%`
}

const ConfidenceBadge = ({ score }: ConfidenceBadgeProps) => {
  return (
    <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
      Confidence {formatScore(score)}
    </span>
  )
}

export default ConfidenceBadge
