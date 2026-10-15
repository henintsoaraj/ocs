import os
import psycopg
from engine import reserve

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    print("1 :", reserve(conn, 1, "appel-test-1", 10))
    print("2 :", reserve(conn, 1, "appel-test-2", 30))
    print("3 :", reserve(conn, 999, "appel-test-3", 10))