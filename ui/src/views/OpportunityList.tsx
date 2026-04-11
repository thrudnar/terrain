import { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Badge } from "../components/Badge";
import { ScoreDisplay } from "../components/ScoreDisplay";
import { FilterBar } from "../components/FilterBar";
import { DataTable } from "../components/DataTable";
import { Skeleton } from "../components/Skeleton";
import { EmptyState } from "../components/EmptyState";
import { useOpportunities } from "../hooks/useOpportunities";
import type { OpportunityFilters, PipelineState, Recommendation } from "../types";

const PIPELINE_STATES: PipelineState[] = ["harvested", "scored", "applied", "active", "closed"];
const RECOMMENDATIONS: Recommendation[] = ["STRONG FIT", "GOOD FIT", "MARGINAL FIT", "SKIP"];

type SortField = "score" | "date";
type SortDir = "asc" | "desc";

export function OpportunityList() {
  const navigate = useNavigate();

  const [filters, setFilters] = useState<OpportunityFilters>({});
  const [sortField, setSortField] = useState<SortField>("date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const { data, isLoading } = useOpportunities(filters);

  const handleFilterChange = useCallback(
    (key: string, value: string) => {
      setFilters((prev) => {
        const next = { ...prev };
        if (value === "") {
          delete next[key as keyof OpportunityFilters];
        } else {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (next as any)[key] = value;
        }
        return next;
      });
    },
    [],
  );

  const clearFilters = useCallback(() => {
    setFilters({});
  }, []);

  const handleSort = useCallback(
    (key: string) => {
      const field = key as SortField;
      if (sortField === field) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortField(field);
        setSortDir("desc");
      }
    },
    [sortField],
  );

  const sorted = useMemo(() => {
    if (!data?.items) return [];
    const items = [...data.items];
    items.sort((a, b) => {
      let cmp = 0;
      if (sortField === "score") {
        cmp = (a.scoring?.overall ?? 0) - (b.scoring?.overall ?? 0);
      } else {
        cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return items;
  }, [data, sortField, sortDir]);

  const activeFilters = useMemo(() => {
    const active: Record<string, string> = {};
    if (filters.pipeline_state) active["pipeline_state"] = filters.pipeline_state;
    if (filters.recommendation) active["recommendation"] = filters.recommendation;
    if (filters.company) active["company"] = filters.company;
    return active;
  }, [filters]);

  const filterBarFilters = useMemo(
    () => [
      {
        key: "pipeline_state",
        label: "Status",
        value: "",
        options: PIPELINE_STATES.map((s) => ({ value: s, label: s })),
      },
      {
        key: "recommendation",
        label: "Recommendation",
        value: "",
        options: RECOMMENDATIONS.map((r) => ({ value: r, label: r })),
      },
    ],
    [],
  );

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

  /* Build rows as Record<string, unknown> for DataTable constraint */
  const rows = useMemo(
    () =>
      sorted.map((opp) => ({
        _key: opp._id ?? opp.source.board_job_id,
        company: opp.company,
        title: opp.title,
        scoring: opp.scoring,
        pipeline_state: opp.pipeline_state,
        work_type: opp.work_type,
        created_at: opp.created_at,
        _id: opp._id,
      })),
    [sorted],
  );

  return (
    <div className="space-y-6">
      <h1 className="text-h1 text-text-primary">Opportunities</h1>

      {/* Filter Bar */}
      <FilterBar
        filters={filterBarFilters}
        activeFilters={activeFilters}
        onChange={handleFilterChange}
        onClear={clearFilters}
      />

      {/* Active Filter Pills */}
      {Object.keys(activeFilters).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(activeFilters).map(([key, value]) => (
            <button
              key={key}
              type="button"
              onClick={() => handleFilterChange(key, "")}
              className="inline-flex items-center gap-1.5 rounded-pill px-3 py-1 text-label bg-brand-tint-12 text-accent hover:bg-brand-tint-08 transition-colors cursor-pointer"
            >
              {key.replace("_", " ")}: {value}
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          ))}
        </div>
      )}

      {/* Data Table */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded-card" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          title="No results"
          description="No opportunities match the current filters."
        />
      ) : (
        <DataTable
          data={rows}
          onRowClick={(row) => navigate(`/opportunities/${row._id}`)}
          sortKey={sortField}
          sortDir={sortDir}
          onSort={handleSort}
          columns={[
            {
              key: "company",
              label: "Company",
              render: (row) => (
                <span className="text-text-primary" style={{ fontWeight: 510 }}>
                  {row.company as string}
                </span>
              ),
            },
            {
              key: "title",
              label: "Title",
              render: (row) => (
                <span className="text-text-secondary">{row.title as string}</span>
              ),
            },
            {
              key: "score",
              label: "Score",
              sortable: true,
              render: (row) => {
                const s = row.scoring as { overall: number; recommendation: "STRONG FIT" | "GOOD FIT" | "MARGINAL FIT" | "SKIP" } | null;
                return s ? (
                  <ScoreDisplay score={s.overall} recommendation={s.recommendation} />
                ) : (
                  <span className="text-text-subtle">--</span>
                );
              },
            },
            {
              key: "pipeline_state",
              label: "Status",
              render: (row) => <Badge status={row.pipeline_state as string} />,
            },
            {
              key: "work_type",
              label: "Work Arrangement",
              render: (row) => {
                const s = row.scoring as { work_arrangement?: string | null } | null;
                return (
                  <span className="text-text-muted">
                    {s?.work_arrangement ?? (row.work_type as string) ?? "--"}
                  </span>
                );
              },
            },
            {
              key: "date",
              label: "Date",
              sortable: true,
              render: (row) => (
                <span className="text-caption text-text-subtle">
                  {formatDate(row.created_at as string)}
                </span>
              ),
            },
          ]}
        />
      )}
    </div>
  );
}
