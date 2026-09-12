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
}

export interface ScreeningBatch {
  id: number;
  job_id: number;
  status: string;
  total_resumes: number;
  processed: number;
  failed: number;
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
  status?: string | null;
  error_message?: string | null;
}

export type CandidateDecision = 'SHORTLIST' | 'REVIEW' | 'REJECT' | 'PRE_SCREENED_OUT' | null;

export interface ScreeningResultResponse extends ScreeningResult {
  display_name?: string | null;
}

export interface GlobalScreeningResultResponse extends ScreeningResultResponse {
  job_title: string;
  candidate_name?: string | null;
}

export interface Interview {
  id: number;
  job_id: number;
  resume_id: number;
  status: string;
  transcript?: string | null;
  evaluation?: any | null;
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
}

export interface BatchProgressResponse {
  job_id: number;
  batches: BatchProgressDetail[];
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
  status: 'PENDING' | 'SENT' | 'FAILED';
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
  org_name?: string | null;
  min_candidates_to_screen?: number | null;
  max_candidates_to_screen?: number | null;
  semantic_gap_threshold?: number | null;
  auto_email_on_shortlist: boolean;
  shortlist_email_template_id?: number | null;
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
  resend: { configured: boolean; detail: { from_email: string | null } };
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
}

// ---------------------------------------------------------------------------
// Emails (additions)
// ---------------------------------------------------------------------------
export type EmailTemplateUpdate = Partial<EmailTemplateCreate>;

export interface EmailMessageGlobalResponse extends EmailMessage {
  job_title?: string | null;
  candidate_name?: string | null;
}
