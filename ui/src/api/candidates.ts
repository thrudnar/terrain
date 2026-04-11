import { apiFetch } from "./client";
import type { AIRoutingConfig, Candidate } from "../types";

export function fetchCandidate(candidateId: string): Promise<Candidate> {
  return apiFetch(`/api/candidates/${candidateId}`);
}

export function updatePrompts(
  candidateId: string,
  prompts: { scoring?: string; cover_letter?: string; dedup?: string },
): Promise<{ status: string }> {
  return apiFetch(`/api/candidates/${candidateId}/prompts`, {
    method: "PATCH",
    body: JSON.stringify(prompts),
  });
}

export function fetchRouting(candidateId: string): Promise<AIRoutingConfig | null> {
  return apiFetch(`/api/candidates/${candidateId}/routing`);
}
