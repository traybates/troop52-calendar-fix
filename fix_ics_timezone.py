#!/usr/bin/env python3
"""
fix_ics_timezone.py

Fixes the known Scoutbook Plus / Internet Advancement calendar export bug where
event times are published in UTC ("Z" suffix) with no TZID/VTIMEZONE information.
Calendar apps (Apple/Google/Outlook) auto-detect this and convert to local time
correctly, but simple embed widgets (like GoDaddy Website + Marketing's Calendar
section) display the raw UTC digits as if they were already local time.

This script:
  1. Downloads the source .ics feed (the raw Scoutbook Plus link)
  2. Converts every UTC ("...Z") DTSTART/DTEND into a local-time value tagged with
     TZID=America/Chicago, with a correct VTIMEZONE block (DST-aware)
  3. Leaves all-day events (VALUE=DATE) untouched, since those have no time to fix
  4. Writes out a corrected .ics file that any calendar widget -- including
     GoDaddy's -- will display at the right wall-clock time

Usage:
    python3 fix_ics_timezone.py <source_url_or_path> <output_path> [--tz America/Chicago]
"""

import sys
import re
import argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

try:
    import requests
except ImportError:
    requests = None

LOCAL_TZID_DEFAULT = "America/Chicago"

# Standard, DST-aware VTIMEZONE block for US Central Time.
# (Same structure used by Outlook/Google exports; valid for any year since it's
# rule-based via RRULE, not a fixed date.)
VTIMEZONE_CHICAGO = """BEGIN:VTIMEZONE
TZID:America/Chicago
X-LIC-LOCATION:America/Chicago
BEGIN:DAYLIGHT
TZOFFSETFROM:-0600
TZOFFSETTO:-0500
TZNAME:CDT
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0500
TZOFFSETTO:-0600
TZNAME:CST
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
END:VTIMEZONE
"""

UTC_DT_RE = re.compile(r'^(DTSTART|DTEND)(;[^:]*)?:(\d{8}T\d{6})Z$')


def fetch_source(source: str) -> str:
    """Read source ICS from a URL or local file path."""
    if source.startswith("http://") or source.startswith("https://"):
        if requests is None:
            raise RuntimeError("requests library not installed")
        resp = requests.get(source, timeout=30)
        resp.raise_for_status()
        return resp.text
    with open(source, "r", encoding="utf-8") as f:
        return f.read()


def convert_line(line: str, tzid: str) -> str:
    """
    Convert a single DTSTART/DTEND line from raw UTC ('...Z') to a local-time
    value tagged with TZID. Leaves VALUE=DATE (all-day) and already-tagged
    TZID lines untouched.
    """
    line = line.rstrip("\r\n")
    m = UTC_DT_RE.match(line)
    if not m:
        return line  # not a bare-UTC DTSTART/DTEND line; leave as-is

    field, existing_params, ts = m.groups()
    utc_dt = datetime.strptime(ts, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    local_dt = utc_dt.astimezone(ZoneInfo(tzid))
    local_str = local_dt.strftime("%Y%m%dT%H%M%S")
    return f"{field};TZID={tzid}:{local_str}"


def convert_line_godaddy(line: str, tzid: str) -> str:
    """
    Like convert_line, but instead of tagging the corrected local time with
    TZID (which GoDaddy's simple calendar widget appears unable to parse --
    it silently drops every event rather than erroring), this re-emits the
    corrected local wall-clock time with a bare 'Z' suffix, exactly like the
    original buggy feed. This is intentionally "mislabeled" UTC: it is not
    correct for real calendar apps (Apple/Google/Outlook would convert it
    again and get the wrong time), but it is exactly what GoDaddy's widget
    needs, since GoDaddy takes the raw digits at face value.
    Use this output only for the GoDaddy website feed -- use the proper
    TZID-tagged output (mode="tzid") for anything people subscribe to
    personally.
    """
    line = line.rstrip("\r\n")
    m = UTC_DT_RE.match(line)
    if not m:
        return line

    field, existing_params, ts = m.groups()
    utc_dt = datetime.strptime(ts, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    local_dt = utc_dt.astimezone(ZoneInfo(tzid))
    local_str = local_dt.strftime("%Y%m%dT%H%M%S")
    return f"{field}:{local_str}Z"


def fix_ics(source_text: str, tzid: str = LOCAL_TZID_DEFAULT, mode: str = "tzid") -> str:
    """
    mode="tzid": proper RFC 5545 output with VTIMEZONE + TZID (correct
        everywhere; use for personal calendar subscriptions).
    mode="godaddy": bare-Z output with times pre-shifted to already be local
        (only correct when consumed by GoDaddy's simple widget).
    """
    lines = source_text.splitlines()
    out_lines = []
    inserted_vtimezone = False
    inserted_calendar_props = False

    for line in lines:
        stripped = line.rstrip("\r\n")

        # Right after CALSCALE (top of the VCALENDAR block), add calendar-level
        # properties some importers -- notably GoDaddy's -- have been reported
        # to require: METHOD:PUBLISH and X-WR-TIMEZONE. Neither was present in
        # the original Scoutbook Plus feed.
        if not inserted_calendar_props and stripped.startswith("CALSCALE:"):
            out_lines.append(stripped)
            out_lines.append("METHOD:PUBLISH")
            out_lines.append(f"X-WR-TIMEZONE:{tzid}")
            inserted_calendar_props = True
            continue

        if mode == "tzid":
            if not inserted_vtimezone and stripped.startswith("BEGIN:VEVENT"):
                out_lines.extend(VTIMEZONE_CHICAGO.strip("\n").splitlines())
                inserted_vtimezone = True
            out_lines.append(convert_line(stripped, tzid))
        else:
            out_lines.append(convert_line_godaddy(stripped, tzid))

    return "\r\n".join(out_lines) + "\r\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Source .ics URL or file path (raw Scoutbook Plus link)")
    parser.add_argument("output", help="Path to write the corrected .ics file")
    parser.add_argument("--tz", default=LOCAL_TZID_DEFAULT, help="IANA timezone name (default: America/Chicago)")
    parser.add_argument("--mode", choices=["tzid", "godaddy"], default="tzid",
                         help="'tzid' = correct RFC 5545 output for personal calendar apps; "
                              "'godaddy' = bare-Z output pre-shifted for GoDaddy's simple widget")
    args = parser.parse_args()

    source_text = fetch_source(args.source)
    fixed_text = fix_ics(source_text, args.tz, mode=args.mode)

    with open(args.output, "w", encoding="utf-8", newline="") as f:
        f.write(fixed_text)

    print(f"Wrote corrected calendar to {args.output}")


if __name__ == "__main__":
    main()
