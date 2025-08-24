from etl.transform import unpivot_row

CFG = {
  "date_column": "Report Date",
  "email_column": "Email Address",
  "timezone": "America/Chicago",
  "habits": {
    "Workout": {"id":"workout","type":"bool"},
    "Meditation (Number of Minutes)": {"id":"meditation_minutes","type":"number"},
    "Mood": {"id":"mood_score","type":"number"}
  },
  "notes_columns": ["Notes"]
}

def test_unpivot_row_user_and_date_only():
    row = {
      "Report Date":"08/20/2025",
      "Email Address":"Test@Example.com",
      "Workout":"Yes",
      "Meditation (Number of Minutes)":"25",
      "Mood":"8",
      "Notes":"did intervals"
    }
    ev = unpivot_row(row, CFG)
    assert {e["habit"] for e in ev} == {"workout","meditation_minutes","mood_score"}
    u = {e["user_email"] for e in ev}
    assert u == {"test@example.com"}
    # noon-local should become some UTC time; presence is enough for unit test
    assert all("ts" in e and e["ts"].tzinfo is not None for e in ev)
    