import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
} from "recharts";
import { Card } from "../components/Card";
import { Button } from "../components/Button";
import { StageIndicator } from "../components/StageIndicator";
import { Skeleton } from "../components/Skeleton";
import { EmptyState } from "../components/EmptyState";
import { useOpportunities } from "../hooks/useOpportunities";
import { usePipelineRuns, useSchedulerStatus, useCostSummary, useRunStage, useToggleScheduler } from "../hooks/usePipeline";
import type { PipelineState, Recommendation } from "../types";

const STAGES = ["harvest", "dedup", "score", "promote", "cover_letter"] as const;

type StageKey = (typeof STAGES)[number];

const stageBorderColors: Record<StageKey, string> = {
  harvest: "border-l-stage-harvest",
  dedup: "border-l-stage-dedup",
  score: "border-l-stage-score",
  promote: "border-l-stage-promote",
  cover_letter: "border-l-stage-coverletter",
};

/* Map pipeline_state to nearest pipeline stage for counting */
const stateToStage: Record<PipelineState, StageKey> = {
  harvested: "harvest",
  scored: "score",
  applied: "promote",
  active: "cover_letter",
  closed: "cover_letter",
};

const TIERS: Recommendation[] = ["STRONG FIT", "GOOD FIT", "MARGINAL FIT", "SKIP"];

const tierBarColors: Record<Recommendation, string> = {
  "STRONG FIT": "var(--color-tier-strong)",
  "GOOD FIT": "var(--color-tier-good)",
  "MARGINAL FIT": "var(--color-tier-marginal)",
  SKIP: "var(--color-tier-skip)",
};

export function Dashboard() {
  const opportunitiesQuery = useOpportunities();
  const runsQuery = usePipelineRuns();
  const schedulerQuery = useSchedulerStatus();
  const costQuery = useCostSummary();
  const runStage = useRunStage();
  const toggleSchedulerMut = useToggleScheduler();

  /* Count opportunities per stage */
  const stageCounts = useMemo(() => {
    const counts: Record<StageKey, number> = {
      harvest: 0,
      dedup: 0,
      score: 0,
      promote: 0,
      cover_letter: 0,
    };
    if (opportunitiesQuery.data?.items) {
      for (const opp of opportunitiesQuery.data.items) {
        const stage = stateToStage[opp.pipeline_state];
        if (stage) counts[stage]++;
      }
    }
    return counts;
  }, [opportunitiesQuery.data]);

  /* Latest run per stage */
  const latestRunByStage = useMemo(() => {
    const map: Partial<Record<string, { status: string; completed_at: string | null }>> = {};
    if (runsQuery.data?.items) {
      for (const run of runsQuery.data.items) {
        if (!map[run.stage]) {
          map[run.stage] = { status: run.status, completed_at: run.completed_at };
        }
      }
    }
    return map;
  }, [runsQuery.data]);

  /* Match distribution for chart */
  const matchDistribution = useMemo(() => {
    const counts: Record<Recommendation, number> = {
      "STRONG FIT": 0,
      "GOOD FIT": 0,
      "MARGINAL FIT": 0,
      SKIP: 0,
    };
    if (opportunitiesQuery.data?.items) {
      for (const opp of opportunitiesQuery.data.items) {
        const rec = opp.scoring?.recommendation;
        if (rec && rec in counts) counts[rec]++;
      }
    }
    return TIERS.map((tier) => ({ tier, count: counts[tier] }));
  }, [opportunitiesQuery.data]);

  const isLoading = opportunitiesQuery.isLoading || runsQuery.isLoading;

  return (
    <div className="space-y-8">
      <h1 className="text-h1 text-text-primary">Dashboard</h1>

      {/* Stage Cards Row */}
      <section>
        <h2 className="text-caption-lg text-text-muted mb-4">Pipeline Stages</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {STAGES.map((stage) => {
            const lastRun = latestRunByStage[stage === "score" ? "scoring" : stage === "promote" ? "promotion" : stage];
            return (
              <Card
                key={stage}
                borderColor={stageBorderColors[stage]}
                className="p-4"
              >
                <StageIndicator stage={stage} className="mb-3" />
                {isLoading ? (
                  <Skeleton className="h-8 w-16 mb-1" />
                ) : (
                  <p className="text-h2 text-text-primary">{stageCounts[stage]}</p>
                )}
                <p className="text-caption text-text-muted">opportunities</p>
                {lastRun && (
                  <p className="text-caption text-text-subtle mt-2">
                    Last run: {lastRun.status}
                  </p>
                )}
              </Card>
            );
          })}
        </div>
      </section>

      {/* Schedule Overview */}
      <section>
        <h2 className="text-caption-lg text-text-muted mb-4">Schedule Overview</h2>
        <Card className="p-5">
          {schedulerQuery.isLoading ? (
            <Skeleton className="h-6 w-48" />
          ) : schedulerQuery.data ? (
            <>
              {/* Scheduler status + master toggle */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${
                      schedulerQuery.data.enabled ? "bg-success" : "bg-text-subtle"
                    }`}
                  />
                  <span className="text-body-medium text-text-primary">
                    Scheduler {schedulerQuery.data.enabled ? "enabled" : "disabled"}
                  </span>
                </div>
                <button
                  onClick={() => toggleSchedulerMut.mutate(!schedulerQuery.data!.enabled)}
                  disabled={toggleSchedulerMut.isPending}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    schedulerQuery.data.enabled ? "bg-accent" : "bg-surface-05"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 rounded-full bg-text-primary transition-transform ${
                      schedulerQuery.data.enabled ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>

              {/* Active runs */}
              {schedulerQuery.data.active_runs.length > 0 && (
                <div className="mb-4 p-3 rounded-md bg-brand-tint-08 border border-accent/20">
                  <p className="text-caption-lg text-accent">
                    {schedulerQuery.data.active_runs.length} stage{schedulerQuery.data.active_runs.length > 1 ? "s" : ""} running...
                  </p>
                </div>
              )}

              {/* Scheduled jobs */}
              {schedulerQuery.data.jobs.length > 0 ? (
                <ul className="space-y-2 mb-4">
                  {schedulerQuery.data.jobs.map((job) => (
                    <li
                      key={job.id}
                      className="flex items-center justify-between py-1 border-b border-border-subtle"
                    >
                      <span className="text-small text-text-secondary">{job.id}</span>
                      <span className="text-caption text-text-subtle">
                        Next: {job.next_run === "paused" ? "paused" : new Date(job.next_run).toLocaleString()}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-caption text-text-subtle mb-4">No scheduled jobs.</p>
              )}

              {/* Recent runs */}
              {runsQuery.data && runsQuery.data.items.length > 0 && (
                <div className="mb-4">
                  <p className="text-caption-lg text-text-muted mb-2">Recent Runs</p>
                  <ul className="space-y-1">
                    {runsQuery.data.items.slice(0, 5).map((run) => (
                      <li
                        key={run._id}
                        className="flex items-center justify-between py-1 text-caption"
                      >
                        <span className="text-text-secondary capitalize">{run.stage}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-text-subtle">
                            {run.items_new > 0 ? `${run.items_new} new` : `${run.items_processed} processed`}
                          </span>
                          <span
                            className={`text-label ${
                              run.status === "completed"
                                ? "text-success"
                                : run.status === "running"
                                  ? "text-accent"
                                  : run.status === "skipped"
                                    ? "text-text-subtle"
                                    : "text-error"
                            }`}
                          >
                            {run.status}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Manual trigger buttons */}
              <div className="flex flex-wrap gap-2 pt-2 border-t border-border-subtle">
                {STAGES.map((stage) => (
                  <Button
                    key={stage}
                    variant="ghost"
                    size="sm"
                    onClick={() => runStage.mutate({ stage })}
                  >
                    Run {stage.replace("_", " ")}
                  </Button>
                ))}
              </div>
            </>
          ) : (
            <EmptyState
              title="Unavailable"
              description="Scheduler status could not be loaded."
            />
          )}
        </Card>
      </section>

      {/* Match Distribution */}
      <section>
        <h2 className="text-caption-lg text-text-muted mb-4">Match Distribution</h2>
        <Card className="p-5">
          {isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : matchDistribution.every((d) => d.count === 0) ? (
            <EmptyState
              title="No data"
              description="No scored opportunities yet."
            />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={matchDistribution} barCategoryGap="20%">
                <CartesianGrid
                  stroke="rgba(255,255,255,0.05)"
                  strokeDasharray="none"
                  vertical={false}
                />
                <XAxis
                  dataKey="tier"
                  tick={{ fill: "var(--color-text-subtle)", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: "var(--color-text-subtle)", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.03)" }}
                  contentStyle={{
                    backgroundColor: "var(--color-bg-surface)",
                    border: "1px solid var(--color-border-default)",
                    borderRadius: 8,
                    color: "var(--color-text-primary)",
                    fontSize: 13,
                  }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {matchDistribution.map((entry) => (
                    <Cell
                      key={entry.tier}
                      fill={tierBarColors[entry.tier]}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </section>

      {/* Cost Summary */}
      <section>
        <h2 className="text-caption-lg text-text-muted mb-4">Cost Summary (30 days)</h2>
        <Card className="p-5">
          {costQuery.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : costQuery.data ? (
            <>
              <ul className="space-y-2 mb-4">
                {Object.entries(costQuery.data.costs_by_task).map(([task, amount]) => (
                  <li
                    key={task}
                    className="flex items-center justify-between py-1 border-b border-border-subtle"
                  >
                    <span className="text-small text-text-secondary">{task}</span>
                    <span className="text-small-medium text-text-primary">
                      ${amount.toFixed(4)}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="flex items-center justify-between pt-2">
                <span className="text-body-medium text-text-primary">Total</span>
                <span className="text-body-medium text-text-primary">
                  $
                  {Object.values(costQuery.data.costs_by_task)
                    .reduce((sum, v) => sum + v, 0)
                    .toFixed(4)}
                </span>
              </div>
            </>
          ) : (
            <EmptyState
              title="Unavailable"
              description="Cost data could not be loaded."
            />
          )}
        </Card>
      </section>
    </div>
  );
}
