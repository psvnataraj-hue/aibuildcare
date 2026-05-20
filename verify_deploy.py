"""One-shot prod deploy verification — run after a Render Manual Deploy.

Usage (from any terminal — cmd.exe, PowerShell, Git Bash, all fine):
    cd C:\\Users\\psvna\\OneDrive\\Documents\\aibuildcare
    python verify_deploy.py

The script will prompt for the admin password (input is hidden — does
not echo to the terminal and is not stored in shell history).

Or pass it via env var (CI-friendly):
    set AIBUILDCARE_VERIFY_ADMIN_PWD=<password>
    python verify_deploy.py

NOTE: command-line arg is intentionally NOT supported any more (used
to be `python verify_deploy.py <password>`) so the password cannot leak
into shell history, chat transcripts, or process listings.

Hits prod (https://aibuildcare-api.onrender.com) over HTTPS. No repo
state is read or written.
"""
import getpass
import json
import os
import sys
import urllib.request
import urllib.error

BASE = "https://aibuildcare-api.onrender.com"
ADMIN_EMAIL = "admin@aibuildcare.app"


def http(method, path, headers=None, body=None):
    """Returns (status_code, response_body_text)."""
    req = urllib.request.Request(
        BASE + path,
        method=method,
        headers=headers or {},
        data=body.encode() if body else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def ok(label):
    print(f"  PASS  {label}")


def fail(label, detail=""):
    print(f"  FAIL  {label}" + (f"  ({detail})" if detail else ""))
    return False


def read_password() -> str:
    """Env-var first (for CI), then hidden interactive prompt. Never
    accepts a command-line argument — see module docstring."""
    pwd = os.environ.get("AIBUILDCARE_VERIFY_ADMIN_PWD")
    if pwd:
        return pwd
    try:
        return getpass.getpass("admin password (hidden): ")
    except (EOFError, KeyboardInterrupt):
        print("\nNo password provided; aborting.")
        sys.exit(2)


def main(password: str) -> int:
    all_pass = True

    print("\n[1/5] Health check")
    code, body = http("GET", "/health")
    if code == 200 and '"ok"' in body:
        ok(f"GET /health -> 200 {body.strip()}")
    else:
        all_pass = fail(f"GET /health -> {code} {body[:100]}")

    print("\n[2/5] Login as admin")
    code, body = http(
        "POST", "/api/v1/auth/login",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"email": ADMIN_EMAIL, "password": password}),
    )
    if code != 200:
        fail(f"login -> {code} {body[:200]}")
        print("\nStopping; can't run authed checks without a token.")
        return 1
    token = json.loads(body)["access_token"]
    ok(f"POST /api/v1/auth/login -> 200 (token len {len(token)})")

    auth = {"Authorization": f"Bearer {token}"}

    print("\n[3/5] E3c: assigned_staff_name field in complaints payload")
    code, body = http("GET", "/api/v1/complaints", headers=auth)
    if code != 200:
        all_pass = fail(f"GET /complaints -> {code} {body[:120]}")
    else:
        rows = json.loads(body)
        if not rows:
            ok("GET /complaints -> 200 (empty list; field check skipped — "
               "no rows on prod yet)")
        elif "assigned_staff_name" in rows[0]:
            ok(f"GET /complaints[0] contains 'assigned_staff_name' = "
               f"{rows[0]['assigned_staff_name']!r}")
        else:
            all_pass = fail(
                "GET /complaints[0] missing 'assigned_staff_name'",
                f"keys: {sorted(rows[0].keys())}",
            )

    print("\n[4/5] B1: cron endpoint is gated correctly")
    code, body = http("POST", "/internal/jobs/tick")
    if code == 503 and "not configured" in body:
        ok(f"POST /internal/jobs/tick (no secret) -> 503 (secret not set, "
           "safe default)")
    elif code == 403:
        ok(f"POST /internal/jobs/tick (no secret) -> 403 (secret set, "
           "header missing)")
    else:
        all_pass = fail(f"POST /internal/jobs/tick -> {code} {body[:120]}")

    print("\n[5/5] B2: /logout actually revokes the token")
    code, body = http("POST", "/api/v1/auth/logout", headers=auth)
    if code == 204:
        ok("POST /api/v1/auth/logout -> 204")
    else:
        all_pass = fail(f"POST /logout -> {code} {body[:120]}")

    # Reuse the token after logout -> must be 401
    code, body = http("GET", "/api/v1/complaints", headers=auth)
    if code == 401:
        ok("GET /complaints with revoked token -> 401 (revocation works)")
    else:
        all_pass = fail(
            "GET /complaints with revoked token still works",
            f"got {code} — auth_sessions enforcement may not be live",
        )

    print()
    if all_pass:
        print("ALL CHECKS PASSED. Deploy is verified live and healthy.")
        return 0
    print("ONE OR MORE CHECKS FAILED. See output above.")
    return 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(
            "verify_deploy.py no longer accepts the password as a "
            "command-line argument (security: prevents leakage via\n"
            "shell history, chat transcripts, and process listings).\n"
            "Either let the script prompt you interactively, or set\n"
            "the AIBUILDCARE_VERIFY_ADMIN_PWD env var first."
        )
        sys.exit(2)
    sys.exit(main(read_password()))
