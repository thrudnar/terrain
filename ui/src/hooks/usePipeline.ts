import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchPipelineRuns,
  fetchSchedulerStatus,
  fetchCostSummary,
  runStage,
  toggleScheduler,
} from "../api/pipeline";

export function usePipelineRuns(limit = 50) {
  return useQuery({
    queryKey: ["pipelineRuns", limit],
    queryFn: () => fetchPipelineRuns("candidate_1", limit),
  });
}

export function useSchedulerStatus() {
  return useQuery({
    queryKey: ["schedulerStatus"],
    queryFn: fetchSchedulerStatus,
    refetchInterval: 5_000,
  });
}

export function useCostSummary(days = 30) {
  return useQuery({
    queryKey: ["costSummary", days],
    queryFn: () => fetchCostSummary(days),
  });
}

export function useRunStage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ stage }: { stage: string }) => runStage(stage),
    onSuccess: () => {
      // Refresh runs and status immediately so UI shows "running"
      qc.invalidateQueries({ queryKey: ["pipelineRuns"] });
      qc.invalidateQueries({ queryKey: ["schedulerStatus"] });
      // Delay opportunity refresh for when the run completes
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["opportunities"] });
        qc.invalidateQueries({ queryKey: ["pipelineRuns"] });
        qc.invalidateQueries({ queryKey: ["schedulerStatus"] });
      }, 5_000);
    },
  });
}

export function useToggleScheduler() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => toggleScheduler(enabled),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedulerStatus"] });
    },
  });
}
