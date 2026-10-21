import os
from concurrent.futures import ThreadPoolExecutor
from collections import Counter

import psycopg

from engine import (
    reserve, terminate,expire_reservations,
    OK, CREDIT_LIMIT, UNKNOWN_ACCOUNT, UNKNOWN_SESSION, SESSION_EXPIRED
)


def state(conn, account_id):
    """Renvoie (balance, reserved) d'un compte."""
    return conn.execute(
        "SELECT balance, reserved FROM accounts WHERE id = %s", (account_id,)
    ).fetchone()


# ---------------------------------------------------------------- reserve()

def test_reserve_ok(conn, account):
    # 60 sur 100 disponibles : accepté, bloqué mais pas prélevé
    assert reserve(conn, account, f"s-{account}", 60) == OK
    assert state(conn, account) == (100, 60)


def test_reserve_credit_limit(conn, account):
    # 120 sur 100 disponibles : refusé, et le compte n'a pas bougé
    assert reserve(conn, account, f"s-{account}", 120) == CREDIT_LIMIT
    assert state(conn, account) == (100, 0)


def test_reserve_unknown_account(conn):
    # Aucun compte n'a l'id -1 : UPDATE 0, puis le SELECT 1 ne trouve rien
    assert reserve(conn, -1, "s-inconnu", 10) == UNKNOWN_ACCOUNT


def test_reserve_retransmission(conn, account):
    # La même demande deux fois (même session_id) :
    # même réponse, mais le crédit n'est bloqué qu'une seule fois
    session = f"s-{account}"
    assert reserve(conn, account, session, 60) == OK
    assert reserve(conn, account, session, 60) == OK
    assert state(conn, account) == (100, 60)


# -------------------------------------------------------------- terminate()

def test_terminate(conn, account):
    # Réserve 60, consomme 40 : on prélève 40, on débloque les 60
    session = f"s-{account}"
    reserve(conn, account, session, 60)
    assert terminate(conn, session, 40) == OK
    assert state(conn, account) == (60, 0)


def test_terminate_twice(conn, account):
    # Une fin d'appel retransmise : reconnue grâce au CDR,
    # même réponse (OK), rien de plus prélevé, un seul ticket
    session = f"s-{account}"
    reserve(conn, account, session, 60)
    terminate(conn, session, 40)
    assert terminate(conn, session, 40) == OK
    assert state(conn, account) == (60, 0)
    assert conn.execute(
        "SELECT count(*) FROM cdrs WHERE session_id = %s", (session,)
    ).fetchone()[0] == 1


def test_terminate_overuse(conn, account):
    # Réserve 30, le réseau annonce 50 : on ne prélève que les 30 réservés
    session = f"s-{account}"
    reserve(conn, account, session, 30)
    assert terminate(conn, session, 50) == OK
    assert state(conn, account) == (70, 0)


# ------------------------------------------------------------- concurrence

def test_concurrent_reservations(conn, account):
    # 100 demandes de 10 en parallèle sur 100 centimes :
    # exactement 10 acceptées, jamais un centime de trop
    conn.commit()   # rendre le compte visible aux autres connexions

    url = os.environ["TEST_DATABASE_URL"]

    def one(i):
        with psycopg.connect(url) as c:
            return reserve(c, account, f"s-{account}-{i}", 10)

    with ThreadPoolExecutor(max_workers=50) as pool:
        results = Counter(pool.map(one, range(100)))

    assert results == {OK: 10, CREDIT_LIMIT: 90}
    assert state(conn, account) == (100, 100)

def test_expire_reservations(conn, account):
    # Une réservation déjà expirée (TTL négatif) et une encore valide
    reserve(conn, account, f"s-{account}-old", 30, ttl_seconds=-1)
    reserve(conn, account, f"s-{account}-new", 20)
    assert state(conn, account) == (100, 50)

    expire_reservations(conn)

    # Seule la réservation expirée est libérée, et rien n'est prélevé
    assert state(conn, account) == (100, 20)

    # Une fin d'appel tardive est reconnue grâce au CDR EXPIRED
    assert terminate(conn, f"s-{account}-old", 30) == SESSION_EXPIRED   # ← avant : UNKNOWN_SESSION
    assert state(conn, account) == (100, 20)

def test_expire_writes_cdr(conn, account):
    session = f"s-{account}"
    reserve(conn, account, session, 60, ttl_seconds=-1)
    expire_reservations(conn)

    assert conn.execute(
        "SELECT reserved, used, charged, status FROM cdrs WHERE session_id = %s",
        (session,),
    ).fetchone() == (60, None, 0, "EXPIRED")

    # La fin d'appel arrive après l'expiration
    assert terminate(conn, session, 40) == SESSION_EXPIRED
    assert state(conn, account) == (100, 0)

def test_terminate_writes_cdr(conn, account):
    # Un dépassement (réserve 30, annonce 50) : le CDR garde
    # ce qui a été annoncé (used) ET ce qui a été prélevé (charged)
    session = f"s-{account}"
    reserve(conn, account, session, 30)
    terminate(conn, session, 50)
    assert conn.execute(
        "SELECT reserved, used, charged, status FROM cdrs WHERE session_id = %s",
        (session,),
    ).fetchone() == (30, 50, 30, "COMPLETED")