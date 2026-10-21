import os
import sys
import psycopg
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

TEST_URL = os.environ.get("TEST_DATABASE_URL", "")

# Garde-fou : les tests vident la base, on refuse de tourner ailleurs
if not TEST_URL.endswith("_test"):
    pytest.exit("TEST_DATABASE_URL doit pointer vers une base *_test", returncode=1)


@pytest.fixture(autouse=True)
def clean_db():
    """Vide toutes les tables AVANT chaque test."""
    with psycopg.connect(TEST_URL) as c:
        c.execute("TRUNCATE cdrs, reservations, accounts RESTART IDENTITY CASCADE")


@pytest.fixture
def conn():
    with psycopg.connect(TEST_URL) as c:
        yield c


@pytest.fixture
def account(conn):
    """Un compte neuf à 100 centimes, propre à chaque test."""
    return conn.execute(
        "INSERT INTO accounts (balance) VALUES (100) RETURNING id"
    ).fetchone()[0]