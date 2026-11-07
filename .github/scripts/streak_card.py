#!/usr/bin/env python3
"""Generate a GitHub contribution streak card (SVG) with no third-party service.

Reads contribution data from the GitHub GraphQL API and writes a static SVG.
Env vars:
  GITHUB_TOKEN  token used for the API (GITHUB_TOKEN from Actions is enough)
  GH_USER       GitHub username
  OUTPUT        output path (default: assets/streak.svg)
  CARD_TZ       time zone used to decide "today" (default: Asia/Bangkok)
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Pastel colours matching the original README
C = {
    "bg": "#F4FAFE",
    "border": "#B8DCEC",
    "stroke": "#C9E2F2",
    "title": "#2F3E4E",
    "text": "#4A5B6E",
    "fire": "#E58AA8",
    "ring": "#F285B0",
    "curr": "#DF4583",
}
WIDTH, HEIGHT, RADIUS = 480, 195, 14
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', sans-serif"

API = "https://api.github.com/graphql"


def gql(query, variables, token):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-streak-card",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


def fetch_days(user, token):
    years = gql(
        "query($u:String!){user(login:$u){contributionsCollection{contributionYears}}}",
        {"u": user},
        token,
    )["user"]["contributionsCollection"]["contributionYears"]
    q = """query($u:String!,$from:DateTime!,$to:DateTime!){
      user(login:$u){contributionsCollection(from:$from,to:$to){
        contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
    days = {}
    for y in sorted(years):
        data = gql(q, {"u": user, "from": f"{y}-01-01T00:00:00Z", "to": f"{y}-12-31T23:59:59Z"}, token)
        cal = data["user"]["contributionsCollection"]["contributionCalendar"]
        for week in cal["weeks"]:
            for d in week["contributionDays"]:
                days[date.fromisoformat(d["date"])] = d["contributionCount"]
    return days


def compute(days, today):
    counts = {d: n for d, n in days.items() if d <= today}
    total = sum(counts.values())
    active = sorted(d for d, n in counts.items() if n > 0)
    first = active[0] if active else today

    # Longest streak: consecutive calendar days with at least one contribution
    longest = (0, None, None)
    run, start, prev = 0, None, None
    for d in active:
        if prev is not None and d == prev + timedelta(days=1):
            run += 1
        else:
            run, start = 1, d
        if run > longest[0]:
            longest = (run, start, d)
        prev = d

    # Current streak: a streak is still alive if today has no contributions yet
    end = today if counts.get(today, 0) > 0 else today - timedelta(days=1)
    n, d = 0, end
    while counts.get(d, 0) > 0:
        n += 1
        d -= timedelta(days=1)
    current = (n, d + timedelta(days=1), end) if n else (0, None, None)
    return total, first, current, longest


def fmt(d, today):
    s = f"{d.strftime('%b')} {d.day}"
    return s if d.year == today.year else f"{s}, {d.year}"


def span(start, end, today):
    if start is None:
        return ""
    if start == end:
        return fmt(start, today)
    return f"{fmt(start, today)} - {fmt(end, today)}"


def render(total, first, current, longest, today):
    cx1, cx2, cx3 = 80, 240, 400
    flame = (
        "M0,-13 C6,-7 10,-2 10,4 C10,10 5.5,14 0,14 C-5.5,14 -10,10 -10,4 "
        "C-10,-1 -7,-5 -4.5,-8 C-4,-4 -2,-1.5 0.5,-0.5 C1,-5 0,-9 0,-13 Z"
    )
    inner = "M0,2 C3,5 4,7 4,9 C4,11.5 2,13 0,13 C-2,13 -4,11.5 -4,9 C-4,7 -2,5 0,2 Z"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="GitHub streak stats">
  <style>
    .num {{ font: 700 28px {FONT}; }}
    .lbl {{ font: 400 14px {FONT}; }}
    .lblb {{ font: 700 14px {FONT}; }}
    .dt {{ font: 400 12px {FONT}; opacity: .85; }}
  </style>
  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="{RADIUS}" fill="{C['bg']}" stroke="{C['border']}"/>
  <line x1="160" y1="28" x2="160" y2="170" stroke="{C['stroke']}" stroke-width="1"/>
  <line x1="320" y1="28" x2="320" y2="170" stroke="{C['stroke']}" stroke-width="1"/>

  <g text-anchor="middle">
    <text x="{cx1}" y="79" class="num" fill="{C['title']}">{total:,}</text>
    <text x="{cx1}" y="114" class="lbl" fill="{C['text']}">Total Contributions</text>
    <text x="{cx1}" y="140" class="dt" fill="{C['text']}">{fmt(first, today)} - Present</text>
  </g>

  <g text-anchor="middle">
    <circle cx="{cx2}" cy="71" r="40" fill="none" stroke="{C['ring']}" stroke-width="5"/>
    <circle cx="{cx2}" cy="31" r="15" fill="{C['bg']}"/>
    <g transform="translate({cx2} 30)">
      <path d="{flame}" fill="{C['fire']}"/>
      <path d="{inner}" fill="{C['bg']}" opacity=".75"/>
    </g>
    <text x="{cx2}" y="81" class="num" fill="{C['curr']}">{current[0]:,}</text>
    <text x="{cx2}" y="140" class="lblb" fill="{C['curr']}">Current Streak</text>
    <text x="{cx2}" y="162" class="dt" fill="{C['text']}">{span(current[1], current[2], today)}</text>
  </g>

  <g text-anchor="middle">
    <text x="{cx3}" y="79" class="num" fill="{C['title']}">{longest[0]:,}</text>
    <text x="{cx3}" y="114" class="lbl" fill="{C['text']}">Longest Streak</text>
    <text x="{cx3}" y="140" class="dt" fill="{C['text']}">{span(longest[1], longest[2], today)}</text>
  </g>
</svg>
"""


def main():
    user = os.environ.get("GH_USER")
    token = os.environ.get("GITHUB_TOKEN")
    out = os.environ.get("OUTPUT", "assets/streak.svg")
    tz = ZoneInfo(os.environ.get("CARD_TZ", "Asia/Bangkok"))
    if not user or not token:
        sys.exit("GH_USER and GITHUB_TOKEN are required")

    today = datetime.now(tz).date()
    try:
        days = fetch_days(user, token)
    except Exception as e:  # keep the previous card instead of publishing a broken one
        print(f"::warning::Could not fetch contributions, keeping old card: {e}")
        return

    svg = render(*compute(days, today), today)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
