import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  description,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-16 px-6 text-center ${className}`}
    >
      <h3 className="text-h3 text-text-primary mb-2">{title}</h3>
      <p className="text-small text-text-muted mb-6 max-w-md">{description}</p>
      {action && <div>{action}</div>}
    </div>
  );
}
