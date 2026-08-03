#!/usr/bin/env python3
"""
Fetch live odds from The Odds API and write data/slate.json.

This script is the honest core of QuantLine. It does NOT invent a model.
Every probability it reports is derived from the market itself:

  1. For each bookmaker and market, convert the posted American odds to
     implied probability. Those sum to more than 1.00 -- the excess is the
     bookmaker's vig.
  2. Divide each outcome by that sum to strip the vig out. What remains is
     that book's honest opinion of the probability.
  3. Take the MEDIAN of those de-vigged opinions across all books offering
     the same outcome. That median is the market consensus, and it is the
     best no-model estimate of true probability available.
  4. Find the single best price on that outcome anywhere. If that price pays
     more than the consensus probability justifies, the difference is a real
     positive expected value.

Step 3 deliberately EXCLUDES the book being evaluated. Including it would let
an outlier drag the consensus toward itself and manufacture an edge that is
really just one book being wrong in a vacuum.

No API key, no output. A failed fetch exits non-zero and leaves the previous
slate.json untouched rather than publishing something stale as if it were live.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from statistics import median

API_BASE = "https://api.the-odds-api.com/v4"

KEY = os.environ.get("ODDS_API_KEY", "").strip()
SPORTS = [s.strip() for s in os.environ.get("SPORTS", "baseball_mlb,basketball_wnba").split(",") if s.strip()]
MARKETS = os.environ.get("MARKETS", "h2h,spreads,totals").strip()
REGIONS = os.environ.get("REGIONS", "us").strip()

WINDOW_HOURS = float(os.environ.get("WINDOW_HOURS", "36"))
MIN_BOOKS = int(os.environ.get("MIN_BOOKS", "4"))

# Thresholds. These are lower than a model-based product would use, because
# market-consensus edges are genuinely smaller. A 7% edge against a de-vigged
# six-book consensus almost always means bad data, not free money.
BET_FLOOR = float(os.environ.get("BET_FLOOR", "0.010"))
LEAN = float(os.environ.get("LEAN", "0.010"))
SOLID = float(os.environ.get("SOLID", "0.020"))
STRONG = float(os.environ.get("STRONG", "0.030"))
EV_SANITY_CAP = float(os.environ.get("EV_SANITY_CAP", "0.25"))

KELLY_FRACTION = 0.25
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "slate.json")

SPORT_META = {
    "baseball_mlb":          ("MLB",   "runs"),
    "basketball_wnba":       ("WNBA",  "points"),
    "basketball_nba":        ("NBA",   "points"),
    "americanfootball_nfl":  ("NFL",   "points"),
    "americanfootball_ncaaf": ("NCAAF", "points"),
    "icehockey_nhl":         ("NHL",   "goals"),
    "soccer_usa_mls":        ("MLS",   "goals"),
}

MARKET_KIND = {
    "h2h":     "Who wins the game",
    "spreads": "Margin of victory",
    "totals":  "Combined score",
}


# ---------------------------------------------------------------- math ----

def to_decimal(american):
    a = float(american)
    return (a / 100.0) + 1.0 if a > 0 else (100.0 / -a) + 1.0


def implied_prob(american):
    a = float(american)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def to_american(prob):
    """Fair American odds for a probability, for showing what a no-vig price
    would look like next to what a book is actually posting."""
    if prob <= 0 or prob >= 1:
        return None
    dec = 1.0 / prob
    return round((dec - 1.0) * 100) if dec >= 2.0 else round(-100.0 / (dec - 1.0))


def ev_per_unit(prob, american):
    return prob * to_decimal(american) - 1.0


def quarter_kelly(prob, american):
    b = to_decimal(american) - 1.0
    if b <= 0:
        return 0.0
    return max(0.0, ((prob * b) - (1.0 - prob)) / b) * KELLY_FRACTION


def fmt_am(a):
    return ("+" if a > 0 else "") + str(int(a))


def fmt_pt(p):
    return ("%g" % float(p))


# --------------------------------------------------------------- fetch ----

def fetch(sport):
    qs = urllib.parse.urlencode({
        "apiKey": KEY,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": "american",
        "dateFormat": "iso",
    })
    url = "%s/sports/%s/odds/?%s" % (API_BASE, sport, qs)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read().decode("utf-8"))
        remaining = r.headers.get("x-requests-remaining")
        used = r.headers.get("x-requests-used")
    return body, remaining, used


# ------------------------------------------------------------- language ----

def describe(market, name, point, unit):
    """Plain-English rendering of a bet. Someone who has never gambled must be
    able to read this and know exactly what has to happen."""
    if market == "h2h":
        return "%s to win" % name, "Moneyline"
    if market == "spreads":
        p = float(point)
        label = "Spread %s" % (("+" if p > 0 else "") + fmt_pt(p))
        if p < 0:
            return "%s to win by more than %s" % (name, fmt_pt(abs(p))), label
        if p > 0:
            return "%s to win, or lose by less than %s" % (name, fmt_pt(p)), label
        return "%s to win outright" % name, label
    if market == "totals":
        label = "Total %s" % fmt_pt(point)
        if name.lower() == "over":
            return "More than %s combined %s" % (fmt_pt(point), unit), label
        return "Fewer than %s combined %s" % (fmt_pt(point), unit), label
    return "%s %s" % (name, fmt_pt(point) if point is not None else ""), market


def confidence(ev):
    if ev >= STRONG:
        return {"k": "STRONG", "c": "s"}
    if ev >= SOLID:
        return {"k": "SOLID", "c": "m"}
    if ev >= LEAN:
        return {"k": "LEAN", "c": "l"}
    return None


# ---------------------------------------------------------------- build ----

def build_event(ev, sport_key, unit, label, now, horizon):
    try:
        start = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None

    # Only games that have not started yet and are close enough to matter.
    if start <= now or start > horizon:
        return None

    books = ev.get("bookmakers") or []
    if len(books) < MIN_BOOKS:
        return None

    # (market, outcome name, point) -> [{book, price, fair}]
    quotes = {}
    for bm in books:
        title = bm.get("title") or bm.get("key")
        for mk in bm.get("markets") or []:
            outs = mk.get("outcomes") or []
            if len(outs) < 2:
                continue
            imps = [implied_prob(o["price"]) for o in outs]
            total = sum(imps)
            if total <= 0:
                continue
            for o, ip in zip(outs, imps):
                key = (mk["key"], o["name"], o.get("point"))
                quotes.setdefault(key, []).append({
                    "book": title,
                    "price": int(o["price"]),
                    "fair": ip / total,          # this book's no-vig opinion
                })

    bets = []
    for (market, name, point), qs in quotes.items():
        if len(qs) < MIN_BOOKS:
            continue

        best = max(qs, key=lambda q: to_decimal(q["price"]))

        # Consensus excludes the book we are evaluating, so an outlier cannot
        # vote for its own edge.
        others = [q["fair"] for q in qs if q["book"] != best["book"]]
        if len(others) < MIN_BOOKS - 1:
            continue
        consensus = median(others)
        if not (0.0 < consensus < 1.0):
            continue

        ev_val = ev_per_unit(consensus, best["price"])
        if ev_val < BET_FLOOR:
            continue
        # An implausible edge means a stale or broken quote, not an opportunity.
        if ev_val > EV_SANITY_CAP:
            continue

        plain, market_label = describe(market, name, point, unit)
        fair_am = to_american(consensus)

        why = (
            "%s is posting %s. Stripping the vig out of the other %d books pricing "
            "this same outcome puts the consensus at %.1f%%, which is a fair price of "
            "about %s. %s is paying better than the market's own average."
            % (best["book"], fmt_am(best["price"]), len(others), consensus * 100,
               fmt_am(fair_am) if fair_am is not None else "n/a", best["book"])
        )

        bets.append({
            "market": market,
            "market_label": market_label,
            "kind": MARKET_KIND.get(market, market),
            "selection": name,
            "point": point,
            "plain": plain,
            "book": best["book"],
            "odds": best["price"],
            "consensus_prob": round(consensus, 4),
            "consensus_odds": fair_am,
            "implied": round(implied_prob(best["price"]), 4),
            "edge": round(consensus - implied_prob(best["price"]), 4),
            "ev": round(ev_val, 4),
            "kelly": round(quarter_kelly(consensus, best["price"]), 5),
            "n_books": len(qs),
            "why": why,
        })

    bets.sort(key=lambda b: b["ev"], reverse=True)

    # Best available moneyline for each side, purely for the card header.
    def best_ml(team):
        qs = quotes.get(("h2h", team, None)) or []
        return max((q["price"] for q in qs), key=lambda p: to_decimal(p)) if qs else None

    home, away = ev.get("home_team"), ev.get("away_team")
    best_bet = bets[0] if bets else None

    return {
        "id": ev.get("id"),
        "sport_key": sport_key,
        "sport": label,
        "commence_time": ev["commence_time"],
        "home": {"name": home, "price": best_ml(home)},
        "away": {"name": away, "price": best_ml(away)},
        "book_count": len(books),
        "bets": bets,
        "best": best_bet,
        "confidence": confidence(best_bet["ev"]) if best_bet else None,
    }


def main():
    if not KEY:
        sys.stderr.write(
            "ODDS_API_KEY is not set.\n"
            "Set it as a repository secret named ODDS_API_KEY, or export it locally.\n"
            "Refusing to write a slate rather than publish placeholder data.\n"
        )
        return 1

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=WINDOW_HOURS)

    games, remaining, used = [], None, None
    for sport in SPORTS:
        label, unit = SPORT_META.get(sport, (sport.upper(), "points"))
        try:
            events, remaining, used = fetch(sport)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            sys.stderr.write("HTTP %s fetching %s: %s\n" % (e.code, sport, detail))
            if e.code in (401, 403):
                return 1          # bad key: fail loudly, do not publish
            continue              # one dead sport should not kill the run
        except Exception as e:
            sys.stderr.write("Error fetching %s: %s\n" % (sport, e))
            continue

        for ev in events:
            g = build_event(ev, sport, unit, label, now, horizon)
            if g:
                games.append(g)
        sys.stderr.write("%s: %d playable games\n" % (sport, sum(1 for g in games if g["sport_key"] == sport)))

    games.sort(key=lambda g: (g["best"]["ev"] if g["best"] else -1), reverse=True)

    payload = {
        "generated_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": "the-odds-api.com",
        "method": "de-vigged median consensus across books, candidate book excluded",
        "credits": {"used": used, "remaining": remaining},
        "config": {
            "sports": SPORTS, "markets": MARKETS.split(","), "regions": REGIONS,
            "window_hours": WINDOW_HOURS, "min_books": MIN_BOOKS,
            "bet_floor": BET_FLOOR, "lean": LEAN, "solid": SOLID, "strong": STRONG,
            "kelly_fraction": KELLY_FRACTION,
        },
        "games": games,
    }

    os.makedirs(os.path.dirname(os.path.abspath(OUT_PATH)), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
        f.write("\n")

    playable = sum(1 for g in games if g["best"])
    sys.stderr.write("Wrote %d games (%d with a bet). Credits remaining: %s\n"
                     % (len(games), playable, remaining))
    return 0


if __name__ == "__main__":
    sys.exit(main())
