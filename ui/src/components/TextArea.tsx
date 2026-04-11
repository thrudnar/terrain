import type { ChangeEventHandler } from "react";

interface TextAreaProps {
  value: string;
  onChange: ChangeEventHandler<HTMLTextAreaElement>;
  placeholder?: string;
  rows?: number;
  monospace?: boolean;
  className?: string;
}

export function TextArea({
  value,
  onChange,
  placeholder,
  rows = 5,
  monospace = false,
  className = "",
}: TextAreaProps) {
  return (
    <textarea
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      rows={rows}
      className={`
        w-full min-h-[120px]
        bg-surface-02 text-text-secondary
        placeholder:text-text-subtle
        border border-border-default rounded-comfortable
        px-3 py-2
        focus:border-accent focus:outline-none
        transition-colors duration-150
        resize-y
        ${monospace ? "font-mono text-mono" : "text-small"}
        ${className}
      `}
    />
  );
}
