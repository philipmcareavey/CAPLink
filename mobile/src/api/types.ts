// Mirrors the backend's own Pydantic schemas (app/schemas/*.py) — field
// names and shapes kept identical rather than renamed, so there's never a
// translation layer to keep in sync by hand.

// Matches app/models/enums.py::StudentBand's real values — kept as a plain
// string rather than a narrow union since the UI only ever formats it for
// display (never switches on a specific value), so there's no exhaustiveness
// risk if the backend adds another band later.
export type StudentBand = string;

export interface StudentProfile {
  id: string;
  degree_title: string;
  band: StudentBand;
  modules: string[];
  skills: string[];
  portfolio_urls: string[];
  hourly_rate_expectation_gbp: number | null;
  weekly_hours_available: number | null;
  is_id_verified: boolean;
  average_rating: number;
  completed_projects_count: number;
  on_time_rate: number;
  data_sharing_consent_at: string | null;
}

export type ProjectCategory = string;
export type ProjectStatus = 'open' | 'pending_review' | 'closed' | 'filled';

export interface ProjectWithMatch {
  id: string;
  business_id: string;
  title: string;
  description: string;
  category: ProjectCategory;
  required_skills: string[];
  duration_label: string;
  estimated_hours: number | null;
  hourly_rate_gbp: number;
  is_remote: boolean;
  location_label: string | null;
  status: ProjectStatus;
  match_score: number;
  match_reasons: string[];
}

export interface EmployerSuggestion {
  employer_type: string;
  reason: string;
}

export interface ApplicationOut {
  id: string;
  project_id: string;
  student_id: string;
  cover_note: string | null;
  proposed_rate_gbp: number | null;
  status: string;
  match_score_at_application: number | null;
}

export interface ConnectStatus {
  onboarded: boolean;
}

export type ApplicationStatus = 'submitted' | 'shortlisted' | 'interviewing' | 'offered' | 'accepted' | 'declined' | 'rejected' | 'withdrawn';

export interface ApplicantOut {
  application_id: string;
  student_id: string;
  student_user_id: string;
  full_name: string;
  degree_title: string;
  status: ApplicationStatus;
  cover_note: string | null;
  proposed_rate_gbp: number | null;
  match_score_at_application: number | null;
}

export interface StudentShortlistEntry {
  student_id: string;
  full_name: string;
  degree_title: string;
  university_name: string;
  average_rating: number;
  completed_projects_count: number;
  match_score: number;
  match_reasons: string[];
}

export interface MatchFactorOut {
  name: string;
  raw_score: number;
  weight: number;
  contribution: number;
  detail: string;
}

export interface MatchExplanationOut {
  score: number;
  algorithm_version: string;
  reasons: string[];
  breakdown: MatchFactorOut[];
}

export type MilestoneStatus = 'pending' | 'submitted' | 'approved' | 'paid' | 'disputed' | 'authorization_failed' | 'refunded' | 'rejected';

export interface MilestoneOut {
  id: string;
  description: string;
  due_date: string | null;
  payment_amount_gbp: number;
  status: MilestoneStatus;
  stripe_payment_intent_status: string | null;
  captured_at: string | null;
}

export type ContractStatus = 'active' | 'completed' | 'terminated' | 'disputed';
export type PaymentRail = 'self_employed' | 'paye_umbrella';

export interface ContractWithCounterpart {
  id: string;
  project_id: string;
  student_id: string;
  business_id: string;
  status: ContractStatus;
  ip_assignment_accepted: boolean;
  nda_accepted: boolean;
  payment_rail: PaymentRail;
  milestones: MilestoneOut[];
  project_title: string;
  counterpart_user_id: string;
  counterpart_name: string;
}

export interface ThreadSummaryOut {
  thread_id: string;
  project_id: string | null;
  counterpart_user_id: string;
  counterpart_name: string;
  last_message_preview: string | null;
  last_message_at: string | null;
  unread_count: number;
}

export interface MessageOut {
  id: string;
  thread_id: string;
  sender_user_id: string;
  content: string;
  is_flagged: boolean;
  is_read: boolean;
  created_at: string;
}

export type RatingVisibility = 'public' | 'private';

export interface RatingHistoryEntry {
  id: string;
  contract_id: string;
  counterpart_user_id: string;
  direction: 'given' | 'received';
  is_released: boolean;
  overall_score: number | null;
  sub_scores: Record<string, number> | null;
  visibility: RatingVisibility;
}

export interface LocalBusinessResult {
  business_id: string;
  company_name: string;
  industry: string | null;
  postcode: string | null;
  latitude: number;
  longitude: number;
  distance_miles: number;
  degree_relevance_score: number;
  degree_relevance_label: string;
  approved_categories: string[];
  average_rating: number;
  completed_projects_count: number;
}

export interface LocalSearchMeta {
  campus_name: string;
  campus_postcode: string | null;
  campus_latitude: number;
  campus_longitude: number;
  radius_miles: number;
  total_results: number;
}

export interface ProjectOut {
  id: string;
  business_id: string;
  title: string;
  description: string;
  category: string;
  required_skills: string[];
  duration_label: string;
  estimated_hours: number | null;
  hourly_rate_gbp: number;
  is_remote: boolean;
  location_label: string | null;
  status: 'open' | 'pending_review' | 'closed' | 'filled';
}

export interface AgreementWithUniversityOut {
  id: string;
  university_id: string;
  university_name: string;
  business_id: string;
  status: 'pending' | 'approved' | 'rejected' | 'suspended';
  allowed_bands: string[];
  allowed_categories: string[];
  max_active_projects: number | null;
  requires_university_project_review: boolean;
}

export interface NotificationPreferenceItem {
  template_key: string;
  label: string;
  enabled: boolean;
}

export interface NotificationPreferencesOut {
  preferences: NotificationPreferenceItem[];
}
