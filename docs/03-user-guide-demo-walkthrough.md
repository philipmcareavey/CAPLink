# User Guide — Demo Walkthrough

This walks through the entire lifecycle CAPLink supports, using `curl` against
your locally running server (`uvicorn app.main:app --reload` on
`http://localhost:8000`), so you can see the platform actually work rather than
just read about it. Every command is copy-pasteable.

If you'd rather click around in a browser instead of the terminal, read
[04-using-the-api-docs-ui.md](04-using-the-api-docs-ui.md) first — it explains
how to authenticate in the Swagger UI, which isn't obvious for this project.

All commands assume you've already run `python -m scripts.seed_demo_data`
(see [02-getting-started.md](02-getting-started.md)), which creates:

| Role              | Email                              | Password       |
|-------------------|-------------------------------------|----------------|
| Student            | `aisha.rahman@manchester.ac.uk`     | `ChangeMe123!` |
| Business           | `hello@datacraft-analytics.com`     | `ChangeMe123!` |
| University admin   | `admin@manchester.ac.uk`            | `ChangeMe123!` |

...plus a university (`manchester`), an **already-approved** partnership between
that university and DataCraft Analytics, and one open project ("Customer Churn
Analysis"). If you have [`jq`](https://jqlang.org/) installed, the token-extraction
one-liners below will Just Work; otherwise copy the `access_token` value out of
the JSON by hand each time.

> Tip: every response is JSON. Pipe any command through `python -m json.tool` if
> you don't have `jq` and want it pretty-printed.

## 0. Log in and grab tokens

```bash
BASE=http://localhost:8000/api/v1

STUDENT_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"aisha.rahman@manchester.ac.uk","password":"ChangeMe123!"}' | jq -r .access_token)

BUSINESS_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"hello@datacraft-analytics.com","password":"ChangeMe123!"}' | jq -r .access_token)

ADMIN_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@manchester.ac.uk","password":"ChangeMe123!"}' | jq -r .access_token)
```

Every authenticated request below sends `-H "Authorization: Bearer $TOKEN"`.
Access tokens expire after 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES` in
`.env`) — if commands start 401ing partway through, just log in again.

## 1. See the world from the student's side

**Their profile:**
```bash
curl -s $BASE/students/me -H "Authorization: Bearer $STUDENT_TOKEN"
```

**Their suggested-projects feed** (this runs the matching engine and logs a
`RecommendationLog` row for each result):
```bash
curl -s "$BASE/projects/feed?page=1&page_size=20" -H "Authorization: Bearer $STUDENT_TOKEN"
```
You should see "Customer Churn Analysis" with a `match_score` and
`match_reasons` like `["Skill match: python, sql", "Within budget", ...]` —
this is because Aisha's seeded skills (Python, SQL, Data Visualisation) and
rate (£19/hr) line up with the project's requirements.

## 2. Apply to the project

```bash
PROJECT_ID=$(curl -s "$BASE/projects/feed" -H "Authorization: Bearer $STUDENT_TOKEN" | jq -r '.[0].id')

APPLICATION_ID=$(curl -s -X POST $BASE/applications \
  -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" \
  -d "{\"project_id\":\"$PROJECT_ID\",\"cover_note\":\"I've done a churn analysis for a class project — happy to share it.\",\"proposed_rate_gbp\":19}" \
  | jq -r .id)
```
This also fires a "new application" push-notification stub to the business
(check the server's terminal log — see [01-project-structure.md](01-project-structure.md)
on the notification stub). Note there's no `GET /applications/mine` endpoint
yet, so hang onto `$APPLICATION_ID` for the next steps — if you lose it, you'll
need to re-apply.

## 3. See the world from the business's side

**Their shortlist for the project** (safeguarding-filtered, then ranked):
```bash
curl -s $BASE/projects/$PROJECT_ID/shortlist -H "Authorization: Bearer $BUSINESS_TOKEN"
```
Aisha appears here *only* because the university↔business agreement is
`APPROVED` and her band (`year_3`) is inside `allowed_bands`. Try
[step 7](#7-see-safeguarding-actually-block-something) below to see what
happens when that isn't true.

**Move the application forward:**
```bash
curl -s -X PATCH $BASE/applications/$APPLICATION_ID \
  -H "Authorization: Bearer $BUSINESS_TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"offered"}'
```

## 4. Sign a contract with milestones

```bash
CONTRACT=$(curl -s -X POST $BASE/contracts \
  -H "Authorization: Bearer $BUSINESS_TOKEN" -H "Content-Type: application/json" \
  -d "{\"application_id\":\"$APPLICATION_ID\",\"milestones\":[
        {\"description\":\"Data cleaning + exploratory analysis\",\"payment_amount_gbp\":80},
        {\"description\":\"Final report + churn drivers\",\"payment_amount_gbp\":120}
      ]}")
echo "$CONTRACT" | jq .
CONTRACT_ID=$(echo "$CONTRACT" | jq -r .id)
MILESTONE_ID=$(echo "$CONTRACT" | jq -r '.milestones[0].id')
```
Note: creating a contract auto-accepts the application and moves the project to
`in_progress`.

**Both parties accept IP-assignment / NDA terms:**
```bash
curl -s -X POST $BASE/contracts/$CONTRACT_ID/accept-terms -H "Authorization: Bearer $STUDENT_TOKEN"
curl -s -X POST $BASE/contracts/$CONTRACT_ID/accept-terms -H "Authorization: Bearer $BUSINESS_TOKEN"
```

## 5. Do the work, get paid

```bash
# Student marks the first milestone as delivered:
curl -s -X POST $BASE/contracts/milestones/$MILESTONE_ID/submit -H "Authorization: Bearer $STUDENT_TOKEN"

# Business approves it and releases payment (Stripe is stubbed — see 01-project-structure.md):
curl -s -X POST $BASE/contracts/milestones/$MILESTONE_ID/approve-and-pay -H "Authorization: Bearer $BUSINESS_TOKEN"
```

## 6. Mutual, blind ratings

Ratings stay hidden from the other party until **both** sides have submitted:

```bash
curl -s -X POST $BASE/ratings \
  -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" \
  -d "{\"contract_id\":\"$CONTRACT_ID\",\"overall_score\":5,\"sub_scores\":{\"clarity_of_brief\":5,\"payment_promptness\":5}}"

curl -s -X POST $BASE/ratings \
  -H "Authorization: Bearer $BUSINESS_TOKEN" -H "Content-Type: application/json" \
  -d "{\"contract_id\":\"$CONTRACT_ID\",\"overall_score\":5,\"sub_scores\":{\"communication\":5,\"quality\":5}}"
```
After the *second* submission, both ratings flip `is_released: true` and each
side's `average_rating` / `completed_projects_count` (visible on
`/students/me` or `/businesses/me`) updates automatically.

## 7. See safeguarding actually block something

This is the important part to demonstrate — a brand-new business has **no**
access to any student until a university explicitly approves it:

The public branding endpoint (`GET /universities/{slug}/public`) deliberately
returns only name/colour/logo — no `id` — since it's unauthenticated and meant
for a public landing page. For this walkthrough, grab the university's id the
same local-dev way as the messaging step above:

```bash
UNI_ID=$(sqlite3 caplink.db "select id from universities where slug='manchester';")
```

```bash
# Register a brand-new, unapproved business:
NEW_BIZ=$(curl -s -X POST $BASE/auth/register/business -H "Content-Type: application/json" \
  -d '{"email":"hi@shadyco.com","password":"ChangeMe123!","full_name":"Shady Co","company_name":"Shady Co"}')
NEW_BIZ_TOKEN=$(echo "$NEW_BIZ" | jq -r .access_token)

# Try to post a Data Analytics project targeting the same university/band — this is rejected:
curl -s -X POST $BASE/projects \
  -H "Authorization: Bearer $NEW_BIZ_TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Test","description":"x","category":"data_analytics","duration_label":"1 week",
       "hourly_rate_gbp":15,"target_university_ids":["'"$UNI_ID"'"],
       "target_bands":["year_3"]}'
# -> 403 Forbidden: "No approved agreement with this university."
```

**Now walk it through the approval flow properly**, as a university admin would:

```bash
NEW_BIZ_PROFILE_ID=$(curl -s $BASE/businesses/me -H "Authorization: Bearer $NEW_BIZ_TOKEN" | jq -r .id)

# The business requests access:
AGREEMENT=$(curl -s -X POST $BASE/universities/$UNI_ID/business-agreements \
  -H "Authorization: Bearer $NEW_BIZ_TOKEN" -H "Content-Type: application/json" \
  -d "{\"business_id\":\"$NEW_BIZ_PROFILE_ID\"}")
AGREEMENT_ID=$(echo "$AGREEMENT" | jq -r .id)

# The university admin reviews and approves it, choosing exactly which bands/categories:
curl -s -X PATCH $BASE/universities/$UNI_ID/business-agreements/$AGREEMENT_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"approved","allowed_bands":["year_3","year_4_plus"],"allowed_categories":["data_analytics"]}'
```

Re-run the "post a project" request from above with `NEW_BIZ_TOKEN` — it now
succeeds, because there's an approved agreement covering that band and
category.

## 8. Messaging, including the safety net

Messaging needs the *other party's* `User.id` — but neither
`GET /students/me` nor `GET /businesses/me` currently returns it (they return
the profile's own id, not the linked user id), and there's no
"get user id by email" endpoint. For this demo, the easiest way to get it is a
one-off lookup straight from the SQLite file (this is a local-dev-only trick;
in a real deployment you wouldn't have file access):

```bash
BUSINESS_USER_ID=$(sqlite3 caplink.db "select id from users where email='hello@datacraft-analytics.com';")
```

```bash
THREAD=$(curl -s -X POST $BASE/messages/threads \
  -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" \
  -d "{\"project_id\":\"$PROJECT_ID\",\"other_user_id\":\"$BUSINESS_USER_ID\"}")
THREAD_ID=$(echo "$THREAD" | jq -r .thread_id)

# A normal message:
curl -s -X POST $BASE/messages -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD_ID\",\"content\":\"Looking forward to getting started!\"}"

# A message that trips the off-platform-contact detector:
curl -s -X POST $BASE/messages -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD_ID\",\"content\":\"Just WhatsApp me on 07911 123456 instead\"}"
```
The second message comes back with `"is_flagged": true` and a
`flagged_reason` — see the regex/phrase rules in
`app/api/v1/endpoints/messages.py`.

## 9. Mobile-specific endpoints

```bash
# Register a device for push notifications:
curl -s -X POST $BASE/mobile/devices -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" \
  -d '{"platform":"ios","push_token":"demo-token-123","app_version":"1.0.0"}'

# One combined payload for a mobile home screen instead of 4-5 calls:
curl -s $BASE/mobile/home -H "Authorization: Bearer $STUDENT_TOKEN"
```

## What to try next

- Re-run [step 1](#1-see-the-world-from-the-students-side)'s feed call and
  notice the `RecommendationLog` entries accumulating — `GET /docs` lets you
  inspect this table indirectly via the recommendation-feedback endpoint.
- Register a second student in a different band (e.g. `year_1`) via
  `POST /auth/register/student` and confirm they *don't* see the churn project
  in their feed — DataCraft's agreement only covers `year_2` and above.
- Try `PATCH /students/me` to change skills, then re-check the feed — the
  match score/reasons change immediately since scoring is stateless and rules
  are re-evaluated on every read.
