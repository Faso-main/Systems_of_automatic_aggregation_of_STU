psql -h localhost -U th3_app -d th3_db

CREATE TABLE IF NOT EXISTS category_similarity (
    category_id_a    bigint NOT NULL,
    category_id_b    bigint NOT NULL,
    similarity       numeric(5,4) NOT NULL,
    common_keys      text[]       NOT NULL,
    only_a_keys      text[]       NOT NULL,
    only_b_keys      text[]       NOT NULL,
    created_at       timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT category_similarity_pk PRIMARY KEY (category_id_a, category_id_b)
);

