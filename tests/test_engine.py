import os
from concurrent.futures import ThreadPoolExecutor
from collections import Counter

import psycopg

from engine import (
    reserve, terminate,
    OK, CREDIT_LIMIT, UNKNOWN_ACCOUNT, UNKNOWN_SESSION,
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
    # La 2e fin d'appel ne trouve plus la réservation : rien n'est débité
    session = f"s-{account}"
    reserve(conn, account, session, 60)
    terminate(conn, session, 40)
    assert terminate(conn, session, 40) == UNKNOWN_SESSION
    assert state(conn, account) == (60, 0)


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

    url = os.environ["DATABASE_URL"]

    def one(i):
        with psycopg.connect(url) as c:
            return reserve(c, account, f"s-{account}-{i}", 10)

    with ThreadPoolExecutor(max_workers=50) as pool:
        results = Counter(pool.map(one, range(100)))

    assert results == {OK: 10, CREDIT_LIMIT: 90}
    assert state(conn, account) == (100, 100)