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
