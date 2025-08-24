habits-etl

Ingest daily habit check-ins from Google Forms/Sheets into TimescaleDB (Postgres) and visualize in Grafana. This repo provides a tiny, testable ETL you can run locally or as a Kubernetes CronJob.

Why not read Sheets directly in Grafana? Because ETL → DB buys you speed, durability, privacy, and real analytics (indexes, SQL, continuous aggregates, and streaks) instead of pulling a public CSV every dashboard refresh. Continuous aggregates precompute summaries so your dashboards stay snappy even as data grows.  ￼

⸻

What it does
	•	Reads one tab from a Google Sheet (the Form responses).
	•	Normalizes rows into tidy events: (ts, user_email, habit, value, notes).
	•	Upserts into a Timescale hypertable.
	•	(Optional) Maintains continuous aggregates for fast daily/weekly rollups.  ￼ ￼
	•	You point Grafana’s built-in Postgres data source at it and build dashboards.  ￼

⸻

Repo layout

habits-etl/
├─ etl/
│  ├─ etl_habits.py         # main ETL entrypoint
│  ├─ transform.py          # parse/normalize rows, robust date handling
│  └─ config/habits.yml     # your sheet mapping (headers → habit ids)
├─ sql/
│  └─ 001_schema.sql        # tables, hypertable, indexes, continuous aggregate
├─ tests/
│  └─ test_transform.py     # minimal unit tests
├─ requirements.txt
├─ .env.example             # sample env vars (copy → .env and fill)
└─ Makefile                 # install, test, run


⸻

Quick start

0) Prereqs
	•	Python 3.11+
	•	Postgres with TimescaleDB extension (self-hosted or Cloud). Continuous aggregates are a Timescale feature atop Postgres materialized views.  ￼
	•	Grafana (OSS or Cloud). The PostgreSQL data source is built-in.  ￼

1) Create a Google Form & Sheet
	•	Create your Form (or copy the question set from this README).
	•	Responses → “Link to Sheets” to create a spreadsheet with a “Form Responses 1” tab.
	•	You’ll use Report Date as the time series date (Form can’t force ISO; ETL normalizes MM/DD/YYYY, ISO, and serial dates).

2) Google Cloud service account (read-only)
	•	In the Google Cloud Console, create a Service Account and generate a JSON key.  ￼
	•	Share the Sheet with the service account’s email (Viewer). This is required; service accounts are separate principals and don’t see your files unless you share.  ￼ ￼

Using Python? The repo uses gspread with service-account auth; it reads via the Sheets & Drive APIs once the sheet is shared.  ￼

3) Configure the ETL

Copy the sample env and fill:

cp .env.example .env

.env:

PG_DSN=postgresql://user:pass@host:5432/metrics
GOOGLE_SA_JSON=/absolute/path/to/service_account.json
HABITS_CFG=etl/config/habits.yml

Map your Sheet headers to habits in etl/config/habits.yml:

sheet_id: "YOUR_SHEET_ID"
tab_name: "Form Responses 1"
timezone: "America/Chicago"
email_column: "Email Address"
date_column: "Report Date"

habits:
  "Sleep (Number of hours)":         { id: "sleep_hours", type: "number" }
  "Nutrition":                       { id: "nutrition_score", type: "number" }
  "Mood":                            { id: "mood_score", type: "number" }
  "Meditation (Number of Minutes)":  { id: "meditation_minutes", type: "number" }
  "Workout":                         { id: "workout", type: "bool" }
  "Water (How many litres?)":        { id: "water_liters", type: "number" }
  "Skin Care":                       { id: "skin_care", type: "bool" }
  "How authentically did you live this day?": { id: "authenticity_score", type: "number" }
notes_columns: ["Notes"]

4) Install, test, run

# export env vars for Make targets
export $(grep -v '^#' .env | tr '\n' ' ')

make install        # pip install -r requirements.txt
make test           # run unit tests
make etl            # runs etl/etl_habits.py once

5) Verify data

Connect Grafana → Add data source → PostgreSQL → point it at your DB. Use the query editor to run:

SELECT * FROM habit_events ORDER BY ts DESC LIMIT 50;

(See Grafana’s Postgres data source docs if you haven’t added one before.)  ￼

⸻

Schema (overview)
	•	habits_raw(row_hash, ingested_at, payload jsonb) — landing zone for forensics.
	•	habit_events(event_id, ts timestamptz, user_email, habit, value, notes, source) — tidy events; UNIQUE(user_email, habit, ts) makes ingestion idempotent.

Timescale setup (created by sql/001_schema.sql):
	•	Hypertable on habit_events(ts) + helpful indexes.
	•	Example continuous aggregate habit_daily with a refresh policy (fast daily rollups).  ￼ ￼

⸻

Grafana: panels you’ll probably want

Add the PostgreSQL data source, then:
	•	Variables
	•	user: SELECT DISTINCT user_email FROM habit_events ORDER BY 1;
	•	habit: SELECT DISTINCT habit FROM habit_events ORDER BY 1;
	•	Time series (Meditation minutes by day)

SELECT time_bucket('1 day', ts) AS day, sum(value) AS minutes
FROM habit_events
WHERE $__timeFilter(ts) AND user_email = '${user}' AND habit = 'meditation_minutes'
GROUP BY 1 ORDER BY 1;


	•	Bar gauge (weekly completion % for boolean habits)

WITH week AS (
  SELECT date_trunc('week', $__timeFrom()) AS start_ts, $__timeTo() AS end_ts
)
SELECT habit,
       100.0 * sum(CASE WHEN value >= 1 THEN 1 ELSE 0 END)::float / GREATEST(count(*),1) AS pct_done
FROM habit_events, week
WHERE ts >= week.start_ts AND ts < week.end_ts
  AND user_email = '${user}'
  AND habit IN ('workout','skin_care')
GROUP BY habit ORDER BY habit;



Grafana has a visual SQL builder if you prefer clicks over code, and you can combine queries with panel-level Transformations.  ￼

⸻

Google Form fields (reference)
	•	Timestamp (ignored by ETL)
	•	Email Address (used for user_email)
	•	Report Date (used for ts; any locale format is fine—ETL normalizes)
	•	Sleep (Number of hours)
	•	Nutrition (1–10)
	•	Mood (1–10)
	•	Meditation (Number of Minutes)
	•	Workout (Yes/No)
	•	Water (How many litres?)
	•	Skin Care (Yes/No)
	•	How authentically did you live this day? (1–10)
	•	Notes (free text; optional)

⸻

Security notes
	•	Never commit your .env or service account JSON. Keep .env.example checked in and .env ignored.
	•	Share the Sheet to the service account email (Viewer); you don’t need to open it publicly.  ￼ ￼

⸻

Packaging as a Kubernetes CronJob (preview)

You can containerize this ETL and schedule it every 15 minutes. Mount the service account JSON as a Secret; inject DB creds as env vars.

apiVersion: batch/v1
kind: CronJob
metadata:
  name: habits-etl
spec:
  schedule: "*/15 * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: etl
            image: python:3.11-slim
            command: ["bash","-lc","pip install -r requirements.txt && python etl/etl_habits.py"]
            workingDir: /app
            env:
              - name: PG_DSN
                valueFrom: { secretKeyRef: { name: habits-etl, key: PG_DSN } }
              - name: HABITS_CFG
                value: etl/config/habits.yml
              - name: GOOGLE_SA_JSON
                value: /var/secrets/sa.json
            volumeMounts:
              - name: app
                mountPath: /app
              - name: secrets
                mountPath: /var/secrets
                readOnly: true
          volumes:
            - name: app
              gitRepo: { repository: "https://github.com/your-org/habits-etl.git" }
            - name: secrets
              secret: { secretName: habits-etl }

On large datasets, prefer Timescale continuous aggregates to keep dashboards fast as history grows.  ￼

⸻

Troubleshooting
	•	403 / Not found when reading the sheet → you didn’t share it to the service account email. Fix by sharing the spreadsheet to that principal.  ￼ ￼
	•	Grafana can’t see tables → confirm the data source points at the right DB/schema and user has rights; see Grafana’s Postgres data source docs.  ￼
	•	Dates look shifted → ETL anchors date-only values at noon local time before converting to UTC to avoid DST cliffs; that’s intentional.

⸻

Roadmap
	•	Pack official Docker image + Helm chart.
	•	Optional Apps Script to backfill an ISO date column in the sheet (purely cosmetic).
	•	“Quality gates” (alert if numeric fields become non-numeric, or daily submissions drop unexpectedly).
	•	Ready-made Grafana dashboard JSON with variables, panels, and thresholds.

⸻

License

MIT (or similar). PRs welcome.

⸻

Setup in under 30 minutes (checklist)
	•	Create GCP service account + JSON key; share the Sheet with it (Viewer).  ￼ ￼
	•	Fill .env; edit etl/config/habits.yml (use your exact header names).
	•	make install && make test && make etl
	•	Add a PostgreSQL data source in Grafana and run the sample query.  ￼

If you want, I can also generate a Grafana dashboard JSON that matches your exact habits.yml so anyone can import and get charts immediately.
