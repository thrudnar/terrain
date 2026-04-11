import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchInterestingCompanies,
  createInterestingCompany,
  updateInterestingCompany,
  deleteInterestingCompany,
} from "../api/interestingCompanies";

export function useInterestingCompanies() {
  return useQuery({
    queryKey: ["interestingCompanies"],
    queryFn: () => fetchInterestingCompanies(),
  });
}

export function useCreateInterestingCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { company_name: string; interest_drivers?: string[]; notes?: string }) =>
      createInterestingCompany(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["interestingCompanies"] });
    },
  });
}

export function useUpdateInterestingCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string; interest_drivers?: string[]; notes?: string }) =>
      updateInterestingCompany(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["interestingCompanies"] });
    },
  });
}

export function useDeleteInterestingCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteInterestingCompany(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["interestingCompanies"] });
    },
  });
}
