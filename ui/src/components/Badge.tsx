type Tier = "STRONG FIT" | "GOOD FIT" | "MARGINAL FIT" | "SKIP";

interface BadgeProps {
  tier?: Tier;
  status?: string;
  className?: string;
}

const tierStyles: Record<Tier, string> = {
  "STRONG FIT": "bg-tier-strong-tint text-tier-strong",
  "GOOD FIT": "bg-tier-good-tint text-tier-good",
  "MARGINAL FIT": "bg-tier-marginal-tint text-tier-marginal",
  SKIP: "bg-tier-skip-tint text-tier-skip",
};

const statusStyles: Record<string, string> = {
  active: "bg-tier-strong-tint text-success",
  completed: "bg-tier-strong-tint text-success",
  warning: "bg-tier-marginal-tint text-warning",
  error: "bg-[--color-error]/12 text-error",
  info: "bg-brand-tint-12 text-accent",
};

export function Badge({ tier, status, className = "" }: BadgeProps) {
  const style = tier
    ? tierStyles[tier]
    : statusStyles[status ?? ""] ?? "bg-surface-05 text-text-muted";

  const label = tier ?? status ?? "";

  return (
    <span
      className={`
        inline-flex items-center
        rounded-pill px-2 py-0.5
        text-label
        ${style}
        ${className}
      `}
    >
      {label}
    </span>
  );
}
