import { useState, useEffect, useRef, useCallback, type ChangeEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card } from "../components/Card";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Select } from "../components/Select";
import { TextArea } from "../components/TextArea";
import { Skeleton } from "../components/Skeleton";
import { useOpportunity, useUpdateNotes, useUpdateApplicationStatus } from "../hooks/useOpportunities";
import { runStageOne } from "../api/pipeline";
import type { Application } from "../types";

const APPLICATION_STATUSES: Application["status"][] = [
  "new",
  "applied",
  "waiting",
  "phone_screen",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
  "dead",
];

export function OpportunityDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: opp, isLoading, isError } = useOpportunity(id ?? "");
  const updateNotes = useUpdateNotes();
  const updateAppStatus = useUpdateApplicationStatus();

  /* Notes with debounced autosave */
  const [localNotes, setLocalNotes] = useState("");
  const [notesSaved, setNotesSaved] = useState(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (opp?.notes !== undefined) setLocalNotes(opp.notes ?? "");
  }, [opp?.notes]);

  const handleNotesChange = useCallback(
    (e: ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      setLocalNotes(value);
      setNotesSaved(false);
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(() => {
        if (id) {
          updateNotes.mutate(
            { id, notes: value },
            { onSuccess: () => setNotesSaved(true) },
          );
        }
      }, 1000);
    },
    [id, updateNotes],
  );

  /* Collapsible job description */
  const [descExpanded, setDescExpanded] = useState(false);

  /* Cover letter regeneration */
  const [regenerating, setRegenerating] = useState(false);
  const handleRegenerate = async () => {
    if (!id) return;
    setRegenerating(true);
    try {
      await runStageOne("cover_letter", id);
    } finally {
      setRegenerating(false);
    }
  };

  /* Loading / error states */
  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-6 w-80" />
        <Skeleton className="h-64 w-full rounded-card" />
      </div>
    );
  }

  if (isError || !opp) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" onClick={() => navigate("/opportunities")}>
          &larr; Back
        </Button>
        <p className="text-body-lg text-text-muted">Opportunity not found.</p>
      </div>
    );
  }

  const scoring = opp.scoring;
  const coverLetter = opp.cover_letter;
  const application = opp.application;
  const errors = opp.errors;

  return (
    <div className="space-y-8">
      {/* Header */}
      <section>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/opportunities")}
          className="mb-4"
        >
          &larr; Back to list
        </Button>

        <div className="flex flex-wrap items-start gap-3">
          <div className="flex-1 min-w-0">
            <h1 className="text-h1 text-text-primary">{opp.company}</h1>
            <p className="text-body-lg text-text-secondary mt-1">{opp.title}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {scoring && <Badge tier={scoring.recommendation} />}
            <Badge status={opp.pipeline_state} />
          </div>
        </div>
      </section>

      {/* Job Description */}
      <Card className="p-5">
        <button
          type="button"
          onClick={() => setDescExpanded((v) => !v)}
          className="flex items-center gap-2 w-full text-left cursor-pointer"
        >
          <h2 className="text-h3 text-text-primary">Job Description</h2>
          <svg
            className={`w-4 h-4 text-text-muted transition-transform ${
              descExpanded ? "rotate-180" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {descExpanded && (
          <div className="mt-4 text-small text-text-secondary whitespace-pre-wrap">
            {opp.description_text}
          </div>
        )}
      </Card>

      {/* Match Assessment */}
      {scoring && (
        <Card className="p-5 space-y-5">
          <h2 className="text-h3 text-text-primary">Match Assessment</h2>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {(
              [
                ["Overall", scoring.overall],
                ["Skills", scoring.skills],
                ["Seniority", scoring.seniority],
                ["Work Type", scoring.work_type],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="text-center">
                <p className="text-h2 text-text-primary">{value}</p>
                <p className="text-caption text-text-muted">{label}</p>
              </div>
            ))}
          </div>

          <p className="text-small text-text-secondary">{scoring.match_summary}</p>

          {scoring.strengths.length > 0 && (
            <div>
              <p className="text-caption-lg text-text-muted mb-2">Strengths</p>
              <ul className="space-y-1">
                {scoring.strengths.map((s, i) => (
                  <li
                    key={i}
                    className="text-small px-3 py-1 rounded-standard bg-tier-strong-tint text-tier-strong"
                  >
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {scoring.gaps.length > 0 && (
            <div>
              <p className="text-caption-lg text-text-muted mb-2">Gaps</p>
              <ul className="space-y-1">
                {scoring.gaps.map((g, i) => (
                  <li
                    key={i}
                    className="text-small px-3 py-1 rounded-standard bg-tier-marginal-tint text-tier-marginal"
                  >
                    {g}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex items-center gap-3">
            <Badge tier={scoring.recommendation} />
            <span className="text-caption text-text-subtle">
              Prompt v{scoring.prompt_version}
            </span>
          </div>
        </Card>
      )}

      {/* Cover Letter */}
      {coverLetter && (
        <Card className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-h3 text-text-primary">Cover Letter</h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRegenerate}
              disabled={regenerating}
            >
              {regenerating ? "Regenerating..." : "Regenerate"}
            </Button>
          </div>

          <div className="border border-border-default rounded-card p-4 text-small text-text-secondary whitespace-pre-wrap">
            {coverLetter.content}
          </div>

          <div className="flex flex-wrap gap-4 text-caption text-text-subtle">
            <span>Prompt v{coverLetter.prompt_version}</span>
            <span>Model: {coverLetter.model}</span>
            <span>Method: {coverLetter.generation_method}</span>
            {coverLetter.skill_used && <span>Skill: {coverLetter.skill_used}</span>}
          </div>
        </Card>
      )}

      {/* Notes */}
      <Card className="p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-h3 text-text-primary">Notes</h2>
          {notesSaved && (
            <span className="text-caption text-text-subtle">Saved</span>
          )}
        </div>
        <TextArea
          value={localNotes}
          onChange={handleNotesChange}
          placeholder="Add notes about this opportunity..."
        />
      </Card>

      {/* Application Status */}
      {application && (
        <Card className="p-5 space-y-3">
          <h2 className="text-h3 text-text-primary">Application Status</h2>
          <Select
            value={application.status}
            options={APPLICATION_STATUSES.map((s) => ({ value: s, label: s }))}
            onChange={(e) => {
              if (id) updateAppStatus.mutate({ id, status: e.target.value });
            }}
          />
          {application.applied_date && (
            <p className="text-caption text-text-subtle">
              Applied: {new Date(application.applied_date).toLocaleDateString()}
            </p>
          )}
        </Card>
      )}

      {/* Error History */}
      {errors.length > 0 && (
        <Card className="p-5 space-y-3">
          <h2 className="text-h3 text-error">Error History</h2>
          <ul className="space-y-3">
            {errors.map((err, i) => (
              <li
                key={i}
                className="border border-border-subtle rounded-card p-3 space-y-1"
              >
                <div className="flex items-center gap-3 text-caption text-text-muted">
                  <span>Stage: {err.stage}</span>
                  <span>Type: {err.error_type}</span>
                </div>
                <p className="text-small text-text-secondary">{err.message}</p>
                <p className="text-caption text-text-subtle">
                  {new Date(err.occurred_at).toLocaleString()}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
