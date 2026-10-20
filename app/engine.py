import psycopg

OK = "OK"
CREDIT_LIMIT = "CREDIT_LIMIT_REACHED"
UNKNOWN_ACCOUNT = "UNKNOWN_ACCOUNT"
UNKNOWN_SESSION = "UNKNOWN_SESSION"
SESSION_EXPIRED = "SESSION_EXPIRED"

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
            # Réservation introuvable : appel déjà traité, ou inconnu ?
            cdr = conn.execute(
                "SELECT status FROM cdrs WHERE session_id = %s",
                (session_id,),
            ).fetchone()
            if cdr is None:
                return UNKNOWN_SESSION
            return OK if cdr[0] == "COMPLETED" else SESSION_EXPIRED

        account_id, reserved_amount = row

        charged = min(used, reserved_amount)
        if used > reserved_amount:
            print(f"ANOMALIE session={session_id} : used={used} > "
                  f"réservé={reserved_amount}, écart de "
                  f"{used - reserved_amount} non prélevé")

        conn.execute(
            """
            UPDATE accounts
            SET balance  = balance  - %s,
                reserved = reserved - %s
            WHERE id = %s
            """,
            (charged, reserved_amount, account_id),
        )

        conn.execute(
            """
            INSERT INTO cdrs (session_id, account_id, reserved, used, charged, status)
            VALUES (%s, %s, %s, %s, %s, 'COMPLETED')
            """,
            (session_id, account_id, reserved_amount, used, charged),
        )
        return OK

def expire_reservations(conn):
    """Libère les réservations expirées, sans rien prélever, et écrit
    un CDR EXPIRED pour chacune. Renvoie le nombre de réservations libérées."""
    with conn.transaction():
        rows = conn.execute(
            """
            DELETE FROM reservations
            WHERE expires_at < now()
            RETURNING account_id, amount, session_id
            """
        ).fetchall()

        for account_id, amount, session_id in rows:
            conn.execute(
                "UPDATE accounts SET reserved = reserved - %s WHERE id = %s",
                (amount, account_id),
            )
            conn.execute(
                """
                INSERT INTO cdrs (session_id, account_id, reserved, used, charged, status)
                VALUES (%s, %s, %s, %s, %s, 'EXPIRED')
                """,
                (session_id, account_id, amount, None, 0),
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