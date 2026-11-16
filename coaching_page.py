"""Coaching tab: level, skill profile, priorities, weekly plan and progress.

All calculations live in coaching.py; this module loads the data and draws.
The structure and rules are in docs/coaching.md.
"""
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import coaching
import playing_time
import ui_helpers
from dartcounter_api import only_player
from match_stats import mark_double_attempts

STATUS_ROLE = {"On target": "good", "Close": "warning", "Focus": "serious"}
STATUS_HEX = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a"}
STATUS_ICON = {"On target": ":material/check_circle:", "Close": ":material/trending_up:",
               "Focus": ":material/my_location:"}


# ------------------------------------------------------------------ data
def _when(df, col="started_at"):
    return df.assign(when=ui_helpers.local_time(df[col])) if not df.empty else df.assign(when=pd.Series(dtype="object"))


def _dated_doubles(match_turns, player, player_id):
    """Darts at doubles with dates, from the same three sources as the Doubles tab."""
    from practice_tab import load_all_practice_data
    from doubles_section import _load_doubles_training

    parts = []
    if not match_turns.empty:
        rb = pd.to_numeric(match_turns["remaining_before"], errors="coerce")
        on = ((rb > 0) & (rb <= 40) & (rb % 2 == 0)) | (rb == 50)
        m = match_turns[on]
        parts.append(pd.DataFrame({
            "when": m["when"], "target": (rb[on] / 2).astype(int),
            "hits": (pd.to_numeric(m["remaining_after"], errors="coerce") == 0).astype(int),
            "attempts": pd.to_numeric(m["darts_thrown"], errors="coerce").fillna(3)}))

    _, _, atc, atc_targets = load_all_practice_data()
    atc = ui_helpers.in_period(only_player(atc, player_id, player))
    if not atc.empty and not atc_targets.empty:
        if "is_cpu" in atc.columns:
            atc = atc[atc["is_cpu"].fillna(0).astype(int) == 0]
        if "number_segment" in atc.columns:
            atc = atc[atc["number_segment"].astype(str).str.lower() == "double"]
        t = atc_targets.merge(_when(atc)[["atc_user_id", "when"]], on="atc_user_id")
        if not t.empty:
            parts.append(pd.DataFrame({"when": t["when"], "target": t["target"], "hits": 1,
                                       "attempts": pd.to_numeric(t["darts_needed"], errors="coerce").fillna(0)}))

    sessions, targets = _load_doubles_training()
    sessions = ui_helpers.in_period(only_player(sessions, player_id, player))
    if not sessions.empty and not targets.empty:
        t = targets.merge(_when(sessions)[["doubles_user_id", "when"]], on="doubles_user_id")
        if not t.empty:
            parts.append(pd.DataFrame({"when": t["when"], "target": t["target"],
                                       "hits": pd.to_numeric(t["hits"], errors="coerce").fillna(0),
                                       "attempts": pd.to_numeric(t["darts_thrown"], errors="coerce").fillna(0)}))
    if not parts:
        return pd.DataFrame(columns=["when", "target", "hits", "attempts"])
    return pd.concat(parts, ignore_index=True)


def _pace(player, player_id):
    """The player's seconds per dart in practice (all four modes), or None."""
    from practice_tab import load_all_practice_data
    from singles_tab import _load_singles
    from doubles_section import _load_doubles_training
    score, _, atc, _ = load_all_practice_data()
    secs = darts = 0
    for df in (score, atc, _load_singles()[0], _load_doubles_training()[0]):
        df = only_player(df, player_id, player)
        if df is None or df.empty or not {"duration_sec", "darts_thrown"}.issubset(df.columns):
            continue
        secs += pd.to_numeric(df["duration_sec"], errors="coerce").sum()
        darts += pd.to_numeric(df["darts_thrown"], errors="coerce").sum()
    return secs / darts if darts else None


def load(player, player_id, matches, all_matches, throws):
    """Build the coaching Data bundle for the selected period."""
    from practice_tab import load_all_practice_data

    m = throws[throws["match_id"].isin(matches["match_id"])] if not throws.empty else throws
    if not m.empty:
        m = mark_double_attempts(m).merge(matches[["match_id", "date"]], on="match_id")
        m["when"] = ui_helpers.match_time(m["date"])
    else:
        m = pd.DataFrame(columns=["match_id", "leg_id", "turn", "score_thrown", "darts_thrown",
                                  "remaining_before", "remaining_after", "is_dbl", "when"])

    ps, pt, _, _ = load_all_practice_data()
    ps = ui_helpers.in_period(only_player(ps, player_id, player))
    ps = _when(ps)
    if not pt.empty and not ps.empty and {"session_id", "user_id"}.issubset(pt.columns):
        pt = pt.merge(ps[["session_id", "user_id", "when"]], on=["session_id", "user_id"])
        pt["score"] = pd.to_numeric(pt["score"], errors="coerce")
    else:
        pt = pd.DataFrame(columns=["session_id", "turn", "score", "when"])

    games = playing_time.sessions(all_matches, player, player_id)
    start = ui_helpers.period_start()
    if start is not None and not games.empty:
        games = games[games["when"] >= start]

    # Doubles count every match in the period, unfinished ones too, like the Doubles tab.
    dm = throws
    if not dm.empty and all_matches is not None and not all_matches.empty:
        dm = dm.merge(all_matches[["match_id", "date"]], on="match_id")
        dm["when"] = ui_helpers.match_time(dm["date"])
    else:
        dm = m
    return coaching.Data(m, ps, pt, _dated_doubles(dm, player, player_id), games)


# ------------------------------------------------------------------ sections
def _level_card(skills):
    sc = skills[0]
    idx, name, low, high = coaching.level(sc.value)
    if idx is None:
        st.info("Play at least 3 matches or 3 Score Training sessions in this period to get a level.")
        return
    nxt = coaching.LEVELS[idx + 1][0] if idx + 1 < len(coaching.LEVELS) else None
    if nxt:
        pct = max(0.0, min(1.0, (sc.value - low) / (high - low)))
        to_go = f"+{high - sc.value:.1f} to {nxt}"
        bar = (f'<div class="da-bar"><span style="width:{pct * 100:.0f}%"></span></div>'
               f'<div class="da-bar-l"><span>{name} {low}</span><span>{to_go}</span>'
               f'<span>{nxt} {high}</span></div>')
    else:
        bar = '<div class="da-bar-l"><span>Top level reached</span></div>'
    st.markdown(
        f'<div class="da-level"><div class="da-level-k">Your level</div>'
        f'<div class="da-level-v">{escape(name)}</div>'
        f'<div class="da-level-s">Scoring average <b class="da-num">{sc.value:.1f}</b> · '
        f'{escape(sc.note.lower())}</div>{bar}</div>', unsafe_allow_html=True)


def _profile_chart(skills):
    c = ui_helpers.colors()
    names = [s.name for s in skills][::-1]
    shown = skills[::-1]
    x = [min(s.score, 120) if s.rated else 0 for s in shown]
    color = [STATUS_HEX[STATUS_ROLE[s.status]] if s.rated else c["empty"] for s in shown]
    text = [f"{s.score:.0f}% · {s.status}" if s.rated else "Not enough data" for s in shown]
    hover = [f"{coaching.fmt(s.key, s.value)} vs target {coaching.fmt(s.key, s.target)}<br>{s.sample_label}"
             for s in shown]
    fig = go.Figure(go.Bar(
        x=x, y=names, orientation="h", marker=dict(color=color, cornerradius=4),
        text=text, textposition="outside", textfont=dict(color=c["text"], size=11), cliponaxis=False,
        customdata=hover, hovertemplate="<b>%{y}</b><br>%{customdata}<extra></extra>"))
    fig.add_vline(x=100, line=dict(color=c["muted"], width=1, dash="dot"))
    fig.update_layout(title="Skills as % of your next-level target", showlegend=False,
                      xaxis=dict(range=[0, 215], ticksuffix="%", tickvals=[0, 50, 100], title=""),  # room for labels on a phone
                      yaxis=dict(title="", type="category"), bargap=0.35)
    ui_helpers.chart(fig, key="coach_profile", height=len(skills) * 40 + 90,
                     margin=dict(t=56, b=30, l=120, r=16))


def _profile_table(skills):
    rows = [{"Skill": s.name, "You": coaching.fmt(s.key, s.value), "Target": coaching.fmt(s.key, s.target),
             "Score": f"{s.score:.0f}%" if s.rated else "–", "Status": s.status, "Based on": s.sample_label}
            for s in skills]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _priority_card(i, s, doubles):
    mode, drill = coaching.DRILLS[s.key]
    extra = ""
    if s.key == "doubles" and not doubles.empty:
        from doubles_section import ranked
        per = doubles.groupby("target")[["hits", "attempts"]].sum().reset_index()
        per["value"] = per["hits"] / per["attempts"].where(per["attempts"] > 0)
        r = ranked(per.dropna(subset=["value"]), 20)
        if len(r) >= 2:
            extra = f"Best rated: **{r.iloc[0]['name']}** · weakest: **{r.iloc[-1]['name']}**."
    with st.container(border=True):
        st.markdown(f"**{i}. {s.name}** · {s.status}")
        st.markdown(f"<span class='da-big da-num'>{coaching.fmt(s.key, s.value)}</span> "
                    f"<span class='da-muted'>target {coaching.fmt(s.key, s.target)}</span>",
                    unsafe_allow_html=True)
        st.caption(f"{s.sample_label} · {coaching.WHY[s.key]}")
        st.markdown(f":material/fitness_center: **{mode}:** {drill}" + (f"  \n{extra}" if extra else ""))


def _plan(prio, data, pace):
    plan = coaching.weekly_plan(prio, data, pace_sec=pace)
    st.markdown(
        f"**{plan['sessions']} sessions × {plan['per_session']} min** this week "
        f"({playing_time.fmt_minutes(plan['sessions'] * plan['per_session'])}). "
        + (f"You averaged {playing_time.fmt_minutes(plan['current'])} a week in this period, "
           "so this is a small step up." if plan["current"] else "Start with this and build up."))
    with st.container(border=True):
        st.markdown(f"**Each session · {plan['per_session']} min**")
        for b in plan["blocks"]:
            st.markdown(
                f"<div class='da-block'><div class='da-block-t'><b>{escape(b['label'])}</b> · "
                f"{escape(b['skill'])}<span class='da-muted da-num'>{b['minutes']} min · ≈{b['darts']} darts</span>"
                f"</div><div class='da-muted'>{escape(b['mode'])}: {escape(b['drill'])}</div></div>",
                unsafe_allow_html=True)
    st.caption(f"Darts are estimated from your practice pace ({pace:.1f} s per dart)." if pace
               else "Darts are estimated at 6 s per dart.")


def _progress(data, level_index, prio):
    cutoff, rows = coaching.then_vs_now(data, level_index)
    if cutoff is None:
        st.info("Progress needs at least 4 days of play in this period. Pick a longer period.")
    else:
        table = []
        for key, a, b in rows:
            if a is None and b is None:
                continue
            if a is None or b is None or pd.isna(a) or pd.isna(b):
                change = "–"
            else:
                d = b - a
                change = "= Same" if abs(d) < 1e-9 else ("▲ Better" if d > 0 else "▼ Worse")
            table.append({"Skill": coaching.NAMES[key],
                          "Earlier → later": f"{coaching.fmt(key, a)} → {coaching.fmt(key, b)}".replace(" / wk", ""),
                          "Change": change})
        st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")
        st.caption(f"Earlier = before {cutoff.strftime('%d %b')}, later = from {cutoff.strftime('%d %b')} "
                   "(the period's days of play split in half). Higher is better for every skill.")

    keys = [p.key for p in prio if p.key in coaching.TREND_KEYS] or ["scoring"]
    for key in keys:
        series = coaching.daily(key, data)
        if len(series) < 2:
            continue
        suffix = "" if key == "scoring" else "%"
        ui_helpers.daily_trend(series, "when", [("value", coaching.NAMES[key], "you")],
                               f"{coaching.NAMES[key]} per day", suffix=suffix, unit="days",
                               key=f"coach_trend_{key}", height=260, show_range=False,
                               decimals=1, margin=dict(t=48, b=30, l=48, r=56))


def _how_it_works():
    with st.expander("How this works"):
        st.markdown(
            "- **Level** comes from your scoring average. Each skill's target is what's typical at the "
            "**next** level, so targets move up as you improve. Targets are rule-of-thumb coaching "
            "targets, not data.\n"
            "- **Score** = your value ÷ target. On target ≥ 100%, Close 80–99%, Focus under 80%.\n"
            "- **Visits** are scoring turns from match legs (before the double zone) and Score Training.\n"
            "- **Finishing** = checkouts ÷ turns where you could finish. **Doubles** = hits ÷ darts at "
            "doubles from matches, Around the Clock (Doubles) and Doubles Training.\n"
            "- **Recovery** = after a visit of 40 or less, how often the next visit reaches your average.\n"
            "- **Stamina** = last 3 vs first 3 turns of Score Training sessions of 6+ turns.\n"
            "- A skill needs a minimum sample before it's rated, so a few lucky darts don't move it.")
        rows = [{"Level": n, "Scoring average": f"{low}+", "Finishing": f"{t['finishing']}%",
                 "Doubles": f"{t['doubles']}%", "Consistency": f"{t['consistency']}%",
                 "Recovery": f"{t['recovery']}%", "Hours / week": t["volume"]}
                for n, low, t in coaching.LEVELS]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


# ------------------------------------------------------------------ page
def render_coaching_page(player_name, t_func, player_id=None, matches=None, all_matches=None,
                         throws=None):
    try:
        data = load(player_name, player_id, matches if matches is not None else pd.DataFrame(columns=["match_id", "date"]),
                    all_matches, throws if throws is not None else pd.DataFrame())
    except Exception as e:
        st.error(f"Coaching data couldn't be loaded: {e}")
        return
    skills = coaching.assess(data)
    rated = [s for s in skills if s.rated]
    if not rated:
        st.info(f"Not enough games in this period ({ui_helpers.period_label().lower()}) for coaching. "
                "Pick a longer period.")
        return
    level_index = coaching.level(skills[0].value)[0]
    prio = coaching.priorities(skills)

    # 1. Where you stand
    st.markdown("##### Where you stand")
    _level_card(skills)
    on_target = sum(s.status == "On target" for s in rated)
    vol = next(s for s in skills if s.key == "volume")
    c1, c2, c3 = st.columns(3)
    c1.metric("Skills on target", f"{on_target} of {len(rated)}",
              help="Rated skills at or above your next-level target.")
    c2.metric("Top priority", prio[0].name if prio else "None",
              help="Your weakest skill compared with its target.")
    c3.metric("Weekly time", coaching.fmt("volume", vol.value).replace(" / wk", ""),
              help=f"Average time played per week in this period. Target {coaching.fmt('volume', vol.target)}.")

    # 2. Skill profile
    st.markdown("##### Skill profile")
    _profile_chart(skills)
    with st.expander("Skill table"):
        _profile_table(skills)

    # 3. Priorities
    st.markdown("##### Your priorities")
    if prio:
        cols = st.columns(len(prio))
        for i, (col, s) in enumerate(zip(cols, prio), start=1):
            with col:
                _priority_card(i, s, data.doubles)
    else:
        weakest = min(rated, key=lambda s: s.score)
        st.success(f"Every rated skill is on target. Stretch goal: **{weakest.name}** "
                   f"({coaching.fmt(weakest.key, weakest.value)}).", icon=":material/check_circle:")

    # 4. Plan
    st.markdown("##### This week's plan")
    _plan(prio, data, _pace(player_name, player_id))

    # 5. Progress
    st.markdown("##### Progress")
    _progress(data, level_index, prio)

    # 6. How this works
    _how_it_works()
