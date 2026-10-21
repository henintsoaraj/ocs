import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def migrate(url):
    with psycopg.connect(url, autocommit=True) as conn:
        # Le carnet : créé seulement s'il n'existe pas encore
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )

        # Ce que cette base a déjà reçu
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}

        # Les fichiers, dans l'ordre de leur numéro
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem          # "001_accounts_reservations"
            if version in applied:
                continue                      # déjà appliquée : passer à la suivante

            with conn.transaction():     # appliquer ET inscrire, ou rien
                conn.execute(path.read_text())
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (version,),
                )
            print(f"appliquée : {version}")


if __name__ == "__main__":
    # L'adresse de la base en argument, sinon DATABASE_URL
    url = sys.argv[1] if len(sys.argv) > 1 else os.environ["DATABASE_URL"]
    migrate(url)