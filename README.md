# QuantLine — Terminal Preview

Static, single-file preview of the QuantLine terminal dashboard (Component #1).
No build step, no dependencies, no network calls. `index.html` is the whole site.

## What this is

A visual and interaction reference for the production Next.js build. It exists to
lock the layout, density, color language, onboarding, and paywall behavior before
any of it is rebuilt as React components.

## The core design rule

**Someone who has never placed a bet must be able to land here cold and understand
what they are looking at, without being told.**

That rule drives every decision in this file, and it inverts the obvious default:

- **Plain English is the default view. Terminal density is the opt-in.** A Bloomberg
  grid is the reward for understanding, not the on-ramp. The toggle is in the header.
- **Same data in both modes — only the words change.** Plain mode never hides a
  column or rounds differently. `SELECTION → "THE BET"`, `EV → "EXPECTED RETURN"`,
  and each header carries a one-line subtitle answering "what is this column?"
- **Every row translates to a sentence.** Click any row to expand a plain-English
  breakdown: what the book's price implies, what the model says, what the gap is
  worth per $100, and what to stake. This is the feature that makes the board
  legible to a newcomer.
- **Probabilities are stated as "44 out of 100," not just "44.3%."** Frequencies are
  measurably easier to reason about than percentages.
- **Bankroll is an input, not a concept.** Enter a real number and every suggested
  stake becomes a dollar figure instead of an abstract "unit."
- **The downside is stated as loudly as the upside.** Every expanded row says how
  often the bet is expected to *lose*, and that losing runs are normal. This is both
  the honest framing and the one that keeps users from blowing up and churning.

A four-step walkthrough opens automatically on first visit (tracked in
`localStorage`, key `ql_seen`) and is re-openable from the header. Finishing it
auto-expands the top row, so the first thing a newcomer sees is a worked example
rather than a wall of numbers. A full glossary lives behind the footer link.

**All odds data in this file is simulated.** Team abbreviations are real; player
names are fictional; every price is invented. The page is labeled as such in the
header. Do not present it as a live feed.

## The math is real

Only `modelProb` is assumed per row. Everything else is computed in-browser from
`(americanOdds, modelProb)`:

| Output | Formula |
|---|---|
| Decimal odds | `a > 0 ? a/100 + 1 : 100/-a + 1` |
| Implied probability | `a > 0 ? 100/(a+100) : -a/(-a+100)` |
| Expected value per unit | `p × decimal − 1` |
| Full Kelly | `(p·b − q) / b`, where `b = decimal − 1`, `q = 1 − p` |
| Displayed stake | quarter Kelly (`full / 4`) |

These are the reference implementations for Component #2 (the calc engine). If the
engine and this page ever disagree, the engine is wrong until proven otherwise.

`ALERT_THRESHOLD = 0.035` matches the ≥3.5% sweep that Component #3 (the Discord
alert bot) will push.

## Run locally

```
python3 -m http.server 4173
```

Then open http://localhost:4173

Opening `index.html` directly via `file://` also works.

## Deploying to GitHub Pages

Push to the default branch, then Settings → Pages → Source: *Deploy from a branch*
→ `main` / `root`. Pages serves `index.html` at the repo root as-is.

Note: GitHub Pages sites are publicly readable regardless of repository visibility
settings on free accounts.

## Compliance

The footer disclaimer is load-bearing, not decoration. It establishes that
QuantLine is educational tracking software that does not accept wagers or handle
funds — which is what keeps the product reviewable by ad networks and app stores.
Do not trim it, and keep all UI copy on the analytics side of the line: "edge,"
"expected value," "model probability" — never "lock," "pick," or "guaranteed."
