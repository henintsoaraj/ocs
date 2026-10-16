import os
import sys
import psycopg
import pytest

# Permet aux tests de trouver app/engine.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


@pytest.fixture
def conn():
    with psycopg.connect(os.environ["DATABASE_URL"]) as c:
        yield c


@pytest.fixture
def account(conn):
    """Un compte neuf à 100 centimes, propre à chaque test."""
    return conn.execute(
        "INSERT INTO accounts (balance) VALUES (100) RETURNING id"
    ).fetchone()[0]