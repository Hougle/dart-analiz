"""Coaching calculations (no Streamlit). The spec is docs/coaching.md.

Everything works on a `Data` bundle that is already limited to the connected
player and the selected period. Every frame has a tz-aware `when` column.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from match_stats import darts_stats

# ------------------------------------------------------------------ levels
# (name, lowest scoring average). Targets per level are rule-of-thumb coaching
# targets, not data: finishing %, doubles %, consistency, recovery %, hours/week.
LEVELS = [
    ("Starter", 0, dict(finishing=10, doubles=8, consistency=40, recovery=30, volume=1.5)),
    ("Developing", 35, dict(finishing=12, doubles=10, consistency=45, recovery=35, volume=2)),
    ("Club", 45, dict(finishing=16, doubles=14, consistency=50, recovery=40, volume=3)),
    ("League", 55, dict(finishing=20, doubles=18, consistency=55, recovery=45, volume=4)),
    ("Advanced", 65, dict(finishing=25, doubles=24, consistency=60, recovery=50, volume=5)),
    ("Elite", 80, dict(finishing=30, doubles=30, consistency=65, recovery=55, volume=6)),
]
ELITE_TARGET = 90  # scoring target once already Elite

SKILLS = ["scoring", "start", "finishing", "doubles", "consistency", "recovery", "stamina", "volume"]
NAMES = {"scoring": "Scoring power", "start": "Strong start", "finishing": "Finishing",
         "doubles": "Doubles accuracy", "consistency": "Consistency", "recovery": "Recovery",
         "stamina": "Stamina", "volume": "Practice volume"}

DRILLS = {
    "scoring": ("Score Training", "10 visits at T20 per set. Beat your set average each time."),
    "start": ("Score Training", "Treat every 3 visits as a leg start. Goal: the first 3 average at least "
                                "your scoring average."),
    "finishing": ("Doubles Training", "Finishes from 40, 32 and 16, three darts each. Count checkouts "
                                      "and beat the count next session."),
    "doubles": ("Doubles Training", "30 darts at your weakest double, then 30 at your best. Count hits."),
    "consistency": ("Score Training", "Count visits within 20 points of your average. Beat the count "
                                      "next session."),
    "recovery": ("Score Training", "After any visit of 40 or less: step off, one breath, reset your "
                                   "stance. Track the next visit."),
    "stamina": ("Score Training", "Add 5 visits to the end of each session and track only those."),
    "volume": ("Any mode", "Add one 20-minute session a week."),
}


WHY = {
    "scoring": "Every point of scoring average takes darts off every leg.",
    "start": "The first 9 darts set up the leg. A slow start leaves you chasing.",
    "finishing": "Legs are won on the double. Missed chances hand your opponent extra visits.",
    "doubles": "Doubles accuracy decides how many darts each checkout costs.",
    "consistency": "Steady visits make your average reliable instead of streaky.",
    "recovery": "One bad visit is normal; two in a row loses legs.",
    "stamina": "Holding your level late keeps long legs and matches winnable.",
    "volume": "Skills only move with regular practice.",
}


@dataclass
class Data:
    match_turns: pd.DataFrame      # player's turns in finished matches, with is_dbl and when
    practice_sessions: pd.DataFrame  # Score Training: session_id, avg_3dart, when
    practice_turns: pd.DataFrame   # Score Training: session_id, turn, score, when
    doubles: pd.DataFrame          # when, target, hits, attempts (all sources)
    games: pd.DataFrame            # time played: when, sec


@dataclass
class Skill:
    key: str
    value: float = None
    target: float = None
    sample: int = 0
    sample_label: str = ""
    note: str = ""
    score: float = None
    status: str = "Not enough data"

    @property
    def name(self):
        return NAMES[self.key]

    @property
    def rated(self):
        return self.score is not None


def _empty(df):
    return df is None or df.empty


def _filter(df, mask_fn):
    return df if _empty(df) else df[mask_fn(df)]


def split(data, cutoff):
    """(before, from) the cutoff timestamp."""
    def part(before):
        return Data(*[_filter(f, (lambda d: d["when"] < cutoff) if before else (lambda d: d["when"] >= cutoff))
                      for f in (data.match_turns, data.practice_sessions, data.practice_turns,
                                data.doubles, data.games)])
    return part(True), part(False)


# ------------------------------------------------------------------ raw values
def scoring(data):
    """(value, source, sample). Match scoring turns if 3+ matches, else Score Training."""
    m = data.match_turns
    if not _empty(m) and m["match_id"].nunique() >= 3:
        s = m[~m["is_dbl"]]
        darts = pd.to_numeric(s["darts_thrown"], errors="coerce").sum()
        if darts:
            return pd.to_numeric(s["score_thrown"], errors="coerce").sum() / darts * 3, "matches", m["match_id"].nunique()
    p = data.practice_sessions
    if not _empty(p) and len(p) >= 3:
        return float(pd.to_numeric(p["avg_3dart"], errors="coerce").mean()), "Score Training", len(p)
    n = 0 if _empty(m) else m["match_id"].nunique()
    return None, "matches", n


def visits(data):
    """Scoring visits from match legs (before the double zone) and Score Training, in turn order."""
    parts = []
    m = data.match_turns
    if not _empty(m):
        s = m[~m["is_dbl"]]
        parts.append(pd.DataFrame({"group": "L" + s["leg_id"].astype(str), "turn": s["turn"],
                                   "score": pd.to_numeric(s["score_thrown"], errors="coerce"),
                                   "when": s["when"]}))
    t = data.practice_turns
    if not _empty(t):
        parts.append(pd.DataFrame({"group": "P" + t["session_id"].astype(str), "turn": t["turn"],
                                   "score": pd.to_numeric(t["score"], errors="coerce"), "when": t["when"]}))
    if not parts:
        return pd.DataFrame(columns=["group", "turn", "score", "when"])
    v = pd.concat(parts, ignore_index=True).dropna(subset=["score"])
    return v.sort_values(["group", "turn"]).reset_index(drop=True)


def consistency(v):
    """(100 − coefficient of variation, visits)."""
    if len(v) < 2 or v["score"].mean() <= 0:
        return None, len(v)
    return max(0.0, 100 - v["score"].std() / v["score"].mean() * 100), len(v)


def recovery(v):
    """(% of visits after a visit ≤ 40 that reach the average visit, number of bad visits)."""
    if v.empty:
        return None, 0
    prev = v.groupby("group")["score"].shift(1)
    after_bad = v[prev <= 40]
    if after_bad.empty:
        return None, 0
    return (after_bad["score"] >= v["score"].mean()).mean() * 100, len(after_bad)


def stamina(data):
    """(% change of the last 3 vs the first 3 turns, pooled over sessions of 6+ turns, sessions)."""
    t = data.practice_turns
    if _empty(t):
        return None, 0
    t = t.assign(score=pd.to_numeric(t["score"], errors="coerce"))
    last = t.groupby("session_id")["turn"].transform("max")
    t = t[last >= 6]
    if t.empty:
        return None, 0
    last = t.groupby("session_id")["turn"].transform("max")
    first, late = t[t["turn"] <= 3]["score"].mean(), t[t["turn"] >= last - 2]["score"].mean()
    if not first:
        return None, t["session_id"].nunique()
    return (late - first) / first * 100, t["session_id"].nunique()


def volume(data):
    """(hours per week from the first to the last game's week, games)."""
    g = data.games
    if _empty(g):
        return None, 0
    week = g["when"].dt.tz_localize(None).dt.to_period("W-SUN")
    weeks = (week.max() - week.min()).n + 1
    return g["sec"].sum() / 3600 / weeks, len(g)


def doubles_rate(data):
    d = data.doubles
    if _empty(d):
        return None, 0
    darts = d["attempts"].sum()
    return (d["hits"].sum() / darts * 100 if darts else None), int(darts)


# ------------------------------------------------------------------ levels & skills
def level(avg):
    """(index, name, band low, band high or None)."""
    if avg is None or pd.isna(avg):
        return None, None, None, None
    i = max(i for i, (_, low, _) in enumerate(LEVELS) if avg >= low)
    high = LEVELS[i + 1][1] if i + 1 < len(LEVELS) else None
    return i, LEVELS[i][0], LEVELS[i][1], high


def targets(level_index):
    nxt = min((level_index or 0) + 1, len(LEVELS) - 1)
    t = dict(LEVELS[nxt][2])
    t["scoring"] = LEVELS[level_index + 1][1] if level_index is not None and level_index + 1 < len(LEVELS) \
        else (ELITE_TARGET if level_index is not None else LEVELS[1][1])
    t["start"] = 100
    t["stamina"] = -5
    return t


def _status(score):
    if score is None:
        return "Not enough data"
    return "On target" if score >= 100 else "Close" if score >= 80 else "Focus"


def assess(data, level_index=None):
    """All skills with value, target, score and status. Targets come from level_index
    (or the level of this data's scoring power when not given)."""
    sc, src, n_sc = scoring(data)
    if level_index is None:
        level_index = level(sc)[0]
    tg = targets(level_index)
    v = visits(data)
    m = data.match_turns
    n_matches = 0 if _empty(m) else m["match_id"].nunique()
    ds = darts_stats(m if not _empty(m) else pd.DataFrame())

    out = {}
    out["scoring"] = Skill("scoring", sc, tg["scoring"], n_sc,
                           f"{n_sc} {'matches' if src == 'matches' else 'sessions'}",
                           note="Adjusted average of match scoring turns" if src == "matches"
                           else "Score Training average (fewer than 3 matches)")
    start = None
    if n_matches >= 3 and ds["first9"] and sc and src == "matches":
        start = ds["first9"] / sc * 100
    out["start"] = Skill("start", start, tg["start"], n_matches, f"{n_matches} matches",
                         note=f"First 9 {ds['first9']:.1f} vs scoring {sc:.1f}" if start else "")
    fin = ds["checkout"] if ds["checkout_chances"] >= 20 else None
    out["finishing"] = Skill("finishing", fin, tg["finishing"], ds["checkout_chances"],
                             f"{ds['checkouts']} of {ds['checkout_chances']} chances")
    dr, darts = doubles_rate(data)
    out["doubles"] = Skill("doubles", dr if darts >= 50 else None, tg["doubles"], darts, f"{darts} darts")
    ci, nv = consistency(v)
    out["consistency"] = Skill("consistency", ci if nv >= 30 else None, tg["consistency"], nv, f"{nv} visits")
    rc, nb = recovery(v)
    out["recovery"] = Skill("recovery", rc if nb >= 10 else None, tg["recovery"], nb, f"{nb} bad visits")
    st_, ns = stamina(data)
    out["stamina"] = Skill("stamina", st_ if ns >= 3 else None, tg["stamina"], ns, f"{ns} sessions")
    vol, ng = volume(data)
    out["volume"] = Skill("volume", vol, tg["volume"], ng, f"{ng} games")

    for s in out.values():
        if s.value is None or pd.isna(s.value) or s.target is None:
            s.value = None
            continue
        if s.key == "stamina":
            s.score = 100.0 if s.value >= s.target else max(0.0, 100 + (s.value - s.target) * 5)
        else:
            s.score = min(120.0, s.value / s.target * 100) if s.target else None
        s.status = _status(s.score)
    return [out[k] for k in SKILLS]


def priorities(skills, n=3):
    """Weakest rated skills that aren't on target, lowest score first; volume goes last."""
    weak = [s for s in skills if s.rated and s.score < 100]
    weak.sort(key=lambda s: (s.key == "volume", s.score))
    return weak[:n]


# ------------------------------------------------------------------ plan
def weekly_plan(prio, data, pace_sec=6.0):
    """Sessions for next week: list of dicts with minutes and blocks (name, mode, minutes, darts)."""
    g = data.games
    current, _ = volume(data)
    weekly = max(60, int(round((current or 0) * 60 * 1.15 / 5)) * 5)
    if _empty(g):
        sessions = 3
    else:
        days = g["when"].dt.date.nunique()
        week = g["when"].dt.tz_localize(None).dt.to_period("W-SUN")
        weeks = (week.max() - week.min()).n + 1
        sessions = int(np.clip(round(days / weeks), 2, 5))
    per = max(15, int(round(weekly / sessions / 5)) * 5)
    pace = pace_sec if pace_sec and pace_sec > 0 else 6.0

    focus = [p.key for p in prio if p.key != "volume"]
    shares = [("Warm-up", "scoring", 0.15)]
    for i, share in enumerate((0.40, 0.25, 0.20)):
        shares.append((f"Priority {i + 1}" if i < len(focus) else "Match play",
                       focus[i] if i < len(focus) else None, share))
    blocks = []
    for label, key, share in shares:
        minutes = max(5, int(round(per * share)))
        mode, drill = DRILLS[key] if key else ("Match vs DartBot", "Play a best of 3 at your level.")
        if label == "Warm-up":
            drill = "Easy visits at T20 to find your rhythm."
        blocks.append(dict(label=label, skill=NAMES.get(key, "Match play") if key else "Match play",
                           mode=mode, drill=drill, minutes=minutes, darts=int(round(minutes * 60 / pace / 5)) * 5))
    total = sum(b["minutes"] for b in blocks)
    return dict(weekly=weekly, sessions=sessions, per_session=total, blocks=blocks,
                current=round((current or 0) * 60))


# ------------------------------------------------------------------ progress
def activity_days(data):
    whens = [f["when"] for f in (data.match_turns, data.practice_turns, data.doubles, data.games)
             if not _empty(f)]
    if not whens:
        return []
    return sorted(pd.concat(whens).dt.tz_localize(None).dt.normalize().unique())


def then_vs_now(data, level_index):
    """(cutoff day, [(skill, earlier value, later value)]) or (None, []) with fewer than 4 days of play."""
    days = activity_days(data)
    if len(days) < 4:
        return None, []
    cutoff = pd.Timestamp(days[len(days) // 2]).tz_localize(data_tz(data))
    before, after = split(data, cutoff)
    a, b = assess(before, level_index), assess(after, level_index)
    return cutoff, [(x, y.value, z.value) for x, y, z in zip(SKILLS, a, b)]


def data_tz(data):
    for f in (data.match_turns, data.practice_turns, data.doubles, data.games):
        if not _empty(f):
            return f["when"].dt.tz
    return "Europe/Istanbul"


def daily(key, data):
    """One pooled value per day for a skill, for trend charts (when = day at noon)."""
    days = activity_days(data)
    rows = []
    for day in days:
        start = pd.Timestamp(day).tz_localize(data_tz(data))
        _, d = split(data, start)
        d, _ = split(d, start + pd.Timedelta(days=1))
        if key == "scoring":
            m = d.match_turns
            if not _empty(m):
                s = m[~m["is_dbl"]]
                darts = pd.to_numeric(s["darts_thrown"], errors="coerce").sum()
                val = pd.to_numeric(s["score_thrown"], errors="coerce").sum() / darts * 3 if darts else None
            else:
                val = None
        elif key == "finishing":
            ds = darts_stats(d.match_turns) if not _empty(d.match_turns) else None
            val = ds["checkout"] if ds and ds["checkout_chances"] >= 3 else None
        elif key == "doubles":
            val, n = doubles_rate(d)
            val = val if n >= 10 else None
        elif key == "consistency":
            val, n = consistency(visits(d))
            val = val if n >= 10 else None
        elif key == "recovery":
            val, n = recovery(visits(d))
            val = val if n >= 3 else None
        else:
            val = None
        if val is not None and not pd.isna(val):
            rows.append(dict(when=start + pd.Timedelta(hours=12), value=val))
    return pd.DataFrame(rows, columns=["when", "value"])


TREND_KEYS = ["scoring", "finishing", "doubles", "consistency", "recovery"]


def fmt(key, value):
    """Display a skill value with its unit."""
    if value is None or pd.isna(value):
        return "–"
    if key == "scoring":
        return f"{value:.1f}"
    if key == "stamina":
        return f"{value:+.1f}%"
    if key == "volume":
        m = int(round(value * 60))
        return f"{m // 60} h {m % 60:02d} m / wk" if m >= 60 else f"{m} m / wk"
    return f"{value:.0f}%" if key in ("start", "consistency", "recovery") else f"{value:.1f}%"
