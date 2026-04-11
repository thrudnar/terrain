import { useState, useCallback, type ChangeEvent } from "react";
import { Card } from "../components/Card";
import { Button } from "../components/Button";
import { TextArea } from "../components/TextArea";
import { Skeleton } from "../components/Skeleton";
import { EmptyState } from "../components/EmptyState";
import {
  useInterestingCompanies,
  useCreateInterestingCompany,
  useDeleteInterestingCompany,
} from "../hooks/useInterestingCompanies";

export function InterestingCompanies() {
  const { data, isLoading } = useInterestingCompanies();
  const createMutation = useCreateInterestingCompany();
  const deleteMutation = useDeleteInterestingCompany();

  /* Inline add form */
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState("");
  const [formDrivers, setFormDrivers] = useState("");
  const [formNotes, setFormNotes] = useState("");

  const resetForm = useCallback(() => {
    setFormName("");
    setFormDrivers("");
    setFormNotes("");
    setShowForm(false);
  }, []);

  const handleSubmit = useCallback(() => {
    if (!formName.trim()) return;
    const drivers = formDrivers
      .split(",")
      .map((d) => d.trim())
      .filter(Boolean);
    createMutation.mutate(
      {
        company_name: formName.trim(),
        interest_drivers: drivers.length > 0 ? drivers : undefined,
        notes: formNotes.trim() || undefined,
      },
      { onSuccess: resetForm },
    );
  }, [formName, formDrivers, formNotes, createMutation, resetForm]);

  const handleDelete = useCallback(
    (id: string, name: string) => {
      if (window.confirm(`Delete "${name}" from interesting companies?`)) {
        deleteMutation.mutate(id);
      }
    },
    [deleteMutation],
  );

  const handleNotesChange = useCallback((e: ChangeEvent<HTMLTextAreaElement>) => {
    setFormNotes(e.target.value);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-h1 text-text-primary">Interesting Companies</h1>
        <Button
          variant="primary"
          size="md"
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? "Cancel" : "Add Company"}
        </Button>
      </div>

      {/* Inline Add Form */}
      {showForm && (
        <Card className="p-5 space-y-4">
          <div>
            <label className="text-caption-lg text-text-muted block mb-1">
              Company Name
            </label>
            <input
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="Acme Corp"
              className="w-full bg-surface-02 text-text-secondary placeholder:text-text-subtle border border-border-default rounded-comfortable px-3 py-2 text-small focus:border-accent focus:outline-none"
            />
          </div>

          <div>
            <label className="text-caption-lg text-text-muted block mb-1">
              Interest Drivers (comma-separated)
            </label>
            <input
              type="text"
              value={formDrivers}
              onChange={(e) => setFormDrivers(e.target.value)}
              placeholder="mission, tech stack, team"
              className="w-full bg-surface-02 text-text-secondary placeholder:text-text-subtle border border-border-default rounded-comfortable px-3 py-2 text-small focus:border-accent focus:outline-none"
            />
          </div>

          <div>
            <label className="text-caption-lg text-text-muted block mb-1">
              Notes
            </label>
            <TextArea
              value={formNotes}
              onChange={handleNotesChange}
              placeholder="Why this company interests you..."
            />
          </div>

          <Button
            variant="primary"
            size="md"
            onClick={handleSubmit}
            disabled={!formName.trim() || createMutation.isPending}
          >
            {createMutation.isPending ? "Saving..." : "Save Company"}
          </Button>
        </Card>
      )}

      {/* Table */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded-card" />
          ))}
        </div>
      ) : !data?.items.length ? (
        <EmptyState
          title="No companies"
          description="No interesting companies yet. Add one to get started."
        />
      ) : (
        <div className="border border-border-default rounded-card overflow-hidden">
          {/* Header */}
          <div className="grid grid-cols-[1fr_1fr_2fr_auto] bg-surface-03 px-3 py-2 text-caption-lg text-text-muted">
            <span>Company</span>
            <span>Interest Drivers</span>
            <span>Notes</span>
            <span className="w-16" />
          </div>

          {/* Rows */}
          {data.items.map((company) => (
            <div
              key={company._id ?? company.company_name}
              className="grid grid-cols-[1fr_1fr_2fr_auto] items-center px-3 py-2 border-t border-border-subtle hover:bg-surface-02 transition-colors"
            >
              <span className="text-small text-text-primary" style={{ fontWeight: 510 }}>
                {company.company_name}
              </span>
              <span className="text-small text-text-secondary">
                {company.interest_drivers.join(", ") || "--"}
              </span>
              <span className="text-small text-text-muted truncate">
                {company.notes ?? "--"}
              </span>
              <div className="w-16 flex justify-end">
                <Button
                  variant="subtle"
                  size="sm"
                  onClick={() => handleDelete(company._id ?? "", company.company_name)}
                  disabled={deleteMutation.isPending}
                >
                  Delete
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
