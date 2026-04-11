import { apiFetch } from "./client";
import type { InterestingCompanyListResponse } from "../types";

export function fetchInterestingCompanies(
  candidateId = "candidate_1",
): Promise<InterestingCompanyListResponse> {
  return apiFetch(`/api/interesting-companies?candidate_id=${candidateId}`);
}

export function createInterestingCompany(
  data: { company_name: string; interest_drivers?: string[]; apprehensions?: string[]; notes?: string },
  candidateId = "candidate_1",
): Promise<{ id: string }> {
  return apiFetch(`/api/interesting-companies?candidate_id=${candidateId}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateInterestingCompany(
  id: string,
  data: { interest_drivers?: string[]; apprehensions?: string[]; notes?: string },
  candidateId = "candidate_1",
): Promise<{ status: string }> {
  return apiFetch(`/api/interesting-companies/${id}?candidate_id=${candidateId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteInterestingCompany(
  id: string,
  candidateId = "candidate_1",
): Promise<void> {
  return apiFetch(`/api/interesting-companies/${id}?candidate_id=${candidateId}`, {
    method: "DELETE",
  });
}
