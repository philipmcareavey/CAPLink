# What Is This, Actually? (The Plain-English Version)

No jargon, no code. This is the "explain it to me like I'm not a programmer"
version of the project.

## The problem it's solving

Universities want their students to get paid work experience — little
freelance-style projects with real businesses — while they're still studying.
Businesses would love access to a pool of bright, cheap, local student talent.
The tricky part is **trust and safety**: a university can't just let any
business message any of its students. They need to control *which* companies
can talk to *which* year-groups, and make sure students get paid properly and
treated well.

CAPLink is the middleman that makes that safe. Think of it like a school
careers fair, except it runs all year round online, and the school (the
university) gets a dashboard to decide exactly which companies are allowed
into the fair and which students they're allowed to talk to.

## Who uses it

- **A university** (e.g. University of Manchester) — pays to license the
  software, the same way a school pays for Google Classroom or Blackboard.
  Their careers team gets an admin panel.
- **A student** at that university — signs up with their university email,
  builds a profile (skills, degree, how many hours a week they're free), and
  gets shown small paid projects that fit them.
- **A business** — signs up, asks a university for permission to reach its
  students, and once approved, posts short paid projects and reviews who
  applies.

## The most important rule in the whole system

**A business cannot see a single student until that student's university has
explicitly said "yes, this company is allowed to talk to our students."**

And it's not just a blanket yes/no — the university also decides *which*
students. A university might say "this data company can talk to our
final-years and postgrads, but not our first-years." Until that permission is
granted, the business is completely blind to the student even existing on the
platform. This is the whole safety model in one sentence, and almost
everything else in the system exists to enforce it.

## What actually happens, start to finish

1. A university signs up for CAPLink (like buying a subscription).
2. A business asks that university for access.
3. The university's careers team reviews the request and approves it — but
   only for certain year-groups and certain types of work (e.g. "data
   analytics projects only, for 2nd-years and up").
4. The business posts a paid project ("Analyse our customer data, £19/hour,
   1-2 weeks").
5. Only students who are (a) at an approved university, (b) in an approved
   year-group, and (c) a good fit for the work even see this project.
6. A simple recommendation system suggests the project to the right students
   and explains *why* it's a good match ("your Python and SQL skills line up",
   "it's within your rate", "you have the hours free this week").
7. The student applies. The business reviews applicants (also ranked by fit)
   and picks one.
8. They agree a contract broken into milestones — e.g. "£80 for the first
   half, £120 for the final report."
9. The student does the work, marks a milestone done, the business approves
   it and the money is released (in a real deployment, via Stripe — the
   payment provider — currently this part is a placeholder for the demo).
10. When the work is finished, both sides rate each other — like Uber ratings,
    but neither side sees the other's rating until *both* have submitted
    theirs, so nobody just copies what the other person said or holds back a
    review out of fear of retaliation.

## Why messages get "flagged" sometimes

Before a contract exists, if a student or business tries to swap phone
numbers, mention WhatsApp, or say things like "I'll just pay you directly," the
system quietly flags it. This protects students from being lured off the
platform before any safety checks apply, and it protects the university/
platform's ability to actually oversee what's happening. It's an automated
first line of defence, not a punishment — in a bigger real product this would
be reviewed by a real person.

## Why it's a "demo" right now

A few pieces are deliberately left as placeholders because they need real
paid accounts/credentials to work for real, and aren't needed to understand or
try out how the platform behaves:

- **Paying people for real** — normally goes through Stripe (a company that
  handles online payments securely). Right now it just pretends the payment
  happened.
- **Phone push notifications** — normally goes through Firebase (Google's
  notification service for apps). Right now it just writes "a notification
  would have been sent" to a log file instead of buzzing a real phone.
- **Verifying a student is really a student** — two separate checks happen here.
  Confirming *which* university someone belongs to still just checks that their
  email ends in that university's domain (e.g. `@manchester.ac.uk`) — a real
  product would hook into the university's actual login system for this part.
  Confirming they actually *own* that email address is real, though: they get
  sent a link and have to click it before they can log in at all (in the local
  demo specifically, this step is skipped for convenience, since there's no real
  way to send emails yet — see below).

Everything else — the accounts, the permission system, the matching, the
applications, the contracts, the milestone payments logic, the ratings, the
messaging safety net — is fully working, you're just running it on your own
laptop instead of a live server on the internet.

## How you'd actually see it work

There's no app or website to click around in yet — just the underlying engine.
The closest thing to "using the product" today is either:

- a page in your browser (`/docs`) that lists every action the system can do
  and lets you try them one at a time, or
- typing commands in a terminal that ask the system to do things (register a
  student, post a project, apply, get paid, leave a rating) and watching the
  responses come back as data.

[03-user-guide-demo-walkthrough.md](03-user-guide-demo-walkthrough.md) does
exactly that second option, one step at a time, using the demo student
"Aisha" and the demo business "DataCraft Analytics" that get created
automatically the first time you set this up.
