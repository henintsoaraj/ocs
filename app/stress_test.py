import os
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import psycopg
from engine import reserve

URL = os.environ["TEST_DATABASE_URL"]

# 1. Un compte neuf avec 1 € (100 centimes)
with psycopg.connect(URL) as conn:
    account_id = conn.execute(
        "INSERT INTO accounts (balance) VALUES (100) RETURNING id"
    ).fetchone()[0]
print("Compte créé :", account_id)

# 2. Une réservation de 10 centimes, chacune avec SA connexion
def one_reservation(i):
    with psycopg.connect(URL) as conn:
        return reserve(conn, account_id, f"stress-{account_id}-{i}", 10)

# 3. 100 demandes lancées en parallèle
with ThreadPoolExecutor(max_workers=50) as pool:
    results = list(pool.map(one_reservation, range(100)))

print(Counter(results))

# 4. L'état final du compte
with psycopg.connect(URL) as conn:
    print(conn.execute(
        "SELECT balance, reserved FROM accounts WHERE id = %s", (account_id,)
    ).fetchone())