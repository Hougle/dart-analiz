# Coaching page: structure and requirements

The Coaching tab answers four questions, in this order:

1. **Where do I stand?** (level)
2. **What's strong and what's holding me back?** (skill profile)
3. **What should I work on first?** (priorities)
4. **What do I do this week, and is it working?** (plan and progress)

Every number comes from the player's own data in the selected period. Targets are rule-of-thumb coaching targets, labelled as such. They aren't data.

## 1. Data sources

| Source | Table / function | Used for |
|---|---|---|
| Match turns | `throws`, marked by `mark_double_attempts` | scoring average, first 9, checkout %, visits |
| Practice turns | `practice_sessions` + `practice_turns` (Score Training) | practice average, visits, stamina |
| Doubles | `doubles_section.double_stats(..., "Combined")`: match checkouts, ATC Doubles, Doubles Training | doubles accuracy, best / weakest double |
| Time played | `playing_time.sessions()` | weekly volume, plan size |

All sources follow the period picker (`ui_helpers.in_period`) and include only the connected player.

**Visits** are one scoring sequence each: the scoring turns of a match leg (before the double zone) plus every Score Training turn, grouped by leg or session and ordered by turn. Consistency and recovery are calculated on visits, so matches and practice both count.

## 2. Skills

Seven skills. Each has a raw value, a target, a score (% of target, capped at 120) and a minimum sample. Below the minimum the skill shows **Not enough data** and is left out of the ranking.

| Skill | Raw value | Higher is better | Minimum sample |
|---|---|---|---|
| Scoring power | Adjusted 3-dart average of match scoring turns. Uses the Score Training average if there are fewer than 3 matches | yes | 3 matches or 3 practice sessions |
| Strong start | First-9 average ÷ scoring average × 100 | yes, target 100% | 3 matches |
| Finishing | Checkouts ÷ checkout chances (turns in the double zone, plus finishes from higher) | yes | 20 chances |
| Doubles accuracy | Hits ÷ darts at doubles, all sources combined | yes | 50 darts |
| Consistency | 100 − coefficient of variation of visit scores | yes | 30 visits |
| Recovery | How often the visit after a bad one (40 or less, same leg/session) reaches the player's average, ÷ how often any visit does, × 100 | yes, target 100% | 10 bad visits |
| Stamina | Mean of the last 3 vs the first 3 turns of each Score Training session (≥ 6 turns), in % | yes, target −5% or better | 3 sessions |
| Practice volume | Hours played per week (weeks from the first to the last game in the period) | yes | 1 game |

### Levels and targets

The level comes from scoring power. Each skill's target is the value expected at the **next** level, so targets move up as the player improves.

| Level | Scoring average | Finishing % | Doubles % | Consistency | Volume h/week |
|---|---|---|---|---|---|
| Starter | < 35 | 10 | 8 | 40 | 1.5 |
| Developing | 35–45 | 12 | 10 | 45 | 2 |
| Club | 45–55 | 16 | 14 | 50 | 3 |
| League | 55–65 | 20 | 18 | 55 | 4 |
| Advanced | 65–80 | 25 | 24 | 60 | 5 |
| Elite | 80+ | 30 | 30 | 65 | 6 |

- **Scoring power** targets the bottom of the next band (Elite targets 90).
- **Strong start** always targets 100%.
- **Recovery** always targets 100%: a bad visit doesn't affect the next one. (The plain after-bad rate isn't used: most visits land below the average, so even an unflappable player reaches it only about 40% of the time.)
- **Stamina** always targets −5%.

### Score and status

- Score = value ÷ target × 100, capped at 120.
- **Stamina:** 100 at −5% or better, minus 5 points for every further % of drop, with a floor of 0.
- Status:
  - **On target**: score ≥ 100
  - **Close**: 80–99
  - **Focus**: under 80

  Status is always shown as a label, never as colour alone.

## 3. Priorities

- Rank the rated skills by score, lowest first. **Practice volume** never ranks above a playing skill: it moves to the end of the focus list unless nothing else is below 100.
- Show the **top 3** skills that aren't on target. If all are on target, show a "Keep it up" card with the weakest skill as the stretch goal.
- Each priority card has:
  - what the data says (value, sample)
  - the target and the gap
  - a concrete drill in a DartCounter mode, with a measurable goal
- One drill per skill:

| Skill | DartCounter mode | Drill |
|---|---|---|
| Scoring power | Score Training | 10 visits at T20 per set. Beat your set average each time |
| Strong start | Score Training | Treat each set of 3 visits as a leg start. Goal: average of the first 3 ≥ your scoring average |
| Finishing | Doubles Training / ATC Doubles | Finishes from 40, 32 and 16: 3 darts each, count checkouts |
| Doubles accuracy | Doubles Training | 30 darts at your weakest rated double, then 30 at your best. Count hits |
| Consistency | Score Training | Count visits within 20 points of your average. Beat the count next session |
| Recovery | Score Training | After any visit ≤ 40: step off, one breath, reset stance. Track the next visit |
| Stamina | Score Training | Add 5 visits to the end of each session and track only those |
| Practice volume | Any | Add one 20-minute session per week |

## 4. Weekly plan

- **Weekly time** = the player's current weekly average + 15%, rounded to 5 minutes, at least 60 minutes.
- **Sessions per week** = the player's average active days per week, rounded, between 2 and 5.
- Each session splits into blocks:
  - warm-up 15% (Score Training)
  - priority 1: 40%
  - priority 2: 25%
  - priority 3 or a match: 20%
- Each block shows minutes and roughly how many darts that is, using the player's own pace (seconds per dart from practice; 6 s if unknown).

## 5. Progress

- **Then vs now:** the period's games are split by date into an earlier half and a later half, with at least 2 days of play in each. Each skill shows earlier → later with the change. If one half is empty, say so instead.
- **Trends:** a daily trend (`ui_helpers.daily_trend`) for each top priority that has a per-day series:
  - scoring average
  - finishing %
  - doubles hit rate
  - consistency
  - recovery

## 6. Page layout (top to bottom)

1. **Where you stand:**
   - a level card: level name, scoring average, and a progress bar to the next level showing how much is still needed
   - 3 metrics: skills on target (n of rated), top priority, weekly time
2. **Skill profile:** a horizontal bar per skill showing % of target, coloured and labelled by status. A table with value, target and sample sits in an expander.
   - **Understand each skill:** pick a skill to see what it measures, how it's calculated, why the target is what it is (`coaching.EXPLAIN`), the player's own numbers behind it, the target at every level (`coaching.ladder`) and the drill.
3. **Your priorities:** 3 cards (side by side on desktop, stacked on a phone).
4. **This week's plan:** one card per session, with blocks, minutes and darts.
5. **Progress:** a then-vs-now table, then trends for the priorities.
6. **How this works:** an expander with the levels/targets table and the definitions, so every number can be traced.

## 7. Rules

- **Period filter:** follows the period filter. If the period has too little data for any skill, show one `st.info` naming the period.
- **Charts:** Plotly `graph_objects`, rendered with `ui_helpers.chart`. Colours come from roles; status colours are only for status.
- **Theme and phone:** works in light and dark and at 375 px wide. No horizontal scroll, no clipped titles.
- **Code:** all calculations live in `coaching.py` (no Streamlit) and are unit-tested in `tests/test_coaching.py`. `coaching_page.py` only draws.
- **Errors:** a missing table never breaks the tab; the affected skill shows Not enough data.
