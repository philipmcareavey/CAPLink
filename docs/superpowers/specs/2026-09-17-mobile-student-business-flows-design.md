# Mobile Student & Business Flows — Design Spec

**Date:** 2026-09-17
**Status:** Approved by Phil (chat, 2026-09-17) — proceeding to implementation plan.
**Tracked as:** continuation of **Workstream 6** (Mobile App Build) in the
104-step Technical Implementation Plan/Tracker — completes step `6.b.i`
("Build mobile student feed, profile, and application flows") and delivers
`6.b.ii` ("Build mobile business shortlist and posting flows").

## 1. Motivation

Workstream 6 built the React Native app's scaffold, auth, and one screen
(the student Feed) against the real live staging API. This spec covers
everything else in `6.b`: the remaining student screens (Profile,
Contracts, Messages, Local Search, Ratings) and the business side
(Projects/Applicants/Shortlist/Contract-creation, plus Contracts and
Messages shared with the student role). Push notifications (`6.c`) and
app-store packaging (`6.d`) are explicitly out of scope — `6.c` needs a
real Firebase/APNs setup this project has deliberately stubbed everywhere
else, and `6.d` needs Apple/Google developer accounts nobody has yet.

## 2. Scope: straight port vs. mobile redesign

Every screen's data and API calls mirror the existing web reference app
(`static/app/js/student.js`, `business.js`, `shared/contracts.js`,
`shared/messaging.js`) exactly — same endpoints, same fields, same
business rules. What differs is *navigation and presentation*, decided
per-screen against how well the web layout actually translates to a phone:

**Straight port** (native components, same information architecture):
- **Ratings** (`My Ratings` tab) — a list of past ratings, given/received,
  visibility rules unchanged.
- **Post a project** (business) — reuses the existing `ApplyModal`
  full-screen-modal pattern already in the app.

**Redesigned for mobile** (real navigation/UX changes, same underlying
data):
- **Messaging** — web is one page swapping a thread list and a chat panel
  via JS. Mobile becomes two real screens: `ThreadsListScreen` →
  (native-stack push) → `ChatScreen`, with native chat bubbles.
- **Student profile** — web embeds it as a card atop the Feed page with an
  inline edit modal. Mobile splits it into its own `ProfileScreen`/tab.
- **Contracts** (student + business, shared) — web shows one card per
  contract with every milestone/button inline. Mobile becomes
  `ContractsListScreen` (compact cards) → tap → `ContractDetailScreen`
  (milestones, actions, terms, rate, message).
- **Business "Projects" tab** — web morphs one tab between a post-form,
  project list, applicant review, shortlist, and contract creation. Mobile
  becomes a real stack: `ProjectsListScreen` → `ProjectDetailScreen`
  (Applicants/Shortlist as an in-screen segmented toggle, not separate
  tabs — see §4) → `ContractFormScreen`, plus `PostProjectScreen` as a
  modal.
- **Local Search** — upgraded from the web's two-field-filter-plus-list to
  a real map view (`react-native-maps`), businesses plotted around campus.

## 3. Required backend change (small, additive)

`GET /universities/{id}/local-businesses` (`app/schemas/local_search.py`)
currently returns `distance_miles` but no coordinates — a map cannot place
a marker from a distance alone. The backend already computes this
(`app/services/geo.py`'s `haversine_distance_miles` reads
`business.latitude`/`longitude` and `university.latitude`/`longitude`
directly), it's just never returned. Add:

- `LocalBusinessResult.latitude: float`, `.longitude: float` (from the
  `BusinessProfile` row already being queried).
- `LocalSearchMeta.campus_latitude: float`, `.campus_longitude: float`
  (from the `University` row already being queried) — so the map can
  center itself without a second round trip.

Both are existing, non-null-once-validated DB columns (the endpoint
already 400s if the university has no lat/lon set) being exposed, not new
data — a pure schema addition, no migration, no behavior change for the
web app (which ignores unknown response fields).

## 4. Navigation architecture

Both role's tab navigators (`StudentTabs.tsx`, `BusinessTabs.tsx`) already
use `@react-navigation/bottom-tabs`. Each tab whose screen needs list→detail
navigation gets its own nested `createNativeStackNavigator()` (the same
package — `@react-navigation/native-stack` — already used by
`RootNavigator.tsx`) rather than introducing a new navigation library:

```
StudentTabs (bottom tabs)
├─ Feed        → FeedScreen (unchanged)
├─ Profile     → ProfileScreen (new)
├─ Contracts   → ContractsStack: ContractsListScreen → ContractDetailScreen
├─ Messages    → MessagesStack: ThreadsListScreen → ChatScreen
├─ Local       → LocalSearchMapScreen (new)
└─ Ratings     → RatingsScreen (new)

BusinessTabs (bottom tabs)
├─ Projects    → ProjectsStack: ProjectsListScreen → ProjectDetailScreen → ContractFormScreen
│                (+ PostProjectScreen as a modal reachable from ProjectsListScreen)
├─ Contracts   → ContractsStack (shared component tree with student, role-aware — see §5.3)
└─ Messages    → MessagesStack (shared with student — see §5.2)
```

`ContractsStack` and `MessagesStack` are literally the same
screens/components for both roles — each screen reads `useAuth().state`
to know the caller's role where behavior actually differs (e.g. "Approve &
pay" only renders for a business viewing a `submitted` milestone), exactly
matching how `shared/contracts.js`/`shared/messaging.js` take a `role`
parameter on the web. They live in `mobile/src/screens/shared/`, not
duplicated under `student/`/`business/`.

## 5. Screen-by-screen design

Each screen: real API calls (no mocking, matching this project's "points
at the real live staging API" convention), the existing loading/
refresh/error pattern from `FeedScreen.tsx` (a centered `ActivityIndicator`
while loading, `RefreshControl` pull-to-refresh, an inline error card),
and the existing design tokens (`#F6F3EC` background / `#FFFDF8` card /
`#DDD6C7` border / `#1B2A45` ink / `#3C4B68` ink-soft / `#A6452F` danger /
`#A87C2A` brass — no new tokens needed).

### 5.1 ProfileScreen (student)

`GET /students/me` → the same `StudentProfile` shape `FeedScreen` already
fetches (degree, band, skills, modules, rate expectation, hours, ratings
summary). Editable fields (skills, rate, hours) via `PATCH /students/me`
in a form, not a modal (this is its own screen now, not an inline card).

### 5.2 ThreadsListScreen + ChatScreen (shared)

- `GET /messages/threads` → `ThreadSummaryOut[]` (`thread_id`,
  `counterpart_name`, `last_message_preview`, `last_message_at`,
  `unread_count`) renders as a tappable list; unread threads get a visual
  badge.
- Tapping a thread pushes `ChatScreen` with `GET /messages/threads/{id}` →
  `MessageOut[]`, rendered as bubbles (`sender_user_id === state.userId`
  distinguishes "mine" vs "theirs", matching the web's exact class-name
  logic), a compose row posting via `POST /messages`
  (`{thread_id, content}`). A message with `is_flagged: true` gets a
  visible warning treatment inline (the off-platform-contact detector —
  same behavior as web, just needs to actually render the flag instead of
  hiding it).
- New threads are started from elsewhere (a Contract card's "Message"
  button, an Applicant card's "Message" button) via
  `POST /messages/threads` (`{project_id, other_user_id}`), then
  navigating straight to `ChatScreen` with the returned `thread_id` — same
  `startThread()`-then-switch-tab pattern as web, adapted to
  `navigation.navigate('Messages', {screen: 'Chat', params: {threadId}})`.

### 5.3 ContractsListScreen + ContractDetailScreen (shared)

- `GET /contracts/mine` → `ContractWithCounterpart[]` (includes
  `project_title`, `counterpart_name` already, so the list screen needs no
  extra calls). List shows one compact card per contract: title,
  counterpart, status badge.
- Tapping pushes `ContractDetailScreen` (contract already in
  navigation params — no extra fetch needed) showing every milestone
  (`description`, `payment_amount_gbp`, `status`, `due_date`) with the
  same role-gated actions as web: student sees "Submit" on a `pending`
  milestone (`POST /contracts/milestones/{id}/submit`), business sees
  "Approve & pay" on a `submitted` one
  (`POST /contracts/milestones/{id}/approve-and-pay`); an "Accept IP/NDA
  terms" button if either `ip_assignment_accepted`/`nda_accepted` is
  false (`POST /contracts/{id}/accept-terms`); a "Message" button
  (starts/opens a thread per §5.2); a "Rate" button opening a rating
  form (`POST /ratings`, `{contract_id, overall_score, sub_scores}`) once
  the contract is far enough along to rate.

### 5.4 LocalSearchMapScreen (student)

`react-native-maps`'s `MapView` centered on `campus_latitude`/
`campus_longitude` from `GET /universities/{id}/local-businesses/meta`
(§3's new fields), zoomed to roughly fit the current radius. Each result
from `GET /universities/{id}/local-businesses` (with its new
`latitude`/`longitude`, §3) becomes a `Marker`; tapping one opens a
callout with `company_name`, `industry`, `degree_relevance_label`,
`average_rating` — the same fields the web card already shows, just in a
map callout instead of a list item. A bottom control (not a full
bottom-sheet library — a simple `View` overlay, matching this app's
existing lightweight-first convention) holds the radius/min-relevance
inputs the web version has, re-querying on change. The 400 "campus
location not set" case renders the same explanatory empty state the web
version shows.

### 5.5 RatingsScreen (student + business, shared)

`GET /ratings/mine` → `RatingHistoryEntry[]`, rendered as two sections in
one scroll view — "Given" and "Received" — split by `direction`, not a
filter toggle (both lists are typically short; showing both at once needs
no extra interaction). A `received` entry
with `is_released: false` shows a "hidden until both sides rate" state
rather than a score (`overall_score`/`sub_scores` are literally `null` on
the wire in that case — nothing to hide client-side, the API already
withholds it).

### 5.6 ProjectsListScreen + ProjectDetailScreen + ContractFormScreen + PostProjectScreen (business)

- `GET /projects/mine` → `ProjectOut[]` lists the business's own projects
  (title, category, status, rate) as tappable cards.
- `PostProjectScreen` (modal, `ApplyModal`-style): the same fields the web
  post-form collects (title, description, category, required_skills,
  duration_label, estimated_hours, hourly_rate_gbp, target_university_ids,
  target_bands) → `POST /projects`.
- Tapping a project pushes `ProjectDetailScreen` with a segmented
  Applicants/Shortlist toggle (in-screen state, not two navigator routes —
  they're two views of the same project, not a deeper drill-down):
  - **Applicants**: `GET /projects/{id}/applications` → `ApplicantOut[]`,
    each with a status-pipeline action (`PATCH /applications/{id}`,
    `{status}`) and a "Message"/"Create contract" action per applicant.
  - **Shortlist**: `GET /projects/{id}/shortlist` → `StudentShortlistEntry[]`
    (ranked candidates, applied or not), each with `match_score` via the
    existing `MatchBadge` component and a "why this match?" action
    fetching `GET /projects/{id}/shortlist/{student_id}/explanation` →
    `MatchExplanationOut` (the same factor breakdown
    `MatchExplanationOut`/`MatchFactorOut` already power on web).
- "Create contract" (from an applicant) pushes `ContractFormScreen`:
  milestone description/amount pairs (add/remove rows) →
  `POST /contracts` (`{application_id, milestones}`).

## 6. New dependencies

- **`react-native-maps`** (runtime): Google Maps on Android. iOS map
  rendering is explicitly deferred — the screen still builds for iOS
  (the library supports Apple Maps there with no extra config), but
  verifying it is out of scope until this session's iOS toolchain
  (Xcode) status is confirmed.
- **`@testing-library/react-native`** (dev-only, zero production
  footprint): the mobile app currently has exactly one smoke test via
  bare `react-test-renderer`. With 10+ new interactive screens, a
  query-based testing API is worth the (test-only) dependency —
  consistent with this project's established "test coverage matters"
  pattern everywhere else (105 backend pytest functions, 102 web Vitest
  tests before this work).

## 7. Maps API key handling

The key lives in `mobile/android/local.properties` (git-ignored via the
existing bare `local.properties` rule in `mobile/.gitignore` — already
used for `sdk.dir`), read into `android/app/build.gradle` and injected
into `AndroidManifest.xml` via a Gradle manifest placeholder
(`com.google.android.geo.API_KEY`). Never hardcoded in any committed
file. A fresh clone without this file present should fail loudly at
Android build time with a clear message (matching this project's existing
"fail loudly, not silently" convention for missing local config), not
silently ship a broken map.

## 8. Testing

- **Unit/component** (`@testing-library/react-native`, §6): each new
  screen gets tests mirroring the existing web Vitest pattern — mock
  `authedApi` at the module level, assert on rendered content and on
  calls made after an interaction (submit a form, tap an action button),
  not on internal state.
- **Backend**: a new pytest test for §3's schema addition, asserting
  `latitude`/`longitude` and `campus_latitude`/`campus_longitude` appear
  correctly in the real HTTP response — following this project's existing
  `test_local_search_e2e.py` pattern (extend it, not a new file).
- No new manual browser/emulator verification step is prescribed here as
  a hard gate the way Workstream 9's was — this is native mobile, not
  something `claude-in-chrome` can drive at all. Manual verification in
  the Android emulator (`CAPLink_Test`, already confirmed working) is
  still expected before considering any given screen done, same as the
  original Feed screen's own verification.

## 9. Non-goals

- Push notifications (`6.c`) — no real Firebase/APNs setup exists.
- App store submission packaging (`6.d`) — no developer accounts exist.
- iOS map rendering verification — toolchain status unconfirmed.
- Any change to the web reference app (`static/app/`) — this spec only
  touches `caplink/mobile/` and the one small backend schema addition in
  §3.
