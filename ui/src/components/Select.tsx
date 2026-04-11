import type { ChangeEventHandler } from "react";

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  value: string;
  onChange: ChangeEventHandler<HTMLSelectElement>;
  options: SelectOption[];
  className?: string;
}

export function Select({ value, onChange, options, className = "" }: SelectProps) {
  return (
    <select
      value={value}
      onChange={onChange}
      className={`
        appearance-none
        bg-surface-02 text-text-secondary
        border border-border-solid-primary
        rounded-comfortable
        px-3 py-2 text-label
        hover:bg-surface-05
        focus:border-accent focus:outline-none
        transition-colors duration-150
        cursor-pointer
        ${className}
      `}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}
