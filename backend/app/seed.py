"""Idempotent seed: admin user, a demo society/units, demo contractors."""
from .config import get_settings
from .db import get_conn, init_db
from .security import hash_password


def seed() -> None:
    init_db()
    s = get_settings()
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (s.seed_admin_email,)
        ).fetchone():
            conn.execute(
                "INSERT INTO users (email, password_hash, full_name, role) "
                "VALUES (?,?,?,?)",
                (
                    s.seed_admin_email,
                    hash_password(s.seed_admin_password),
                    "Administrator",
                    "admin",
                ),
            )
        if not conn.execute("SELECT 1 FROM societies").fetchone():
            conn.execute(
                "INSERT INTO societies (name, address) VALUES (?,?)",
                ("Palms Residency", "Goregaon, Mumbai 400065"),
            )
            for u in ["5B", "12A", "3C", "9D"]:
                conn.execute(
                    "INSERT INTO units (society_id, unit_number) "
                    "VALUES (1, ?)",
                    (u,),
                )
        if not conn.execute("SELECT 1 FROM contractors").fetchone():
            for name, spec, phone in [
                ("CoolAir Services", "AC/Cooling", "+919000000001"),
                ("AquaFix Plumbers", "Plumbing", "+919000000002"),
                ("Voltz Electricals", "Electrical", "+919000000003"),
                ("LiftCare", "Elevator", "+919000000004"),
            ]:
                conn.execute(
                    "INSERT INTO contractors (name, specialty, phone) "
                    "VALUES (?,?,?)",
                    (name, spec, phone),
                )
        # multi-society Phase 1: every legacy/global row belongs to the
        # default (first) society. Idempotent - only fills NULLs.
        soc = conn.execute(
            "SELECT id FROM societies ORDER BY id LIMIT 1"
        ).fetchone()
        if soc:
            did = dict(soc)["id"]
            for tbl in ("users", "contractors", "categories", "complaints"):
                conn.execute(
                    f"UPDATE {tbl} SET society_id = ? "
                    "WHERE society_id IS NULL",
                    (did,),
                )
            # E1a: seed sensible per-category SLA defaults for the
            # default society (idempotent — skip if a row exists).
            SLA_DEFAULTS = {
                "AC/Cooling":   (30, 4),
                "Plumbing":     (60, 8),
                "Electrical":   (30, 6),
                "Elevator":     (15, 2),     # safety
                "Housekeeping": (60, 24),
                "Security":     (15, 2),     # safety
                "Other":        (120, 24),
            }
            ESC = (
                '{"1":{"after_hours":2,"notify":"manager"},'
                '"2":{"after_hours":4,"notify":"sr_manager"},'
                '"3":{"after_hours":8,"notify":"secretary"}}'
            )
            for cat, (resp_m, resolve_h) in SLA_DEFAULTS.items():
                if not conn.execute(
                    "SELECT 1 FROM category_sla_config "
                    "WHERE society_id = ? AND category = ?",
                    (did, cat),
                ).fetchone():
                    conn.execute(
                        "INSERT INTO category_sla_config "
                        "(society_id, category, target_response_time_minutes, "
                        "target_resolution_time_hours, "
                        "priority_high_multiplier, escalation_levels) "
                        "VALUES (?,?,?,?,?,?)",
                        (did, cat, resp_m, resolve_h, 0.5, ESC),
                    )


if __name__ == "__main__":
    seed()
    print("seeded:", get_settings().seed_admin_email)
