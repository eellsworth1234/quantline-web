# QuantLine — Today's Slate

Live sports-betting analytics. Static front end on GitHub Pages, odds refreshed by
a scheduled GitHub Action. No server to run.

**Live:** https://eellsworth1234.github.io/quantline-web/

> **Status:** the app ships with **no data**. It stays empty until you add an
> Odds API key — see [Bringing the feed online](#bringing-the-feed-online).
> That is deliberate: there is no sample data anywhere in this repo.

## No fake bets

This is the rule the whole design serves: **the app must never display a game or
a price that does not exist.**

- `data/slate.json` ships with `"games": []`. There is no fallback fixture and no
  demo mode. If the feed has not run, the app says so and renders nothing.
- If the fetch fails, the script exits non-zero *without writing*, so a broken run
  leaves the last good slate in place rather than publishing garbage.
- Games that have already started are dropped by the fetcher, and dropped again in
  the browser every 60 seconds — a stale JSON can never surface a started game.
- Prices with an implausible edge (>25% EV) are discarded as bad data, not
  surfaced as opportunity.

## Where the probabilities come from

The earlier prototype invented a `modelProb` per bet. That number is gone. There
is no proprietary model here, and pretending otherwise would make every "edge" on
screen a fabrication.

Instead every probability is **derived from the market itself**:

1. Convert each book's posted American odds to implied probability. Both sides sum
   to more than 1.00 — the excess is that book's **vig**.
2. Divide each outcome by that sum to strip the vig out. What remains is that
   book's honest opinion.
3. Take the **median** of those de-vigged opinions across every book pricing the
   same outcome. That median is the market consensus.
4. Find the best price available anywhere on that outcome. If it pays more than
   the consensus justifies, that gap is a real positive expected value.

Step 3 **excludes the book being evaluated**. Including it would let an outlier
drag the consensus toward itself and manufacture an edge that is really just one
book being wrong in a vacuum.

The claim the app makes is therefore checkable: *"this book is paying more than
the other books on the same outcome, right now."* It is not a prediction about
who plays better tonight, and the UI says so.

### Consequence: the numbers got smaller, and that is correct

Fabricated edges ran +3% to +7%. Real de-vigged consensus edges are typically
**+1% to +3%**, and a $500 bankroll produces stakes of a few dollars. Thresholds
were retuned to match reality:

| Tier | EV |
|---|---|
| `STRONG` | ≥ 3.0% |
| `SOLID` | ≥ 2.0% |
| `LEAN` | ≥ 1.0% |
| `NO BET` | below 1.0% (`BET_FLOOR`) |

A 7% edge against a six-book consensus almost always means stale data, not free
money — hence the sanity cap.

## Bringing the feed online

1. Get a key at **the-odds-api.com**. The free tier is 500 credits/month.
2. Add it as a repository secret named `ODDS_API_KEY`
   (Settings → Secrets and variables → Actions → New repository secret).
   Or from the CLI:
   ```
   gh secret set ODDS_API_KEY --repo eellsworth1234/quantline-web
   ```
3. Run **Refresh odds** from the Actions tab (`workflow_dispatch`), or wait for
   the next scheduled run.

The key is only ever read from GitHub Secrets by the Action. It is never present
in the published page — the front end reads a committed JSON file, so there is no
client-side API key to steal and no way for a visitor to burn your quota.

### Credit budget

The Odds API charges **one credit per market per region per request**. The current
config is 2 sports × 3 markets × 1 region = **6 credits per run**, twice daily ≈
**372 credits/month**, inside the free tier with headroom for manual runs.

To go properly live, upgrade the plan and change the cron in
`.github/workflows/refresh-odds.yml` to `*/15 * * * *`. Nothing else changes.

Player props are not fetched. They require per-event requests and would blow the
credit budget many times over — worth adding once the plan supports it.

## Layout

```
index.html                      the whole front end, no build step
data/slate.json                 written by the Action, read by the page
scripts/fetch_odds.py           fetch, de-vig, find edges, write the slate
.github/workflows/refresh-odds.yml   cron + manual dispatch
```

Tunable via workflow env: `SPORTS`, `MARKETS`, `REGIONS`, `WINDOW_HOURS`,
`MIN_BOOKS`, `BET_FLOOR`, `LEAN`, `SOLID`, `STRONG`.

`MIN_BOOKS=4` is a quality gate: fewer than four books pricing an outcome means
the consensus is not trustworthy, so the outcome is skipped entirely.

## The core design rule

**Someone who has never placed a bet must be able to land here cold, understand
what they are looking at, and know what to do — without being told.**

- **The data board is not the product.** The default view is a slate of upcoming
  games. Each card answers one question: *should I bet this, and if so, what
  exactly?* The dense terminal grid is the opt-in **DATA BOARD** toggle.
- Every game resolves to **✓ RECOMMENDED BET** (the bet in plain words, best price,
  which book, why, and a dollar stake) or **× NO BET** (skip it).
- **"No bet" is a first-class verdict and is never paywalled.** Most games are
  skips. Telling someone to sit out should not cost money; only picks are gated.
- **Confidence tags translate EV.** STRONG/SOLID/LEAN describe how well a bet
  *pays*, not how likely it is to *win* — the walkthrough says so explicitly.
- **Probabilities are frequencies.** "45 chances in 100," not "45.0%."
- **Bankroll is an input**, so Kelly renders as real dollars, never "units."
- **The downside is stated as loudly as the upside.** Every expanded card says how
  often the bet is expected to lose and that losing runs are normal.

## Positioning caveat

Recommendation language ("recommended bet," confidence tags) reads closer to a
picks service than a pure analytics utility, which is what ad networks and app
review scrutinise. Mitigations in place: the reasoning and math are always one tap
away, the disclaimer and 1-800-GAMBLER are on every view, and nothing accepts
wagers, holds funds, or links out to a sportsbook.

Keep UI copy on the analytics side: "edge," "expected return," "consensus." Never
"lock," "guaranteed," or "can't lose."

## Verifying the math

```
python3 scripts/fetch_odds.py
```

With `ODDS_API_KEY` exported it writes a real slate. Without it, it refuses to run
rather than emit placeholder data.

## Run locally

```
python3 -m http.server 4173
```

Then open http://localhost:4173. Note that `file://` will not work — the page
fetches `data/slate.json`, which needs an HTTP origin.

## Caveat that matters

Prices move constantly. A pregame edge found at 13:00 UTC may be gone by the time
anyone reads it, which is why the app shows a live/stale feed age in the header
and tells users to confirm the number at the book before acting. On the free tier
refreshing twice a day, treat everything on screen as indicative rather than
actionable.
