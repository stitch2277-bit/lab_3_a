BEGIN;

CREATE TABLE credentials (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title varchar(120) NOT NULL CHECK (btrim(title) <> ''),
    username varchar(160) NOT NULL CHECK (btrim(username) <> ''),
    password_token bytea NOT NULL CHECK (octet_length(password_token) > 0)
);

CREATE TABLE activity_log (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    credential_id bigint NOT NULL,
    title varchar(120) NOT NULL,
    action varchar(6) NOT NULL CHECK (action IN ('create', 'update', 'reveal', 'delete')),
    occurred_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX activity_log_occurred_at_idx ON activity_log (occurred_at DESC, id DESC);

COMMIT;
