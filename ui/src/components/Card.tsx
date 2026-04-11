import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  borderColor?: string;
}

export function Card({ children, className = "", borderColor }: CardProps) {
  return (
    <div
      className={`
        bg-surface-02 border border-border-default rounded-card
        ${borderColor ? `border-l-3 ${borderColor}` : ""}
        ${className}
      `}
    >
      {children}
    </div>
  );
}
