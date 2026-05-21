# Findings — architectural issues surfaced during synthetic-data build

This directory captures architectural issues that were **discovered while
building the synthetic-data + diagnostics system** (branch
`claude/synthetic-data-and-diagnostics-2026-05-22`), but which are
**deliberately NOT being fixed on this branch** — each one needs its own
design conversation and a separate change set.

Why a `findings/` directory rather than inline fixes:

- The fixes have real architectural choices attached (e.g. "should
  admin be tenant-scoped or platform-global?") — those decisions belong
  to product, not to a test-data PR.
- Mixing fixes into a test-data branch hides them in a noisy diff and
  couples unrelated concerns.
- Keeping findings together makes it easy to scope a follow-up
  hardening sprint that addresses all of them coherently.

Each finding has its own markdown file with: what was discovered, where
in the code (with file:line citations), the immediate impact, whether
the issue is dormant or active today, the architectural decisions
attached, and a recommended path forward.

## Current findings

| # | Title | Severity | Status today |
|---|---|---|---|
| 001 | Admin role has cross-tenant data reach | **HIGH** | Dormant (only one admin exists; activates the moment a second admin is created on a different society) |
| 002 | No orphaned-work handling when staff/contractors are deactivated | MEDIUM | Active (deactivation today already produces zombie complaints) |

## How this directory grows

Subsequent parts of the synthetic-data build (Parts 3-6) may surface
additional findings. The walkthrough/demo step (Part 6) is particularly
likely to surface UX-level issues. New findings get added as
`NNN_short_slug.md` files and the table above is updated.

## What goes in `findings/` vs what gets fixed inline

**Fix inline (on this branch):**

- Bugs in code I'm writing for Parts 2-6 (the generator, seeder, wipe
  utility, diagnostics, etc.)
- Schema additions clearly needed for the synthetic-data system itself
  (e.g., `societies.is_demo`)
- Documentation gaps

**Goes in findings/ (separate work):**

- Architectural choices that need a product decision
- Pre-existing bugs in production code that I happen to discover while
  reading existing code
- Anything where the "right" fix depends on whether a second customer
  has been onboarded yet

This separation keeps the test-data PR reviewable and keeps the
findings actionable.
