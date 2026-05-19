"""One-off: scoped-clear the 5 audio test tickets for a clean pilot slate.

Safe by construction:
  * targets ONLY the explicitly named ticket numbers,
  * ABORTS if the complaints table contains anything other than exactly
    those 5 rows (protects real pilot data if state drifted),
  * deletes child rows before parents (no ON DELETE CASCADE in PG schema),
  * preserves categories / contractors / system_config (never touched).

Run:  cd backend && .venv/Scripts/python ../scripts/clear_test_tickets.py
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # Windows cp1252 console safety

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import get_conn  # noqa: E402

EXPECTED = {f"SER-2026-{n:05d}" for n in range(1, 6)}


def _count(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]


def main() -> int:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, ticket_number, channel, status, "
            "substr(raw_text,1,60) AS snippet "
            "FROM complaints ORDER BY id"
        ).fetchall()

        print(f"complaints currently in DB: {len(rows)}")
        for r in rows:
            print(
                f"  id={r['id']:>3}  {r['ticket_number']}  "
                f"[{r['channel']}/{r['status']}]  {r['snippet']!r}"
            )

        found = {r["ticket_number"] for r in rows}
        if len(rows) != 5 or found != EXPECTED:
            print(
                "\nABORT: table is not the expected 5 audio test tickets.\n"
                f"  expected: {sorted(EXPECTED)}\n"
                f"  found:    {sorted(found)}\n"
                "Nothing deleted. Inspect manually before clearing."
            )
            return 1

        ids = [r["id"] for r in rows]
        ph = ",".join("?" * len(ids))
        pre = {
            t: _count(conn, t)
            for t in ("categories", "contractors", "system_config")
        }

        for child in (
            "complaint_messages",
            "complaint_status_history",
            "complaint_ratings",
        ):
            c = conn.execute(
                f"DELETE FROM {child} WHERE complaint_id IN ({ph})", ids
            )
            print(f"deleted {c.rowcount} from {child}")
        c = conn.execute(
            f"DELETE FROM complaints WHERE id IN ({ph})", ids
        )
        print(f"deleted {c.rowcount} from complaints")

        post_complaints = _count(conn, "complaints")
        post = {
            t: _count(conn, t)
            for t in ("categories", "contractors", "system_config")
        }

    print("\n--- result ---")
    print(f"complaints remaining: {post_complaints} (expect 0)")
    for t in pre:
        ok = "OK" if pre[t] == post[t] else "CHANGED!"
        print(f"  {t}: {pre[t]} -> {post[t]}  [{ok}]")
    return 0 if post_complaints == 0 and pre == post else 2


if __name__ == "__main__":
    raise SystemExit(main())
