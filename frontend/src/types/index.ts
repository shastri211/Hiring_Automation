export interface Job {
  id: number;
  title: string;
  description: string;
  department?: string | null;
  location?: string | null;
  employment_type?: string | null;
  requirements?: string[] | null;
  required_skills: string[];
  preferred_skills: string[];
  experience: Record<string, any>;
  education: Record<string, any>;
  hard_constraints: Record<string, any>;
  status?: string;
  /** AI-structured summary of `description` (from job_profile). Falls back to
   * `description` in the UI when null (older jobs, or profiling failure). */
  role_summary?: string | null;
  responsibilities?: string[] | null;
  /** Public candidate apply link token - null when applications are closed. */
  application_token?: string | null;
  /** Full /apply/<token> URL; null when closed or PUBLIC_APP_BASE_URL is unset. */
  application_url?: string | null;
}

export interface Resume {
  id: number;
  batch_id?: number | null;
  job_id: number;
  filename: string;
  file_hash: string;
  storage_key: string;
  status: string;
  workflow_stage?: string | null;
  extracted_text?: string | null;
  error_message?: string | null;
}

export interface CandidateProfile {
  id: number;
  resume_id: number;
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  summary?: string | null;
  total_experience_years?: number | null;
  education?: any[] | null;
  experience?: any[] | null;
  projects?: any[] | null;
  skills?: string[] | null;
  certifications?: any[] | null;
  languages?: string[] | null;
  achievements?: any[] | null;
}

export interface ScreeningResult {
  id?: number | null;
  job_id: number;
  resume_id: number;
  score?: number | null;
  semantic_score?: number | null;
  strengths?: string[] | null;
  gaps?: string[] | null;
  evidence?: string[] | null;
  decision?: CandidateDecision; // e.g., 'SHORTLIST', 'REVIEW', 'REJECT'
  notes?: string | null;
  /** When the screening result row was created (returned by the API). */
  created_at?: string | null;
  status?: string | null;
  error_message?: string | null;
}

export type CandidateDecision = 'SHORTLIST' | 'REVIEW' | 'REJECT' | 'PRE_SCREENED_OUT' | null;

export interface ScreeningResultResponse extends ScreeningResult {
  display_name?: string | null;
  // Phase 6 (backend): the canonical Candidate this resume resolves to
  // (following any merge), and how many jobs they've applied to in total.
  candidate_id?: number | null;
  applications_count?: number | null;
  // Phase 8 (backend): this resume's own unresolved candidate id - use this,
  // not candidate_id, to check/undo THIS resume's merge state (candidate_id
  // is always the canonical survivor, whose merged_into_id is always null).
  // Only populated by the single-resume detail endpoint.
  raw_candidate_id?: number | null;
  // True when this is the placeholder result from every LLM provider
  // failing for this one candidate (a transient outage) - offers a "Retry
  // Evaluation" action instead of showing it as a genuine (if empty) outcome.
  evaluation_failed?: boolean;
}

export interface GlobalScreeningResultResponse extends ScreeningResultResponse {
  job_title: string;
  candidate_name?: string | null;
}

export interface Interview {
  id: number;
  job_id: number;
  resume_id: number;
  // PENDING | SCHEDULED | IN_PROGRESS | COMPLETED | FAILED |
  // RESCHEDULE_PENDING | NO_SHOW | DECLINED
  status: string;
  transcript?: string | null;
  evaluation?: InterviewEvaluationData | null;
  /** Latest-attempt-only classified outcome (verbatim call_disposition, or "manual_decline"). */
  outcome?: string | null;
  /** Number of retries consumed so far, capped by the backend's INTERVIEW_MAX_RETRY_ATTEMPTS. */
  retry_count?: number;

  // Dograh browser/web-interview provider fields (A10).
  provider?: string | null;
  provider_run_id?: string | null;
  public_token?: string | null;
  link_expires_at?: string | null;
  transcript_url?: string | null;
  recording_url?: string | null;
  scheduled_at?: string | null;
  completed_at?: string | null;
  /** Pre-built full candidate-facing interview URL (null until public_token + PUBLIC_APP_BASE_URL are set). */
  interview_link?: string | null;
}

// Canonical Dograh evaluation envelope (see app/services/interview.py::_normalize_evaluation_data).
// Legacy/unrecognized evaluation JSON won't match this shape - always check `source` before relying on it.
// Mirrors the flat shape app/services/interview.py::_normalize_evaluation_data
// stores Interview.evaluation as - no gathered_context/cost_info/source
// wrapper, every field directly at the top level.
export interface InterviewEvaluationData {
  workflow_run_id?: string | number | null;
  transcript_url?: string | null;
  recording_url?: string | null;
  user_recording_url?: string | null;
  bot_recording_url?: string | null;
  call_duration_seconds?: number | null;
  call_disposition?: string | null;
  years_relevant_experience?: string | null;
  key_skills_mentioned?: string | null;
  notice_period?: string | null;
  salary_expectation?: string | null;
  motivation_summary?: string | null;
  concerns_or_gaps?: string | null;
  // Added alongside the interview-prompt review - assessed by the LLM from
  // the conversation itself, not just captured facts.
  communication_clarity?: string | null;
  demonstrated_skill_depth?: string | null;
  interview_recommendation?: string | null;
}

// GET /public/interview/{token}
export interface PublicInterviewRoomResponse {
  candidate_name: string;
  job_title: string;
  dograh_base_url: string | null;
  dograh_widget_base_url: string | null;
  dograh_embed_token: string | null;
  dograh_environment: string | null;
  dograh_api_endpoint: string | null;
  initial_context: {
    job_id: number;
    resume_id: number;
    interview_id: number;
    candidate_name: string;
    candidate_summary: string;
    job_title: string;
    job_requirements: string;
  };
}

export type PublicInterviewErrorReason = 'not_found' | 'expired' | 'already_completed' | 'closed';

// GET /public/jobs/{token}
export interface PublicJobResponse {
  title: string;
  role_summary?: string | null;
  responsibilities: string[];
  description: string;
}

export type PublicApplyErrorReason =
  | 'not_found'
  | 'closed'
  | 'rate_limited'
  | 'temporarily_unavailable'
  | 'invalid_file'
  | 'consent_required'
  | 'invalid_email'
  | 'invalid_name'
  | 'invalid_phone';

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
export type UserRole = 'admin' | 'member';

export interface UserResponse {
  id: number;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string | null;
}

/** GET /auth/me and POST /auth/login - the logged-in user plus their
 * organization and account flags. */
export interface MeResponse extends UserResponse {
  organization: { id: number; name: string };
  is_platform_admin: boolean;
  must_change_password: boolean;
}

export interface SignupRequest {
  company_name: string;
  name: string;
  email: string;
  password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface UserUpdate {
  role?: UserRole;
  is_active?: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserCreate {
  email: string;
  password: string;
  name: string;
}

// API Error handling interface
export interface ApiError {
  message: string;
  code?: string;
  status?: number;
  details?: any;
}

// Pagination response
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// Upload Response
export interface UploadResponse {
  message: string;
  batch_id: number;
  job_id: number;
  accepted_files: number;
  duplicate_files: number;
  invalid_files: number;
  /** ZIP uploads only: a corrupt/unreadable entry inside an otherwise-valid archive. Always 0 for non-ZIP requests. */
  failed_files: number;
}

// Progress Responses
export interface BatchProgressDetail {
  batch_id: number;
  status: string;
  total: number;
  processing: number;
  completed: number;
  failed: number;
  shortlisted: number;
  review: number;
  rejected: number;
  pre_screened_out?: number;
  batch_type: 'UPLOAD' | 'SCREEN' | 'APPLICATION';
}

export interface BatchProgressResponse {
  job_id: number;
  batches: BatchProgressDetail[];
  // READY resumes of this job with no screening result yet.
  unscreened: number;
}

export interface JobBatchOverviewItem {
  job_id: number;
  job_title: string;
  job_status?: string | null;
  batch_id: number;
  batch_status: string;
  total: number;
  processed: number;
  failed: number;
  created_at?: string | null;
  batch_type: 'UPLOAD' | 'SCREEN' | 'APPLICATION';
}

// Candidate Profile Detail
export interface CandidateProfileDetail {
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  summary?: string | null;
  total_experience_years?: number | null;
  education?: any | null;
  experience?: any | null;
  skills?: any | null;
  projects?: any | null;
  certifications?: any | null;
  languages?: any | null;
  achievements?: any | null;
}

export interface CandidateDetailResponse {
  resume_id: number;
  filename: string;
  status: string;
  error_message?: string | null;
  profile?: CandidateProfileDetail | null;
  screening?: ScreeningResultResponse | null;
  interview?: Interview | null;
  /** Only for resumes submitted via the public apply link: what the candidate
   * typed into the form - unverified, never merged into the extracted profile. */
  self_reported_contact?: SelfReportedContact | null;
}

export interface SelfReportedContact {
  name: string;
  email: string;
  phone?: string | null;
  submitted_at: string;
}

export interface ScreeningResultsParams {
  decision?: CandidateDecision;
  min_score?: number;
  max_score?: number;
  status?: string;
  sort_by?: string;
  page?: number;
  page_size?: number;
}

export interface IntegrationResponse {
  success: boolean;
  message: string;
}

// ---------------------------------------------------------------------------
// Candidate identity / deduplication (mirrors app/schemas/candidate.py)
// ---------------------------------------------------------------------------
export interface CandidateResponse {
  id: number;
  canonical_name?: string | null;
  primary_email?: string | null;
  primary_phone?: string | null;
  // Non-null means this candidate has been merged away and is no longer
  // canonical - merged_into_name is resolved server-side for display only.
  merged_into_id?: number | null;
  merged_into_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CandidateNameUpdateRequest {
  canonical_name: string | null;
}

export interface CandidateSummary {
  id: number;
  canonical_name?: string | null;
  primary_email?: string | null;
  primary_phone?: string | null;
  applications_count: number;
}

export type MatchSuggestionStatus = 'PENDING' | 'MERGED' | 'REJECTED';

// Mirrors CandidateMatchSuggestionResponse - the actual response shape of
// POST .../merge and .../reject, which return the bare suggestion row with
// no candidate context (unlike the list endpoint below).
export interface CandidateMatchSuggestionResponse {
  id: number;
  resume_id: number;
  candidate_a_id: number;
  candidate_b_id: number;
  confidence: number;
  signals?: Record<string, unknown> | null;
  status: MatchSuggestionStatus;
  reviewed_by?: number | null;
  reviewed_at?: string | null;
  created_at?: string | null;
}

// Mirrors CandidateMatchSuggestionDetailResponse - GET .../match-suggestions'
// actual shape, adding the candidate/resume context a reviewer needs.
export interface CandidateMatchSuggestion extends CandidateMatchSuggestionResponse {
  // candidate_a is always the pre-existing candidate, candidate_b the newer
  // one created for resume_id - merging always absorbs b into a.
  candidate_a: CandidateSummary;
  candidate_b: CandidateSummary;
  resume_filename?: string | null;
  job_id?: number | null;
  job_title?: string | null;
}

export interface MergeCandidatesRequest {
  absorbed_candidate_id: number;
  into_candidate_id: number;
}

export interface UnmergeCandidateResponse {
  absorbed_candidate_id: number;
  into_candidate_id: number;
  reverted_at: string;
}

export interface EmailTemplate {
  id: number;
  name: string;
  subject: string;
  body_content: string;
  created_at: string;
  updated_at?: string;
}

export interface EmailTemplateCreate {
  name: string;
  subject: string;
  body_content: string;
}

export interface EmailMessage {
  id: number;
  job_id: number;
  resume_id: number;
  template_id?: number;
  subject: string;
  body_content: string;
  status: 'PENDING' | 'SENT' | 'SIMULATED' | 'FAILED' | 'BLOCKED';
  provider_message_id?: string;
  error_message?: string;
  created_at: string;
  sent_at?: string;
}

export interface BulkEmailRequest {
  resume_ids: number[];
  template_id: number;
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
export interface AppSettingsResponse {
  id: number;
  /** The organization's own name (admin-editable via PATCH /settings/). */
  organization_name?: string | null;
  min_candidates_to_screen?: number | null;
  max_candidates_to_screen?: number | null;
  semantic_gap_threshold?: number | null;
  auto_email_on_shortlist: boolean;
  shortlist_email_template_id?: number | null;
  auto_generate_interview_on_shortlist: boolean;
  auto_email_on_interview_scheduled: boolean;
  interview_scheduled_email_template_id?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export type AppSettingsUpdate = Partial<Omit<AppSettingsResponse, 'id' | 'created_at' | 'updated_at'>>;

// ---------------------------------------------------------------------------
// Integrations
// ---------------------------------------------------------------------------
export interface IntegrationsStatusResponse {
  smtp: { configured: boolean; detail: { from_email: string | null; host: string | null } };
  dograh: {
    configured: boolean;
    detail: {
      base_url: string | null;
      embed_token_set: boolean;
      webhook_secret_set: boolean;
      public_app_url: string | null;
    };
  };
}

// ---------------------------------------------------------------------------
// Talent Pool
// ---------------------------------------------------------------------------
export interface TalentPoolEntry {
  id: number;
  resume_id: number;
  added_from_job_id?: number | null;
  tags: string[];
  notes?: string | null;
  added_at?: string | null;
  updated_at?: string | null;
  display_name?: string | null;
  email?: string | null;
  phone?: string | null;
  job_id?: number | null;
  job_title?: string | null;
  candidate_id?: number | null;
  applications_count?: number | null;
}

export interface TalentPoolEntryCreate {
  resume_id: number;
  added_from_job_id?: number | null;
  tags?: string[];
  notes?: string | null;
}

export interface TalentPoolEntryUpdate {
  tags?: string[];
  notes?: string | null;
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------
export interface FunnelResponse {
  job_id?: number | null;
  uploaded: number;
  processed: number;
  screened: number;
  shortlisted: number;
  interviewed: number;
  completed: number;
}

export interface DecisionCount {
  decision?: string | null;
  count: number;
}

export interface DecisionBreakdownResponse {
  items: DecisionCount[];
  total: number;
}

export interface ThroughputPoint {
  date: string;
  count: number;
}

export interface ThroughputResponse {
  items: ThroughputPoint[];
}

export interface TimeInStageResponse {
  resume_to_screened_seconds_approx?: number | null;
  screened_to_interview_seconds_approx?: number | null;
}

export interface JobVolumeItem {
  job_id: number;
  job_title: string;
  resume_count: number;
}

export interface JobVolumeResponse {
  items: JobVolumeItem[];
}

// ---------------------------------------------------------------------------
// Global Interviews
// ---------------------------------------------------------------------------
export interface GlobalInterviewResponse extends Interview {
  created_at?: string | null;
  updated_at?: string | null;
  job_title: string;
  candidate_name?: string | null;
  resume_filename?: string | null;
}

// ---------------------------------------------------------------------------
// Interview Analysis
// ---------------------------------------------------------------------------
export interface InterviewAnalysisSummaryResponse {
  job_id?: number | null;
  total_interviews: number;
  completed_interviews: number;
  completion_rate: number;
  avg_call_duration_seconds?: number | null;
  disposition_breakdown: Record<string, number>;
}

export interface InterviewAnalysisItem {
  id: number;
  job_id: number;
  resume_id: number;
  status: string;
  job_title: string;
  candidate_name?: string | null;
  source: string;
  workflow_run_id?: string | null;
  call_disposition: string;
  gathered_context: Record<string, any>;
  cost_info: Record<string, any>;
  user_recording_url?: string | null;
  bot_recording_url?: string | null;
  created_at?: string | null;
  interview_recommendation?: string | null;
  communication_clarity?: string | null;
  demonstrated_skill_depth?: string | null;
}

// ---------------------------------------------------------------------------
// Emails (additions)
// ---------------------------------------------------------------------------
export type EmailTemplateUpdate = Partial<EmailTemplateCreate>;

export interface EmailMessageGlobalResponse extends EmailMessage {
  job_title?: string | null;
  candidate_name?: string | null;
}
