import { EmptyState } from "../components/EmptyState";

export function PromptComparison() {
  return (
    <div className="space-y-6">
      <h1 className="text-h1 text-text-primary">A/B Prompt Comparison</h1>
      <EmptyState
        title="Coming soon"
        description="Prompt comparison coming soon -- requires opportunities scored with multiple prompt versions."
      />
    </div>
  );
}
