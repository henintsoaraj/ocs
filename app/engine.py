import psycopg

OK = "OK"
CREDIT_LIMIT = "CREDIT_LIMIT_REACHED"
UNKNOWN_ACCOUNT = "UNKNOWN_ACCOUNT"
UNKNOWN_SESSION = "UNKNOWN_SESSION"

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

def terminate(conn, session_id, used):
    with conn.transaction():
        row = conn.execute(
            """
            DELETE FROM reservations
            WHERE session_id = %s
            RETURNING account_id, amount
            """,
            (session_id,),
        ).fetchone()

        if row is None:
            return UNKNOWN_SESSION

        account_id, reserved_amount = row

        amount_real = min(used, reserved_amount)
        if used > reserved_amount:
            print(f"ANOMALIE session={session_id} : used={used} > réservé={reserved_amount}, "
                  f"écart de {used - reserved_amount} non prélevé")

        conn.execute(
            """
            UPDATE accounts
            SET balance  = balance  - %s,
                reserved = reserved - %s
            WHERE id = %s
            """,
            (amount_real, reserved_amount, account_id),
        )
        return OK

def expire_reservations(conn):
    """Libère les réservations expirées, sans rien prélever.
    Renvoie le nombre de réservations libérées."""
    with conn.transaction():
        rows = conn.execute(
            """
            DELETE FROM reservations
            WHERE expires_at < now()
            RETURNING account_id, amount
            """
        ).fetchall()

        for account_id, amount in rows:
            conn.execute(
                "UPDATE accounts SET reserved = reserved - %s WHERE id = %s",
                (amount, account_id),
            )

        return len(rows)

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