import type { ReactNode } from "react";

interface Filter {
  key: string;
  label: string;
  value: string;
  options?: { value: string; label: string }[];
}

interface FilterBarProps {
  filters: Filter[];
  activeFilters: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onClear: () => void;
  children?: ReactNode;
}

export function FilterBar({
  filters,
  activeFilters,
  onChange,
  onClear,
}: FilterBarProps) {
  const hasActive = Object.keys(activeFilters).length > 0;

  return (
    <div className="flex items-center gap-2 flex-wrap bg-surface-02 border-b border-border-subtle px-3 py-2">
      {filters.map((filter) => {
        const isActive = activeFilters[filter.key] != null;

        if (filter.options) {
          return (
            <select
              key={filter.key}
              value={activeFilters[filter.key] ?? ""}
              onChange={(e) => onChange(filter.key, e.target.value)}
              className={`
                appearance-none
                px-2.5 py-0.5 rounded-pill text-label
                transition-colors duration-150
                cursor-pointer border
                ${
                  isActive
                    ? "bg-brand-tint-12 text-accent border-transparent"
                    : "bg-surface-02 text-text-secondary border-border-solid-primary hover:bg-surface-05"
                }
              `}
            >
              <option value="">{filter.label}</option>
              {filter.options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          );
        }

        return (
          <button
            key={filter.key}
            type="button"
            onClick={() =>
              onChange(filter.key, isActive ? "" : filter.value)
            }
            className={`
              px-2.5 py-0.5 rounded-pill text-label
              transition-colors duration-150
              cursor-pointer border
              ${
                isActive
                  ? "bg-brand-tint-12 text-accent border-transparent"
                  : "bg-surface-02 text-text-secondary border-border-solid-primary hover:bg-surface-05"
              }
            `}
          >
            {filter.label}
          </button>
        );
      })}

      {hasActive && (
        <button
          type="button"
          onClick={onClear}
          className="px-2 py-0.5 text-label text-text-muted hover:text-text-secondary transition-colors duration-150 cursor-pointer"
        >
          Clear all
        </button>
      )}
    </div>
  );
}
