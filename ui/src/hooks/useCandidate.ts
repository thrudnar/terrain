import { useQuery } from "@tanstack/react-query";
import { fetchCandidate } from "../api/candidates";

export function useCandidate(candidateId = "candidate_1") {
  return useQuery({
    queryKey: ["candidate", candidateId],
    queryFn: () => fetchCandidate(candidateId),
  });
}
