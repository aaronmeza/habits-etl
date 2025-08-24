import os, yaml, json, gspread, psycopg
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from transform import row_hash, unpivot_row

load_dotenv()
CFG_PATH = os.environ.get("HABITS_CFG", "etl/config/habits.yml")
PG_DSN = os.environ["PG_DSN"]  # e.g. postgresql://user:pass@host:5432/db
SA_JSON = os.environ["GOOGLE_SA_JSON"]  # path to service account JSON

def get_ws(sheet_id: str, tab_name: str):
    scope = ["https://www.googleapis.com/auth/spreadsheets.readonly",
             "https://www.googleapis.com/auth/drive.readonly"]
    creds = Credentials.from_service_account_file(SA_JSON, scopes=scope)
    client = gspread.authorize(creds)
    sh = client.open_by_key(sheet_id)
    return sh.worksheet(tab_name)

def ensure_schema(conn: psycopg.Connection):
    with conn.cursor() as cur:
        cur.execute(open("sql/001_schema.sql","r").read())
    conn.commit()

def upsert(conn: psycopg.Connection, events, raw_row):
    rh = row_hash(raw_row)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO habits_raw(row_hash, payload) VALUES(%s, %s::jsonb) ON CONFLICT DO NOTHING",
            (rh, json.dumps(raw_row))
        )
        for e in events:
            cur.execute("""
                INSERT INTO habit_events(ts, user_email, habit, value, notes, source)
                VALUES (%s, %s, %s, %s, %s, 'sheets')
                ON CONFLICT (user_email, habit, ts) DO UPDATE SET
                  value = EXCLUDED.value,
                  notes = COALESCE(EXCLUDED.notes, habit_events.notes)
            """, (e["ts"], e["user_email"], e["habit"], e["value"], e["notes"]))
    conn.commit()

def main():
    cfg = yaml.safe_load(open(CFG_PATH))
    ws = get_ws(cfg["sheet_id"], cfg["tab_name"])
    rows = ws.get_all_records()  # list[dict] keyed by header row
    with psycopg.connect(PG_DSN) as conn:
        ensure_schema(conn)
        for row in rows:
            events = unpivot_row(row, cfg)
            if events:
                upsert(conn, events, row)

if __name__ == "__main__":
    main()