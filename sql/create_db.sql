--
-- PostgreSQL database dump
--

-- Dumped from database version 14.5 (Ubuntu 14.5-0ubuntu0.22.04.1)
-- Dumped by pg_dump version 14.5 (Ubuntu 14.5-0ubuntu0.22.04.1)

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
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: car_classes; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.car_classes (
    car_class_id integer NOT NULL,
    name character varying(20),
    game_id integer
);


ALTER TABLE public.car_classes OWNER TO alexander;

--
-- Name: car_classes_car_class_id_seq; Type: SEQUENCE; Schema: public; Owner: alexander
--

CREATE SEQUENCE public.car_classes_car_class_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.car_classes_car_class_id_seq OWNER TO alexander;

--
-- Name: car_classes_car_class_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alexander
--

ALTER SEQUENCE public.car_classes_car_class_id_seq OWNED BY public.car_classes.car_class_id;


--
-- Name: categories; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.categories (
    category_id smallint NOT NULL,
    name character varying(20) NOT NULL,
    round_weekday smallint,
    game_id integer,
    championship_id smallint
);


ALTER TABLE public.categories OWNER TO alexander;

--
-- Name: categories_category_id_seq; Type: SEQUENCE; Schema: public; Owner: alexander
--

CREATE SEQUENCE public.categories_category_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.categories_category_id_seq OWNER TO alexander;

--
-- Name: categories_category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alexander
--

ALTER SEQUENCE public.categories_category_id_seq OWNED BY public.categories.category_id;


--
-- Name: category_classes; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.category_classes (
    category_id smallint NOT NULL,
    car_class_id integer NOT NULL
);


ALTER TABLE public.category_classes OWNER TO alexander;

--
-- Name: category_sessions; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.category_sessions (
    category_id smallint NOT NULL,
    session_id smallint NOT NULL
);


ALTER TABLE public.category_sessions OWNER TO alexander;

--
-- Name: championships; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.championships (
    championship_id smallint NOT NULL,
    championship_name character varying(60) NOT NULL,
    start date NOT NULL,
    "end" date
);


ALTER TABLE public.championships OWNER TO alexander;

--
-- Name: championships_championship_id_seq; Type: SEQUENCE; Schema: public; Owner: alexander
--

CREATE SEQUENCE public.championships_championship_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.championships_championship_id_seq OWNER TO alexander;

--
-- Name: championships_championship_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alexander
--

ALTER SEQUENCE public.championships_championship_id_seq OWNED BY public.championships.championship_id;


--
-- Name: driver_assignments; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.driver_assignments (
    joined_on date,
    left_on date,
    bought_for smallint,
    is_leader boolean,
    assignment_id uuid NOT NULL,
    driver_id smallint NOT NULL,
    team_id smallint NOT NULL
);


ALTER TABLE public.driver_assignments OWNER TO alexander;

--
-- Name: driver_championships; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.driver_championships (
    driver_id smallint NOT NULL,
    championship_id smallint NOT NULL
);


ALTER TABLE public.driver_championships OWNER TO alexander;

--
-- Name: drivers; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.drivers (
    driver_id smallint NOT NULL,
    psn_id character varying(16) NOT NULL,
    telegram_id integer
);


ALTER TABLE public.drivers OWNER TO alexander;

--
-- Name: drivers_categories; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.drivers_categories (
    joined_on date,
    licence_points integer,
    race_number smallint,
    driver_id smallint NOT NULL,
    category_id smallint NOT NULL,
    car_class_id integer,
    left_on date
);


ALTER TABLE public.drivers_categories OWNER TO alexander;

--
-- Name: drivers_driver_id_seq; Type: SEQUENCE; Schema: public; Owner: alexander
--

CREATE SEQUENCE public.drivers_driver_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.drivers_driver_id_seq OWNER TO alexander;

--
-- Name: drivers_driver_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alexander
--

ALTER SEQUENCE public.drivers_driver_id_seq OWNED BY public.drivers.driver_id;


--
-- Name: games; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.games (
    game_id integer NOT NULL,
    name character varying(30)
);


ALTER TABLE public.games OWNER TO alexander;

--
-- Name: games_game_id_seq; Type: SEQUENCE; Schema: public; Owner: alexander
--

CREATE SEQUENCE public.games_game_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.games_game_id_seq OWNER TO alexander;

--
-- Name: games_game_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alexander
--

ALTER SEQUENCE public.games_game_id_seq OWNED BY public.games.game_id;


--
-- Name: point_systems; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.point_systems (
    point_system_id smallint NOT NULL,
    point_system character varying(60) NOT NULL
);


ALTER TABLE public.point_systems OWNER TO alexander;

--
-- Name: point_systems_point_system_id_seq; Type: SEQUENCE; Schema: public; Owner: alexander
--

CREATE SEQUENCE public.point_systems_point_system_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.point_systems_point_system_id_seq OWNER TO alexander;

--
-- Name: point_systems_point_system_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alexander
--

ALTER SEQUENCE public.point_systems_point_system_id_seq OWNED BY public.point_systems.point_system_id;


--
-- Name: qualifying_results; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.qualifying_results (
    qualifying_result_id smallint NOT NULL,
    "position" smallint NOT NULL,
    laptime double precision,
    penalty_points smallint NOT NULL,
    driver_id smallint NOT NULL,
    round_id smallint NOT NULL,
    category_id smallint NOT NULL,
    session_id smallint NOT NULL
);


ALTER TABLE public.qualifying_results OWNER TO alexander;

--
-- Name: qualifying_results_qualifying_result_id_seq; Type: SEQUENCE; Schema: public; Owner: alexander
--

CREATE SEQUENCE public.qualifying_results_qualifying_result_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.qualifying_results_qualifying_result_id_seq OWNER TO alexander;

--
-- Name: qualifying_results_qualifying_result_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alexander
--

ALTER SEQUENCE public.qualifying_results_qualifying_result_id_seq OWNED BY public.qualifying_results.qualifying_result_id;


--
-- Name: race_results; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.race_results (
    result_id integer NOT NULL,
    finishing_position smallint,
    fastest_lap_points smallint,
    penalty_points smallint,
    gap_to_first double precision,
    driver_id smallint,
    round_id smallint,
    category_id smallint,
    session_id smallint
);


ALTER TABLE public.race_results OWNER TO alexander;

--
-- Name: race_results_result_id_seq; Type: SEQUENCE; Schema: public; Owner: alexander
--

CREATE SEQUENCE public.race_results_result_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.race_results_result_id_seq OWNER TO alexander;

--
-- Name: race_results_result_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alexander
--

ALTER SEQUENCE public.race_results_result_id_seq OWNED BY public.race_results.result_id;


--
-- Name: reports; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.reports (
    report_id integer NOT NULL,
    number smallint NOT NULL,
    incident_time character varying(12) NOT NULL,
    report_reason character varying(2000) NOT NULL,
    video_link character varying(80),
    fact character varying(400),
    penalty character varying(100),
    time_penalty smallint,
    championship_penalty_points smallint,
    licence_penalty_points smallint,
    penalty_reason character varying(2000),
    is_reviewed boolean,
    is_queued boolean,
    report_time timestamp without time zone,
    category_id smallint NOT NULL,
    round_id smallint NOT NULL,
    session_id smallint NOT NULL,
    reported_driver_id character varying(16) NOT NULL,
    reporting_driver_id character varying(16),
    channel_message_id bigint,
    reported_team_id smallint NOT NULL,
    reporting_team_id smallint
);


ALTER TABLE public.reports OWNER TO alexander;

--
-- Name: reports_report_id_seq; Type: SEQUENCE; Schema: public; Owner: alexander
--

CREATE SEQUENCE public.reports_report_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.reports_report_id_seq OWNER TO alexander;

--
-- Name: reports_report_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alexander
--

ALTER SEQUENCE public.reports_report_id_seq OWNED BY public.reports.report_id;


--
-- Name: rounds; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.rounds (
    round_id smallint NOT NULL,
    number smallint NOT NULL,
    date date NOT NULL,
    circuit character varying(40) NOT NULL,
    completed boolean DEFAULT false,
    category_id smallint,
    championship_id smallint
);


ALTER TABLE public.rounds OWNER TO alexander;

--
-- Name: rounds_round_id_seq; Type: SEQUENCE; Schema: public; Owner: alexander
--

CREATE SEQUENCE public.rounds_round_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.rounds_round_id_seq OWNER TO alexander;

--
-- Name: rounds_round_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alexander
--

ALTER SEQUENCE public.rounds_round_id_seq OWNED BY public.rounds.round_id;


--
-- Name: sessions; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.sessions (
    session_id smallint NOT NULL,
    name character varying(30) NOT NULL,
    point_system_id smallint NOT NULL
);


ALTER TABLE public.sessions OWNER TO alexander;

--
-- Name: sessions_session_id_seq; Type: SEQUENCE; Schema: public; Owner: alexander
--

CREATE SEQUENCE public.sessions_session_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.sessions_session_id_seq OWNER TO alexander;

--
-- Name: sessions_session_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alexander
--

ALTER SEQUENCE public.sessions_session_id_seq OWNED BY public.sessions.session_id;


--
-- Name: teams; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.teams (
    team_id smallint NOT NULL,
    name character varying(20),
    credits smallint NOT NULL
);


ALTER TABLE public.teams OWNER TO alexander;

--
-- Name: teams_team_id_seq; Type: SEQUENCE; Schema: public; Owner: alexander
--

CREATE SEQUENCE public.teams_team_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.teams_team_id_seq OWNER TO alexander;

--
-- Name: teams_team_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alexander
--

ALTER SEQUENCE public.teams_team_id_seq OWNED BY public.teams.team_id;


--
-- Name: car_classes car_class_id; Type: DEFAULT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.car_classes ALTER COLUMN car_class_id SET DEFAULT nextval('public.car_classes_car_class_id_seq'::regclass);


--
-- Name: categories category_id; Type: DEFAULT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.categories ALTER COLUMN category_id SET DEFAULT nextval('public.categories_category_id_seq'::regclass);


--
-- Name: championships championship_id; Type: DEFAULT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.championships ALTER COLUMN championship_id SET DEFAULT nextval('public.championships_championship_id_seq'::regclass);


--
-- Name: drivers driver_id; Type: DEFAULT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.drivers ALTER COLUMN driver_id SET DEFAULT nextval('public.drivers_driver_id_seq'::regclass);


--
-- Name: games game_id; Type: DEFAULT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.games ALTER COLUMN game_id SET DEFAULT nextval('public.games_game_id_seq'::regclass);


--
-- Name: point_systems point_system_id; Type: DEFAULT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.point_systems ALTER COLUMN point_system_id SET DEFAULT nextval('public.point_systems_point_system_id_seq'::regclass);


--
-- Name: qualifying_results qualifying_result_id; Type: DEFAULT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.qualifying_results ALTER COLUMN qualifying_result_id SET DEFAULT nextval('public.qualifying_results_qualifying_result_id_seq'::regclass);


--
-- Name: race_results result_id; Type: DEFAULT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.race_results ALTER COLUMN result_id SET DEFAULT nextval('public.race_results_result_id_seq'::regclass);


--
-- Name: reports report_id; Type: DEFAULT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.reports ALTER COLUMN report_id SET DEFAULT nextval('public.reports_report_id_seq'::regclass);


--
-- Name: rounds round_id; Type: DEFAULT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.rounds ALTER COLUMN round_id SET DEFAULT nextval('public.rounds_round_id_seq'::regclass);


--
-- Name: sessions session_id; Type: DEFAULT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.sessions ALTER COLUMN session_id SET DEFAULT nextval('public.sessions_session_id_seq'::regclass);


--
-- Name: teams team_id; Type: DEFAULT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.teams ALTER COLUMN team_id SET DEFAULT nextval('public.teams_team_id_seq'::regclass);


--
-- Data for Name: car_classes; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.car_classes (car_class_id, name, game_id) FROM stdin;
1	Gr.3	1
2	Gr.4	1
3	Gr.3	2
4	Gr.4	2
\.


--
-- Data for Name: categories; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.categories (category_id, name, round_weekday, game_id, championship_id) FROM stdin;
3	PRO-AM	3	2	1
2	AM	1	1	1
1	PRO	0	1	1
\.


--
-- Data for Name: category_classes; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.category_classes (category_id, car_class_id) FROM stdin;
1	1
1	2
2	2
3	3
\.


--
-- Data for Name: category_sessions; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.category_sessions (category_id, session_id) FROM stdin;
1	3
1	6
2	1
2	2
2	6
3	6
3	1
3	2
\.


--
-- Data for Name: championships; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.championships (championship_id, championship_name, start, "end") FROM stdin;
1	eSports Championship 1	2022-10-20	\N
\.


--
-- Data for Name: driver_assignments; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.driver_assignments (joined_on, left_on, bought_for, is_leader, assignment_id, driver_id, team_id) FROM stdin;
2022-10-23	\N	\N	\N	f5ebb15a-d4e3-46eb-8dce-19e7874c5cba	3	1
2022-10-23	\N	\N	\N	13ea937c-9d2f-4783-a0f6-05cc6392b51e	5	1
2022-10-23	\N	\N	\N	4fd06e91-e309-448f-8cfe-57315fe7368b	6	1
2022-10-23	\N	\N	\N	97153664-5a80-4b68-b2a3-3c46762989ab	7	1
2022-10-23	\N	\N	\N	5b9b9ab1-a347-4082-b78b-03e2f04dc052	8	1
2022-10-23	\N	\N	\N	07fdcb26-2fee-4fa9-9eb4-3a4e79eb0a82	10	2
2022-10-23	\N	\N	\N	bf0e0a81-5fb4-48b7-bed4-ab48b7a69bc1	11	2
2022-10-23	\N	\N	\N	7b4cb711-0765-4ec9-a87f-4886ffaf7b10	12	2
2022-10-23	\N	\N	\N	80ba0254-78ba-46c2-9b92-0b71d7775d2c	13	2
2022-10-23	\N	\N	\N	08fdd3fd-cdb3-4ba2-a4fb-20214e2ae082	14	2
2022-10-23	\N	\N	\N	944c45bb-6174-4ecb-9693-05096f207762	15	3
2022-10-23	\N	\N	\N	60e1237a-24a8-4f58-aedc-00027eb58741	17	3
2022-10-23	\N	\N	\N	176e8317-5742-4d63-b3af-223998a4ef95	18	3
2022-10-23	\N	\N	\N	b0112bee-756a-4966-a15a-63ef781067e2	19	3
2022-10-23	\N	\N	\N	d4fb8640-e500-4033-9575-40d7c804d613	20	3
2022-10-23	\N	\N	\N	f2c1fb29-febe-4a39-90b2-c810ecfda51b	22	4
2022-10-23	\N	\N	\N	bbba40ea-6979-4889-85f4-dce50f07366f	23	4
2022-10-23	\N	\N	\N	09b4d56b-931a-4979-8680-4824a432c29c	24	4
2022-10-23	\N	\N	\N	bf5ab71c-493c-4715-993e-e33410929331	25	4
2022-10-23	\N	\N	\N	d07c8233-2aa4-4364-b9d6-bdb05dfc85c9	26	4
2022-10-23	\N	\N	\N	994594cf-5cf4-4b35-affc-7f9613ebd76d	28	5
2022-10-23	\N	\N	\N	25b9e5ff-50f5-4495-a49b-4a435058ca76	29	5
2022-10-23	\N	\N	\N	72d4c15f-4a0c-4f1d-bef8-308e64669234	30	5
2022-10-23	\N	\N	\N	e6e9873d-fd68-4acb-9ce2-d599e2d773d3	31	5
2022-10-23	\N	\N	\N	107e463f-65b9-4784-86f8-9bc22e8cacd2	32	5
2022-10-23	\N	\N	\N	b252c623-87d0-4006-beb1-1967e81d574d	34	6
2022-10-23	\N	\N	\N	1d5c29d5-45c5-425d-ba62-eadaa7829189	35	6
2022-10-23	\N	\N	\N	6e5f9886-6069-4b7f-89a6-cf19a93a9662	36	6
2022-10-23	\N	\N	\N	ac2fae41-247b-4cfc-906f-e62a4674e44c	37	6
2022-10-23	\N	\N	\N	64770216-d972-45d2-a2b7-376205a964cf	38	6
2022-10-23	\N	\N	\N	200bbff3-8f10-4667-9bae-401fa3e4e845	39	7
2022-10-23	\N	\N	\N	7ee68f41-09eb-4fa7-a6cf-950a30127e69	40	7
2022-10-23	\N	\N	\N	f4864be2-4b85-41b6-bc03-522f1c0c4d07	42	7
2022-10-23	\N	\N	\N	30ba062b-5d14-4e70-90dd-f0222b73ff0d	43	7
2022-10-23	\N	\N	\N	7dba9dd3-15ec-4baa-8e0d-1e3c3a575c8d	44	7
2022-10-23	\N	\N	t	eb9047ec-cd93-4231-85d4-ce1891d53a50	16	3
2022-10-23	\N	\N	t	55582ad2-ae80-4fa0-8298-532e4d4f380f	4	1
2022-10-23	\N	\N	t	ada7e0d1-9255-4294-8cc8-b68b5ec0be51	9	2
2022-10-23	\N	\N	t	b13ce593-d559-4cfc-b907-622bd390a084	21	4
2022-10-23	\N	\N	t	0a5bb2be-0f18-4fb7-a7e1-0a6e744b08e3	41	7
2022-10-23	\N	\N	t	d9bc6308-08f0-4681-8fab-d93cb5c4a25b	27	5
2022-10-23	\N	\N	t	ad3b3216-b865-4e29-9838-81c18c665860	33	6
\.


--
-- Data for Name: driver_championships; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.driver_championships (driver_id, championship_id) FROM stdin;
\.


--
-- Data for Name: drivers; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.drivers (driver_id, psn_id, telegram_id) FROM stdin;
3	RTI_MarcRacer_62	\N
4	GDC_77	\N
5	Sturla04	\N
6	RTI_Revenge	\N
12	RTI_Nik89sf	\N
17	alecala06_atlas	\N
18	MatteoFixC8	\N
20	BlackSail	\N
21	RTI_antofox26	\N
22	RTI_Elgallo17	\N
23	Paperfico	\N
24	RTI_Falco72ac	\N
25	RTI_HawkOne	\N
26	RTI_Shardana	\N
32	RTI_Jacobomber06	\N
33	Mantextek05	\N
34	domdila	\N
36	RTI_Mattia76pg	\N
40	LuigiUSocij	\N
41	mattly94	\N
42	lukadevil90	\N
7	chiasiellis	\N
8	maurynho993	\N
9	RTI_DOOM	\N
10	zaffaror	\N
11	freedom-aj	\N
14	RTI_Morrisss0087	\N
15	piter-72	\N
19	Turbolibix46	\N
28	Alphy_31	\N
29	kimi-ice1983	\N
30	dariuccinopanzon	\N
31	RTI_andrea43race	\N
35	ivanven	\N
37	RTI_Strummer	\N
38	RTI_Ninja98	\N
39	RTI_Oliver	\N
44	Lightning_blu	\N
13	XAceOfPeaksX	\N
43	RTI_Samtor	\N
27	RTI_Gigi-Rox	383460444
16	RTI_Sbinotto17	633997625
\.


--
-- Data for Name: drivers_categories; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.drivers_categories (joined_on, licence_points, race_number, driver_id, category_id, car_class_id, left_on) FROM stdin;
2022-10-23	10	62	3	1	1	\N
2022-10-23	10	77	4	1	2	\N
2022-10-23	10	0	9	1	1	\N
2022-10-23	10	50	10	1	2	\N
2022-10-23	10	98	15	1	1	\N
2022-10-23	10	17	16	1	2	\N
2022-10-23	10	26	21	1	1	\N
2022-10-23	10	175	22	1	2	\N
2022-10-23	10	5	27	1	1	\N
2022-10-23	10	31	28	1	2	\N
2022-10-23	10	16	33	1	1	\N
2022-10-23	10	9	34	1	2	\N
2022-10-23	10	82	39	1	1	\N
2022-10-23	10	95	40	1	2	\N
2022-10-23	10	65	7	2	2	\N
2022-10-23	10	27	8	2	2	\N
2022-10-23	10	17	13	2	2	\N
2022-10-23	10	22	14	2	2	\N
2022-10-23	10	46	19	2	2	\N
2022-10-23	10	95	25	2	2	\N
2022-10-23	10	3	26	2	2	\N
2022-10-23	10	43	31	2	2	\N
2022-10-23	10	14	32	2	2	\N
2022-10-23	10	70	37	2	2	\N
2022-10-23	10	98	38	2	2	\N
2022-10-23	10	10	44	2	2	\N
2022-10-23	10	7	20	2	2	\N
2022-10-23	10	13	5	3	3	\N
2022-10-23	10	17	6	3	3	\N
2022-10-23	10	11	12	3	3	\N
2022-10-23	10	27	17	3	3	\N
2022-10-23	10	8	18	3	3	\N
2022-10-23	10	2	23	3	3	\N
2022-10-23	10	46	29	3	3	\N
2022-10-23	10	24	30	3	3	\N
2022-10-23	10	17	35	3	3	\N
2022-10-23	10	76	36	3	3	\N
2022-10-23	10	18	41	3	3	\N
2022-10-23	10	23	42	3	3	\N
2022-10-23	10	30	11	3	3	\N
2022-10-23	10	17	24	3	3	\N
2022-10-23	10	21	43	2	2	\N
\.


--
-- Data for Name: games; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.games (game_id, name) FROM stdin;
1	gts
2	gt7
\.


--
-- Data for Name: point_systems; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.point_systems (point_system_id, point_system) FROM stdin;
1	12.5 10 8 6.5 5.5 5 4.5 4 3.5 3 2.5 2 1.5 1
2	40 35 32 27 25 23 22 20 15 12 9 6 4 2
\.


--
-- Data for Name: qualifying_results; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.qualifying_results (qualifying_result_id, "position", laptime, penalty_points, driver_id, round_id, category_id, session_id) FROM stdin;
\.


--
-- Data for Name: race_results; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.race_results (result_id, finishing_position, fastest_lap_points, penalty_points, gap_to_first, driver_id, round_id, category_id, session_id) FROM stdin;
\.


--
-- Data for Name: reports; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.reports (report_id, number, incident_time, report_reason, video_link, fact, penalty, time_penalty, championship_penalty_points, licence_penalty_points, penalty_reason, is_reviewed, is_queued, report_time, category_id, round_id, session_id, reported_driver_id, reporting_driver_id, channel_message_id, reported_team_id, reporting_team_id) FROM stdin;
29	1	11:11	RTI_Oliver manca il punto di staccata spingendo piter-72 fuori pista.	\N	\N	\N	\N	\N	\N	\N	f	f	2022-10-30 10:40:03.729449	1	1	3	RTI_Oliver	piter-72	54	7	3
\.


--
-- Data for Name: rounds; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.rounds (round_id, number, date, circuit, completed, category_id, championship_id) FROM stdin;
8	4	2022-11-21	Mount Panorama Circuit	f	1	1
9	4	2022-11-22	Mount Panorama Circuit	f	2	1
10	4	2022-11-24	Mount Panorama Circuit	f	3	1
11	5	2022-11-28	Autodromo Nazionale di Monza	f	1	1
12	5	2022-11-29	Autodromo Nazionale di Monza	f	2	1
13	5	2022-12-01	Autodromo Nazionale di Monza	f	3	1
14	6	2022-12-05	Circuit de Spa-Francorchamps	f	1	1
15	6	2022-12-06	Circuit de Spa-Francorchamps	f	2	1
16	6	2022-12-08	Circuit de Spa-Francorchamps	f	3	1
17	7	2022-12-12	Autódromo José Carlos Pace	f	1	1
18	7	2022-12-13	Autódromo José Carlos Pace	f	2	1
19	7	2022-12-15	Autódromo José Carlos Pace	f	3	1
24	3	2022-11-15	Circuit de la Sarthe	f	2	1
25	3	2022-11-17	Circuit de la Sarthe	f	3	1
1	1	2022-10-31	Suzuka Circuit	f	1	1
4	2	2022-11-07	Circuit de Barcelona-Catalunya	f	1	1
23	3	2022-11-14	Circuit de la Sarthe	f	1	1
3	1	2022-11-03	Suzuka Circuit	f	3	1
6	2	2022-11-10	Circuit de Barcelona-Catalunya	f	3	1
2	1	2022-11-01	Suzuka Circuit	f	2	1
5	2	2022-11-08	Circuit de Barcelona-Catalunya	f	2	1
\.


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.sessions (session_id, name, point_system_id) FROM stdin;
1	Gara 1	1
2	Gara 2	1
6	Qualifica	1
3	Gara	2
\.


--
-- Data for Name: teams; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.teams (team_id, name, credits) FROM stdin;
1	#A24	0
2	3Drap	0
3	Fonzar	0
5	ITR	0
6	MSC	0
7	Prandelli	0
4	GO-TV	0
\.


--
-- Name: car_classes_car_class_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.car_classes_car_class_id_seq', 4, true);


--
-- Name: categories_category_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.categories_category_id_seq', 3, true);


--
-- Name: championships_championship_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.championships_championship_id_seq', 1, true);


--
-- Name: drivers_driver_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.drivers_driver_id_seq', 44, true);


--
-- Name: games_game_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.games_game_id_seq', 2, true);


--
-- Name: point_systems_point_system_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.point_systems_point_system_id_seq', 2, true);


--
-- Name: qualifying_results_qualifying_result_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.qualifying_results_qualifying_result_id_seq', 1, false);


--
-- Name: race_results_result_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.race_results_result_id_seq', 170, true);


--
-- Name: reports_report_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.reports_report_id_seq', 29, true);


--
-- Name: rounds_round_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.rounds_round_id_seq', 25, true);


--
-- Name: sessions_session_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.sessions_session_id_seq', 6, true);


--
-- Name: teams_team_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.teams_team_id_seq', 7, true);


--
-- Name: race_results _driver_round_session_uc; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.race_results
    ADD CONSTRAINT _driver_round_session_uc UNIQUE (driver_id, round_id, session_id);


--
-- Name: car_classes car_classes_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.car_classes
    ADD CONSTRAINT car_classes_pkey PRIMARY KEY (car_class_id);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (category_id);


--
-- Name: category_classes category_classes_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.category_classes
    ADD CONSTRAINT category_classes_pkey PRIMARY KEY (category_id, car_class_id);


--
-- Name: category_sessions category_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.category_sessions
    ADD CONSTRAINT category_sessions_pkey PRIMARY KEY (category_id, session_id);


--
-- Name: championships championships_championship_name_key; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.championships
    ADD CONSTRAINT championships_championship_name_key UNIQUE (championship_name);


--
-- Name: championships championships_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.championships
    ADD CONSTRAINT championships_pkey PRIMARY KEY (championship_id);


--
-- Name: driver_assignments driver_assignments_joined_on_driver_id_team_id_key; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.driver_assignments
    ADD CONSTRAINT driver_assignments_joined_on_driver_id_team_id_key UNIQUE (joined_on, driver_id, team_id);


--
-- Name: driver_assignments driver_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.driver_assignments
    ADD CONSTRAINT driver_assignments_pkey PRIMARY KEY (assignment_id, driver_id, team_id);


--
-- Name: driver_championships driver_championships_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.driver_championships
    ADD CONSTRAINT driver_championships_pkey PRIMARY KEY (driver_id, championship_id);


--
-- Name: drivers_categories drivers_categories_joined_on_driver_id_category_id_key; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.drivers_categories
    ADD CONSTRAINT drivers_categories_joined_on_driver_id_category_id_key UNIQUE (joined_on, driver_id, category_id);


--
-- Name: drivers_categories drivers_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.drivers_categories
    ADD CONSTRAINT drivers_categories_pkey PRIMARY KEY (driver_id, category_id);


--
-- Name: drivers drivers_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.drivers
    ADD CONSTRAINT drivers_pkey PRIMARY KEY (driver_id);


--
-- Name: drivers drivers_psn_id_key; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.drivers
    ADD CONSTRAINT drivers_psn_id_key UNIQUE (psn_id);


--
-- Name: games games_name_key; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.games
    ADD CONSTRAINT games_name_key UNIQUE (name);


--
-- Name: games games_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.games
    ADD CONSTRAINT games_pkey PRIMARY KEY (game_id);


--
-- Name: point_systems point_systems_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.point_systems
    ADD CONSTRAINT point_systems_pkey PRIMARY KEY (point_system_id);


--
-- Name: qualifying_results qualifying_results_driver_id_round_id_key; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.qualifying_results
    ADD CONSTRAINT qualifying_results_driver_id_round_id_key UNIQUE (driver_id, round_id);


--
-- Name: qualifying_results qualifying_results_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.qualifying_results
    ADD CONSTRAINT qualifying_results_pkey PRIMARY KEY (qualifying_result_id);


--
-- Name: race_results race_results_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.race_results
    ADD CONSTRAINT race_results_pkey PRIMARY KEY (result_id);


--
-- Name: reports reports_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_pkey PRIMARY KEY (report_id);


--
-- Name: rounds rounds_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.rounds
    ADD CONSTRAINT rounds_pkey PRIMARY KEY (round_id);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (session_id);


--
-- Name: teams teams_name_key; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_name_key UNIQUE (name);


--
-- Name: teams teams_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_pkey PRIMARY KEY (team_id);


--
-- Name: car_classes car_classes_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.car_classes
    ADD CONSTRAINT car_classes_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(game_id);


--
-- Name: categories categories_championship_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_championship_id_fkey FOREIGN KEY (championship_id) REFERENCES public.championships(championship_id);


--
-- Name: categories categories_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(game_id);


--
-- Name: category_classes category_classes_car_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.category_classes
    ADD CONSTRAINT category_classes_car_class_id_fkey FOREIGN KEY (car_class_id) REFERENCES public.car_classes(car_class_id);


--
-- Name: category_classes category_classes_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.category_classes
    ADD CONSTRAINT category_classes_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(category_id);


--
-- Name: category_sessions category_sessions_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.category_sessions
    ADD CONSTRAINT category_sessions_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(category_id);


--
-- Name: category_sessions category_sessions_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.category_sessions
    ADD CONSTRAINT category_sessions_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id);


--
-- Name: driver_assignments driver_assignments_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.driver_assignments
    ADD CONSTRAINT driver_assignments_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.drivers(driver_id);


--
-- Name: driver_assignments driver_assignments_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.driver_assignments
    ADD CONSTRAINT driver_assignments_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- Name: driver_championships driver_championships_championship_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.driver_championships
    ADD CONSTRAINT driver_championships_championship_id_fkey FOREIGN KEY (championship_id) REFERENCES public.championships(championship_id);


--
-- Name: driver_championships driver_championships_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.driver_championships
    ADD CONSTRAINT driver_championships_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.drivers(driver_id);


--
-- Name: drivers_categories drivers_categories_car_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.drivers_categories
    ADD CONSTRAINT drivers_categories_car_class_id_fkey FOREIGN KEY (car_class_id) REFERENCES public.car_classes(car_class_id);


--
-- Name: drivers_categories drivers_categories_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.drivers_categories
    ADD CONSTRAINT drivers_categories_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(category_id);


--
-- Name: drivers_categories drivers_categories_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.drivers_categories
    ADD CONSTRAINT drivers_categories_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.drivers(driver_id);


--
-- Name: qualifying_results qualifying_results_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.qualifying_results
    ADD CONSTRAINT qualifying_results_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(category_id);


--
-- Name: qualifying_results qualifying_results_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.qualifying_results
    ADD CONSTRAINT qualifying_results_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.drivers(driver_id);


--
-- Name: qualifying_results qualifying_results_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.qualifying_results
    ADD CONSTRAINT qualifying_results_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(round_id);


--
-- Name: qualifying_results qualifying_results_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.qualifying_results
    ADD CONSTRAINT qualifying_results_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id);


--
-- Name: race_results race_results_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.race_results
    ADD CONSTRAINT race_results_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(category_id);


--
-- Name: race_results race_results_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.race_results
    ADD CONSTRAINT race_results_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.drivers(driver_id);


--
-- Name: race_results race_results_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.race_results
    ADD CONSTRAINT race_results_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(round_id);


--
-- Name: race_results race_results_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.race_results
    ADD CONSTRAINT race_results_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id);


--
-- Name: reports reports_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(category_id);


--
-- Name: reports reports_reported_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_reported_driver_id_fkey FOREIGN KEY (reported_driver_id) REFERENCES public.drivers(psn_id);


--
-- Name: reports reports_reported_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_reported_team_id_fkey FOREIGN KEY (reported_team_id) REFERENCES public.teams(team_id) NOT VALID;


--
-- Name: reports reports_reporting_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_reporting_driver_id_fkey FOREIGN KEY (reporting_driver_id) REFERENCES public.drivers(psn_id);


--
-- Name: reports reports_reporting_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_reporting_team_id_fkey FOREIGN KEY (reporting_team_id) REFERENCES public.teams(team_id) NOT VALID;


--
-- Name: reports reports_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(round_id);


--
-- Name: reports reports_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id);


--
-- Name: rounds rounds_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.rounds
    ADD CONSTRAINT rounds_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(category_id);


--
-- Name: rounds rounds_championship_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.rounds
    ADD CONSTRAINT rounds_championship_id_fkey FOREIGN KEY (championship_id) REFERENCES public.championships(championship_id);


--
-- Name: sessions sessions_point_system_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_point_system_id_fkey FOREIGN KEY (point_system_id) REFERENCES public.point_systems(point_system_id);


--
-- PostgreSQL database dump complete
--

