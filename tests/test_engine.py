from engine import reserve, OK, CREDIT_LIMIT


def state(conn, account_id):
    return conn.execute(
        "SELECT balance, reserved FROM accounts WHERE id = %s", (account_id,)
    ).fetchone()


def test_reserve_ok(conn, account):
    assert reserve(conn, account, f"s-{account}", 60) == OK
    assert state(conn, account) == (100, 60)

def test_reserve_credit_limit(conn, account):
    assert reserve(conn, account, f"s-{account}", 120) == CREDIT_LIMIT
    assert state(conn, account) == (100, 0)