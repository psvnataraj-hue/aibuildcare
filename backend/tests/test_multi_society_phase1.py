"""Multi-society Phase 1: additive society_id columns + seed backfill.

Phase 1 is behaviour-neutral: it only guarantees every legacy row is
stamped with the default society. Enforcement/isolation arrives later.
"""
from app.db import get_conn


def _default_society(conn) -> int:
    return dict(
        conn.execute(
            "SELECT id FROM societies ORDER BY id LIMIT 1"
        ).fetchone()
    )["id"]


def test_society_id_columns_exist_and_backfilled(client):
    with get_conn() as conn:
        did = _default_society(conn)
        for tbl in ("users", "contractors", "categories"):
            rows = [
                dict(r)
                for r in conn.execute(
                    f"SELECT society_id FROM {tbl}"
                ).fetchall()
            ]
            assert rows, f"{tbl} should be seeded"
            assert all(
                r["society_id"] == did for r in rows
            ), f"{tbl} not fully backfilled to default society"


def test_complaints_have_society_column(client):
    # column present (complaints already had society_id in schema);
    # query must not error even though table is empty
    with get_conn() as conn:
        conn.execute("SELECT society_id FROM complaints").fetchall()


def test_seed_backfill_is_idempotent(client):
    from app.seed import seed

    seed()  # second run must not raise or create NULLs
    with get_conn() as conn:
        for tbl in ("users", "contractors", "categories"):
            n = dict(
                conn.execute(
                    f"SELECT COUNT(*) AS c FROM {tbl} "
                    "WHERE society_id IS NULL"
                ).fetchone()
            )["c"]
            assert n == 0, f"{tbl} has unscoped rows after re-seed"
