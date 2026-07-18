# Student–Business Matching Platform
## Full Business & Technical Implementation Plan

**Working name:** *Bridge* (placeholder — rename as desired)

---

## 1. Vision & Value Proposition

A two-sided marketplace connecting higher-education students with businesses that need flexible, intelligent talent — ranging from a two-week micro-project to a full internship.

| For Businesses | For Students |
|---|---|
| On-demand access to vetted, motivated student talent | Paid work that builds real experience |
| Lower cost/risk than hiring, faster than recruiting | Portfolio-building projects tied to their field of study |
| Pipeline into future graduate hiring | Verified ratings/reputation that compound over time |
| Structured, IP-safe project scoping | Career guidance via AI-suggested roles and employers |

**Core mechanic:** a bidirectional recommendation engine + mutual rating system, similar in spirit to a hybrid of Upwork (project marketplace), LinkedIn (professional identity/reputation) and a graduate-recruitment ATS — but scoped specifically to the HE-to-industry bridge, with built-in trust/safeguarding for a young, often first-time-working user base.

---

## 2. Primary Personas

1. **The Student** — undergrad/postgrad, wants paid, CV-relevant work; time-poor around exams; often first professional experience.
2. **The SME/Startup Hirer** — wants cheap, fast, low-commitment access to skilled labour for a defined task (e.g. market research, a website, data analysis, a marketing campaign).
3. **The Corporate/Grad-Pipeline Hirer** — larger company using the platform as a structured internship/early-talent funnel, cares about employer branding and volume screening.
4. **The University Careers Team** (secondary/institutional persona) — may want visibility into student engagement, employability stats, and to co-brand or endorse the platform.

---

## 3. Core Feature Set

### 3.1 Student-side
- Rich profile: degree, modules, skills (self-declared + verified via completed projects), portfolio uploads, availability calendar, hourly/day-rate expectations, right-to-work status
- Project/job discovery feed with filters (remote/local, duration, pay, skill match)
- **AI-suggested projects** — ranked by fit (see §4)
- Application & proposal submission (cover note, availability, rate)
- In-app messaging with businesses (monitored, see §7)
- Contract acceptance, milestone tracking, timesheet/deliverable submission
- Payment tracking & payout (Stripe Connect or similar)
- Post-project rating of the business + ability to request business rates them
- Reputation dashboard: aggregate rating, completed projects, skills endorsed, badges (e.g. "verified", "top-rated", "on-time")
- **AI career-suggestions**: "based on your profile, you may suit these employer types / roles"

### 3.2 Business-side
- Company profile with verification (Companies House / business registration check)
- Post a project or role: scope, deliverables, duration, budget, required skills, seniority level
- **AI-suggested student shortlist** — ranked candidates before businesses even browse
- Search/filter students by university, skill, rating, availability, past project types
- Messaging, interview scheduling
- Contract generation (templated, IP-assignment and confidentiality clauses built in)
- Milestone approval & payment release (escrow model)
- Post-project rating of student
- Repeat-hire / "save student" / talent pool features
- Analytics: spend, project outcomes, time-to-fill

### 3.3 Platform / Admin
- Identity verification pipeline (student = university email + optional ID; business = company registration lookup)
- Dispute resolution workflow
- Trust & Safety moderation queue (flagged messages, reported users)
- Payments/escrow ledger, invoicing, tax documentation (e.g. UK: right-to-work, student visa hour limits if applicable)
- Content moderation for project postings (no ambiguous scope, no exploitative unpaid "expenses only" listings)
- Recommendation engine admin controls (weighting, cold-start rules, manual promotion of projects)
- Reporting dashboards for university partners

---

## 4. Matching & Recommendation Engine

Three related but distinct recommendation surfaces:

### A. Student → Project matching
**Signal inputs:** declared skills, degree/module content, past project categories & ratings, stated interests, availability, rate expectations, geographic constraints, engagement history (what they click/apply to, not just profile data).

**Approach (phased):**
- *Phase 1 (MVP):* rules-based scoring — weighted match on skill tags, degree relevance, availability, and rate band. Simple and explainable.
- *Phase 2:* collaborative filtering — "students like you also applied to/succeeded in…" using application and rating outcomes as implicit feedback.
- *Phase 3:* embedding-based semantic matching — represent student profiles and project descriptions as vectors (e.g. using an LLM embedding model) so a project asking for "someone who can build a churn-prediction model" matches a stats/data-science student even without exact keyword overlap. Re-rank with a learned model trained on historical successful matches (completed + highly rated).

### B. Business → Student shortlist
Mirror of the above, additionally weighted by the business's own historical hiring pattern and stated preferences (e.g. "we've had success with penultimate-year engineering students").

### C. Career/Employer suggestions for students
A longer-horizon recommendation: "employers who typically value someone with your profile," using aggregated (anonymised) data on what skill/degree combinations succeed with which employer types. This is a discovery/inspiration feature, not a hard match — framed as guidance, not guarantee.

**Cold-start handling:** for new users with no history, fall back to rules-based/content matching (skills + degree) until enough interaction data exists; clearly flag "new to platform" so ratings-weighting doesn't unfairly penalise first-timers.

**Explainability:** every recommendation should show *why* ("matched on: Python, data visualisation, availability") — builds trust and gives users actionable profile-improvement feedback.

---

## 5. Rating & Reputation System

- **Bidirectional, mandatory-to-unlock:** payment/next-project release can nudge (not force) both parties to rate — mutual, blind until both submit or a time window expires (prevents retaliatory rating).
- **Structured + freeform:** star rating plus specific sub-scores — for students: communication, quality of work, reliability, professionalism; for businesses: clarity of brief, payment promptness, respectful treatment, mentorship value.
- **Weighted reputation score:** recency-weighted, volume-adjusted (5⭐ from 1 job weighs less than from 20), with outlier/abuse detection (e.g. flag sudden pile-on of 1-star ratings for review).
- **Public vs private feedback:** star scores + tags shown publicly; free-text comment optionally private-to-platform for moderation/dispute use only, to reduce reputational-risk chilling effects on honest feedback.
- **Dispute path:** either party can flag a rating for platform review before it's permanently attached.
- **Anti-gaming safeguards:** rate-limit review submissions, detect review-swapping rings, require a minimum engagement threshold (e.g. a real milestone completed) before a rating counts.

---

## 6. Technical Architecture

### 6.1 Suggested stack
| Layer | Recommendation | Notes |
|---|---|---|
| Frontend (web) | React (Next.js) | SEO-friendly for project listings, fast iteration |
| Mobile | React Native | Reuse logic/components with web |
| Backend | Node.js (NestJS) or Python (FastAPI/Django) | FastAPI is a strong choice if the recommendation engine is Python/ML-heavy |
| Database | PostgreSQL | Relational integrity for contracts, payments, ratings |
| Search/matching index | Elasticsearch or pgvector (Postgres extension) | pgvector is simpler to operate for embedding-based matching at moderate scale |
| Recommendation service | Separate microservice (Python) | Can iterate on ML independently of core app |
| Auth & identity | Auth0/Clerk + custom verification pipeline | University SSO (Shibboleth/OAuth) integration for student verification is a strong trust signal |
| Payments | Stripe Connect (marketplace/escrow mode) | Handles KYC, payouts, marketplace fee split |
| Messaging | In-house (Postgres + WebSocket) or Sendbird/Stream | Needs moderation hooks — build vs buy trade-off |
| File storage | S3-compatible object storage | Portfolios, contracts, deliverables |
| Notifications | SendGrid/Postmark (email), OneSignal (push) | |
| Infra | AWS or GCP, containerised (Docker/Kubernetes or simpler: Render/Fly.io for MVP) | Don't over-engineer infra pre-PMF |
| Analytics | PostHog/Mixpanel + a data warehouse (BigQuery) for the recommender's training data | |

### 6.2 Core data model (simplified entities)
```
User (id, type: student|business|admin, email, verification_status)
StudentProfile (user_id, university, degree, modules[], skills[], rate_expectation, availability)
BusinessProfile (user_id, company_name, registration_no, industry, verification_status)
Project (id, business_id, title, description, skills_required[], duration, budget, status)
Application (id, project_id, student_id, cover_note, proposed_rate, status)
Contract (id, project_id, student_id, business_id, terms, milestones[], status)
Milestone (id, contract_id, description, due_date, status, payment_amount)
Payment (id, contract_id, milestone_id, amount, status, stripe_ref)
Rating (id, contract_id, rater_id, ratee_id, scores{}, comment, visibility)
Message (id, thread_id, sender_id, content, flagged_bool)
RecommendationLog (id, user_id, recommended_entity_id, entity_type, score, reason, shown_at, action_taken)
```
`RecommendationLog` is worth calling out specifically — capturing what was recommended, why, and what the user did with it is the training data for every future improvement to the matching engine. Build this from day one even if the engine itself starts simple.

### 6.3 Matching engine architecture
```
[Student/Project data] → [Feature pipeline] → [Scoring service]
                                                      │
                                    ┌─────────────────┼─────────────────┐
                              Rules engine     Collaborative filter   Embedding similarity
                              (MVP, always on)  (once enough data)    (Phase 3)
                                    └─────────────────┼─────────────────┘
                                              [Blended ranker] → [Explanation generator] → API
```

---

## 7. Trust, Safety & Compliance

This is a young user base doing paid work for external businesses — treat safeguarding and legal compliance as first-class, not an afterthought:

- **Identity verification:** university email + optional student ID upload for students; company registration number check (e.g. Companies House API in the UK) for businesses.
- **Safe communication:** in-app messaging only until a contract is signed, with keyword-based flagging for inappropriate contact requests or attempts to move off-platform to avoid fees.
- **Fair pay enforcement:** minimum rate floor, no unpaid "exposure" listings permitted, escrow so students aren't working on trust alone.
- **IP & confidentiality:** every contract auto-includes a standard IP-assignment and NDA clause (legally reviewed once, templated).
- **Right-to-work / visa hour limits:** flag and enforce weekly hour caps for international students where relevant.
- **Dispute resolution & moderation team:** human review path for flagged messages, poor-conduct reports, and non-payment.
- **Data protection:** GDPR-compliant handling of student personal data; clear consent for university-partner data sharing/reporting.
- **Under-18 edge case:** most HE students are 18+, but some pre-university or apprenticeship-adjacent users might not be — build age-gating and stricter contact rules if the platform ever admits under-18s.

---

## 8. Business Model

| Revenue stream | Mechanism |
|---|---|
| Platform fee (primary) | % commission on project value (e.g. 10–15% from business, or split both sides) |
| Subscription tier for businesses | Unlimited postings, advanced shortlisting/analytics, priority support |
| Featured/promoted project listings | Businesses pay to boost visibility |
| University partnership fees | White-labelled portal / employability reporting dashboard for careers services |
| Premium student profile tools | Optional — CV review, interview prep, skill certification (careful not to gate core opportunity access behind paywalls) |

---

## 9. MVP Definition (what to build first)

Ruthlessly cut to prove the core loop: **a business can post a project → students apply → one gets hired → work happens → both rate each other.**

**In scope for MVP:**
- Student & business sign-up + basic profile
- University email verification (simple domain check)
- Project posting (manual categories/skills tags, no AI yet)
- Rules-based matching/search (skill + availability filter)
- Application flow + basic messaging
- Manual/templated contract acceptance
- Stripe Connect payment with milestone release
- Post-project bidirectional star rating
- Basic admin panel for moderation

**Explicitly deferred:**
- ML-based recommendation engine (start rules-based)
- Mobile app (start responsive web)
- University partnership dashboards
- Advanced analytics
- Career-suggestion feature

---

## 10. Step-by-Step Implementation Roadmap

**Phase 0 — Validation (2–4 weeks)**
1. Interview 15–20 students and 10–15 SMEs/startups to validate demand, pricing tolerance, and pain points.
2. Define initial skill taxonomy and project categories.
3. Decide on legal structure for contracts/escrow (may need legal counsel for marketplace T&Cs).
4. Finalise MVP scope (above) and success metrics.

**Phase 1 — MVP Build (8–12 weeks)**
5. Set up infra: repo, CI/CD, staging/prod environments, chosen stack.
6. Build auth + verification (student email domain check, business registration check).
7. Build profile creation flows (student + business).
8. Build project posting + rules-based search/filter (no ML yet).
9. Build application + messaging flow.
10. Integrate Stripe Connect for escrow/milestone payments.
11. Build contract templating (with legal-reviewed IP/NDA clauses).
12. Build rating system (mutual, blind-until-both-submit).
13. Build minimal admin/moderation panel.
14. Internal QA + a small closed pilot (e.g. one university, 20 businesses).

**Phase 2 — Pilot & Iterate (6–8 weeks)**
15. Run closed pilot; instrument `RecommendationLog`-equivalent event tracking even though matching is still rules-based, to start collecting training data.
16. Collect qualitative feedback from both sides; fix trust/friction points (this is usually where most churn hides — payment delays, unclear scope, poor first matches).
17. Tune rules-based matching weights based on real application/hire outcomes.
18. Formalise dispute-resolution and safeguarding processes based on real incidents (if any).

**Phase 3 — Recommendation Engine v1 (4–6 weeks, can overlap Phase 2)**
19. Build collaborative-filtering layer using pilot data (applications, hires, ratings).
20. Add "why recommended" explanation generation.
21. A/B test rules-based vs blended ranking on live traffic.

**Phase 4 — Scale Features (ongoing)**
22. Career/employer-suggestion feature for students (aggregated success-pattern insights).
23. University partner dashboards (employability reporting, co-branding).
24. Mobile app (React Native) once web usage patterns justify it.
25. Embedding-based semantic matching (Phase 3 of §4) once volume supports it.
26. Subscription tier + promoted listings monetisation features.

**Phase 5 — Trust & Ecosystem Maturity**
27. Verified skill badges (e.g. via completed-project outcomes, not just self-declaration).
28. Talent-pool / repeat-hire tooling for businesses.
29. Expand geographic/university coverage; formal partnership agreements.
30. Continuous fairness/bias auditing of the recommendation engine (e.g. check it isn't systematically under-recommending students from certain universities or backgrounds).

---

## 11. Success Metrics (KPIs)

| Category | Metric |
|---|---|
| Liquidity | Time-to-first-application per project; applications per project |
| Match quality | % of applications leading to hire; post-hire rating average |
| Trust | Dispute rate; on-time payment rate; repeat-hire rate |
| Growth | Student sign-ups per university; business retention/repeat-posting rate |
| Recommendation engine | Click-through & apply-through rate on suggested projects vs browsed; lift over rules-based baseline |

---

## 12. Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Cold-start (no students without projects, no projects without students) | Seed supply manually — recruit anchor SME clients and a pilot cohort of students before public launch |
| Payment disputes / non-payment | Escrow model, milestone-based release |
| Low-quality or exploitative project postings | Moderation queue, minimum-rate floor, category restrictions |
| Rating manipulation | Structured scoring, anomaly detection, dispute path |
| Legal exposure (employment status, IP, safeguarding) | Templated legally-reviewed contracts, clear T&Cs distinguishing freelance/project work from employment |
| Recommendation engine bias | Explainability + periodic fairness auditing across university/demographic segments |

---

## 13. What I Can Generate Next

I can go straight into building any of the following — happy to start immediately:

1. **Clickable prototype** — a React-based interactive mockup of the core flows (student profile, project feed, matching, rating) to pressure-test the UX.
2. **Database schema + backend scaffold** — a working FastAPI/NestJS starter with the data model above.
3. **Matching engine prototype** — a Python notebook/service demonstrating the rules-based scoring approach on sample data.
4. **Pitch deck** — investor/stakeholder-facing version of this plan.
5. **Legal document templates** — draft (non-binding, needs lawyer sign-off) contract/NDA/IP clauses.

