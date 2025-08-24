from etl.transform import parse_report_date
from zoneinfo import ZoneInfo

def test_parse_mmddyyyy_to_utc():
    dt = parse_report_date("8/22/2025", "America/Chicago")
    # Noon CDT = 17:00Z
    assert dt.tzinfo is not None
    assert dt.hour == 17 and dt.minute == 0

def test_parse_serial_date_to_utc():
    # 8/22/2025 in Google serials (check in Sheets: =DATE(2025,8,22) -> 45519)
    dt = parse_report_date(45519, "America/Chicago")
    assert dt.hour == 17  # noon local == 17:00Z during CDT
