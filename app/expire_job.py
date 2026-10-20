# app/expire_job.py
import os
import psycopg
from engine import expire_reservations

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    n = expire_reservations(conn)
    print(f"{n} réservation(s) expirée(s) libérée(s)")