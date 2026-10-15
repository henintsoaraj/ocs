import os
import psycopg

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    row = conn.execute("SELECT * FROM accounts").fetchall()
    print(row)