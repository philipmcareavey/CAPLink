# CAPLink Documentation

This folder is a self-contained guide for getting the CAPLink backend demo running
and understanding what it does — written for someone who has never touched this
codebase before, with no assumed FastAPI/SQLAlchemy experience.

Read them in this order:

1. **[01-project-structure.md](01-project-structure.md)** — what CAPLink is, how the
   code is organised, and how the pieces (models, schemas, services, endpoints) fit
   together.
2. **[02-getting-started.md](02-getting-started.md)** — install everything and get the
   server running locally, including fixes for every snag a fresh Mac is likely to
   hit.
3. **[03-user-guide-demo-walkthrough.md](03-user-guide-demo-walkthrough.md)** — a full
   worked example: register accounts, approve a business, post a project, apply,
   sign a contract, get paid, leave a rating.
4. **[04-using-the-api-docs-ui.md](04-using-the-api-docs-ui.md)** — CAPLink has no
   web front-end yet; the "user interface" for this demo is the interactive Swagger
   page at `/docs`. This explains how to actually drive it, including how to
   authenticate with the Authorize button.
5. **[05-explain-it-simply.md](05-explain-it-simply.md)** — a plain-English
   explanation of what this project *is* and why it exists, no jargon, suitable for
   explaining to someone non-technical.
6. **[06-troubleshooting.md](06-troubleshooting.md)** — every error we actually hit
   getting this running on a real machine, and the fix.

If you only read one file, read #2 to get it running, then #3 to see it do
something.
