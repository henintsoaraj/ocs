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