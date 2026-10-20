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

CREATE TABLE cdrs (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT    NOT NULL UNIQUE,
    account_id  BIGINT  NOT NULL REFERENCES accounts(id),
    reserved    BIGINT  NOT NULL,
    used        BIGINT,               -- NULL si l'appel a expiré
    charged     BIGINT  NOT NULL,
    status      TEXT    NOT NULL CHECK (status IN ('COMPLETED', 'EXPIRED')),
    ended_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);