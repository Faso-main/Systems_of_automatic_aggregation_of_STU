--
-- PostgreSQL database cluster dump
--

\restrict ES3mj3SfXXpFwBJXtvIwtTFjx96nRCvK9XndzEOTuco8333NUrzxq1ha7N2TVcj

SET default_transaction_read_only = off;

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

--
-- Roles
--

CREATE ROLE postgres;
ALTER ROLE postgres WITH SUPERUSER INHERIT CREATEROLE CREATEDB LOGIN REPLICATION BYPASSRLS;
CREATE ROLE th3_app;
ALTER ROLE th3_app WITH SUPERUSER INHERIT NOCREATEROLE NOCREATEDB LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'SCRAM-SHA-256$4096:iAScoW7b46R81OO2MgwHow==$PEdk3BSz/rooVWhILZTUy0zkkbEbYf9g1p3WA9+MV4I=:iNL3Zih8xvyuPmDY2whXW15QT/+qsAPqFTkwQy2yfdc=';

--
-- User Configurations
--






\unrestrict ES3mj3SfXXpFwBJXtvIwtTFjx96nRCvK9XndzEOTuco8333NUrzxq1ha7N2TVcj

--
-- Databases
--

--
-- Database "template1" dump
--

\connect template1

--
-- PostgreSQL database dump
--

\restrict hqZSjDSSwJghoo98na1dmnS2vylsbUadskgsv2M9bVue32uMkPHT4HitPkQhHd7

-- Dumped from database version 16.10 (Ubuntu 16.10-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.10 (Ubuntu 16.10-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- PostgreSQL database dump complete
--

\unrestrict hqZSjDSSwJghoo98na1dmnS2vylsbUadskgsv2M9bVue32uMkPHT4HitPkQhHd7

--
-- Database "postgres" dump
--

\connect postgres

--
-- PostgreSQL database dump
--

\restrict ykbVnobaQnIZQTcDiBGN6LsnGa6zBAEszdvk9nGw4Hxwaa7Eil3kWsNM2uafnwA

-- Dumped from database version 16.10 (Ubuntu 16.10-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.10 (Ubuntu 16.10-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- PostgreSQL database dump complete
--

\unrestrict ykbVnobaQnIZQTcDiBGN6LsnGa6zBAEszdvk9nGw4Hxwaa7Eil3kWsNM2uafnwA

--
-- Database "th3_db" dump
--

--
-- PostgreSQL database dump
--

\restrict S4lm0acQhh3GybYAIPygmzqmxjiByoVS1Gd4p6l6BnJjdKhj82zfYADkGxjhniX

-- Dumped from database version 16.10 (Ubuntu 16.10-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.10 (Ubuntu 16.10-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: th3_db; Type: DATABASE; Schema: -; Owner: -
--

CREATE DATABASE th3_db WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'en_US.UTF-8';


\unrestrict S4lm0acQhh3GybYAIPygmzqmxjiByoVS1Gd4p6l6BnJjdKhj82zfYADkGxjhniX
\connect th3_db
\restrict S4lm0acQhh3GybYAIPygmzqmxjiByoVS1Gd4p6l6BnJjdKhj82zfYADkGxjhniX

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: refresh_new_items_for_category(bigint); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.refresh_new_items_for_category(cat_id bigint) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    gen_ts TIMESTAMPTZ;
    new_cnt INTEGER;
BEGIN
    SELECT COALESCE(generated_at, created_at)
    INTO gen_ts
    FROM product_category
    WHERE id = cat_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT COUNT(*)
    INTO new_cnt
    FROM product p
    WHERE p.category_id = cat_id
      AND p.imported_at > gen_ts;

    UPDATE product_category c
    SET
        has_new_items   = (new_cnt > 0),
        new_items_count = new_cnt
    WHERE c.id = cat_id;
END;
$$;


--
-- Name: trg_product_after_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_product_after_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    PERFORM refresh_new_items_for_category(OLD.category_id);
    RETURN OLD;
END;
$$;


--
-- Name: trg_product_after_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_product_after_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    PERFORM refresh_new_items_for_category(NEW.category_id);
    RETURN NEW;
END;
$$;


--
-- Name: trg_product_after_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_product_after_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.category_id = OLD.category_id THEN
        RETURN NEW;
    END IF;

    PERFORM refresh_new_items_for_category(OLD.category_id);
    PERFORM refresh_new_items_for_category(NEW.category_id);

    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: category_family; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.category_family (
    id bigint NOT NULL,
    name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: category_family_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.category_family_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: category_family_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.category_family_id_seq OWNED BY public.category_family.id;


--
-- Name: category_family_member; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.category_family_member (
    family_id bigint NOT NULL,
    category_id bigint NOT NULL
);


--
-- Name: category_feature; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.category_feature (
    id bigint NOT NULL,
    category_id bigint NOT NULL,
    key text NOT NULL,
    value text NOT NULL,
    original_text text,
    sort_order integer
);


--
-- Name: category_feature_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.category_feature_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: category_feature_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.category_feature_id_seq OWNED BY public.category_feature.id;


--
-- Name: category_similarity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.category_similarity (
    category_id_a bigint NOT NULL,
    category_id_b bigint NOT NULL,
    similarity numeric(5,4) NOT NULL,
    common_keys text[] NOT NULL,
    only_a_keys text[] NOT NULL,
    only_b_keys text[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    key_similarity numeric(5,4),
    value_similarity numeric(5,4)
);


--
-- Name: generation_run; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.generation_run (
    id bigint NOT NULL,
    run_type text NOT NULL,
    source_csv text,
    model_name text,
    generated_at timestamp with time zone DEFAULT now() NOT NULL,
    meta jsonb
);


--
-- Name: generation_run_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.generation_run_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: generation_run_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.generation_run_id_seq OWNED BY public.generation_run.id;


--
-- Name: product; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product (
    id bigint NOT NULL,
    category_id bigint,
    name text NOT NULL,
    producer text,
    country text,
    image_url text,
    raw_specs jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    imported_at timestamp with time zone DEFAULT now() NOT NULL,
    is_used_for_training boolean DEFAULT false NOT NULL,
    training_used_at timestamp with time zone
);


--
-- Name: product_category; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_category (
    id bigint NOT NULL,
    name text NOT NULL,
    short_description text,
    generated_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    admin_status text DEFAULT 'new'::text NOT NULL,
    admin_rating smallint,
    last_generation_run_id bigint,
    has_new_items boolean DEFAULT false NOT NULL,
    new_items_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT chk_product_category_admin_rating CHECK (((admin_rating IS NULL) OR ((admin_rating >= 1) AND (admin_rating <= 5))))
);


--
-- Name: product_feature; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_feature (
    id bigint NOT NULL,
    product_id bigint NOT NULL,
    key text NOT NULL,
    value text NOT NULL,
    original_text text,
    is_selected boolean DEFAULT true NOT NULL,
    source text,
    generation_run_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: product_feature_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.product_feature_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: product_feature_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.product_feature_id_seq OWNED BY public.product_feature.id;


--
-- Name: product_group; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_group (
    id bigint NOT NULL,
    name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: product_group_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.product_group_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: product_group_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.product_group_id_seq OWNED BY public.product_group.id;


--
-- Name: product_group_member; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_group_member (
    group_id bigint NOT NULL,
    product_id bigint NOT NULL
);


--
-- Name: product_similarity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_similarity (
    product_id_a bigint NOT NULL,
    product_id_b bigint NOT NULL,
    similarity numeric(5,4) NOT NULL,
    key_similarity numeric(5,4),
    value_similarity numeric(5,4),
    common_keys text[] NOT NULL,
    only_a_keys text[] NOT NULL,
    only_b_keys text[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: category_family id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_family ALTER COLUMN id SET DEFAULT nextval('public.category_family_id_seq'::regclass);


--
-- Name: category_feature id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_feature ALTER COLUMN id SET DEFAULT nextval('public.category_feature_id_seq'::regclass);


--
-- Name: generation_run id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.generation_run ALTER COLUMN id SET DEFAULT nextval('public.generation_run_id_seq'::regclass);


--
-- Name: product_feature id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_feature ALTER COLUMN id SET DEFAULT nextval('public.product_feature_id_seq'::regclass);


--
-- Name: product_group id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_group ALTER COLUMN id SET DEFAULT nextval('public.product_group_id_seq'::regclass);


--
-- Name: category_family_member category_family_member_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_family_member
    ADD CONSTRAINT category_family_member_pkey PRIMARY KEY (family_id, category_id);


--
-- Name: category_family category_family_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_family
    ADD CONSTRAINT category_family_pkey PRIMARY KEY (id);


--
-- Name: category_feature category_feature_category_id_key_value_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_feature
    ADD CONSTRAINT category_feature_category_id_key_value_key UNIQUE (category_id, key, value);


--
-- Name: category_feature category_feature_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_feature
    ADD CONSTRAINT category_feature_pkey PRIMARY KEY (id);


--
-- Name: category_similarity category_similarity_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_similarity
    ADD CONSTRAINT category_similarity_pk PRIMARY KEY (category_id_a, category_id_b);


--
-- Name: generation_run generation_run_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.generation_run
    ADD CONSTRAINT generation_run_pkey PRIMARY KEY (id);


--
-- Name: product_category product_category_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_category
    ADD CONSTRAINT product_category_pkey PRIMARY KEY (id);


--
-- Name: product_feature product_feature_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_feature
    ADD CONSTRAINT product_feature_pkey PRIMARY KEY (id);


--
-- Name: product_group_member product_group_member_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_group_member
    ADD CONSTRAINT product_group_member_pkey PRIMARY KEY (group_id, product_id);


--
-- Name: product_group product_group_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_group
    ADD CONSTRAINT product_group_pkey PRIMARY KEY (id);


--
-- Name: product product_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product
    ADD CONSTRAINT product_pkey PRIMARY KEY (id);


--
-- Name: product_similarity product_similarity_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_similarity
    ADD CONSTRAINT product_similarity_pk PRIMARY KEY (product_id_a, product_id_b);


--
-- Name: idx_category_feature_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_category_feature_category ON public.category_feature USING btree (category_id);


--
-- Name: idx_category_feature_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_category_feature_key ON public.category_feature USING btree (key);


--
-- Name: idx_generation_run_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_generation_run_type ON public.generation_run USING btree (run_type);


--
-- Name: idx_product_category_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_product_category_id ON public.product USING btree (category_id);


--
-- Name: idx_product_feature_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_product_feature_key ON public.product_feature USING btree (key);


--
-- Name: idx_product_feature_product; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_product_feature_product ON public.product_feature USING btree (product_id);


--
-- Name: product product_after_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER product_after_delete AFTER DELETE ON public.product FOR EACH ROW EXECUTE FUNCTION public.trg_product_after_delete();


--
-- Name: product product_after_insert; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER product_after_insert AFTER INSERT ON public.product FOR EACH ROW EXECUTE FUNCTION public.trg_product_after_insert();


--
-- Name: product product_after_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER product_after_update AFTER UPDATE ON public.product FOR EACH ROW EXECUTE FUNCTION public.trg_product_after_update();


--
-- Name: category_family_member category_family_member_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_family_member
    ADD CONSTRAINT category_family_member_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.product_category(id);


--
-- Name: category_family_member category_family_member_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_family_member
    ADD CONSTRAINT category_family_member_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.category_family(id) ON DELETE CASCADE;


--
-- Name: category_feature category_feature_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_feature
    ADD CONSTRAINT category_feature_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.product_category(id) ON DELETE CASCADE;


--
-- Name: product product_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product
    ADD CONSTRAINT product_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.product_category(id) ON DELETE SET NULL;


--
-- Name: product_category product_category_last_generation_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_category
    ADD CONSTRAINT product_category_last_generation_run_id_fkey FOREIGN KEY (last_generation_run_id) REFERENCES public.generation_run(id);


--
-- Name: product_feature product_feature_generation_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_feature
    ADD CONSTRAINT product_feature_generation_run_id_fkey FOREIGN KEY (generation_run_id) REFERENCES public.generation_run(id);


--
-- Name: product_feature product_feature_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_feature
    ADD CONSTRAINT product_feature_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.product(id) ON DELETE CASCADE;


--
-- Name: product_group_member product_group_member_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_group_member
    ADD CONSTRAINT product_group_member_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.product_group(id) ON DELETE CASCADE;


--
-- Name: product_group_member product_group_member_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_group_member
    ADD CONSTRAINT product_group_member_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.product(id);


--
-- PostgreSQL database dump complete
--

\unrestrict S4lm0acQhh3GybYAIPygmzqmxjiByoVS1Gd4p6l6BnJjdKhj82zfYADkGxjhniX

--
-- PostgreSQL database cluster dump complete
--

