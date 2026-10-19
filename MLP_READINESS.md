# Buildwise GH — MLP readiness

## Working assumption

“MLP” means **Minimum Lovable Product**: a small, polished product suitable for a controlled pilot with Ghanaian homeowners, small developers or design professionals. It does not mean a licensed engineering, quantity-surveying or permit product.

## In place

- Account registration, sign-in and private project ownership.
- Project briefs with optional names; list, detail and delete flows.
- Deterministic brief extraction with visible concept assumptions.
- Schematic SVG room plan, draggable browser massing view and downloadable GLB.
- Sequential schedule and indicative cost allocation with a CSV export.
- Preliminary compliance screen with explicit non-approval wording.
- Responsive same-origin UI, SQLite local setup, Postgres Render Blueprint, Docker setup.
- Unit and API integration tests for authentication, project ownership, generation, export and deletion.

## Gates before an external pilot

1. **Revoke any token shared in chat.** Use GitHub's local/secure authentication flow; do not paste replacement credentials into chat.
2. **Get a professional review of product claims and data.** Starter Ghana cost rates and screening values are placeholders, not verified current prices or legal code extracts.
3. **Decide whether to add a real AI provider.** The current parser is deterministic/rule-based; it does not call an LLM. Any provider would need a server-side secret configured securely in Render and a privacy decision about sending user briefs externally.
4. **Populate the contractor directory only with vetted, permissioned entries.** It intentionally starts empty rather than inventing businesses or phone numbers.
5. **Complete launch safeguards:** email verification/account recovery, account deletion, database migrations, rate limiting, backups, monitoring, privacy notice and terms reviewed for the actual service.
6. **Deploy and verify on Render.** Render Blueprint is prepared, but a repository push and Render resource approval require authenticated GitHub/Render access not available in this chat session.
7. **Pilot-test with real users and devices** before wider promotion; confirm that the concept outputs are understandable and not mistaken for construction documents.
