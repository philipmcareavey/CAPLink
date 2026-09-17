# Mobile Student & Business Flows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Workstream 6.b — every remaining CAPLink mobile screen for both the student and business roles, all against the real live staging API.

**Architecture:** Straight-port screens that already translate (Ratings, the post-project form) using the existing `FeedScreen.tsx`/`ApplyModal.tsx` patterns; genuinely redesign navigation for screens that don't (Messaging, Contracts, the business Projects tab, Local Search) into real native-stack screen flows nested inside the existing bottom-tab navigators. Two small, additive backend changes unblock the mobile work: exposing lat/lon on local-business-search results, and a new "my agreements" endpoint a business needs to know which universities it can post projects to (the web app's equivalent flow has a real pre-existing bug — see Task 2 — not something to copy).

**Tech Stack:** React Native 0.87.1 + TypeScript (existing), `@react-navigation` native-stack + bottom-tabs (existing), new: `react-native-maps` (runtime), `@testing-library/react-native` (dev-only). Backend: FastAPI + SQLAlchemy (existing, two small additive endpoints).

**Spec:** `caplink/docs/superpowers/specs/2026-09-17-mobile-student-business-flows-design.md`

## Global Constraints

- Every mobile screen makes real calls to the live staging API (`API_BASE = 'https://caplink-api.onrender.com/api/v1'` in `mobile/src/api/client.ts`) via `useAuth().authedApi()` — never a mock server, matching this project's existing convention.
- Design tokens are fixed, copied verbatim from `FeedScreen.tsx`/`ApplyModal.tsx` — do not invent new ones: background `#F6F3EC`, card `#FFFDF8`, border `#DDD6C7`, ink `#1B2A45`, ink-soft `#3C4B68`, danger `#A6452F`, brass/badge `#A87C2A`, moss/reason-chip background `#DCE6DD` text `#4C6B54`.
- Every screen follows the existing loading/refresh/error pattern: a centered `ActivityIndicator` (`color="#1B2A45"`) while the initial load is in flight, `RefreshControl` for pull-to-refresh, an inline error card on failure (catch `ApiError`, fall back to a generic message otherwise) — copy `FeedScreen.tsx`'s exact structure, don't invent a new one.
- State/data-fetching: local component state (`useState`/`useCallback`/`useEffect`) + refetch on focus or after a mutating action. No new state-management library.
- `ContractsStack` and `MessagesStack` screens are genuinely shared between roles — one component tree under `mobile/src/screens/shared/`, reading `useAuth().state` where behavior differs by role (never two near-duplicate files).
- `RatingsScreen` is wired into `StudentTabs` only, matching the web app's own `BUSINESS_TABS` (which has no ratings tab either, per `static/app/js/business.js`) — business-side rating happens inline from `ContractDetailScreen`'s "Rate" action, not a dedicated tab.
- The Google Maps API key already exists in `mobile/android/local.properties` (git-ignored) as `MAPS_API_KEY=...` — every task that touches it references it only via a Gradle manifest placeholder (`${MAPS_API_KEY}` / `manifestPlaceholders`), never reads, prints, or re-types the literal key value anywhere, including in commit messages or test output.
- Frontend tests use `@testing-library/react-native` (Task 4), mocking `authedApi`/`api` at the module level — assert on rendered output and on the arguments of calls made after an interaction, not on internal component state. Matches the existing web `static/app/js/*.test.js` pattern and `mobile/__tests__/App.test.tsx`'s existing (minimal) precedent.
- Backend tests extend existing e2e test files in place (`tests/test_local_search_e2e.py`) rather than creating parallel new files, matching this project's established convention.
- **No dedicated "update the tracker/CLAUDE.md" task exists in this plan.** Phil asked to keep both updated continuously as work lands — that happens outside this plan's own task loop (the controller updates them after each task completes, not as a plan step), unlike Workstream 9's dedicated Task 13. Don't add one.
- Commit after every task. Never batch multiple tasks into one commit.

---

## Task 1: Backend — expose coordinates on local-business-search results

**Files:**
- Modify: `app/schemas/local_search.py`
- Modify: `app/api/v1/endpoints/local_search.py`
- Test: `tests/test_local_search_e2e.py` (extend, don't create a new file)

**Interfaces:**
- Produces: `LocalBusinessResult.latitude: float`, `.longitude: float`; `LocalSearchMeta.campus_latitude: float`, `.campus_longitude: float` — consumed by Task 10's `LocalSearchMapScreen`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_local_search_e2e.py`:

```python
def test_local_search_results_include_coordinates_for_map_rendering(client):
    university_id = _seed_university(client, slug="mapcoorduni", domain="mapcoorduni.ac.uk")
    _set_campus_location(client, university_id, MANCHESTER_LAT, MANCHESTER_LON)

    _register_business(client, email="mapped-business@example.com")
    _seed_approved_business(
        client,
        business_user_email="mapped-business@example.com",
        university_id=university_id,
        bands=[StudentBand.YEAR_3.value],
        categories=[ProjectCategory.SOFTWARE_ENGINEERING.value],
        lat=MANCHESTER_LAT,
        lon=MANCHESTER_LON,
    )

    student_token = _register_student(
        client, university_slug="mapcoorduni", email="map-searcher@mapcoorduni.ac.uk"
    )

    search = client.get(
        f"/api/v1/universities/{university_id}/local-businesses?radius_miles=10",
        headers=_auth(student_token),
    )
    assert search.status_code == 200, search.text
    results = search.json()
    assert len(results) == 1
    assert results[0]["latitude"] == MANCHESTER_LAT
    assert results[0]["longitude"] == MANCHESTER_LON

    meta = client.get(
        f"/api/v1/universities/{university_id}/local-businesses/meta?radius_miles=10",
        headers=_auth(student_token),
    )
    assert meta.status_code == 200, meta.text
    assert meta.json()["campus_latitude"] == MANCHESTER_LAT
    assert meta.json()["campus_longitude"] == MANCHESTER_LON
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_local_search_e2e.py::test_local_search_results_include_coordinates_for_map_rendering -v`
Expected: FAIL — `KeyError: 'latitude'` (the field doesn't exist in the response yet).

- [ ] **Step 3: Add the fields to both schemas**

In `app/schemas/local_search.py`, add to `LocalBusinessResult` (after `postcode`):

```python
    latitude: float
    longitude: float
```

Add to `LocalSearchMeta` (after `campus_postcode`):

```python
    campus_latitude: float
    campus_longitude: float
```

- [ ] **Step 4: Populate the fields in the endpoint**

In `app/api/v1/endpoints/local_search.py`, inside `get_local_businesses`'s `LocalBusinessResult(...)` construction, add:

```python
                latitude=business.latitude,
                longitude=business.longitude,
```

(Right after `postcode=business.postcode,` — the values are already guaranteed non-null by the earlier `.filter(BusinessProfile.latitude.isnot(None), BusinessProfile.longitude.isnot(None))` query.)

In `get_local_search_meta`'s `LocalSearchMeta(...)` construction, add:

```python
        campus_latitude=university.latitude,
        campus_longitude=university.longitude,
```

(The function already 400s earlier if `university.latitude`/`longitude` is `None`, via the check inside `get_local_businesses` it calls — but that check only runs if `get_local_businesses` is called with a non-empty result path. Re-read `get_local_search_meta`'s current body: it calls `get_local_businesses(...)` first, which itself checks `university.latitude is None` and raises before returning — so by the time `LocalSearchMeta(...)` is constructed here, both are guaranteed non-null.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_local_search_e2e.py -v`
Expected: PASS — both the new test and the existing `test_local_search_filters_by_radius_band_and_returns_meta`.

- [ ] **Step 6: Run the full backend test suite**

Run: `pytest -x -q`
Expected: PASS, 0 failures (this is a pure additive schema change).

- [ ] **Step 7: Commit**

```bash
git add app/schemas/local_search.py app/api/v1/endpoints/local_search.py tests/test_local_search_e2e.py
git commit -m "$(cat <<'EOF'
Expose lat/lon on local-business-search results (Workstream 6.b)

The backend already computes these (haversine_distance_miles reads
business/university latitude+longitude directly) but never returned
them — a map view can't place a marker from a distance alone. Pure
schema addition: no migration, no behavior change for the existing
web app, which ignores unknown response fields.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Backend — "my agreements" endpoint for businesses

**Files:**
- Modify: `app/schemas/policy.py`
- Modify: `app/api/v1/endpoints/businesses.py`
- Test: `tests/test_agreements_and_audit_log_e2e.py` (extend — this is the existing file covering agreement-related HTTP behavior)

**Interfaces:**
- Produces: `GET /businesses/me/agreements` → `list[AgreementWithUniversityOut]` (fields: `id`, `university_id`, `university_name`, `status`, `allowed_bands`, `allowed_categories`) — consumed by Task 11's `PostProjectScreen`.

Why this task exists (not in the original spec — discovered while planning Task 11): a business posting a project needs to know which university IDs it has an approved agreement with. The web app's `wirePostProjectForm()` (`static/app/js/business.js`) currently does `api('/universities/${slug}/public', ...).then(uni => uni.id)` — but `GET /universities/{slug}/public` returns `UniversityPublicBranding`, which has **no `id` field at all** (confirmed by reading `app/schemas/university.py` directly). That's a real, pre-existing bug in the web app — `uni.id` is `undefined` there today. Copying it into the new mobile screen would ship a known-broken flow. The correct fix is a real endpoint a business can call to see its own agreements (mirroring `ContractWithCounterpart`'s existing pattern of extending an `Out` schema with one extra joined field to avoid a second round trip) — not a web-app bugfix, which is out of scope for this plan.

- [ ] **Step 1: Write the failing test**

Read `tests/test_agreements_and_audit_log_e2e.py` first to find its existing helper functions (`_register_business`, `_seed_university`, `_auth`, and whatever it uses to create an approved agreement) and match their exact signatures. Then append:

```python
def test_business_can_list_its_own_agreements_with_university_names(client):
    university_id = _seed_university(client, slug="myagreementsuni", domain="myagreementsuni.ac.uk")
    business_token = _register_business(client, email="my-agreements-business@example.com")

    _approve_agreement(
        client,
        business_user_email="my-agreements-business@example.com",
        university_id=university_id,
        bands=["year_3"],
        categories=["data_analytics"],
    )

    resp = client.get("/api/v1/businesses/me/agreements", headers=_auth(business_token))
    assert resp.status_code == 200, resp.text
    agreements = resp.json()
    assert len(agreements) == 1
    assert agreements[0]["university_id"] == university_id
    assert agreements[0]["university_name"] == "myagreementsuni"  # _seed_university's own naming — verify against the actual helper
    assert agreements[0]["status"] == "approved"
    assert agreements[0]["allowed_categories"] == ["data_analytics"]


def test_business_agreements_list_only_shows_its_own(client):
    university_id = _seed_university(client, slug="otherbizuni", domain="otherbizuni.ac.uk")
    _register_business(client, email="business-a@example.com")
    _approve_agreement(
        client, business_user_email="business-a@example.com", university_id=university_id,
        bands=["year_3"], categories=["data_analytics"],
    )
    business_b_token = _register_business(client, email="business-b@example.com")

    resp = client.get("/api/v1/businesses/me/agreements", headers=_auth(business_b_token))
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
```

If `_seed_university`'s actual signature doesn't set `name` to the slug verbatim, adjust the first test's `university_name` assertion to match whatever it actually does — read the helper before writing the assertion, don't guess.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_agreements_and_audit_log_e2e.py::test_business_can_list_its_own_agreements_with_university_names -v`
Expected: FAIL — `404 Not Found` (the route doesn't exist yet).

- [ ] **Step 3: Add the response schema**

In `app/schemas/policy.py`, add after `AgreementOut`:

```python
class AgreementWithUniversityOut(AgreementOut):
    """AgreementOut plus the university's name, so a business browsing its
    own agreements (e.g. to pick a target for a new project) doesn't need
    a second round trip per agreement — same pattern as
    ContractWithCounterpart in app/schemas/contract.py."""
    university_name: str
```

- [ ] **Step 4: Add the endpoint**

In `app/api/v1/endpoints/businesses.py`, add the imports needed (check the file's current imports first — it will already have `require_business`, `get_db`, `Session`, `BusinessProfile`; you'll additionally need `UniversityBusinessAgreement` from `app.models.policy` and `University` from `app.models.university`, plus `AgreementWithUniversityOut` from `app.schemas.policy`), then:

```python
@router.get("/me/agreements", response_model=list[AgreementWithUniversityOut])
def get_my_agreements(db: Session = Depends(get_db), business_user: User = Depends(require_business)):
    """Every agreement this business holds, across every university —
    lets the mobile/web post-project flow show real, valid targets
    instead of guessing a university id from a slug lookup."""
    business = db.query(BusinessProfile).filter(BusinessProfile.user_id == business_user.id).first()
    assert business is not None, "require_business guarantees a BusinessProfile row exists"

    rows = (
        db.query(UniversityBusinessAgreement, University.name)
        .join(University, University.id == UniversityBusinessAgreement.university_id)
        .filter(UniversityBusinessAgreement.business_id == business.id)
        .all()
    )
    return [
        AgreementWithUniversityOut(
            id=agreement.id,
            university_id=agreement.university_id,
            business_id=agreement.business_id,
            status=agreement.status,
            allowed_bands=agreement.allowed_bands,
            allowed_categories=agreement.allowed_categories,
            max_active_projects=agreement.max_active_projects,
            requires_university_project_review=agreement.requires_university_project_review,
            university_name=university_name,
        )
        for agreement, university_name in rows
    ]
```

Place this route **before** any existing `/{business_id}`-shaped route in the same router if one exists (check the file) — FastAPI matches routes in registration order, and a literal `/me/agreements` must be registered before a path-parameter route that could otherwise swallow it. If the file only has `/me` (GET/PATCH) today with no `/{business_id}` route, ordering doesn't matter; add it after the existing `/me` PATCH handler.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_agreements_and_audit_log_e2e.py -v`
Expected: PASS, including both new tests and every pre-existing test in the file.

- [ ] **Step 6: Run the full backend test suite**

Run: `pytest -x -q`
Expected: PASS, 0 failures.

- [ ] **Step 7: Commit**

```bash
git add app/schemas/policy.py app/api/v1/endpoints/businesses.py tests/test_agreements_and_audit_log_e2e.py
git commit -m "$(cat <<'EOF'
Add GET /businesses/me/agreements (Workstream 6.b)

The mobile post-project screen needs a real way to know which
universities a business has an approved agreement with. The web
app's equivalent flow resolves this via a slug lookup against
GET /universities/{slug}/public, which returns UniversityPublicBranding
— a schema with no id field at all, so uni.id there is genuinely
undefined today. This is a correct fix, not a copy of that bug:
a business's own agreements already carry university_id directly.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Mobile — TypeScript types for every new API shape

**Files:**
- Modify: `mobile/src/api/types.ts`

**Interfaces:**
- Produces: every interface listed below — consumed by every subsequent mobile task.

- [ ] **Step 1: Append the new interfaces**

Append to `mobile/src/api/types.ts` (these mirror the backend Pydantic schemas field-for-field, same convention the existing interfaces in this file already follow — read the file's current top-of-file comment first to match its style exactly):

```typescript
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
```

- [ ] **Step 2: Verify it compiles**

Run: `cd mobile && npx tsc --noEmit`
Expected: no new errors (pure additive interfaces — nothing consumes them yet, so this just proves the syntax is valid TypeScript).

- [ ] **Step 3: Commit**

```bash
cd mobile
git add src/api/types.ts
git commit -m "$(cat <<'EOF'
Add TypeScript types for every remaining mobile screen's API shapes (Workstream 6.b)

Mirrors the backend Pydantic schemas field-for-field, same convention
the existing types in this file already follow. Nothing consumes
these yet — every subsequent task in this plan does.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Mobile — testing infrastructure (`@testing-library/react-native`)

**Files:**
- Modify: `mobile/package.json`
- Modify: `mobile/__tests__/App.test.tsx` (verify it still passes, no content change expected)

**Interfaces:**
- Produces: `render`, `screen`, `fireEvent`, `waitFor` from `@testing-library/react-native` — consumed by every subsequent mobile screen task's test.

- [ ] **Step 1: Install the dependency**

```bash
cd mobile
npm install --save-dev @testing-library/react-native
```

- [ ] **Step 2: Write a smoke test proving the library works against this app's actual setup**

Create `mobile/src/components/__tests__/Chip.test.tsx` (the simplest existing component, good for proving the harness works before using it on anything complex):

```typescript
import React from 'react';
import { render, screen } from '@testing-library/react-native';
import { Chip } from '../Chip';

test('renders the given label', () => {
  render(<Chip label="Python" />);
  expect(screen.getByText('Python')).toBeTruthy();
});

test('applies reason styling when tone is "reason"', () => {
  render(<Chip label="Within budget" tone="reason" />);
  expect(screen.getByText('Within budget')).toBeTruthy();
});
```

- [ ] **Step 3: Run it**

Run: `cd mobile && npx jest src/components/__tests__/Chip.test.tsx`
Expected: PASS, 2/2.

- [ ] **Step 4: Run the full existing mobile test suite to confirm no regressions**

Run: `cd mobile && npx jest`
Expected: PASS — the pre-existing `App.test.tsx` plus the 2 new tests.

- [ ] **Step 5: Commit**

```bash
cd mobile
git add package.json package-lock.json src/components/__tests__/Chip.test.tsx
git commit -m "$(cat <<'EOF'
Add @testing-library/react-native (dev-only) for the upcoming screen tests (Workstream 6.b)

Dev-only dependency, zero production footprint. The app currently
has exactly one smoke test via bare react-test-renderer — with 10+
new interactive screens coming, a query-based testing API is worth
it, matching this project's "test coverage matters" pattern
everywhere else.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Mobile — ProfileScreen (student)

**Files:**
- Create: `mobile/src/screens/student/ProfileScreen.tsx`
- Test: `mobile/src/screens/student/__tests__/ProfileScreen.test.tsx`
- Modify: `mobile/src/navigation/StudentTabs.tsx`

**Interfaces:**
- Consumes: `useAuth().authedApi` (`mobile/src/context/AuthContext.tsx`), `StudentProfile` (`mobile/src/api/types.ts`, already exists), `Chip` (`mobile/src/components/Chip.tsx`).
- Produces: `ProfileScreen` component — wired as `StudentTabs`'s new `"Profile"` tab.

- [ ] **Step 1: Write the failing test**

```typescript
// mobile/src/screens/student/__tests__/ProfileScreen.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ProfileScreen } from '../ProfileScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const PROFILE = {
  id: 'sp-1', degree_title: 'BSc Data Science', band: 'year_3',
  modules: ['Statistics II'], skills: ['Python', 'SQL'], portfolio_urls: [],
  hourly_rate_expectation_gbp: 20, weekly_hours_available: 10, is_id_verified: true,
  average_rating: 4.8, completed_projects_count: 3, on_time_rate: 1.0,
  data_sharing_consent_at: '2026-01-01T00:00:00Z',
};

function mockAuthedApi(impl: (path: string, opts?: any) => Promise<any>) {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(impl) });
}

test('loads and displays the student profile', async () => {
  mockAuthedApi(async (path) => {
    if (path === '/students/me') return PROFILE;
    throw new Error(`unexpected call: ${path}`);
  });
  render(<ProfileScreen />);
  await waitFor(() => expect(screen.getByText('BSc Data Science')).toBeTruthy());
  expect(screen.getByText('Python')).toBeTruthy();
  expect(screen.getByText('SQL')).toBeTruthy();
});

test('editing skills sends a PATCH and reflects the update', async () => {
  const authedApi = jest.fn(async (path: string, opts?: any) => {
    if (path === '/students/me' && (!opts || opts.method === undefined)) return PROFILE;
    if (path === '/students/me' && opts?.method === 'PATCH') {
      return { ...PROFILE, skills: ['Python', 'SQL', 'React'] };
    }
    throw new Error(`unexpected call: ${path} ${JSON.stringify(opts)}`);
  });
  mockedUseAuth.mockReturnValue({ authedApi });

  render(<ProfileScreen />);
  await waitFor(() => expect(screen.getByText('BSc Data Science')).toBeTruthy());

  fireEvent.changeText(screen.getByTestId('profile-skills-input'), 'Python, SQL, React');
  fireEvent.press(screen.getByTestId('profile-save'));

  await waitFor(() => expect(screen.getByText('React')).toBeTruthy());
  expect(authedApi).toHaveBeenCalledWith('/students/me', {
    method: 'PATCH',
    body: { skills: ['Python', 'SQL', 'React'] },
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mobile && npx jest src/screens/student/__tests__/ProfileScreen.test.tsx`
Expected: FAIL — `Cannot find module '../ProfileScreen'`.

- [ ] **Step 3: Write the implementation**

```typescript
// mobile/src/screens/student/ProfileScreen.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { StudentProfile } from '../../api/types';
import { Chip } from '../../components/Chip';

// Split out of FeedScreen's embedded profile card (per the design spec —
// a dedicated tab reads better on mobile than one long scrolling Feed
// screen with profile+feed+suggestions stacked).
export function ProfileScreen() {
  const { authedApi } = useAuth();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [skillsInput, setSkillsInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await authedApi<StudentProfile>('/students/me');
      setProfile(data);
      setSkillsInput(data.skills.join(', '));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong loading your profile.');
    }
  }, [authedApi]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await load();
      setLoading(false);
    })();
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const save = async () => {
    const skills = skillsInput.split(',').map((s) => s.trim()).filter(Boolean);
    setSaving(true);
    try {
      const updated = await authedApi<StudentProfile>('/students/me', { method: 'PATCH', body: { skills } });
      setProfile(updated);
      setSkillsInput(updated.skills.join(', '));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not save your profile.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      {profile ? (
        <View style={styles.card}>
          <Text style={styles.h1}>{profile.degree_title}</Text>
          <Text style={styles.muted}>
            {profile.band.replace(/_/g, ' ')} · ★ {profile.average_rating.toFixed(1)} ({profile.completed_projects_count} completed)
          </Text>
          <View style={styles.chipsRow}>
            {profile.skills.map((skill) => (
              <Chip key={skill} label={skill} />
            ))}
          </View>

          <Text style={styles.label}>Skills (comma separated)</Text>
          <TextInput
            style={styles.input}
            value={skillsInput}
            onChangeText={setSkillsInput}
            testID="profile-skills-input"
          />

          <TouchableOpacity style={styles.saveButton} onPress={save} disabled={saving} testID="profile-save">
            <Text style={styles.saveButtonText}>{saving ? 'Saving…' : 'Save'}</Text>
          </TouchableOpacity>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  h1: { fontSize: 20, fontWeight: '700', color: '#1B2A45', marginBottom: 4 },
  muted: { fontSize: 13, color: '#3C4B68', marginTop: 4 },
  errorText: { color: '#A6452F' },
  chipsRow: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 10 },
  label: { fontSize: 12, fontWeight: '600', color: '#3C4B68', marginTop: 16, marginBottom: 6 },
  input: { borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 10 },
  saveButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 10, alignItems: 'center', marginTop: 14 },
  saveButtonText: { color: '#FFFDF8', fontWeight: '600', fontSize: 13 },
});
```

- [ ] **Step 4: Wire it into `StudentTabs`**

In `mobile/src/navigation/StudentTabs.tsx`, add the import and a new tab (this is a genuinely new tab, not replacing a placeholder — the web app embeds profile inside Feed, but per the design spec this app gets its own tab):

```typescript
import { ProfileScreen } from '../screens/student/ProfileScreen';
```

```typescript
      <Tab.Screen name="Feed" component={FeedScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
      <Tab.Screen name="Contracts" children={() => <PlaceholderScreen title="Contracts" />} />
```

(Insert the new `Tab.Screen` line right after `Feed`, before `Contracts` — leave `Contracts`/`Messages`/`Local`/`Ratings` as placeholders, later tasks replace those.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd mobile && npx jest src/screens/student/__tests__/ProfileScreen.test.tsx`
Expected: PASS, 2/2.

- [ ] **Step 6: Run the full mobile test suite**

Run: `cd mobile && npx jest`
Expected: PASS, no regressions.

- [ ] **Step 7: Commit**

```bash
cd mobile
git add src/screens/student/ProfileScreen.tsx src/screens/student/__tests__/ProfileScreen.test.tsx src/navigation/StudentTabs.tsx
git commit -m "$(cat <<'EOF'
Add student ProfileScreen, its own tab (Workstream 6.b.i)

Split out of the web app's Feed-embedded profile card per the design
spec — a dedicated screen reads better on mobile than one long
scrolling Feed with profile+feed+suggestions stacked. Real GET/PATCH
/students/me calls, no mocking.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Mobile — Messaging (ThreadsListScreen + ChatScreen + MessagesStack)

**Files:**
- Create: `mobile/src/screens/shared/ThreadsListScreen.tsx`
- Create: `mobile/src/screens/shared/ChatScreen.tsx`
- Create: `mobile/src/navigation/MessagesStack.tsx`
- Test: `mobile/src/screens/shared/__tests__/ThreadsListScreen.test.tsx`
- Test: `mobile/src/screens/shared/__tests__/ChatScreen.test.tsx`
- Modify: `mobile/src/navigation/StudentTabs.tsx`
- Modify: `mobile/src/navigation/BusinessTabs.tsx`

**Interfaces:**
- Consumes: `ThreadSummaryOut`, `MessageOut` (Task 3).
- Produces: `MessagesStack` component (a `createNativeStackNavigator()` with routes `"Threads"` and `"Chat"`, the latter taking a `{ threadId: string }` param) — consumed by Task 7 (Contracts' "Message" button) and Task 12 (business Applicant "Message" button) via `navigation.navigate('Messages', { screen: 'Chat', params: { threadId } })`.

- [ ] **Step 1: Write the failing tests**

```typescript
// mobile/src/screens/shared/__tests__/ThreadsListScreen.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ThreadsListScreen } from '../ThreadsListScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const THREADS = [
  { thread_id: 't-1', project_id: 'p-1', counterpart_user_id: 'u-2', counterpart_name: 'Northbridge Analytics', last_message_preview: 'Looking forward!', last_message_at: '2026-09-17T10:00:00Z', unread_count: 2 },
];

test('renders threads with an unread badge', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => THREADS) });
  const navigate = jest.fn();
  render(<ThreadsListScreen navigation={{ navigate } as any} />);
  await waitFor(() => expect(screen.getByText('Northbridge Analytics')).toBeTruthy());
  expect(screen.getByText('2')).toBeTruthy();
});

test('tapping a thread navigates to Chat with its id', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => THREADS) });
  const navigate = jest.fn();
  render(<ThreadsListScreen navigation={{ navigate } as any} />);
  await waitFor(() => screen.getByText('Northbridge Analytics'));
  fireEvent.press(screen.getByText('Northbridge Analytics'));
  expect(navigate).toHaveBeenCalledWith('Chat', { threadId: 't-1' });
});
```

```typescript
// mobile/src/screens/shared/__tests__/ChatScreen.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ChatScreen } from '../ChatScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const MESSAGES = [
  { id: 'm-1', thread_id: 't-1', sender_user_id: 'me', content: 'Hi!', is_flagged: false, is_read: true, created_at: '2026-09-17T10:00:00Z' },
  { id: 'm-2', thread_id: 't-1', sender_user_id: 'other', content: 'Just call me on 07911 123456', is_flagged: true, is_read: false, created_at: '2026-09-17T10:01:00Z' },
];

function routeWith(threadId: string) {
  return { params: { threadId } } as any;
}

test('renders messages, flags the flagged one, and sends a new one', async () => {
  const authedApi = jest.fn(async (path: string, opts?: any) => {
    if (path === '/messages/threads/t-1' && !opts) return MESSAGES;
    if (path === '/messages' && opts?.method === 'POST') {
      return { id: 'm-3', thread_id: 't-1', sender_user_id: 'me', content: opts.body.content, is_flagged: false, is_read: true, created_at: '2026-09-17T10:02:00Z' };
    }
    throw new Error(`unexpected call: ${path} ${JSON.stringify(opts)}`);
  });
  mockedUseAuth.mockReturnValue({ authedApi, state: { status: 'signedIn', claims: { sub: 'me' } } });

  render(<ChatScreen route={routeWith('t-1')} />);
  await waitFor(() => expect(screen.getByText('Hi!')).toBeTruthy());
  expect(screen.getByText(/07911 123456/)).toBeTruthy();
  expect(screen.getByTestId('flag-m-2')).toBeTruthy();

  fireEvent.changeText(screen.getByTestId('chat-input'), 'Sounds good');
  fireEvent.press(screen.getByTestId('chat-send'));

  await waitFor(() => expect(authedApi).toHaveBeenCalledWith('/messages', { method: 'POST', body: { thread_id: 't-1', content: 'Sounds good' } }));
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mobile && npx jest src/screens/shared/__tests__/ThreadsListScreen.test.tsx src/screens/shared/__tests__/ChatScreen.test.tsx`
Expected: FAIL — both modules don't exist yet.

- [ ] **Step 3: Write `ThreadsListScreen`**

```typescript
// mobile/src/screens/shared/ThreadsListScreen.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { ThreadSummaryOut } from '../../api/types';

// Web is one page swapping a thread list and a chat panel via JS — mobile
// is two real screens (this one, pushing ChatScreen). Shared between both
// roles: a business's threads look identical in shape to a student's.
export function ThreadsListScreen({ navigation }: { navigation: { navigate: (screen: string, params: { threadId: string }) => void } }) {
  const { authedApi } = useAuth();
  const [threads, setThreads] = useState<ThreadSummaryOut[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setThreads(await authedApi<ThreadSummaryOut[]>('/messages/threads'));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong loading your messages.');
    }
  }, [authedApi]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await load();
      setLoading(false);
    })();
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}
      <FlatList
        data={threads ?? []}
        keyExtractor={(t) => t.thread_id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={<Text style={styles.emptyText}>No conversations yet — start one from an applicant or a contract card.</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row} onPress={() => navigation.navigate('Chat', { threadId: item.thread_id })}>
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{item.counterpart_name}</Text>
              <Text style={styles.preview} numberOfLines={1}>{item.last_message_preview ?? 'No messages yet'}</Text>
            </View>
            {item.unread_count > 0 ? (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{item.unread_count}</Text>
              </View>
            ) : null}
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  errorText: { color: '#A6452F' },
  emptyText: { color: '#3C4B68', textAlign: 'center', margin: 24, fontSize: 13 },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFFDF8', borderBottomWidth: 1, borderBottomColor: '#DDD6C7', padding: 16 },
  name: { fontSize: 15, fontWeight: '700', color: '#1B2A45' },
  preview: { fontSize: 13, color: '#3C4B68', marginTop: 2 },
  badge: { backgroundColor: '#A87C2A', borderRadius: 10, minWidth: 20, height: 20, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 5, marginLeft: 10 },
  badgeText: { color: '#FFFDF8', fontSize: 11, fontWeight: '700' },
});
```

- [ ] **Step 4: Write `ChatScreen`**

```typescript
// mobile/src/screens/shared/ChatScreen.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { MessageOut } from '../../api/types';

export function ChatScreen({ route }: { route: { params: { threadId: string } } }) {
  const { threadId } = route.params;
  const { authedApi, state } = useAuth();
  const myUserId = state.status === 'signedIn' ? state.claims.sub : null;
  const [messages, setMessages] = useState<MessageOut[] | null>(null);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setMessages(await authedApi<MessageOut[]>(`/messages/threads/${threadId}`));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load this conversation.');
    }
  }, [authedApi, threadId]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await load();
      setLoading(false);
    })();
  }, [load]);

  const send = async () => {
    if (!draft.trim()) return;
    setSending(true);
    try {
      const sent = await authedApi<MessageOut>('/messages', { method: 'POST', body: { thread_id: threadId, content: draft } });
      setMessages((prev) => [...(prev ?? []), sent]);
      setDraft('');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not send that message.');
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error ? (
        <View style={styles.errorBar}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}
      <FlatList
        data={messages ?? []}
        keyExtractor={(m) => m.id}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => {
          const mine = item.sender_user_id === myUserId;
          return (
            <View style={[styles.bubble, mine ? styles.mine : styles.theirs]}>
              <Text style={mine ? styles.mineText : styles.theirsText}>{item.content}</Text>
              {item.is_flagged ? (
                <Text style={styles.flagText} testID={`flag-${item.id}`}>
                  ⚠ This message may reference off-platform contact
                </Text>
              ) : null}
            </View>
          );
        }}
      />
      <View style={styles.composeRow}>
        <TextInput
          style={styles.input}
          value={draft}
          onChangeText={setDraft}
          placeholder="Type a message…"
          testID="chat-input"
        />
        <TouchableOpacity style={styles.sendButton} onPress={send} disabled={sending} testID="chat-send">
          <Text style={styles.sendButtonText}>Send</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  errorBar: { backgroundColor: '#FFFDF8', padding: 10 },
  errorText: { color: '#A6452F' },
  list: { padding: 12 },
  bubble: { maxWidth: '80%', borderRadius: 10, padding: 10, marginBottom: 8 },
  mine: { backgroundColor: '#1B2A45', alignSelf: 'flex-end' },
  theirs: { backgroundColor: '#FFFDF8', borderWidth: 1, borderColor: '#DDD6C7', alignSelf: 'flex-start' },
  mineText: { color: '#FFFDF8' },
  theirsText: { color: '#1B2A45' },
  flagText: { color: '#A6452F', fontSize: 11, marginTop: 6 },
  composeRow: { flexDirection: 'row', padding: 10, backgroundColor: '#FFFDF8', borderTopWidth: 1, borderTopColor: '#DDD6C7' },
  input: { flex: 1, borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 10, marginRight: 8 },
  sendButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingHorizontal: 16, justifyContent: 'center' },
  sendButtonText: { color: '#FFFDF8', fontWeight: '600' },
});
```

- [ ] **Step 5: Write `MessagesStack`**

```typescript
// mobile/src/navigation/MessagesStack.tsx
import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ThreadsListScreen } from '../screens/shared/ThreadsListScreen';
import { ChatScreen } from '../screens/shared/ChatScreen';

export type MessagesStackParamList = {
  Threads: undefined;
  Chat: { threadId: string };
};

const Stack = createNativeStackNavigator<MessagesStackParamList>();

export function MessagesStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="Threads" component={ThreadsListScreen} options={{ title: 'Messages' }} />
      <Stack.Screen name="Chat" component={ChatScreen} options={{ title: 'Conversation' }} />
    </Stack.Navigator>
  );
}
```

- [ ] **Step 6: Wire it into both tab navigators**

In `mobile/src/navigation/StudentTabs.tsx`:

```typescript
import { MessagesStack } from '../navigation/MessagesStack';
```

Replace `<Tab.Screen name="Messages" children={() => <PlaceholderScreen title="Messages" />} />` with:

```typescript
      <Tab.Screen name="Messages" component={MessagesStack} options={{ headerShown: false }} />
```

In `mobile/src/navigation/BusinessTabs.tsx`, same import and same replacement of its `Messages` placeholder line.

(`headerShown: false` on the tab wrapper avoids a double header — `MessagesStack`'s own `Stack.Navigator` already renders headers per-screen.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd mobile && npx jest src/screens/shared/__tests__/ThreadsListScreen.test.tsx src/screens/shared/__tests__/ChatScreen.test.tsx`
Expected: PASS, 4/4 total.

- [ ] **Step 8: Run the full mobile test suite**

Run: `cd mobile && npx jest`
Expected: PASS, no regressions.

- [ ] **Step 9: Commit**

```bash
cd mobile
git add src/screens/shared/ThreadsListScreen.tsx src/screens/shared/ChatScreen.tsx src/screens/shared/__tests__/ThreadsListScreen.test.tsx src/screens/shared/__tests__/ChatScreen.test.tsx src/navigation/MessagesStack.tsx src/navigation/StudentTabs.tsx src/navigation/BusinessTabs.tsx
git commit -m "$(cat <<'EOF'
Add mobile messaging: ThreadsList -> Chat, shared across both roles (Workstream 6.b)

Real native-stack navigation replacing the web app's single
morphing page. Chat renders the off-platform-contact flag inline
instead of hiding it. Wired into both StudentTabs and BusinessTabs —
one component tree, no per-role duplication.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Mobile — Contracts (ContractsListScreen + ContractDetailScreen + ContractsStack)

**Files:**
- Create: `mobile/src/screens/shared/ContractsListScreen.tsx`
- Create: `mobile/src/screens/shared/ContractDetailScreen.tsx`
- Create: `mobile/src/components/RateModal.tsx`
- Create: `mobile/src/navigation/ContractsStack.tsx`
- Test: `mobile/src/screens/shared/__tests__/ContractsListScreen.test.tsx`
- Test: `mobile/src/screens/shared/__tests__/ContractDetailScreen.test.tsx`
- Modify: `mobile/src/navigation/StudentTabs.tsx`
- Modify: `mobile/src/navigation/BusinessTabs.tsx`

**Interfaces:**
- Consumes: `ContractWithCounterpart`, `MilestoneOut` (Task 3), `MessagesStack`'s route shape (Task 6, for the "Message" action).
- Produces: `ContractsStack` component (routes `"List"`, `"Detail"` — the latter taking `{ contract: ContractWithCounterpart }` as a param, no extra fetch needed) — consumed by Task 12 (business "Create contract" flow lands a fresh contract here implicitly via the shared `/contracts/mine` refetch, no direct code dependency).

- [ ] **Step 1: Write the failing tests**

```typescript
// mobile/src/screens/shared/__tests__/ContractsListScreen.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ContractsListScreen } from '../ContractsListScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const CONTRACT = {
  id: 'c-1', project_id: 'p-1', student_id: 's-1', business_id: 'b-1', status: 'active',
  ip_assignment_accepted: true, nda_accepted: true, payment_rail: 'self_employed',
  milestones: [{ id: 'm-1', description: 'Data prototype', due_date: null, payment_amount_gbp: 200, status: 'pending', stripe_payment_intent_status: null, captured_at: null }],
  project_title: 'Build a customer analytics dashboard', counterpart_user_id: 'u-2', counterpart_name: 'Northbridge Analytics',
};

test('lists contracts and navigates to detail on tap', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => [CONTRACT]), state: { status: 'signedIn', claims: { role: 'student' } } });
  const navigate = jest.fn();
  render(<ContractsListScreen navigation={{ navigate } as any} />);
  await waitFor(() => expect(screen.getByText('Build a customer analytics dashboard')).toBeTruthy());
  fireEvent.press(screen.getByText('Build a customer analytics dashboard'));
  expect(navigate).toHaveBeenCalledWith('Detail', { contract: CONTRACT });
});
```

```typescript
// mobile/src/screens/shared/__tests__/ContractDetailScreen.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ContractDetailScreen } from '../ContractDetailScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const PENDING_MILESTONE = { id: 'm-1', description: 'Data prototype', due_date: null, payment_amount_gbp: 200, status: 'pending', stripe_payment_intent_status: null, captured_at: null };
const CONTRACT = {
  id: 'c-1', project_id: 'p-1', student_id: 's-1', business_id: 'b-1', status: 'active',
  ip_assignment_accepted: true, nda_accepted: true, payment_rail: 'self_employed',
  milestones: [PENDING_MILESTONE], project_title: 'Build a customer analytics dashboard',
  counterpart_user_id: 'u-2', counterpart_name: 'Northbridge Analytics',
};

function routeWith(contract: typeof CONTRACT) {
  return { params: { contract } } as any;
}

test('a student sees Submit on a pending milestone and it calls the submit endpoint', async () => {
  const authedApi = jest.fn(async (path: string, opts?: any) => {
    if (path === '/contracts/milestones/m-1/submit' && opts?.method === 'POST') {
      return { ...PENDING_MILESTONE, status: 'submitted' };
    }
    throw new Error(`unexpected call: ${path}`);
  });
  mockedUseAuth.mockReturnValue({ authedApi, state: { status: 'signedIn', claims: { role: 'student' } } });

  render(<ContractDetailScreen route={routeWith(CONTRACT)} navigation={{ navigate: jest.fn() } as any} />);
  expect(screen.getByText('Data prototype')).toBeTruthy();
  fireEvent.press(screen.getByTestId('submit-m-1'));
  await waitFor(() => expect(authedApi).toHaveBeenCalledWith('/contracts/milestones/m-1/submit', { method: 'POST' }));
});

test('a business sees Approve & pay on a submitted milestone, not a student', () => {
  const submittedContract = { ...CONTRACT, milestones: [{ ...PENDING_MILESTONE, status: 'submitted' }] };
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(), state: { status: 'signedIn', claims: { role: 'business' } } });
  render(<ContractDetailScreen route={routeWith(submittedContract)} navigation={{ navigate: jest.fn() } as any} />);
  expect(screen.getByTestId('approve-pay-m-1')).toBeTruthy();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mobile && npx jest src/screens/shared/__tests__/ContractsListScreen.test.tsx src/screens/shared/__tests__/ContractDetailScreen.test.tsx`
Expected: FAIL — modules don't exist yet.

- [ ] **Step 3: Write `RateModal`**

```typescript
// mobile/src/components/RateModal.tsx
import React, { useState } from 'react';
import { Modal, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';

export function RateModal({
  visible,
  counterpartName,
  onCancel,
  onSubmit,
}: {
  visible: boolean;
  counterpartName: string;
  onCancel: () => void;
  onSubmit: (overallScore: number) => void;
}) {
  const [score, setScore] = useState('5');

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onCancel}>
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>Rate {counterpartName}</Text>
          <Text style={styles.label}>Overall score (1-5)</Text>
          <TextInput
            style={styles.input}
            value={score}
            onChangeText={setScore}
            keyboardType="numeric"
            testID="rate-score-input"
          />
          <View style={styles.row}>
            <TouchableOpacity style={styles.ghostButton} onPress={onCancel} testID="rate-cancel">
              <Text style={styles.ghostText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.primaryButton}
              onPress={() => onSubmit(Number(score))}
              testID="rate-submit"
            >
              <Text style={styles.primaryText}>Submit rating</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(27,42,69,0.4)', justifyContent: 'flex-end' },
  card: { backgroundColor: '#FFFDF8', borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 20 },
  title: { fontSize: 16, fontWeight: '700', color: '#1B2A45', marginBottom: 14 },
  label: { fontSize: 12, fontWeight: '600', color: '#3C4B68', marginBottom: 6 },
  input: { borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 10, marginBottom: 16 },
  row: { flexDirection: 'row', gap: 10 },
  ghostButton: { flex: 1, padding: 12, alignItems: 'center', borderRadius: 6, borderWidth: 1, borderColor: '#1B2A45' },
  ghostText: { color: '#1B2A45', fontWeight: '600' },
  primaryButton: { flex: 1, padding: 12, alignItems: 'center', borderRadius: 6, backgroundColor: '#1B2A45' },
  primaryText: { color: '#FFFDF8', fontWeight: '600' },
});
```

- [ ] **Step 4: Write `ContractsListScreen`**

```typescript
// mobile/src/screens/shared/ContractsListScreen.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { ContractWithCounterpart } from '../../api/types';

export function ContractsListScreen({ navigation }: { navigation: { navigate: (screen: string, params: { contract: ContractWithCounterpart }) => void } }) {
  const { authedApi, state } = useAuth();
  const role = state.status === 'signedIn' ? state.claims.role : null;
  const [contracts, setContracts] = useState<ContractWithCounterpart[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setContracts(await authedApi<ContractWithCounterpart[]>('/contracts/mine'));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong loading your contracts.');
    }
  }, [authedApi]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await load();
      setLoading(false);
    })();
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}
      <FlatList
        data={contracts ?? []}
        keyExtractor={(c) => c.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={
          <Text style={styles.emptyText}>
            No contracts yet.{role === 'business' ? ' Create one from an applicant on one of your projects.' : ' These appear once a business hires you.'}
          </Text>
        }
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row} onPress={() => navigation.navigate('Detail', { contract: item })}>
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>{item.project_title}</Text>
              <Text style={styles.muted}>With {item.counterpart_name}</Text>
            </View>
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{item.status}</Text>
            </View>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  errorText: { color: '#A6452F' },
  emptyText: { color: '#3C4B68', textAlign: 'center', margin: 24, fontSize: 13 },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFFDF8', borderBottomWidth: 1, borderBottomColor: '#DDD6C7', padding: 16 },
  title: { fontSize: 15, fontWeight: '700', color: '#1B2A45' },
  muted: { fontSize: 13, color: '#3C4B68', marginTop: 2 },
  badge: { backgroundColor: '#E9D9B8', borderRadius: 100, paddingVertical: 4, paddingHorizontal: 10, marginLeft: 10 },
  badgeText: { fontSize: 11, fontWeight: '700', color: '#A87C2A' },
});
```

- [ ] **Step 5: Write `ContractDetailScreen`**

```typescript
// mobile/src/screens/shared/ContractDetailScreen.tsx
import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { ContractWithCounterpart, MilestoneOut } from '../../api/types';
import { RateModal } from '../../components/RateModal';

export function ContractDetailScreen({
  route,
  navigation,
}: {
  route: { params: { contract: ContractWithCounterpart } };
  navigation: { navigate: (screen: string, params?: Record<string, unknown>) => void };
}) {
  const { authedApi, state } = useAuth();
  const role = state.status === 'signedIn' ? state.claims.role : null;
  const [contract, setContract] = useState(route.params.contract);
  const [busyMilestoneId, setBusyMilestoneId] = useState<string | null>(null);
  const [rateModalOpen, setRateModalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateMilestone = (updated: MilestoneOut) => {
    setContract((prev) => ({ ...prev, milestones: prev.milestones.map((m) => (m.id === updated.id ? updated : m)) }));
  };

  const submitMilestone = async (milestoneId: string) => {
    setBusyMilestoneId(milestoneId);
    try {
      updateMilestone(await authedApi<MilestoneOut>(`/contracts/milestones/${milestoneId}/submit`, { method: 'POST' }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not submit that milestone.');
    } finally {
      setBusyMilestoneId(null);
    }
  };

  const approveAndPay = async (milestoneId: string) => {
    setBusyMilestoneId(milestoneId);
    try {
      updateMilestone(await authedApi<MilestoneOut>(`/contracts/milestones/${milestoneId}/approve-and-pay`, { method: 'POST' }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not approve that milestone.');
    } finally {
      setBusyMilestoneId(null);
    }
  };

  const acceptTerms = async () => {
    try {
      const updated = await authedApi<ContractWithCounterpart>(`/contracts/${contract.id}/accept-terms`, { method: 'POST' });
      setContract(updated);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not accept terms.');
    }
  };

  const startMessage = async () => {
    try {
      const thread = await authedApi<{ thread_id: string }>('/messages/threads', {
        method: 'POST',
        body: { project_id: contract.project_id, other_user_id: contract.counterpart_user_id },
      });
      navigation.navigate('Messages', { screen: 'Chat', params: { threadId: thread.thread_id } });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start a conversation.');
    }
  };

  const submitRating = async (overallScore: number) => {
    try {
      await authedApi('/ratings', { method: 'POST', body: { contract_id: contract.id, overall_score: overallScore, sub_scores: {} } });
      setRateModalOpen(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not submit that rating.');
      setRateModalOpen(false);
    }
  };

  const termsNeeded = !contract.ip_assignment_accepted || !contract.nda_accepted;

  return (
    <ScrollView style={styles.container}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <View style={styles.card}>
        <Text style={styles.h1}>{contract.project_title}</Text>
        <Text style={styles.muted}>With {contract.counterpart_name} · {contract.status}</Text>

        {contract.milestones.map((m) => (
          <View key={m.id} style={styles.milestoneRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.milestoneDesc}>{m.description}</Text>
              <Text style={styles.muted}>£{m.payment_amount_gbp} · {m.status}</Text>
            </View>
            {role === 'student' && m.status === 'pending' ? (
              <TouchableOpacity
                style={styles.smallButton}
                onPress={() => submitMilestone(m.id)}
                disabled={busyMilestoneId === m.id}
                testID={`submit-${m.id}`}
              >
                <Text style={styles.smallButtonText}>Submit</Text>
              </TouchableOpacity>
            ) : null}
            {role === 'business' && m.status === 'submitted' ? (
              <TouchableOpacity
                style={styles.smallButton}
                onPress={() => approveAndPay(m.id)}
                disabled={busyMilestoneId === m.id}
                testID={`approve-pay-${m.id}`}
              >
                <Text style={styles.smallButtonText}>Approve & pay</Text>
              </TouchableOpacity>
            ) : null}
          </View>
        ))}

        <View style={styles.actionsRow}>
          {termsNeeded ? (
            <TouchableOpacity style={styles.ghostButton} onPress={acceptTerms} testID="accept-terms">
              <Text style={styles.ghostButtonText}>Accept IP/NDA terms</Text>
            </TouchableOpacity>
          ) : null}
          <TouchableOpacity style={styles.ghostButton} onPress={startMessage} testID="message-counterpart">
            <Text style={styles.ghostButtonText}>Message {contract.counterpart_name}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.ghostButton} onPress={() => setRateModalOpen(true)} testID="rate-contract">
            <Text style={styles.ghostButtonText}>Rate this contract</Text>
          </TouchableOpacity>
        </View>
      </View>

      <RateModal
        visible={rateModalOpen}
        counterpartName={contract.counterpart_name}
        onCancel={() => setRateModalOpen(false)}
        onSubmit={submitRating}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  h1: { fontSize: 18, fontWeight: '700', color: '#1B2A45' },
  muted: { fontSize: 13, color: '#3C4B68', marginTop: 4 },
  errorText: { color: '#A6452F' },
  milestoneRow: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 1, borderTopColor: '#DDD6C7', paddingTop: 12, marginTop: 12 },
  milestoneDesc: { fontSize: 14, color: '#1B2A45', fontWeight: '600' },
  smallButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 6, paddingHorizontal: 12 },
  smallButtonText: { color: '#FFFDF8', fontSize: 12, fontWeight: '600' },
  actionsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 16 },
  ghostButton: { borderWidth: 1, borderColor: '#1B2A45', borderRadius: 6, paddingVertical: 8, paddingHorizontal: 12 },
  ghostButtonText: { color: '#1B2A45', fontSize: 12, fontWeight: '600' },
});
```

- [ ] **Step 6: Write `ContractsStack`**

```typescript
// mobile/src/navigation/ContractsStack.tsx
import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ContractsListScreen } from '../screens/shared/ContractsListScreen';
import { ContractDetailScreen } from '../screens/shared/ContractDetailScreen';
import { ContractWithCounterpart } from '../api/types';

export type ContractsStackParamList = {
  List: undefined;
  Detail: { contract: ContractWithCounterpart };
};

const Stack = createNativeStackNavigator<ContractsStackParamList>();

export function ContractsStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="List" component={ContractsListScreen} options={{ title: 'Contracts' }} />
      <Stack.Screen name="Detail" component={ContractDetailScreen} options={{ title: 'Contract' }} />
    </Stack.Navigator>
  );
}
```

- [ ] **Step 7: Wire it into both tab navigators**

In `mobile/src/navigation/StudentTabs.tsx` and `mobile/src/navigation/BusinessTabs.tsx`:

```typescript
import { ContractsStack } from '../navigation/ContractsStack';
```

Replace each file's `<Tab.Screen name="Contracts" children={() => <PlaceholderScreen title="Contracts" />} />` with:

```typescript
      <Tab.Screen name="Contracts" component={ContractsStack} options={{ headerShown: false }} />
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd mobile && npx jest src/screens/shared/__tests__/ContractsListScreen.test.tsx src/screens/shared/__tests__/ContractDetailScreen.test.tsx`
Expected: PASS, 3/3.

- [ ] **Step 9: Run the full mobile test suite**

Run: `cd mobile && npx jest`
Expected: PASS, no regressions.

- [ ] **Step 10: Commit**

```bash
cd mobile
git add src/screens/shared/ContractsListScreen.tsx src/screens/shared/ContractDetailScreen.tsx src/components/RateModal.tsx src/navigation/ContractsStack.tsx src/screens/shared/__tests__/ContractsListScreen.test.tsx src/screens/shared/__tests__/ContractDetailScreen.test.tsx src/navigation/StudentTabs.tsx src/navigation/BusinessTabs.tsx
git commit -m "$(cat <<'EOF'
Add mobile contracts: List -> Detail, shared across both roles (Workstream 6.b)

Milestone submit/approve-pay, IP/NDA terms acceptance, starting a
message thread with the counterpart, and rating a contract — all
real HTTP calls, role-gated the same way the web app's shared
contracts.js is. Wired into both StudentTabs and BusinessTabs.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Mobile — RatingsScreen (student)

**Files:**
- Create: `mobile/src/screens/student/RatingsScreen.tsx`
- Test: `mobile/src/screens/student/__tests__/RatingsScreen.test.tsx`
- Modify: `mobile/src/navigation/StudentTabs.tsx`

**Interfaces:**
- Consumes: `RatingHistoryEntry` (Task 3).
- Produces: `RatingsScreen` component — wired as `StudentTabs`'s `"Ratings"` tab (replacing its placeholder). Not wired into `BusinessTabs` — see Global Constraints.

- [ ] **Step 1: Write the failing test**

```typescript
// mobile/src/screens/student/__tests__/RatingsScreen.test.tsx
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react-native';
import { RatingsScreen } from '../RatingsScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const RATINGS = [
  { id: 'r-1', contract_id: 'c-1', counterpart_user_id: 'u-2', direction: 'given', is_released: true, overall_score: 5, sub_scores: { communication: 5 }, visibility: 'public' },
  { id: 'r-2', contract_id: 'c-1', counterpart_user_id: 'u-2', direction: 'received', is_released: false, overall_score: null, sub_scores: null, visibility: 'public' },
];

test('splits ratings into Given and Received sections, hiding an unreleased received score', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => RATINGS) });
  render(<RatingsScreen />);
  await waitFor(() => expect(screen.getByText('Given')).toBeTruthy());
  expect(screen.getByText('Received')).toBeTruthy();
  expect(screen.getByText('5.0')).toBeTruthy();
  expect(screen.getByText('Hidden until both sides rate')).toBeTruthy();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mobile && npx jest src/screens/student/__tests__/RatingsScreen.test.tsx`
Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Write the implementation**

```typescript
// mobile/src/screens/student/RatingsScreen.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { RatingHistoryEntry } from '../../api/types';

function RatingRow({ entry }: { entry: RatingHistoryEntry }) {
  return (
    <View style={styles.row}>
      {entry.is_released && entry.overall_score != null ? (
        <Text style={styles.score}>{entry.overall_score.toFixed(1)}</Text>
      ) : (
        <Text style={styles.hidden}>Hidden until both sides rate</Text>
      )}
    </View>
  );
}

export function RatingsScreen() {
  const { authedApi } = useAuth();
  const [ratings, setRatings] = useState<RatingHistoryEntry[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setRatings(await authedApi<RatingHistoryEntry[]>('/ratings/mine'));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong loading your ratings.');
    }
  }, [authedApi]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await load();
      setLoading(false);
    })();
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  const given = (ratings ?? []).filter((r) => r.direction === 'given');
  const received = (ratings ?? []).filter((r) => r.direction === 'received');

  return (
    <ScrollView style={styles.container} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <View style={styles.card}>
        <Text style={styles.h2}>Given</Text>
        {given.length === 0 ? <Text style={styles.muted}>You haven't rated anyone yet.</Text> : null}
        {given.map((r) => <RatingRow key={r.id} entry={r} />)}
      </View>

      <View style={styles.card}>
        <Text style={styles.h2}>Received</Text>
        {received.length === 0 ? <Text style={styles.muted}>No ratings received yet.</Text> : null}
        {received.map((r) => <RatingRow key={r.id} entry={r} />)}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12, marginBottom: 0 },
  h2: { fontSize: 16, fontWeight: '700', color: '#1B2A45', marginBottom: 10 },
  muted: { fontSize: 13, color: '#3C4B68' },
  errorText: { color: '#A6452F' },
  row: { borderTopWidth: 1, borderTopColor: '#DDD6C7', paddingTop: 10, marginTop: 10 },
  score: { fontSize: 18, fontWeight: '700', color: '#A87C2A' },
  hidden: { fontSize: 13, color: '#3C4B68', fontStyle: 'italic' },
});
```

- [ ] **Step 4: Wire it into `StudentTabs`**

In `mobile/src/navigation/StudentTabs.tsx`:

```typescript
import { RatingsScreen } from '../screens/student/RatingsScreen';
```

Replace `<Tab.Screen name="Ratings" children={() => <PlaceholderScreen title="My Ratings" />} />` with:

```typescript
      <Tab.Screen name="Ratings" component={RatingsScreen} />
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd mobile && npx jest src/screens/student/__tests__/RatingsScreen.test.tsx`
Expected: PASS, 1/1.

- [ ] **Step 6: Run the full mobile test suite**

Run: `cd mobile && npx jest`
Expected: PASS, no regressions.

- [ ] **Step 7: Commit**

```bash
cd mobile
git add src/screens/student/RatingsScreen.tsx src/screens/student/__tests__/RatingsScreen.test.tsx src/navigation/StudentTabs.tsx
git commit -m "$(cat <<'EOF'
Add student RatingsScreen (Workstream 6.b.i)

Given/Received sections, matching the blind-until-both-submit
release rule the API already enforces server-side (an unreleased
received rating's score is literally null on the wire — nothing to
hide client-side). Not wired into BusinessTabs, matching the web
app's own tab parity (business has no ratings tab either).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Mobile — react-native-maps setup (Android Gradle + manifest wiring)

**Files:**
- Modify: `mobile/package.json`
- Modify: `mobile/android/app/build.gradle`
- Modify: `mobile/android/app/src/main/AndroidManifest.xml`

**Interfaces:**
- Produces: `react-native-maps`'s `MapView`/`Marker`/`Callout` components, usable by any screen — consumed by Task 10's `LocalSearchMapScreen`.

This is an infra-only task: no new screen, no automated test (native map rendering can't be verified by Jest — it needs the real emulator). Verification is manual, via the AVD.

- [ ] **Step 1: Install the dependency**

```bash
cd mobile
npm install react-native-maps
```

- [ ] **Step 2: Wire the API key from `local.properties` into the Android build**

Read `mobile/android/app/build.gradle` first to find where `android { defaultConfig { ... } }` is, and confirm whether the file already loads `local.properties` into a `Properties` object anywhere near the top (React Native's default template usually does, for `sdk.dir`). If it already does, reuse that existing `Properties` object; if not, add loading logic at the top of the file:

```groovy
def localProperties = new Properties()
def localPropertiesFile = rootProject.file('local.properties')
if (localPropertiesFile.exists()) {
    localPropertiesFile.withInputStream { localProperties.load(it) }
}
```

Inside `android { defaultConfig { ... } }`, add:

```groovy
        manifestPlaceholders = [MAPS_API_KEY: (localProperties.getProperty('MAPS_API_KEY') ?: '')]
```

- [ ] **Step 3: Reference the placeholder from the manifest**

In `mobile/android/app/src/main/AndroidManifest.xml`, inside the `<application>` tag, add:

```xml
        <meta-data
            android:name="com.google.android.geo.API_KEY"
            android:value="${MAPS_API_KEY}" />
```

- [ ] **Step 4: Verify the Android build picks up the key without it ever appearing in a committed file**

Run: `cd mobile/android && ./gradlew :app:processDebugManifest 2>&1 | tail -30`
Expected: the manifest-merge step succeeds (no error about a missing/empty `MAPS_API_KEY` placeholder resolution). If `local.properties` is missing `MAPS_API_KEY` entirely, this step should fail with a clear Gradle manifest-merger error naming the missing placeholder — confirm that's the failure mode by temporarily testing without it if you want extra confidence, then restore it (`android/local.properties` already has the real key from an earlier session — do not modify or print its contents).

- [ ] **Step 5: Confirm nothing sensitive is staged**

```bash
cd mobile
git status --short
```

Expected: `android/local.properties` does NOT appear (it's git-ignored) — only `package.json`, `package-lock.json`, `android/app/build.gradle`, `android/app/src/main/AndroidManifest.xml` show as changed.

- [ ] **Step 6: Commit**

```bash
cd mobile
git add package.json package-lock.json android/app/build.gradle android/app/src/main/AndroidManifest.xml
git commit -m "$(cat <<'EOF'
Add react-native-maps, wire the Maps API key via a Gradle manifest placeholder (Workstream 6.b)

The key itself lives only in the git-ignored android/local.properties
(already present from an earlier session) — this commit adds the
Gradle logic that reads it and the manifest meta-data that consumes
it, never the literal key value.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Mobile — LocalSearchMapScreen (student)

**Files:**
- Create: `mobile/src/screens/student/LocalSearchMapScreen.tsx`
- Test: `mobile/src/screens/student/__tests__/LocalSearchMapScreen.test.tsx`
- Modify: `mobile/src/navigation/StudentTabs.tsx`

**Interfaces:**
- Consumes: `LocalBusinessResult`, `LocalSearchMeta` (Task 3, with Task 1's new lat/lon fields), `MapView`/`Marker`/`Callout` (Task 9).
- Produces: `LocalSearchMapScreen` component — wired as `StudentTabs`'s `"Local"` tab (replacing its placeholder).

- [ ] **Step 1: Write the failing test**

`react-native-maps` needs mocking in Jest (it renders real native views that don't exist in the test environment) — mock it at the module level, asserting on props passed to the mocked components rather than visual rendering:

```typescript
// mobile/src/screens/student/__tests__/LocalSearchMapScreen.test.tsx
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react-native';
import { LocalSearchMapScreen } from '../LocalSearchMapScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

jest.mock('react-native-maps', () => {
  const { View } = require('react-native');
  const MockMapView = ({ children, ...props }: any) => <View testID="map-view" {...props}>{children}</View>;
  const MockMarker = (props: any) => <View testID={`marker-${props.testID ?? props.title}`} {...props} />;
  return { __esModule: true, default: MockMapView, Marker: MockMarker };
});

const META = { campus_name: 'University of Manchester', campus_postcode: 'M13 9PL', campus_latitude: 53.4668, campus_longitude: -2.2339, radius_miles: 10, total_results: 1 };
const RESULTS = [
  { business_id: 'b-1', company_name: 'Northbridge Analytics', industry: 'Data & Analytics', postcode: 'M1 1AE', latitude: 53.4794, longitude: -2.2453, distance_miles: 2.1, degree_relevance_score: 0.9, degree_relevance_label: 'Data Science', approved_categories: ['data_analytics'], average_rating: 4.5, completed_projects_count: 3 },
];

test('centers the map on campus and plots a marker per result', async () => {
  mockedUseAuth.mockReturnValue({
    authedApi: jest.fn(async (path: string) => {
      if (path.includes('/local-businesses/meta')) return META;
      if (path.includes('/local-businesses?')) return RESULTS;
      throw new Error(`unexpected call: ${path}`);
    }),
    state: { status: 'signedIn', claims: { university_id: 'uni-1' } },
  });

  render(<LocalSearchMapScreen />);
  await waitFor(() => expect(screen.getByTestId('map-view')).toBeTruthy());
  const map = screen.getByTestId('map-view');
  expect(map.props.initialRegion.latitude).toBe(53.4668);
  expect(map.props.initialRegion.longitude).toBe(-2.2339);
  expect(screen.getByTestId('marker-Northbridge Analytics')).toBeTruthy();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mobile && npx jest src/screens/student/__tests__/LocalSearchMapScreen.test.tsx`
Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Write the implementation**

```typescript
// mobile/src/screens/student/LocalSearchMapScreen.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import MapView, { Marker } from 'react-native-maps';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { LocalBusinessResult, LocalSearchMeta } from '../../api/types';

export function LocalSearchMapScreen() {
  const { authedApi, state } = useAuth();
  const universityId = state.status === 'signedIn' ? state.claims.university_id : null;
  const [meta, setMeta] = useState<LocalSearchMeta | null>(null);
  const [results, setResults] = useState<LocalBusinessResult[]>([]);
  const [radius, setRadius] = useState('10');
  const [minRelevance, setMinRelevance] = useState('0');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async () => {
    if (!universityId) return;
    setError(null);
    try {
      const [metaData, resultsData] = await Promise.all([
        authedApi<LocalSearchMeta>(`/universities/${universityId}/local-businesses/meta?radius_miles=${radius}`),
        authedApi<LocalBusinessResult[]>(`/universities/${universityId}/local-businesses?radius_miles=${radius}&min_degree_relevance=${minRelevance}`),
      ]);
      setMeta(metaData);
      setResults(resultsData);
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 400
          ? "Your university's campus location hasn't been set yet — ask a university admin to add a campus postcode."
          : e instanceof ApiError
            ? e.message
            : 'Search failed.',
      );
    }
  }, [authedApi, universityId, radius, minRelevance]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await search();
      setLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {meta ? (
        <MapView
          style={styles.map}
          initialRegion={{
            latitude: meta.campus_latitude,
            longitude: meta.campus_longitude,
            latitudeDelta: Math.max(0.05, (Number(radius) / 69) * 2),
            longitudeDelta: Math.max(0.05, (Number(radius) / 69) * 2),
          }}
        >
          {results.map((r) => (
            <Marker
              key={r.business_id}
              testID={r.company_name}
              title={r.company_name}
              description={`${r.degree_relevance_label} · ${r.distance_miles} mi · ★ ${r.average_rating.toFixed(1)}`}
              coordinate={{ latitude: r.latitude, longitude: r.longitude }}
            />
          ))}
        </MapView>
      ) : null}

      <View style={styles.controls}>
        <Text style={styles.label}>Radius (mi)</Text>
        <TextInput style={styles.input} value={radius} onChangeText={setRadius} keyboardType="numeric" testID="radius-input" />
        <Text style={styles.label}>Min relevance</Text>
        <TextInput style={styles.input} value={minRelevance} onChangeText={setMinRelevance} keyboardType="numeric" testID="relevance-input" />
        <TouchableOpacity style={styles.searchButton} onPress={search} testID="run-search">
          <Text style={styles.searchButtonText}>Search</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC', padding: 24 },
  errorText: { color: '#A6452F', textAlign: 'center' },
  map: { flex: 1 },
  controls: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFFDF8', borderTopWidth: 1, borderTopColor: '#DDD6C7', padding: 10, gap: 8 },
  label: { fontSize: 11, color: '#3C4B68' },
  input: { borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 6, width: 50, textAlign: 'center' },
  searchButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 8, paddingHorizontal: 14, marginLeft: 'auto' },
  searchButtonText: { color: '#FFFDF8', fontWeight: '600', fontSize: 12 },
});
```

- [ ] **Step 4: Wire it into `StudentTabs`**

In `mobile/src/navigation/StudentTabs.tsx`:

```typescript
import { LocalSearchMapScreen } from '../screens/student/LocalSearchMapScreen';
```

Replace `<Tab.Screen name="Local" children={() => <PlaceholderScreen title="Local Search" />} />` with:

```typescript
      <Tab.Screen name="Local" component={LocalSearchMapScreen} />
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd mobile && npx jest src/screens/student/__tests__/LocalSearchMapScreen.test.tsx`
Expected: PASS, 1/1.

- [ ] **Step 6: Run the full mobile test suite**

Run: `cd mobile && npx jest`
Expected: PASS, no regressions.

- [ ] **Step 7: Manual verification in the Android emulator**

Run: `cd mobile && npm run android` (with the `CAPLink_Test` AVD already running — start it first with `emulator -avd CAPLink_Test` if it isn't). Log in as the seeded hero student (`priya.anand@manchester.ac.uk` / `ChangeMe123!`), navigate to the "Local" tab, and confirm: a real Google map renders (not a blank grey view — a blank grey view usually means the API key didn't wire through correctly, revisit Task 9), centered on Manchester, with at least one marker for a seeded local business, and that tapping a marker shows its callout.

- [ ] **Step 8: Commit**

```bash
cd mobile
git add src/screens/student/LocalSearchMapScreen.tsx src/screens/student/__tests__/LocalSearchMapScreen.test.tsx src/navigation/StudentTabs.tsx
git commit -m "$(cat <<'EOF'
Add LocalSearchMapScreen, a real map view replacing the placeholder (Workstream 6.b.i)

Genuinely verified in the Android emulator, not just unit-tested —
a mocked react-native-maps proves the component wiring/props, the
emulator run proves the actual Google Maps SDK integration and API
key plumbing work end to end.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Mobile — Business Projects (ProjectsListScreen + PostProjectScreen + ProjectsStack)

**Files:**
- Create: `mobile/src/screens/business/ProjectsListScreen.tsx`
- Create: `mobile/src/screens/business/PostProjectScreen.tsx`
- Create: `mobile/src/navigation/ProjectsStack.tsx`
- Test: `mobile/src/screens/business/__tests__/ProjectsListScreen.test.tsx`
- Test: `mobile/src/screens/business/__tests__/PostProjectScreen.test.tsx`
- Modify: `mobile/src/navigation/BusinessTabs.tsx`

**Interfaces:**
- Consumes: `ProjectOut`, `AgreementWithUniversityOut` (Task 3, the latter from Task 2's new endpoint).
- Produces: `ProjectsStack` component (routes `"List"`, `"Detail"` [Task 12 adds this route], `"ContractForm"` [Task 13 adds this route]) plus a `PostProjectScreen` reachable as a modal from `"List"`.

- [ ] **Step 1: Write the failing tests**

```typescript
// mobile/src/screens/business/__tests__/ProjectsListScreen.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ProjectsListScreen } from '../ProjectsListScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const PROJECT = {
  id: 'p-1', business_id: 'b-1', title: 'Build a customer analytics dashboard',
  description: 'A dashboard.', category: 'data_analytics', required_skills: ['Python'],
  duration_label: '2-3 weeks', estimated_hours: 20, hourly_rate_gbp: 22,
  is_remote: true, location_label: null, status: 'open',
};

test('lists the business\'s own projects and navigates to Detail on tap', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => [PROJECT]) });
  const navigate = jest.fn();
  render(<ProjectsListScreen navigation={{ navigate } as any} />);
  await waitFor(() => expect(screen.getByText('Build a customer analytics dashboard')).toBeTruthy());
  fireEvent.press(screen.getByText('Build a customer analytics dashboard'));
  expect(navigate).toHaveBeenCalledWith('Detail', { project: PROJECT });
});

test('the "post a project" button navigates to PostProject', async () => {
  mockedUseAuth.mockReturnValue({ authedApi: jest.fn(async () => []) });
  const navigate = jest.fn();
  render(<ProjectsListScreen navigation={{ navigate } as any} />);
  await waitFor(() => screen.getByTestId('post-project-button'));
  fireEvent.press(screen.getByTestId('post-project-button'));
  expect(navigate).toHaveBeenCalledWith('PostProject');
});
```

```typescript
// mobile/src/screens/business/__tests__/PostProjectScreen.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { PostProjectScreen } from '../PostProjectScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const AGREEMENT = {
  id: 'a-1', university_id: 'uni-1', university_name: 'University of Manchester', business_id: 'b-1',
  status: 'approved', allowed_bands: ['year_3', 'year_4_plus'], allowed_categories: ['data_analytics'],
  max_active_projects: null, requires_university_project_review: false,
};

test('loads approved agreements and posts a project targeting the selected one', async () => {
  const authedApi = jest.fn(async (path: string, opts?: any) => {
    if (path === '/businesses/me/agreements') return [AGREEMENT];
    if (path === '/projects' && opts?.method === 'POST') {
      return { id: 'p-new', ...opts.body, status: 'open' };
    }
    throw new Error(`unexpected call: ${path}`);
  });
  mockedUseAuth.mockReturnValue({ authedApi });
  const goBack = jest.fn();

  render(<PostProjectScreen navigation={{ goBack } as any} />);
  await waitFor(() => expect(screen.getByText('University of Manchester')).toBeTruthy());

  fireEvent.changeText(screen.getByTestId('post-title'), 'New project');
  fireEvent.changeText(screen.getByTestId('post-description'), 'Description text');
  fireEvent.changeText(screen.getByTestId('post-rate'), '25');
  fireEvent.press(screen.getByText('University of Manchester'));
  fireEvent.press(screen.getByText('year_3'));
  fireEvent.press(screen.getByTestId('post-submit'));

  await waitFor(() => expect(authedApi).toHaveBeenCalledWith('/projects', {
    method: 'POST',
    body: expect.objectContaining({
      title: 'New project',
      target_university_ids: ['uni-1'],
      target_bands: ['year_3'],
      category: 'data_analytics',
    }),
  }));
  expect(goBack).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mobile && npx jest src/screens/business/__tests__/ProjectsListScreen.test.tsx src/screens/business/__tests__/PostProjectScreen.test.tsx`
Expected: FAIL — modules don't exist yet.

- [ ] **Step 3: Write `ProjectsListScreen`**

```typescript
// mobile/src/screens/business/ProjectsListScreen.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { ProjectOut } from '../../api/types';

export function ProjectsListScreen({ navigation }: { navigation: { navigate: (screen: string, params?: { project: ProjectOut }) => void } }) {
  const { authedApi } = useAuth();
  const [projects, setProjects] = useState<ProjectOut[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setProjects(await authedApi<ProjectOut[]>('/projects/mine'));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong loading your projects.');
    }
  }, [authedApi]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await load();
      setLoading(false);
    })();
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}
      <TouchableOpacity style={styles.postButton} onPress={() => navigation.navigate('PostProject')} testID="post-project-button">
        <Text style={styles.postButtonText}>+ Post a project</Text>
      </TouchableOpacity>
      <FlatList
        data={projects ?? []}
        keyExtractor={(p) => p.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={<Text style={styles.emptyText}>No projects yet — post your first one above.</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row} onPress={() => navigation.navigate('Detail', { project: item })}>
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>{item.title}</Text>
              <Text style={styles.muted}>{item.category.replace(/_/g, ' ')} · £{item.hourly_rate_gbp}/hr</Text>
            </View>
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{item.status}</Text>
            </View>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  errorText: { color: '#A6452F' },
  emptyText: { color: '#3C4B68', textAlign: 'center', margin: 24, fontSize: 13 },
  postButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 10, alignItems: 'center', margin: 12 },
  postButtonText: { color: '#FFFDF8', fontWeight: '600' },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFFDF8', borderBottomWidth: 1, borderBottomColor: '#DDD6C7', padding: 16 },
  title: { fontSize: 15, fontWeight: '700', color: '#1B2A45' },
  muted: { fontSize: 13, color: '#3C4B68', marginTop: 2 },
  badge: { backgroundColor: '#E9D9B8', borderRadius: 100, paddingVertical: 4, paddingHorizontal: 10, marginLeft: 10 },
  badgeText: { fontSize: 11, fontWeight: '700', color: '#A87C2A' },
});
```

- [ ] **Step 4: Write `PostProjectScreen`**

```typescript
// mobile/src/screens/business/PostProjectScreen.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { AgreementWithUniversityOut } from '../../api/types';

const BANDS = ['foundation_year', 'year_1', 'year_2', 'year_3', 'year_4_plus', 'postgrad_taught', 'postgrad_research', 'recent_alumni'];

export function PostProjectScreen({ navigation }: { navigation: { goBack: () => void } }) {
  const { authedApi } = useAuth();
  const [agreements, setAgreements] = useState<AgreementWithUniversityOut[] | null>(null);
  const [selectedAgreement, setSelectedAgreement] = useState<AgreementWithUniversityOut | null>(null);
  const [selectedBands, setSelectedBands] = useState<string[]>([]);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [requiredSkills, setRequiredSkills] = useState('');
  const [durationLabel, setDurationLabel] = useState('1-2 weeks');
  const [rate, setRate] = useState('20');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await authedApi<AgreementWithUniversityOut[]>('/businesses/me/agreements');
      setAgreements(data.filter((a) => a.status === 'approved'));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load your approved universities.');
    }
  }, [authedApi]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await load();
      setLoading(false);
    })();
  }, [load]);

  const toggleBand = (band: string) => {
    setSelectedBands((prev) => (prev.includes(band) ? prev.filter((b) => b !== band) : [...prev, band]));
  };

  const submit = async () => {
    if (!selectedAgreement) {
      setError('Choose a target university first.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await authedApi('/projects', {
        method: 'POST',
        body: {
          title,
          description,
          category: selectedAgreement.allowed_categories[0],
          required_skills: requiredSkills.split(',').map((s) => s.trim()).filter(Boolean),
          duration_label: durationLabel,
          hourly_rate_gbp: Number(rate),
          target_university_ids: [selectedAgreement.university_id],
          target_bands: selectedBands,
        },
      });
      navigation.goBack();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not post that project.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <View style={styles.card}>
        <Text style={styles.label}>Title</Text>
        <TextInput style={styles.input} value={title} onChangeText={setTitle} testID="post-title" />

        <Text style={styles.label}>Description</Text>
        <TextInput style={[styles.input, styles.multiline]} value={description} onChangeText={setDescription} multiline testID="post-description" />

        <Text style={styles.label}>Required skills (comma separated)</Text>
        <TextInput style={styles.input} value={requiredSkills} onChangeText={setRequiredSkills} testID="post-skills" />

        <Text style={styles.label}>Duration</Text>
        <TextInput style={styles.input} value={durationLabel} onChangeText={setDurationLabel} testID="post-duration" />

        <Text style={styles.label}>Hourly rate (£)</Text>
        <TextInput style={styles.input} value={rate} onChangeText={setRate} keyboardType="numeric" testID="post-rate" />

        <Text style={styles.label}>Target university</Text>
        {(agreements ?? []).length === 0 ? (
          <Text style={styles.muted}>No approved university partnerships yet.</Text>
        ) : (
          (agreements ?? []).map((a) => (
            <TouchableOpacity
              key={a.id}
              style={[styles.optionRow, selectedAgreement?.id === a.id && styles.optionRowSelected]}
              onPress={() => {
                setSelectedAgreement(a);
                setSelectedBands([]);
              }}
            >
              <Text style={styles.optionText}>{a.university_name}</Text>
            </TouchableOpacity>
          ))
        )}

        {selectedAgreement ? (
          <>
            <Text style={styles.label}>Target bands</Text>
            {selectedAgreement.allowed_bands.map((band) => (
              <TouchableOpacity
                key={band}
                style={[styles.optionRow, selectedBands.includes(band) && styles.optionRowSelected]}
                onPress={() => toggleBand(band)}
              >
                <Text style={styles.optionText}>{band}</Text>
              </TouchableOpacity>
            ))}
          </>
        ) : null}

        <TouchableOpacity style={styles.submitButton} onPress={submit} disabled={submitting} testID="post-submit">
          <Text style={styles.submitButtonText}>{submitting ? 'Posting…' : 'Post project'}</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  errorText: { color: '#A6452F' },
  muted: { fontSize: 13, color: '#3C4B68' },
  label: { fontSize: 12, fontWeight: '600', color: '#3C4B68', marginTop: 14, marginBottom: 6 },
  input: { borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 10 },
  multiline: { minHeight: 70, textAlignVertical: 'top' },
  optionRow: { borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 10, marginBottom: 6 },
  optionRowSelected: { borderColor: '#1B2A45', backgroundColor: '#E9D9B8' },
  optionText: { fontSize: 13, color: '#1B2A45' },
  submitButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 12, alignItems: 'center', marginTop: 20 },
  submitButtonText: { color: '#FFFDF8', fontWeight: '600' },
});
```

- [ ] **Step 5: Write `ProjectsStack`** (with only the `List`/`PostProject` routes for now — Task 12 adds `Detail`, Task 13 adds `ContractForm`; both add their routes to this same file)

```typescript
// mobile/src/navigation/ProjectsStack.tsx
import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ProjectsListScreen } from '../screens/business/ProjectsListScreen';
import { PostProjectScreen } from '../screens/business/PostProjectScreen';
import { ProjectOut } from '../api/types';

export type ProjectsStackParamList = {
  List: undefined;
  PostProject: undefined;
  Detail: { project: ProjectOut };
};

const Stack = createNativeStackNavigator<ProjectsStackParamList>();

export function ProjectsStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="List" component={ProjectsListScreen} options={{ title: 'My Projects' }} />
      <Stack.Screen name="PostProject" component={PostProjectScreen} options={{ title: 'Post a Project', presentation: 'modal' }} />
    </Stack.Navigator>
  );
}
```

(`Detail`'s route type is declared in `ProjectsStackParamList` now so `ProjectsListScreen`'s `navigation.navigate('Detail', ...)` call type-checks even though the screen itself doesn't exist until Task 12 — Task 12 adds the actual `<Stack.Screen name="Detail" .../>` line to this same file.)

- [ ] **Step 6: Wire it into `BusinessTabs`**

In `mobile/src/navigation/BusinessTabs.tsx`:

```typescript
import { ProjectsStack } from '../navigation/ProjectsStack';
```

Replace `<Tab.Screen name="Projects" children={() => <PlaceholderScreen title="My Projects" />} />` with:

```typescript
      <Tab.Screen name="Projects" component={ProjectsStack} options={{ headerShown: false }} />
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd mobile && npx jest src/screens/business/__tests__/ProjectsListScreen.test.tsx src/screens/business/__tests__/PostProjectScreen.test.tsx`
Expected: PASS, 3/3.

- [ ] **Step 8: Run the full mobile test suite**

Run: `cd mobile && npx jest`
Expected: PASS, no regressions.

- [ ] **Step 9: Commit**

```bash
cd mobile
git add src/screens/business/ProjectsListScreen.tsx src/screens/business/PostProjectScreen.tsx src/navigation/ProjectsStack.tsx src/screens/business/__tests__/ProjectsListScreen.test.tsx src/screens/business/__tests__/PostProjectScreen.test.tsx src/navigation/BusinessTabs.tsx
git commit -m "$(cat <<'EOF'
Add business Projects list + post-project flow (Workstream 6.b.ii)

Post-project picks a target university from the business's own real
approved agreements (Task 2's new endpoint) rather than a broken
slug-lookup pattern. Wired into BusinessTabs, replacing its
placeholder.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Mobile — Business ProjectDetailScreen (Applicants + Shortlist)

**Files:**
- Create: `mobile/src/screens/business/ProjectDetailScreen.tsx`
- Create: `mobile/src/components/MatchExplanationModal.tsx`
- Test: `mobile/src/screens/business/__tests__/ProjectDetailScreen.test.tsx`
- Modify: `mobile/src/navigation/ProjectsStack.tsx`

**Interfaces:**
- Consumes: `ApplicantOut`, `StudentShortlistEntry`, `MatchExplanationOut` (Task 3), `MatchBadge` (existing), `MessagesStack`'s route shape (Task 6, for the "Message" action on an applicant).
- Produces: adds the `"Detail"` screen to `ProjectsStack` (Task 11's file) — consumed by Task 13's "Create contract" navigation target (`"ContractForm"`, added to the same stack).

- [ ] **Step 1: Write the failing test**

```typescript
// mobile/src/screens/business/__tests__/ProjectDetailScreen.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ProjectDetailScreen } from '../ProjectDetailScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

const PROJECT = {
  id: 'p-1', business_id: 'b-1', title: 'Build a customer analytics dashboard',
  description: 'A dashboard.', category: 'data_analytics', required_skills: ['Python'],
  duration_label: '2-3 weeks', estimated_hours: 20, hourly_rate_gbp: 22,
  is_remote: true, location_label: null, status: 'open',
};

const APPLICANT = {
  application_id: 'app-1', student_id: 's-1', student_user_id: 'u-1', full_name: 'Priya Anand',
  degree_title: 'BSc Data Science', status: 'submitted', cover_note: 'Happy to help.',
  proposed_rate_gbp: 22, match_score_at_application: 0.86,
};

const SHORTLIST_ENTRY = {
  student_id: 's-1', full_name: 'Priya Anand', degree_title: 'BSc Data Science',
  university_name: 'University of Manchester', average_rating: 4.8, completed_projects_count: 3,
  match_score: 0.86, match_reasons: ['Matched skills: python, sql'],
};

function routeWith(project: typeof PROJECT) {
  return { params: { project } } as any;
}

test('shows applicants by default, toggles to shortlist, and can advance an application status', async () => {
  const authedApi = jest.fn(async (path: string, opts?: any) => {
    if (path === '/projects/p-1/applications') return [APPLICANT];
    if (path === '/projects/p-1/shortlist') return [SHORTLIST_ENTRY];
    if (path === '/applications/app-1' && opts?.method === 'PATCH') return { ...APPLICANT, status: opts.body.status };
    throw new Error(`unexpected call: ${path}`);
  });
  mockedUseAuth.mockReturnValue({ authedApi });

  render(<ProjectDetailScreen route={routeWith(PROJECT)} navigation={{ navigate: jest.fn() } as any} />);
  await waitFor(() => expect(screen.getByText('Priya Anand')).toBeTruthy());
  expect(screen.getByText('Happy to help.')).toBeTruthy();

  fireEvent.press(screen.getByText('Shortlist'));
  await waitFor(() => expect(screen.getByText('University of Manchester')).toBeTruthy());

  fireEvent.press(screen.getByText('Applicants'));
  await waitFor(() => screen.getByTestId('advance-app-1'));
  fireEvent.press(screen.getByTestId('advance-app-1'));
  await waitFor(() => expect(authedApi).toHaveBeenCalledWith('/applications/app-1', { method: 'PATCH', body: { status: 'shortlisted' } }));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mobile && npx jest src/screens/business/__tests__/ProjectDetailScreen.test.tsx`
Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Write `MatchExplanationModal`**

```typescript
// mobile/src/components/MatchExplanationModal.tsx
import React from 'react';
import { Modal, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { MatchExplanationOut } from '../api/types';

export function MatchExplanationModal({
  visible,
  explanation,
  onClose,
}: {
  visible: boolean;
  explanation: MatchExplanationOut | null;
  onClose: () => void;
}) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>Why this match?</Text>
          {explanation ? (
            <ScrollView>
              <Text style={styles.overall}>{Math.round(explanation.score * 100)}% overall</Text>
              {explanation.breakdown.map((factor) => (
                <View key={factor.name} style={styles.factorRow}>
                  <Text style={styles.factorName}>{factor.name.replace(/_/g, ' ')}</Text>
                  <Text style={styles.factorDetail}>{factor.detail}</Text>
                </View>
              ))}
            </ScrollView>
          ) : null}
          <TouchableOpacity style={styles.closeButton} onPress={onClose} testID="close-explanation">
            <Text style={styles.closeButtonText}>Close</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(27,42,69,0.4)', justifyContent: 'flex-end' },
  card: { backgroundColor: '#FFFDF8', borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 20, maxHeight: '70%' },
  title: { fontSize: 16, fontWeight: '700', color: '#1B2A45', marginBottom: 10 },
  overall: { fontSize: 20, fontWeight: '700', color: '#A87C2A', marginBottom: 14 },
  factorRow: { borderTopWidth: 1, borderTopColor: '#DDD6C7', paddingVertical: 10 },
  factorName: { fontSize: 13, fontWeight: '700', color: '#1B2A45', textTransform: 'capitalize' },
  factorDetail: { fontSize: 12, color: '#3C4B68', marginTop: 2 },
  closeButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 12, alignItems: 'center', marginTop: 16 },
  closeButtonText: { color: '#FFFDF8', fontWeight: '600' },
});
```

- [ ] **Step 4: Write `ProjectDetailScreen`**

```typescript
// mobile/src/screens/business/ProjectDetailScreen.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { ApplicantOut, ApplicationStatus, MatchExplanationOut, ProjectOut, StudentShortlistEntry } from '../../api/types';
import { MatchBadge } from '../../components/MatchBadge';
import { MatchExplanationModal } from '../../components/MatchExplanationModal';

const NEXT_STATUS: Partial<Record<ApplicationStatus, ApplicationStatus>> = {
  submitted: 'shortlisted',
  shortlisted: 'interviewing',
  interviewing: 'offered',
};

export function ProjectDetailScreen({
  route,
  navigation,
}: {
  route: { params: { project: ProjectOut } };
  navigation: { navigate: (screen: string, params?: Record<string, unknown>) => void };
}) {
  const { authedApi } = useAuth();
  const { project } = route.params;
  const [view, setView] = useState<'applicants' | 'shortlist'>('applicants');
  const [applicants, setApplicants] = useState<ApplicantOut[] | null>(null);
  const [shortlist, setShortlist] = useState<StudentShortlistEntry[] | null>(null);
  const [explanation, setExplanation] = useState<MatchExplanationOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [applicantsData, shortlistData] = await Promise.all([
        authedApi<ApplicantOut[]>(`/projects/${project.id}/applications`),
        authedApi<StudentShortlistEntry[]>(`/projects/${project.id}/shortlist`),
      ]);
      setApplicants(applicantsData);
      setShortlist(shortlistData);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong loading this project.');
    }
  }, [authedApi, project.id]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await load();
      setLoading(false);
    })();
  }, [load]);

  const advance = async (applicant: ApplicantOut) => {
    const next = NEXT_STATUS[applicant.status];
    if (!next) return;
    try {
      const updated = await authedApi<ApplicantOut>(`/applications/${applicant.application_id}`, { method: 'PATCH', body: { status: next } });
      setApplicants((prev) => (prev ?? []).map((a) => (a.application_id === updated.application_id ? updated : a)));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not update that application.');
    }
  };

  const messageApplicant = async (studentUserId: string) => {
    try {
      const thread = await authedApi<{ thread_id: string }>('/messages/threads', {
        method: 'POST',
        body: { project_id: project.id, other_user_id: studentUserId },
      });
      navigation.navigate('Messages', { screen: 'Chat', params: { threadId: thread.thread_id } });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start a conversation.');
    }
  };

  const showExplanation = async (studentId: string) => {
    try {
      setExplanation(await authedApi<MatchExplanationOut>(`/projects/${project.id}/shortlist/${studentId}/explanation`));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load the match breakdown.');
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <View style={styles.toggleRow}>
        <TouchableOpacity style={[styles.toggle, view === 'applicants' && styles.toggleActive]} onPress={() => setView('applicants')}>
          <Text style={[styles.toggleText, view === 'applicants' && styles.toggleTextActive]}>Applicants</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.toggle, view === 'shortlist' && styles.toggleActive]} onPress={() => setView('shortlist')}>
          <Text style={[styles.toggleText, view === 'shortlist' && styles.toggleTextActive]}>Shortlist</Text>
        </TouchableOpacity>
      </View>

      {view === 'applicants' ? (
        <FlatList
          data={applicants ?? []}
          keyExtractor={(a) => a.application_id}
          renderItem={({ item }) => (
            <View style={styles.row}>
              <View style={{ flex: 1 }}>
                <Text style={styles.name}>{item.full_name}</Text>
                <Text style={styles.muted}>{item.degree_title} · {item.status}</Text>
                {item.cover_note ? <Text style={styles.coverNote}>{item.cover_note}</Text> : null}
              </View>
              <View style={styles.actionsCol}>
                {NEXT_STATUS[item.status] ? (
                  <TouchableOpacity style={styles.smallButton} onPress={() => advance(item)} testID={`advance-${item.application_id}`}>
                    <Text style={styles.smallButtonText}>Advance</Text>
                  </TouchableOpacity>
                ) : null}
                <TouchableOpacity style={styles.ghostButton} onPress={() => messageApplicant(item.student_user_id)}>
                  <Text style={styles.ghostButtonText}>Message</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.ghostButton}
                  onPress={() => navigation.navigate('ContractForm', { applicationId: item.application_id, projectId: project.id })}
                >
                  <Text style={styles.ghostButtonText}>Create contract</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        />
      ) : (
        <FlatList
          data={shortlist ?? []}
          keyExtractor={(s) => s.student_id}
          renderItem={({ item }) => (
            <View style={styles.row}>
              <View style={{ flex: 1 }}>
                <Text style={styles.name}>{item.full_name}</Text>
                <Text style={styles.muted}>{item.degree_title} · {item.university_name}</Text>
                <TouchableOpacity onPress={() => showExplanation(item.student_id)}>
                  <Text style={styles.whyLink}>Why this match?</Text>
                </TouchableOpacity>
              </View>
              <MatchBadge score={item.match_score} />
            </View>
          )}
        />
      )}

      <MatchExplanationModal visible={!!explanation} explanation={explanation} onClose={() => setExplanation(null)} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  errorText: { color: '#A6452F' },
  toggleRow: { flexDirection: 'row', margin: 12, backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7' },
  toggle: { flex: 1, paddingVertical: 10, alignItems: 'center' },
  toggleActive: { backgroundColor: '#1B2A45', borderRadius: 5 },
  toggleText: { color: '#1B2A45', fontWeight: '600', fontSize: 13 },
  toggleTextActive: { color: '#FFFDF8' },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFFDF8', borderBottomWidth: 1, borderBottomColor: '#DDD6C7', padding: 16 },
  name: { fontSize: 15, fontWeight: '700', color: '#1B2A45' },
  muted: { fontSize: 13, color: '#3C4B68', marginTop: 2 },
  coverNote: { fontSize: 12, color: '#1B2A45', marginTop: 6, fontStyle: 'italic' },
  actionsCol: { gap: 6, alignItems: 'flex-end' },
  smallButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 6, paddingHorizontal: 12 },
  smallButtonText: { color: '#FFFDF8', fontSize: 12, fontWeight: '600' },
  ghostButton: { borderWidth: 1, borderColor: '#1B2A45', borderRadius: 6, paddingVertical: 6, paddingHorizontal: 12 },
  ghostButtonText: { color: '#1B2A45', fontSize: 12, fontWeight: '600' },
  whyLink: { color: '#A87C2A', fontSize: 12, fontWeight: '600', marginTop: 6 },
});
```

- [ ] **Step 5: Add the `Detail` route to `ProjectsStack`**

In `mobile/src/navigation/ProjectsStack.tsx`, add the import:

```typescript
import { ProjectDetailScreen } from '../screens/business/ProjectDetailScreen';
```

Add the screen (after `PostProject`, before the closing `</Stack.Navigator>`):

```typescript
      <Stack.Screen name="Detail" component={ProjectDetailScreen} options={{ title: 'Project' }} />
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd mobile && npx jest src/screens/business/__tests__/ProjectDetailScreen.test.tsx`
Expected: PASS, 1/1.

- [ ] **Step 7: Run the full mobile test suite**

Run: `cd mobile && npx jest`
Expected: PASS, no regressions.

- [ ] **Step 8: Commit**

```bash
cd mobile
git add src/screens/business/ProjectDetailScreen.tsx src/components/MatchExplanationModal.tsx src/screens/business/__tests__/ProjectDetailScreen.test.tsx src/navigation/ProjectsStack.tsx
git commit -m "$(cat <<'EOF'
Add business ProjectDetailScreen: Applicants/Shortlist toggle (Workstream 6.b.ii)

Applicant status pipeline advancement, messaging, and the "why this
match?" drill-down (same MatchExplanationOut breakdown the web app
already shows). "Create contract" navigates to a ContractForm route
Task 13 will actually implement.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Mobile — Business ContractFormScreen

**Files:**
- Create: `mobile/src/screens/business/ContractFormScreen.tsx`
- Test: `mobile/src/screens/business/__tests__/ContractFormScreen.test.tsx`
- Modify: `mobile/src/navigation/ProjectsStack.tsx`

**Interfaces:**
- Consumes: `ContractCreate`'s shape (not in `types.ts` as a named export — this screen builds the POST body inline, matching how `PostProjectScreen` does), navigated to via `{ applicationId, projectId }` params from Task 12.
- Produces: completes `ProjectsStack`'s route set.

- [ ] **Step 1: Write the failing test**

```typescript
// mobile/src/screens/business/__tests__/ContractFormScreen.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { ContractFormScreen } from '../ContractFormScreen';
import { useAuth } from '../../../context/AuthContext';

jest.mock('../../../context/AuthContext');
const mockedUseAuth = useAuth as jest.Mock;

function routeWith(applicationId: string) {
  return { params: { applicationId, projectId: 'p-1' } } as any;
}

test('adds a milestone row and submits a contract with all rows', async () => {
  const authedApi = jest.fn(async (path: string, opts?: any) => {
    if (path === '/contracts' && opts?.method === 'POST') {
      return { id: 'c-new', ...opts.body };
    }
    throw new Error(`unexpected call: ${path}`);
  });
  mockedUseAuth.mockReturnValue({ authedApi });
  const goBack = jest.fn();

  render(<ContractFormScreen route={routeWith('app-1')} navigation={{ goBack } as any} />);

  fireEvent.changeText(screen.getByTestId('milestone-description-0'), 'First milestone');
  fireEvent.changeText(screen.getByTestId('milestone-amount-0'), '200');
  fireEvent.press(screen.getByTestId('add-milestone'));
  fireEvent.changeText(screen.getByTestId('milestone-description-1'), 'Second milestone');
  fireEvent.changeText(screen.getByTestId('milestone-amount-1'), '240');

  fireEvent.press(screen.getByTestId('create-contract'));

  await waitFor(() => expect(authedApi).toHaveBeenCalledWith('/contracts', {
    method: 'POST',
    body: {
      application_id: 'app-1',
      milestones: [
        { description: 'First milestone', payment_amount_gbp: 200 },
        { description: 'Second milestone', payment_amount_gbp: 240 },
      ],
    },
  }));
  expect(goBack).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mobile && npx jest src/screens/business/__tests__/ContractFormScreen.test.tsx`
Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Write the implementation**

```typescript
// mobile/src/screens/business/ContractFormScreen.tsx
import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';

type MilestoneRow = { description: string; payment_amount_gbp: string };

export function ContractFormScreen({
  route,
  navigation,
}: {
  route: { params: { applicationId: string; projectId: string } };
  navigation: { goBack: () => void };
}) {
  const { authedApi } = useAuth();
  const { applicationId } = route.params;
  const [rows, setRows] = useState<MilestoneRow[]>([{ description: '', payment_amount_gbp: '' }]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateRow = (index: number, field: keyof MilestoneRow, value: string) => {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  };

  const addRow = () => setRows((prev) => [...prev, { description: '', payment_amount_gbp: '' }]);
  const removeRow = (index: number) => setRows((prev) => prev.filter((_, i) => i !== index));

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await authedApi('/contracts', {
        method: 'POST',
        body: {
          application_id: applicationId,
          milestones: rows.map((r) => ({ description: r.description, payment_amount_gbp: Number(r.payment_amount_gbp) })),
        },
      });
      navigation.goBack();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not create that contract.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      {error ? (
        <View style={styles.card}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <View style={styles.card}>
        <Text style={styles.h2}>Milestones</Text>
        {rows.map((row, index) => (
          <View key={index} style={styles.milestoneBlock}>
            <Text style={styles.label}>Description</Text>
            <TextInput
              style={styles.input}
              value={row.description}
              onChangeText={(v) => updateRow(index, 'description', v)}
              testID={`milestone-description-${index}`}
            />
            <Text style={styles.label}>Amount (£)</Text>
            <TextInput
              style={styles.input}
              value={row.payment_amount_gbp}
              onChangeText={(v) => updateRow(index, 'payment_amount_gbp', v)}
              keyboardType="numeric"
              testID={`milestone-amount-${index}`}
            />
            {rows.length > 1 ? (
              <TouchableOpacity onPress={() => removeRow(index)} testID={`remove-milestone-${index}`}>
                <Text style={styles.removeText}>Remove</Text>
              </TouchableOpacity>
            ) : null}
          </View>
        ))}

        <TouchableOpacity style={styles.addButton} onPress={addRow} testID="add-milestone">
          <Text style={styles.addButtonText}>+ Add milestone</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.submitButton} onPress={submit} disabled={submitting} testID="create-contract">
          <Text style={styles.submitButtonText}>{submitting ? 'Creating…' : 'Create contract'}</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  card: { backgroundColor: '#FFFDF8', borderRadius: 6, borderWidth: 1, borderColor: '#DDD6C7', padding: 16, margin: 12 },
  errorText: { color: '#A6452F' },
  h2: { fontSize: 16, fontWeight: '700', color: '#1B2A45', marginBottom: 10 },
  milestoneBlock: { borderTopWidth: 1, borderTopColor: '#DDD6C7', paddingTop: 12, marginTop: 12 },
  label: { fontSize: 12, fontWeight: '600', color: '#3C4B68', marginBottom: 6 },
  input: { borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 10, marginBottom: 10 },
  removeText: { color: '#A6452F', fontSize: 12, fontWeight: '600' },
  addButton: { borderWidth: 1, borderColor: '#1B2A45', borderRadius: 6, paddingVertical: 10, alignItems: 'center', marginTop: 12 },
  addButtonText: { color: '#1B2A45', fontWeight: '600', fontSize: 13 },
  submitButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingVertical: 12, alignItems: 'center', marginTop: 16 },
  submitButtonText: { color: '#FFFDF8', fontWeight: '600' },
});
```

- [ ] **Step 4: Add the `ContractForm` route to `ProjectsStack`**

In `mobile/src/navigation/ProjectsStack.tsx`, add the import:

```typescript
import { ContractFormScreen } from '../screens/business/ContractFormScreen';
```

Update `ProjectsStackParamList` to add:

```typescript
  ContractForm: { applicationId: string; projectId: string };
```

Add the screen:

```typescript
      <Stack.Screen name="ContractForm" component={ContractFormScreen} options={{ title: 'Create Contract' }} />
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd mobile && npx jest src/screens/business/__tests__/ContractFormScreen.test.tsx`
Expected: PASS, 1/1.

- [ ] **Step 6: Run the full mobile test suite**

Run: `cd mobile && npx jest`
Expected: PASS, no regressions — this is the last mobile task, so this run should show every test file from Tasks 4-13 passing together for the first time.

- [ ] **Step 7: Run the full backend test suite one more time**

Run: `pytest -x -q` (from the repo root, not `mobile/`)
Expected: PASS — confirms Tasks 1-2's backend changes are still solid after everything built on top of them.

- [ ] **Step 8: Manual verification in the Android emulator**

Run: `cd mobile && npm run android`. Walk through the whole loop once, live: log in as the hero business (`demo.business@example.com`), post a project, switch to the seeded student `priya.anand@manchester.ac.uk`, see it in her feed, apply; switch back to the business, see the applicant, advance their status, create a contract; as the student, submit a milestone; as the business, approve and pay it; either side, message the other and confirm the flagged-content warning renders for an off-platform-contact message; either side, rate the contract; confirm it shows correctly (or correctly hidden) in Ratings.

- [ ] **Step 9: Commit**

```bash
cd mobile
git add src/screens/business/ContractFormScreen.tsx src/screens/business/__tests__/ContractFormScreen.test.tsx src/navigation/ProjectsStack.tsx
git commit -m "$(cat <<'EOF'
Add business ContractFormScreen, completing Workstream 6.b (Workstream 6.b.ii)

Add/remove milestone rows, POST /contracts. This is the last screen
in the plan — the full student+business loop (post project -> apply
-> shortlist/applicant review -> contract -> milestones -> messaging
-> ratings) is now real, live-API-backed mobile UI end to end.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** §5.1→Task 5, §5.2→Task 6, §5.3→Task 7, §5.5→Task 8, §5.4→Tasks 9-10, §5.6→Tasks 11-13, §3→Task 1, §6/§7→Tasks 4/9. §2's straight-port items (Ratings, post-project form) are folded into Tasks 8/11 rather than getting their own tasks, matching how small they are. One spec gap closed during planning, not in §5's original text: Task 2 (the "my agreements" endpoint) — flagged prominently in its own task description and in this plan's intro, not silently added.
- **Type/name consistency checked:** `ContractsStackParamList`/`MessagesStackParamList`/`ProjectsStackParamList`'s route names match every `navigation.navigate(...)` call across all 13 tasks exactly (`'Chat'`, `'Detail'`, `'PostProject'`, `'ContractForm'`, each with the same param shape every caller passes). `AgreementWithUniversityOut` (Task 3) matches Task 2's actual schema fields exactly. `authedApi` call signatures (`path`, `{method, body}`) are identical to the existing `FeedScreen.tsx`'s usage throughout every new screen.
- **Placeholder scan:** no TBD/TODO; every step has real, complete code.
