#!/usr/bin/env python3
"""
Estimate your overall FPL rank for a given points total using a classic league.

Binary-searches the league standings pages (each page shows 50 teams in rank order).
Finds a page whose top team has your target points, then finds the left/right
boundaries to get the rank range; reports the middle rank as the estimate.

Usage:
  python scripts/get_overall_rank_from_points.py

Uses: LEAGUE_ID (classic league), TARGET_POINTS (your points total).
Set these at the top of the file or make them CLI/env for sharing.
"""
import requests
import time

LEAGUE_ID = 314
TARGET_POINTS = 1572
TOTAL_PAGES = 250889  # current approx
SLEEP = 0.15


def get_top_team(page):
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{LEAGUE_ID}/standings/?page_standings={page}"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    top = data["standings"]["results"][0]
    return {
        "page": page,
        "points": top["total"],
        "rank": top["rank"],
        "entry": top["entry"],
        "team": top["entry_name"]
    }


def find_any_page_with_target():
    lo, hi = 1, TOTAL_PAGES

    while lo <= hi:
        mid = (lo + hi) // 2
        team = get_top_team(mid)
        pts = team["points"]

        if pts == TARGET_POINTS:
            return mid
        elif pts > TARGET_POINTS:
            lo = mid + 1
        else:
            hi = mid - 1

        time.sleep(SLEEP)

    return None


def find_boundary(start_page, direction):
    lo, hi = (1, start_page) if direction == "left" else (start_page, TOTAL_PAGES)
    boundary = start_page

    while lo <= hi:
        mid = (lo + hi) // 2
        team = get_top_team(mid)
        pts = team["points"]

        if pts == TARGET_POINTS:
            boundary = mid
            if direction == "left":
                hi = mid - 1
            else:
                lo = mid + 1
        else:
            if pts > TARGET_POINTS:
                lo = mid + 1
            else:
                hi = mid - 1

        time.sleep(SLEEP)

    return boundary


print("🔍 Searching for a page with target points...")
page = find_any_page_with_target()

if page is None:
    print("❌ Target points not found.")
    exit()

print(f"✅ Found target points on page {page}")

print("⬅️ Finding first page with target points...")
first_page = find_boundary(page, "left")

print("➡️ Finding last page with target points...")
last_page = find_boundary(page, "right")

middle_page = (first_page + last_page) // 2
team = get_top_team(middle_page)

print("\n📊 Estimated Rank for Target Points")
print("----------------------------------")
print(f"Points: {TARGET_POINTS}")
print(f"First page: {first_page}")
print(f"Last page: {last_page}")
print(f"Middle page: {middle_page}")
print(f"Estimated Rank: {team['rank']}")
print(f"Team ID (entry): {team['entry']}")
print(f"Team: {team['team']}")
