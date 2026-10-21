CREATE TABLE accounts (
    id       BIGSERIAL PRIMARY KEY,
    balance  BIGINT NOT NULL CHECK (balance >= 0),   -- en centimes
    reserved BIGINT NOT NULL DEFAULT 0
             CHECK (reserved >= 0 AND reserved <= balance)
);

CREATE TABLE reservations (
    id          BIGSERIAL PRIMARY KEY,
    account_id  BIGINT NOT NULL REFERENCES accounts(id),
    session_id  TEXT   NOT NULL UNIQUE,   -- identifie l'appel
    amount      BIGINT NOT NULL CHECK (amount > 0),
    expires_at  TIMESTAMPTZ NOT NULL
);