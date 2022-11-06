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
    driver_id smallint NOT NULL,
    warnings smallint DEFAULT 0,
    licence_points smallint DEFAULT 0,
    team_id smallint,
    assignment_id smallint NOT NULL
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
    telegram_id character varying(15)
);


ALTER TABLE public.drivers OWNER TO alexander;

--
-- Name: drivers_categories; Type: TABLE; Schema: public; Owner: alexander
--

CREATE TABLE public.drivers_categories (
    joined_on date,
    licence_points integer DEFAULT 10,
    race_number smallint,
    driver_id smallint NOT NULL,
    category_id smallint NOT NULL,
    car_class_id integer,
    left_on date,
    warnings smallint DEFAULT 0
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
    "position" smallint,
    relative_position smallint,
    laptime double precision,
    penalty_points smallint DEFAULT 0,
    driver_id smallint NOT NULL,
    round_id smallint NOT NULL,
    category_id smallint NOT NULL,
    session_id smallint NOT NULL,
    warnings smallint DEFAULT 0,
    licence_points smallint DEFAULT 0
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
    relative_position smallint,
    fastest_lap_points smallint,
    penalty_points smallint DEFAULT 0,
    penalty_seconds double precision DEFAULT 0,
    gap_to_first double precision,
    total_racetime double precision,
    driver_id smallint,
    round_id smallint,
    category_id smallint,
    session_id smallint,
    warnings smallint DEFAULT 0,
    licence_points smallint DEFAULT 0
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
    report_reason character varying(2000),
    video_link character varying(80),
    fact character varying(400),
    penalty character varying(300),
    time_penalty smallint DEFAULT 0,
    championship_penalty_points smallint DEFAULT 0,
    licence_penalty_points smallint DEFAULT 0,
    penalty_reason character varying(2000),
    is_reviewed boolean,
    is_queued boolean,
    report_time timestamp without time zone,
    category_id smallint NOT NULL,
    round_id smallint NOT NULL,
    session_id smallint NOT NULL,
    channel_message_id bigint,
    reported_team_id smallint NOT NULL,
    reporting_team_id smallint,
    warnings smallint DEFAULT 0,
    licence_points smallint DEFAULT 0,
    reported_driver_id smallint,
    reporting_driver_id smallint
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

COPY public.driver_assignments (joined_on, left_on, bought_for, is_leader, driver_id, warnings, licence_points, team_id, assignment_id) FROM stdin;
2022-10-23	\N	\N	f	3	0	0	1	1
2022-10-23	\N	\N	f	5	0	0	1	2
2022-10-23	\N	\N	f	6	0	0	1	3
2022-10-23	\N	\N	f	7	0	0	1	4
2022-10-23	\N	\N	f	8	0	0	1	5
2022-10-23	\N	\N	f	10	0	0	2	6
2022-10-23	\N	\N	f	11	0	0	2	7
2022-10-23	\N	\N	f	12	0	0	2	8
2022-10-23	\N	\N	f	13	0	0	2	9
2022-10-23	\N	\N	f	14	0	0	2	10
2022-10-23	\N	\N	f	15	0	0	3	11
2022-10-23	\N	\N	f	17	0	0	3	12
2022-10-23	\N	\N	f	18	0	0	3	13
2022-10-23	\N	\N	f	19	0	0	3	14
2022-10-23	\N	\N	f	20	0	0	3	15
2022-10-23	\N	\N	f	22	0	0	4	16
2022-10-23	\N	\N	f	23	0	0	4	17
2022-10-23	\N	\N	f	24	0	0	4	18
2022-10-23	\N	\N	f	25	0	0	4	19
2022-10-23	\N	\N	f	26	0	0	4	20
2022-10-23	\N	\N	f	28	0	0	5	21
2022-10-23	\N	\N	f	29	0	0	5	22
2022-10-23	\N	\N	f	30	0	0	5	23
2022-10-23	\N	\N	f	31	0	0	5	24
2022-10-23	\N	\N	f	32	0	0	5	25
2022-10-23	\N	\N	f	34	0	0	6	26
2022-10-23	\N	\N	f	35	0	0	6	27
2022-10-23	\N	\N	f	36	0	0	6	28
2022-10-23	\N	\N	f	37	0	0	6	29
2022-10-23	\N	\N	f	38	0	0	6	30
2022-10-23	\N	\N	f	39	0	0	7	31
2022-10-23	\N	\N	f	40	0	0	7	32
2022-10-23	\N	\N	f	42	0	0	7	33
2022-10-23	\N	\N	f	43	0	0	7	34
2022-10-23	\N	\N	f	44	0	0	7	35
2022-10-23	\N	\N	t	16	0	0	3	36
2022-10-23	\N	\N	t	4	0	0	1	37
2022-10-23	\N	\N	t	9	0	0	2	38
2022-10-23	\N	\N	t	21	0	0	4	39
2022-10-23	\N	\N	t	41	0	0	7	40
2022-10-23	\N	\N	t	27	0	0	5	41
2022-10-23	\N	\N	t	33	0	0	6	42
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
20	BlackSail	\N
23	Paperfico	\N
25	RTI_HawkOne	\N
26	RTI_Shardana	\N
9	RTI_DOOM	\N
22	RTI_Elgallo17	219223863
27	RTI_Gigi-Rox	383460444
28	Alphy_31	1543224317
33	Mantextek05	800167010
41	mattly94	212989058
16	RTI_Sbinotto17	633997625
4	GDC_77	386766202
5	Sturla04	998444984
6	RTI_Revenge	173005072
7	chiasiellis	938810293
8	maurynho993	309397287
10	zaffaror	1441898190
11	freedom-aj	1992356952
12	RTI_Nik89sf	637077056
13	XAceOfPeaksX	499299093
14	RTI_Morrisss0087	1120007440
15	piter-72	440476513
17	alecala06_atlas	5087429156
18	MatteoFixC8	812972256
19	Turbolibix46	1078642982
24	RTI_Falco72ac	784236675
29	kimi-ice1983	501624659
30	dariuccinopanzon	1338429985
31	RTI_andrea43race	539432905
32	RTI_Jacobomber06	994012943
34	domdila	1283601230
35	ivanven	2114794810
36	RTI_Mattia76pg	168758814
37	RTI_Strummer	478254181
38	RTI_Ninja98	941661051
39	RTI_Oliver	1029597631
40	LuigiUSocij	470047055
42	lukadevil90	659383243
43	RTI_Samtor	886549791
44	Lightning_blu	918599592
21	RTI_antofox26	601552815
\.


--
-- Data for Name: drivers_categories; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.drivers_categories (joined_on, licence_points, race_number, driver_id, category_id, car_class_id, left_on, warnings) FROM stdin;
2022-10-23	10	62	3	1	1	\N	0
2022-10-23	10	77	4	1	2	\N	0
2022-10-23	10	0	9	1	1	\N	0
2022-10-23	10	50	10	1	2	\N	0
2022-10-23	10	98	15	1	1	\N	0
2022-10-23	10	17	16	1	2	\N	0
2022-10-23	10	26	21	1	1	\N	0
2022-10-23	10	175	22	1	2	\N	0
2022-10-23	10	5	27	1	1	\N	0
2022-10-23	10	31	28	1	2	\N	0
2022-10-23	10	16	33	1	1	\N	0
2022-10-23	10	9	34	1	2	\N	0
2022-10-23	10	82	39	1	1	\N	0
2022-10-23	10	95	40	1	2	\N	0
2022-10-23	10	65	7	2	2	\N	0
2022-10-23	10	27	8	2	2	\N	0
2022-10-23	10	17	13	2	2	\N	0
2022-10-23	10	22	14	2	2	\N	0
2022-10-23	10	46	19	2	2	\N	0
2022-10-23	10	95	25	2	2	\N	0
2022-10-23	10	3	26	2	2	\N	0
2022-10-23	10	43	31	2	2	\N	0
2022-10-23	10	14	32	2	2	\N	0
2022-10-23	10	70	37	2	2	\N	0
2022-10-23	10	98	38	2	2	\N	0
2022-10-23	10	10	44	2	2	\N	0
2022-10-23	10	7	20	2	2	\N	0
2022-10-23	10	13	5	3	3	\N	0
2022-10-23	10	17	6	3	3	\N	0
2022-10-23	10	11	12	3	3	\N	0
2022-10-23	10	27	17	3	3	\N	0
2022-10-23	10	8	18	3	3	\N	0
2022-10-23	10	2	23	3	3	\N	0
2022-10-23	10	46	29	3	3	\N	0
2022-10-23	10	24	30	3	3	\N	0
2022-10-23	10	17	35	3	3	\N	0
2022-10-23	10	76	36	3	3	\N	0
2022-10-23	10	18	41	3	3	\N	0
2022-10-23	10	23	42	3	3	\N	0
2022-10-23	10	30	11	3	3	\N	0
2022-10-23	10	17	24	3	3	\N	0
2022-10-23	10	21	43	2	2	\N	0
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

COPY public.qualifying_results (qualifying_result_id, "position", laptime, penalty_points, driver_id, round_id, category_id, session_id, warnings, licence_points) FROM stdin;
\.


--
-- Data for Name: race_results; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.race_results (result_id, finishing_position, fastest_lap_points, penalty_points, penalty_seconds, gap_to_first, total_racetime, driver_id, round_id, category_id, session_id, warnings, licence_points) FROM stdin;
\.


--
-- Data for Name: reports; Type: TABLE DATA; Schema: public; Owner: alexander
--

COPY public.reports (report_id, number, incident_time, report_reason, video_link, fact, penalty, time_penalty, championship_penalty_points, licence_penalty_points, penalty_reason, is_reviewed, is_queued, report_time, category_id, round_id, session_id, channel_message_id, reported_team_id, reporting_team_id, warnings, licence_points, reported_driver_id, reporting_driver_id) FROM stdin;
30	1	4:30	Mantextek effettua impeding nei confronti di ElGallo facendolo finire in ghiaia	https://youtu.be/tyHtd7tSxo8	\N	\N	30	\N	\N	\N	f	f	\N	1	1	6	687	6	4	0	0	33	22
31	1	2:20	maurynho993 tampona Turbolibix46 in curva 1, facendolo uscire di pista e perdere una posizione	\N	\N	\N	30	\N	\N	\N	f	f	\N	2	2	1	689	1	3	0	0	8	19
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
4	2	2022-11-07	Circuit de Barcelona-Catalunya	f	1	1
23	3	2022-11-14	Circuit de la Sarthe	f	1	1
3	1	2022-11-03	Suzuka Circuit	f	3	1
6	2	2022-11-10	Circuit de Barcelona-Catalunya	f	3	1
2	1	2022-11-01	Suzuka Circuit	f	2	1
5	2	2022-11-08	Circuit de Barcelona-Catalunya	f	2	1
1	1	2022-10-31	Suzuka Circuit	f	1	1
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

SELECT pg_catalog.setval('public.qualifying_results_qualifying_result_id_seq', 14, true);


--
-- Name: race_results_result_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.race_results_result_id_seq', 184, true);


--
-- Name: reports_report_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alexander
--

SELECT pg_catalog.setval('public.reports_report_id_seq', 33, true);


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
-- Name: driver_assignments driver_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.driver_assignments
    ADD CONSTRAINT driver_assignments_pkey PRIMARY KEY (assignment_id) INCLUDE (team_id, driver_id);


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
    ADD CONSTRAINT driver_assignments_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id) NOT VALID;


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
    ADD CONSTRAINT reports_reported_driver_id_fkey FOREIGN KEY (reported_driver_id) REFERENCES public.drivers(driver_id) NOT VALID;


--
-- Name: reports reports_reported_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_reported_team_id_fkey FOREIGN KEY (reported_team_id) REFERENCES public.teams(team_id) NOT VALID;


--
-- Name: reports reports_reporting_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alexander
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_reporting_driver_id_fkey FOREIGN KEY (reporting_driver_id) REFERENCES public.drivers(driver_id) NOT VALID;


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

