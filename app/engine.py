import psycopg

OK = "OK"
CREDIT_LIMIT = "CREDIT_LIMIT_REACHED"
UNKNOWN_ACCOUNT = "UNKNOWN_ACCOUNT"

def reserve(conn, account_id, session_id, amount, ttl_seconds=60):
    with conn.transaction():
        already = conn.execute(
            """
            SELECT 1 FROM reservations WHERE session_id = %s
            """,
            (session_id,),
        ).fetchone()
        if already:
            return OK

        cur = conn.execute(
            """
            UPDATE accounts
            SET reserved = reserved + %s
            WHERE id = %s
            AND balance - reserved >= %s          
            """,
            (amount, account_id, amount)
        )

        if cur.rowcount == 0:
            exists = conn.execute(
                """
                SELECT 1 FROM accounts WHERE id = %s

                """,
                (account_id,),
            ).fetchone()
            return CREDIT_LIMIT if exists else UNKNOWN_ACCOUNT

        conn.execute(
            """
            INSERT INTO reservations (account_id, session_id, a0mount, expires_at)
            VALUES (%s, %s, %s, now() + make_interval(secs => %s))
            """,
            (account_id, session_id, amount, ttl_seconds),
        )
        return OK