import os
import psycopg
from engine import reserve, terminate

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    acc = conn.execute(
        "INSERT INTO accounts (balance) VALUES (100) RETURNING id"
    ).fetchone()[0]

    print("réserve :", reserve(conn, acc, f"appel-{acc}", 60))
    print("état    :", conn.execute(
        "SELECT balance, reserved FROM accounts WHERE id = %s", (acc,)).fetchone())

    print("termine :", terminate(conn, f"appel-{acc}", 40))
    print("état    :", conn.execute(
        "SELECT balance, reserved FROM accounts WHERE id = %s", (acc,)).fetchone())

    print("termine :", terminate(conn, f"appel-{acc}", 40))

    print("réserve :", reserve(conn, acc, f"appel-{acc}-b", 30))
    print("termine :", terminate(conn, f"appel-{acc}-b", 50))
    print("état    :", conn.execute(
        "SELECT balance, reserved FROM accounts WHERE id = %s", (acc,)).fetchone())