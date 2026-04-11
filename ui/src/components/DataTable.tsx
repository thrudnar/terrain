import type { ReactNode } from "react";

interface Column<T> {
  key: string;
  label: string;
  sortable?: boolean;
  render?: (row: T) => ReactNode;
}

type SortDir = "asc" | "desc";

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  sortKey?: string;
  sortDir?: SortDir;
  onSort?: (key: string) => void;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  onRowClick,
  sortKey,
  sortDir,
  onSort,
}: DataTableProps<T>) {
  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface-03">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`
                  px-3 py-2 text-left text-caption-lg text-text-muted
                  ${col.sortable ? "cursor-pointer select-none hover:text-text-primary" : ""}
                `}
                onClick={col.sortable && onSort ? () => onSort(col.key) : undefined}
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {col.sortable && sortKey === col.key && (
                    <span className="text-text-subtle">
                      {sortDir === "asc" ? "\u2191" : "\u2193"}
                    </span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr
              key={i}
              className={`
                border-b border-border-subtle
                hover:bg-surface-02
                ${onRowClick ? "cursor-pointer" : ""}
              `}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((col) => (
                <td key={col.key} className="px-3 py-2 text-small text-text-secondary">
                  {col.render
                    ? col.render(row)
                    : (row[col.key] as ReactNode)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
