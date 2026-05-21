# Finding 003 — User-facing "complaint/complainant" labels read wrong outside housing

**Discovered**: 2026-05-22, while planning Part 3 (historical complaints
seed). Generating a few hundred records full of the word "complaint"
made the misfit visible for non-housing verticals.

**Severity**: LOW (cosmetic), but **becomes high-impact at demo time**
for hospital / office / event prospects.

**Status today**: active for all four demo tenants, but only noticeable
on Sunrise / Stellar / Meridian — Greenwood is housing, where
"complaint" is appropriate vocabulary.

---

## What's wrong

The schema, code, services, and user-facing labels consistently use the
words **"complaint"** (the entity) and **"complainant"** (the filer).
That terminology fits housing societies perfectly — residents file
complaints, secretaries handle them. It does *not* fit the other three
verticals:

| Vertical | "complaint" reads as… | Should be… |
|---|---|---|
| Greenwood (housing) | natural — exactly right | (keep "complaint") |
| Sunrise (hospital) | wrong — "Room 12 needs cleaning" is a *request*, not a *complaint*; calling a nurse "the complainant" is inappropriate | **"request"** / **"requester"** |
| Stellar (events) | mostly wrong — "AV mic not working" is a *ticket* or *issue*, an event manager filing it isn't a *complainant* | **"ticket"** / **"reporter"** or **"request"** / **"requester"** |
| Meridian (office) | wrong — a tenant employee reporting "lift not working" is filing a *service request* | **"request"** / **"requester"** |

The hospital case is the most pointed: "complainant" has an
adversarial / formal-grievance connotation that's actively wrong for a
nursing supervisor reporting that a bedpan needs replacing. A doctor or
hospital admin reviewing the demo dashboard will notice this in the
first thirty seconds.

---

## Scope of the rename

The rename is **user-facing only** — schema columns, service-layer
identifiers, log-line keys, and code variable names can stay as
`complaint*`. What changes:

1. **Dashboard labels** — the page titles ("Complaints"), navigation,
   buttons ("File new complaint" → "Create new request"), column
   headers, status pills.
2. **WhatsApp template messages** — the strings the user receives:
   * "Your complaint has been received" → "Your request has been received"
   * "Your complaint has been resolved" → "Your request has been resolved"
   * "Please rate your complaint experience" → "…your request handling"
3. **Email subject lines** for SLA-breach + weekly summary notifications.
4. **API response label keys** in `/auth/me` / dashboard payload — IF
   the frontend pulls human-readable labels from the backend (otherwise
   purely frontend).

What does NOT change:

- `complaints` table name and any column names
- Service function names (`complaint_service.create_complaint`, etc.)
- Internal log line keys (e.g., `event: complaint_created`)
- API endpoint paths (`/api/v1/complaints`) — breaking-change, defer
- Code-level variable names

The principle: keep the engineering vocabulary stable, change only the
words a user sees.

---

## Per-vertical strategy

Three options, escalating in scope:

**Option A — Vertical-aware label dictionary (one config per society).**

- Add a `terminology_labels` JSON field on `societies` or a separate
  per-society dictionary table.
- The frontend reads labels per-society at login (`/auth/me` extension)
  and substitutes throughout the UI.
- WhatsApp templates likewise read from the dictionary.
- Each vertical gets its preferred terminology; housing keeps
  "complaint", others get "request".

Pros: cleanest. Each customer's UI matches their domain vocabulary
exactly. Onboarding a new vertical is a config change, not a code change.
Cons: requires frontend + backend work + content audit of every label
and message template.

**Option B — Global rename to "request/requester".**

- "request" is more vertical-neutral than "complaint" — works for
  housing ("AC not cooling" *is* a request for maintenance) AND
  hospital AND office AND events.
- One-time rename of all labels + templates to "request/requester".
- No per-vertical dictionary.

Pros: simpler. Avoids the "is this customer a housing-society or a
hospital today?" awareness in the UI.
Cons: housing customers might prefer "complaint" — but "request" reads
fine there too.

**Option C — Status quo, document the gap.**

- Keep "complaint/complainant" everywhere.
- Add a note to onboarding docs that the labels assume a housing-style
  deployment.
- Customers who care can request a frontend skin.

Pros: zero work.
Cons: cosmetic embarrassment in non-housing demos. Probably loses deals
in the hospital vertical specifically.

**Recommendation**: **Option B** (global rename to "request/requester")
before the first non-housing demo. It's the smaller change set and
"request" works fine for housing customers too — there's no upside to
maintaining vertical-aware dictionaries when one neutral word fits all.

---

## Why this isn't blocking Part 3

Part 3 generates ~200-300 *historical* records using the current schema
(`complaints` table, `complaint_messages`, etc.). Those records survive
the rename — only the labels change, not the data.

Generating the test data today using "complaint" terminology is the
right call because (a) the schema is what the schema is, (b) re-running
the generator post-rename is a single command, and (c) blocking the
test-data work on a label rename would couple unrelated concerns.

---

## Recommended next steps (separate change set)

1. Decide Option A vs B (Nataraj decision, before first non-housing
   demo).
2. Identify the full set of user-facing strings touching
   "complaint/complainant" — frontend code + WhatsApp templates + email
   templates. Estimate: 30-60 strings.
3. Rename in one pass + audit + ship.
4. Estimate: 1 day for Option B, 2-3 days for Option A.

**Critical-path timing**: must be done before the first Sunrise /
Stellar / Meridian demo to a prospect. Not blocking for Palms ops or
for Sravya's testing on the demos (she'll see the misfit but won't
mistake it for a bug).
