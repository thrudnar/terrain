import { apiFetch } from "./client";
import type {
  CostSummary,
  PipelineRun,
  PipelineRunListResponse,
  RunTriggeredResponse,
  SchedulerStatus,
  StageResult,
} from "../types";

export function runStage(
  stage: string,
  candidateId = "candidate_1",
  options?: Record<string, unknown>,
): Promise<RunTriggeredResponse> {
  return apiFetch(`/api/pipeline/${stage}/run`, {
    method: "POST",
    body: JSON.stringify({ candidate_id: candidateId, options }),
  });
}

export function runStageOne(
  stage: string,
  opportunityId: string,
  candidateId = "candidate_1",
): Promise<StageResult> {
  return apiFetch(`/api/pipeline/${stage}/run-one`, {
    method: "POST",
    body: JSON.stringify({ candidate_id: candidateId, opportunity_id: opportunityId }),
  });
}

export function fetchPipelineRuns(
  candidateId = "candidate_1",
  limit = 50,
): Promise<PipelineRunListResponse> {
  return apiFetch(`/api/pipeline/runs?candidate_id=${candidateId}&limit=${limit}`);
}

export function fetchPipelineRun(runId: string): Promise<PipelineRun> {
  return apiFetch(`/api/pipeline/runs/${runId}`);
}

export function fetchSchedulerStatus(): Promise<SchedulerStatus> {
  return apiFetch("/api/pipeline/status");
}

export function toggleScheduler(enabled: boolean): Promise<SchedulerStatus> {
  return apiFetch("/api/pipeline/scheduler/toggle", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
}

export function fetchCostSummary(
  days = 30,
  candidateId = "candidate_1",
): Promise<CostSummary> {
  return apiFetch(`/api/pipeline/costs?candidate_id=${candidateId}&days=${days}`);
}
