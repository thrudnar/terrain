import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchOpportunities,
  fetchOpportunity,
  updateNotes,
  updateApplicationStatus,
  createOpportunity,
} from "../api/opportunities";
import type { OpportunityFilters } from "../types";

export function useOpportunities(filters: OpportunityFilters = {}) {
  return useQuery({
    queryKey: ["opportunities", filters],
    queryFn: () => fetchOpportunities(filters),
  });
}

export function useOpportunity(id: string) {
  return useQuery({
    queryKey: ["opportunity", id],
    queryFn: () => fetchOpportunity(id),
    enabled: !!id,
  });
}

export function useUpdateNotes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes: string }) =>
      updateNotes(id, notes),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["opportunity", id] });
    },
  });
}

export function useUpdateApplicationStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      updateApplicationStatus(id, status),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["opportunity", id] });
      qc.invalidateQueries({ queryKey: ["opportunities"] });
    },
  });
}

export function useCreateOpportunity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { company: string; title: string; description_text: string }) =>
      createOpportunity(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["opportunities"] });
    },
  });
}
