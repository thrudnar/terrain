import type { ReactNode, MouseEventHandler } from "react";

type ButtonVariant = "primary" | "ghost" | "subtle" | "pill";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  disabled?: boolean;
  className?: string;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-brand text-white hover:bg-accent-hover rounded-comfortable",
  ghost:
    "bg-surface-02 text-text-secondary border border-border-solid-primary hover:bg-surface-05 rounded-comfortable",
  subtle:
    "bg-surface-04 text-text-secondary hover:bg-surface-05 rounded-comfortable",
  pill:
    "bg-transparent text-text-secondary border border-border-solid-primary hover:bg-surface-02 rounded-pill",
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: "px-2 py-1 text-label",
  md: "px-3 py-2 text-label",
  lg: "px-4 py-2 text-label",
};

export function Button({
  variant = "ghost",
  size = "md",
  children,
  onClick,
  disabled = false,
  className = "",
}: ButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`
        inline-flex items-center justify-center
        transition-colors duration-150
        cursor-pointer
        disabled:opacity-40 disabled:pointer-events-none
        ${variantStyles[variant]}
        ${sizeStyles[size]}
        ${className}
      `}
    >
      {children}
    </button>
  );
}
