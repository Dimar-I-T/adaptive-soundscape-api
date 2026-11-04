--
-- PostgreSQL database dump
--

\restrict mIdeMba8OTWyY62ghKcYydYaK7gbKUzSKYsyHADklNYLQUydZyahBICN1YbAT7a

-- Dumped from database version 18.6 (ac70818)
-- Dumped by pg_dump version 18.6

-- Started on 2026-11-04 09:09:38

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 2 (class 3079 OID 16565)
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- TOC entry 3454 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- TOC entry 867 (class 1247 OID 32780)
-- Name: sound_type_enum; Type: TYPE; Schema: public; Owner: neondb_owner
--

CREATE TYPE public.sound_type_enum AS ENUM (
    'default',
    'rain',
    'water_stream',
    'wind',
    'sea_waves'
);


ALTER TYPE public.sound_type_enum OWNER TO neondb_owner;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 221 (class 1259 OID 49152)
-- Name: sound_profiles; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.sound_profiles (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    title text,
    sound_type public.sound_type_enum,
    analysis jsonb,
    r2_audio_url text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.sound_profiles OWNER TO neondb_owner;

--
-- TOC entry 220 (class 1259 OID 16579)
-- Name: users; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.users (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    username text NOT NULL,
    email text NOT NULL,
    password_hash text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    sound_preference_default public.sound_type_enum DEFAULT 'default'::public.sound_type_enum
);


ALTER TABLE public.users OWNER TO neondb_owner;

--
-- TOC entry 3300 (class 2606 OID 49162)
-- Name: sound_profiles sound_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.sound_profiles
    ADD CONSTRAINT sound_profiles_pkey PRIMARY KEY (id);


--
-- TOC entry 3294 (class 2606 OID 16595)
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- TOC entry 3296 (class 2606 OID 16591)
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- TOC entry 3298 (class 2606 OID 16593)
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- TOC entry 3301 (class 2606 OID 49163)
-- Name: sound_profiles sound_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.sound_profiles
    ADD CONSTRAINT sound_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 2069 (class 826 OID 16400)
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: cloud_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE cloud_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO neon_superuser WITH GRANT OPTION;


--
-- TOC entry 2070 (class 826 OID 16399)
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: cloud_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE cloud_admin IN SCHEMA public GRANT SELECT,INSERT,DELETE,TRUNCATE,MAINTAIN,UPDATE ON TABLES TO neon_superuser WITH GRANT OPTION;


-- Completed on 2026-11-04 09:09:44

--
-- PostgreSQL database dump complete
--

\unrestrict mIdeMba8OTWyY62ghKcYydYaK7gbKUzSKYsyHADklNYLQUydZyahBICN1YbAT7a

