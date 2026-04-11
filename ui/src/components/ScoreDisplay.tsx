import { Badge } from "./Badge.tsx";

type Tier = "STRONG FIT" | "GOOD FIT" | "MARGINAL FIT" | "SKIP";

interface ScoreDisplayProps {
  score: number;
  recommendation: Tier;
  className?: string;
}

export function ScoreDisplay({
  score,
  recommendation,
  className = "",
}: ScoreDisplayProps) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <span className="text-h2 text-text-primary">{score}</span>
      <Badge tier={recommendation} />
    </div>
  );
}
