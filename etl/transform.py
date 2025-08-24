from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo
import hashlib, json
from typing import Dict, List, Any

@dataclass
class HabitSpec:
    id: str
    type: str  # "bool" | "number"
    invert: bool = False

TRUTHY = {"yes","true","1","y","t","on"}

def row_hash(row: Dict[str, Any]) -> bytes:
    blob = json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).digest()

def parse_report_date(s: str, tzname: str) -> datetime:
    """Sheets often stores date-only values. We anchor at local NOON to dodge DST cliffs, then to UTC."""
    s = str(s).strip()
    local = ZoneInfo(tzname)
    fmts = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y")  # add more if you need
    for f in fmts:
        try:
            d = datetime.strptime(s, f).date()
            dt_local = datetime.combine(d, time(12, 0, 0), tzinfo=local)  # noon local
            return dt_local.astimezone(ZoneInfo("UTC"))
        except Exception:
            pass
    # If it's actually a datetime string, try a few common formats:
    for f in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S"):
        try:
            dt = datetime.strptime(s, f).replace(tzinfo=local)
            return dt.astimezone(ZoneInfo("UTC"))
        except Exception:
            pass
    # last resort: fromisoformat
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=local)
    return dt.astimezone(ZoneInfo("UTC"))

def unpivot_row(row: Dict[str, Any], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    tz = cfg.get("timezone", "America/Chicago")
    ts_col = cfg["date_column"]
    email_col = cfg.get("email_column", "Email Address")

    # missing required fields? skip row
    if not row.get(ts_col) or not row.get(email_col):
        return []

    ts = parse_report_date(row[ts_col], tz)
    user_email = str(row[email_col]).strip().lower()

    notes = []
    for ncol in cfg.get("notes_columns", []):
        if row.get(ncol):
            notes.append(f"{ncol}: {row[ncol]}")
    notes_str = " | ".join(notes) if notes else None

    events = []
    for sheet_col, spec_raw in cfg["habits"].items():
        spec = HabitSpec(**spec_raw)
        raw = row.get(sheet_col, "")
        if raw is None or str(raw).strip() == "":
            continue

        if spec.type == "bool":
            v = 1.0 if str(raw).strip().lower() in TRUTHY else 0.0
            if spec.invert:
                v = 1.0 - v
        else:
            try:
                v = float(str(raw).strip())
            except ValueError:
                continue

        events.append({
            "ts": ts,
            "user_email": user_email,
            "habit": spec.id,
            "value": v,
            "notes": notes_str
        })
    return events
