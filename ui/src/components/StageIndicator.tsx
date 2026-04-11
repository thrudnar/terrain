type Stage = "harvest" | "dedup" | "score" | "promote" | "cover_letter";

interface StageIndicatorProps {
  stage: Stage;
  className?: string;
}

const stageConfig: Record<Stage, { dot: string; label: string }> = {
  harvest: { dot: "bg-stage-harvest", label: "Harvest" },
  dedup: { dot: "bg-stage-dedup", label: "Dedup" },
  score: { dot: "bg-stage-score", label: "Score" },
  promote: { dot: "bg-stage-promote", label: "Promote" },
  cover_letter: { dot: "bg-stage-coverletter", label: "Cover Letter" },
};

export function StageIndicator({ stage, className = "" }: StageIndicatorProps) {
  const { dot, label } = stageConfig[stage];

  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      <span className={`inline-block h-2 w-2 rounded-full ${dot}`} />
      <span className="text-caption-lg text-text-secondary">{label}</span>
    </div>
  );
}
