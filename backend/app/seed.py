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


if __name__ == "__main__":
    seed()
    print("seeded:", get_settings().seed_admin_email)
