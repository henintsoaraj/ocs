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
            INSERT INTO reservations (account_id, session_id, amount, expires_at)
            VALUES (%s, %s, %s, now() + make_interval(secs => %s))
            """,
            (account_id, session_id, amount, ttl_seconds),
        )
        return OK

# def reserve_naive(conn, account_id, session_id, amount):
#     with conn.transaction():
#         # 1. Lire
#         balance, reserved = conn.execute(
#             "SELECT balance, reserved FROM accounts WHERE id = %s",
#             (account_id,),
#         ).fetchone()

#         # 2. Vérifier (en Python, pas dans la base)
#         if balance - reserved < amount:
#             return CREDIT_LIMIT

#         # 3. Écrire la nouvelle valeur calculée en Python
#         conn.execute(
#             "UPDATE accounts SET reserved = %s WHERE id = %s",
#             (reserved + amount, account_id),
#         )
#         # return OK