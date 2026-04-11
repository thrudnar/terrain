import { apiFetch } from "./client";
import type {
  Opportunity,
  OpportunityFilters,
  OpportunityListResponse,
} from "../types";

export function fetchOpportunities(
  filters: OpportunityFilters = {},
  candidateId = "candidate_1",
): Promise<OpportunityListResponse> {
  const params = new URLSearchParams({ candidate_id: candidateId });
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  return apiFetch<OpportunityListResponse>(`/api/opportunities?${params}`);
}

export function fetchOpportunity(
  id: string,
  candidateId = "candidate_1",
): Promise<Opportunity> {
  return apiFetch<Opportunity>(
    `/api/opportunities/${id}?candidate_id=${candidateId}`,
  );
}

export function updateNotes(
  id: string,
  notes: string,
  candidateId = "candidate_1",
): Promise<{ status: string }> {
  return apiFetch(`/api/opportunities/${id}/notes?candidate_id=${candidateId}`, {
    method: "PATCH",
    body: JSON.stringify({ notes }),
  });
}

export function updateApplicationStatus(
  id: string,
  status: string,
  candidateId = "candidate_1",
): Promise<{ status: string }> {
  return apiFetch(
    `/api/opportunities/${id}/application?candidate_id=${candidateId}`,
    { method: "PATCH", body: JSON.stringify({ status }) },
  );
}

export function createOpportunity(
  data: { company: string; title: string; description_text: string; location?: string; url?: string },
  candidateId = "candidate_1",
): Promise<{ id: string }> {
  return apiFetch(`/api/opportunities?candidate_id=${candidateId}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}
