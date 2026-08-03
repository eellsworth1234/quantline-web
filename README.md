# QuantLine — Today's Slate

Static, single-file preview of the QuantLine app (Component #1).
No build step, no dependencies, no network calls. `index.html` is the whole site.

**Live:** https://eellsworth1234.github.io/quantline-web/

## What this is

A visual and interaction reference for the production Next.js build. It exists to
lock the information architecture, copy, onboarding, and paywall behavior before
any of it is rebuilt as React components.

## The core design rule

**Someone who has never placed a bet must be able to land here cold, understand
what they are looking at, and know what to do — without being told.**

That rule produced the central decision in v0.2: **the data board is not the
product.** The product is a slate of today's games where each card answers one
question — *should I bet this, and if so, what exactly?*

Every game resolves to one of two verdicts:

- **✓ RECOMMENDED BET** — the exact bet in plain words ("Cubs to win"), the best
  price across six books, which book has it, a written reason, a confidence tag,
  and a dollar stake sized to the user's bankroll.
- **× NO BET** — the price is fair, there is nothing to win, skip the game.

The dense terminal grid still exists behind the **DATA BOARD** toggle, for users
who want raw numbers. It is the opt-in, not the default.

### Supporting decisions

- **Confidence tags translate expected value.** Nobody new knows what "+4.2% EV"
  feels like; everybody knows STRONG vs SOLID vs LEAN. The tag describes how well
  the bet *pays*, not how likely it is to *win* — the walkthrough says so explicitly.
- **"No bet" is a first-class result, never a gap.** Most games should be skips,
  and the UI says so out loud: *"Most games are a no bet, and that is the point."*
- **"No bet" verdicts are never paywalled.** Telling someone to sit out is free;
  only the picks are gated. Gating the skips would invert the product's ethics.
- **Probabilities are frequencies.** "44 chances in 100," not "44.3%." Measurably
  easier to reason about.
- **Bankroll is an input, not a concept.** Real dollars, never abstract "units."
  A $500 bankroll makes even the strongest pick a ~$6 bet — that lesson lands far
  harder as a number on screen than as a paragraph.
- **The downside is stated as loudly as the upside.** Every expanded card says how
  often the bet is expected to *lose* and that losing runs are normal. Honest, and
  it keeps users from blowing up in week one and churning.

A four-step walkthrough opens on first visit (`localStorage` key `ql_seen`) and is
re-openable from the header. A full glossary sits behind the footer link.

## Positioning caveat

Recommendation language ("recommended bet," confidence tags) reads closer to a
picks service than to a pure analytics utility. That is a deliberate product
choice for comprehension, but it is the thing most likely to attract scrutiny
from ad networks and app-store review. The mitigations in place:

- The reasoning and the underlying math are always one tap away — this is analysis
  shown transparently, not a tip handed down.
- The compliance disclaimer and 1-800-GAMBLER are in the footer on every view.
- Nothing accepts wagers, holds funds, or links out to a sportsbook.

Keep UI copy on the analytics side of the line: "edge," "expected return," "model
probability." Never "lock," "guaranteed," or "can't lose."

## The math is real

Only `modelProb` is assumed per bet. Everything else is computed in-browser from
`(americanOdds, modelProb)`:

| Output | Formula |
|---|---|
| Decimal odds | `a > 0 ? a/100 + 1 : 100/-a + 1` |
| Implied probability | `a > 0 ? 100/(a+100) : -a/(-a+100)` |
| Expected value per unit | `p × decimal − 1` |
| Full Kelly | `(p·b − q) / b`, where `b = decimal − 1`, `q = 1 − p` |
| Displayed stake | quarter Kelly (`full / 4`) × bankroll |

These are the reference implementations for Component #2 (the calc engine). If the
engine and this page ever disagree, the engine is wrong until proven otherwise.

Thresholds:

- `BET_FLOOR = 0.015` — below this the card returns **NO BET**.
- `ALERT_THRESHOLD = 0.035` — matches the sweep Component #3 (the Discord bot) pushes.

## Data

**All odds data is simulated.** Team names and venues are real; player names,
records, prices and reasoning are invented. The header carries a permanent
`SIMULATED FEED · NOT LIVE ODDS` badge. Do not present it as a live feed.

## Run locally

```
python3 -m http.server 4173
```

Then open http://localhost:4173 — or just open `index.html` directly.

## Deploying

Pages serves `index.html` from `main` at the repo root. Push and it redeploys.
GitHub Pages sites are publicly readable regardless of repository visibility.
