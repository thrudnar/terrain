/* TypeScript interfaces matching backend Pydantic models */

export interface Source {
  board: string;
  board_job_id: string;
  collection: string;
  url: string;
  first_seen: string;
  last_seen: string;
  posted_date: string | null;
}

export interface DedupResult {
  status: "unique" | "duplicate" | "repost_unchanged" | "repost_evolved";
  parent_id: string | null;
  checked_at: string;
  method: "exact" | "similarity";
  similarity_score: number | null;
}

export interface ScoringResult {
  prompt_version: string;
  model: string;
  overall: number;
  skills: number;
  seniority: number;
  work_type: number;
  work_arrangement: string | null;
  salary_range: string | null;
  match_summary: string;
  strengths: string[];
  gaps: string[];
  recommendation: "STRONG FIT" | "GOOD FIT" | "MARGINAL FIT" | "SKIP";
  reasoning: string;
  scored_at: string;
}

export interface Application {
  status: "new" | "applied" | "waiting" | "phone_screen" | "interview" | "offer" | "rejected" | "withdrawn" | "dead";
  applied_date: string | null;
  application_link: string | null;
  contact: string | null;
  resume_version: string | null;
  source: "harvested" | "manual";
}

export interface CoverLetter {
  prompt_version: string;
  model: string;
  content: string;
  generated_at: string;
  skill_used: string | null;
  generation_method: "batch" | "realtime";
}

export interface GmailEvent {
  gmail_message_id: string;
  subject: string;
  received_at: string;
  characterization: string;
}

export interface OpportunityError {
  stage: string;
  occurred_at: string;
  run_id: string | null;
  error_type: "rate_limit" | "api_error" | "parse_error" | "timeout" | "validation";
  message: string;
  retryable: boolean;
  resolved_at: string | null;
}

export type PipelineState = "harvested" | "scored" | "applied" | "active" | "closed";
export type Recommendation = "STRONG FIT" | "GOOD FIT" | "MARGINAL FIT" | "SKIP";

export interface Opportunity {
  _id: string | null;
  candidate_id: string;
  source: Source;
  company: string;
  title: string;
  location: string | null;
  work_type: string | null;
  description_text: string;
  description_hash: string | null;
  dedup: DedupResult | null;
  scoring: ScoringResult | null;
  application: Application | null;
  cover_letter: CoverLetter | null;
  notes: string | null;
  gmail_events: GmailEvent[];
  interesting_company_match: boolean;
  errors: OpportunityError[];
  pipeline_state: PipelineState;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface OpportunityListResponse {
  items: Opportunity[];
  count: number;
}

export interface Candidate {
  _id: string | null;
  candidate_id: string;
  name: string;
  active_prompts: {
    scoring: string;
    cover_letter: string;
    dedup: string;
  };
  prompt_history: Array<{
    type: string;
    version: string;
    activated: string;
    deactivated: string | null;
  }>;
  schedules: {
    harvest_linkedin: string | null;
    harvest_jobright: string | null;
    score_batch: string | null;
    cover_letter_batch: string | null;
  };
  ai_routing: AIRoutingConfig | null;
}

export interface AIRoutingConfig {
  scoring: AIRoutingEntry;
  cover_letter: AIRoutingEntry;
  dedup_similarity: AIRoutingEntry;
  email_classification: AIRoutingEntry | null;
}

export interface AIRoutingEntry {
  provider: string;
  model: string;
  skill: string | null;
}

export type PipelineStage = "harvest" | "dedup" | "scoring" | "promotion" | "cover_letter";
export type RunStatus = "running" | "completed" | "failed" | "skipped";

export interface PipelineRun {
  _id: string | null;
  candidate_id: string;
  stage: PipelineStage;
  source: string | null;
  started_at: string;
  completed_at: string | null;
  trigger: "scheduled" | "manual";
  items_processed: number;
  items_new: number;
  items_duplicate: number;
  items_error: number;
  prompt_version: string | null;
  batch_id: string | null;
  cost_usd: number;
  error_log: string[];
  status: RunStatus;
}

export interface PipelineRunListResponse {
  items: PipelineRun[];
  count: number;
}

export interface StageResult {
  stage: PipelineStage;
  items_processed: number;
  items_new: number;
  items_error: number;
  errors: string[];
  duration_seconds: number;
}

export interface RunTriggeredResponse {
  run_id: string;
  stage: string;
  status: string;
}

export interface SchedulerStatus {
  running: boolean;
  enabled: boolean;
  jobs: Array<{ id: string; next_run: string }>;
  active_runs: string[];
}

export interface CostSummary {
  costs_by_task: Record<string, number>;
  since: string;
}

export interface HealthResponse {
  status: string;
  environment: string;
  database: string;
  ollama: string;
  scheduler: string;
  uptime_seconds: number;
}

export interface InterestingCompany {
  _id: string | null;
  candidate_id: string;
  company_name: string;
  interest_drivers: string[];
  apprehensions: string[];
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface InterestingCompanyListResponse {
  items: InterestingCompany[];
  count: number;
}

export interface OpportunityFilters {
  pipeline_state?: PipelineState;
  recommendation?: Recommendation;
  work_arrangement?: string;
  company?: string;
  search_text?: string;
  archived?: boolean;
}
