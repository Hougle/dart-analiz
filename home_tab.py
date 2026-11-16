"""Home: one screen that answers 'how am I doing?'."""
import pandas as pd
import streamlit as st

import ui_helpers
from dartcounter_api import only_player


def _practice_frames(player, player_id):
    """All practice sessions of the player as (kind, local time, headline value, unit) rows."""
    from practice_tab import load_all_practice_data
    from singles_tab import _load_singles
    from doubles_section import _load_doubles_training

    score, _, atc, _ = load_all_practice_data()
    singles, _ = _load_singles()
    doubles, _ = _load_doubles_training()
    atc = only_player(atc, player_id, player)
    if atc is not None and not atc.empty and "is_cpu" in atc.columns:
        atc = atc[atc["is_cpu"].fillna(0).astype(int) == 0]
    rows = []
    for kind, df, col, unit in (("Score Training", score, "avg_3dart", "avg"),
                                ("Around the Clock", atc, "hit_rate", "%"),
                                ("Singles Training", singles, "hit_rate", "%"),
                                ("Doubles Training", doubles, "hit_rate", "%")):
        df = only_player(df, player_id, player) if kind != "Around the Clock" else df
        if df is None or df.empty or "started_at" not in df.columns:
            continue
        rows.append(pd.DataFrame({"kind": kind, "when": ui_helpers.local_time(df["started_at"]),
                                  "value": pd.to_numeric(df.get(col), errors="coerce"), "unit": unit}))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["kind", "when", "value", "unit"])


def _delta(now, before, fmt="{:+.1f}"):
    if now is None or before is None or pd.isna(now) or pd.isna(before) or now == before:
        return None
    return fmt.format(now - before)


def render(matches, player, player_id, efe_throws, last_sync, all_matches=None):
    """matches: the player's finished matches (all time) with date, opponent, result, avg, adjusted_avg.
    all_matches: every match of the player, unfinished ones too (for time played)."""
    import playing_time
    from doubles_section import double_stats, ranked

    practice = _practice_frames(player, player_id)
    m = matches.copy()
    m["when"] = ui_helpers.match_time(m["date"])

    # ---- This week vs last week (always the last 7 days, whatever the period filter says)
    today = pd.Timestamp.now(tz=ui_helpers.TZ).normalize()
    this_start, last_start = today - pd.Timedelta(days=6), today - pd.Timedelta(days=13)

    def window(df, start, end=None):
        mask = df["when"] >= start
        if end is not None:
            mask &= df["when"] < end
        return df[mask]

    m_now, m_before = window(m, this_start), window(m, last_start, this_start)
    p_now, p_before = window(practice, this_start), window(practice, last_start, this_start)
    s_now = p_now[p_now["kind"] == "Score Training"]["value"]
    s_before = p_before[p_before["kind"] == "Score Training"]["value"]
    played = playing_time.sessions(all_matches if all_matches is not None else matches, player, player_id)
    t_now, t_before = window(played, this_start)["sec"].sum() / 60, window(played, last_start, this_start)["sec"].sum() / 60

    st.markdown("##### This week")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Matches", len(m_now), delta=_delta(len(m_now), len(m_before), "{:+d}"),
              help="Last 7 days, compared with the 7 days before.")
    c2.metric("Match average", f"{m_now['avg'].mean():.1f}" if len(m_now) else "–",
              delta=_delta(m_now["avg"].mean() if len(m_now) else None,
                           m_before["avg"].mean() if len(m_before) else None),
              help="Raw 3-dart average of this week's matches vs last week's.")
    c3.metric("Practice sessions", len(p_now), delta=_delta(len(p_now), len(p_before), "{:+d}"),
              help="Score Training, Around the Clock, Singles and Doubles Training together.")
    c4.metric("Practice average", f"{s_now.mean():.1f}" if len(s_now) else "–",
              delta=_delta(s_now.mean() if len(s_now) else None,
                           s_before.mean() if len(s_before) else None),
              help="Score Training 3-dart average this week vs last week.")
    c5.metric("Time played", playing_time.fmt_minutes(t_now),
              delta=(("+" if t_now > t_before else "−") + playing_time.fmt_minutes(abs(t_now - t_before)))
              if round(t_now) != round(t_before) else None,
              help="Matches and practice at their real length, last 7 days vs the 7 days before.")
    if not len(m_now) and not len(p_now):
        last = pd.concat([m["when"], practice["when"]]).max()
        st.caption("Nothing played in the last 7 days"
                   + (f" — last game was {last.strftime('%d %b')}." if pd.notna(last) else "."))

    # ---- Time played per week in the selected period
    playing_time.render(all_matches if all_matches is not None else matches, player, player_id)

    # ---- Doubles snapshot for the selected period
    st.markdown(f"##### Doubles · {ui_helpers.period_label().lower()}")
    r = ranked(double_stats(efe_throws, player, player_id), 20)
    c1, c2, c3 = st.columns(3)
    if len(r) >= 2:
        best, worst = r.iloc[0], r.iloc[-1]
        c1.metric("Best double", best["name"], help=f"{ui_helpers.pct(best['value'] * 100)} · 1 hit in "
                                                    f"{best['per_hit']:.1f} darts (at least 20 darts)")
        c2.metric("Weakest double", worst["name"],
                  help=f"{ui_helpers.pct(worst['value'] * 100)}"
                       + (f" · 1 hit in {worst['per_hit']:.1f} darts" if worst["per_hit"] else ""))
        c3.metric("Next focus", f"50 darts at {worst['name']}",
                  help="Start each practice session with 50 darts at your weakest double. "
                       "The Coaching tab has more.")
    else:
        c1.metric("Best double", "–")
        c2.metric("Weakest double", "–")
        c3.metric("Next focus", "–")
        st.caption("Doubles need at least 20 darts each to be ranked. Pick a longer period or play "
                   "Doubles Training.")

    # ---- One trend: practice average per day in the period (match average if no practice)
    sp = practice[practice["kind"] == "Score Training"]
    start = ui_helpers.period_start()
    if start is not None:
        sp = sp[sp["when"] >= start]
    if not sp.empty:
        ui_helpers.daily_trend(sp, "when", [("value", "3-dart avg", "you")],
                               "Score Training average per day", y_title="3-dart average",
                               key="home_trend", height=300)
    else:
        mp = m if start is None else m[m["when"] >= start]
        if not mp.empty:
            ui_helpers.daily_trend(mp, "when", [("avg", "Match average", "you")],
                                   "Match average per day", y_title="3-dart average", unit="matches",
                                   key="home_trend", height=300)

    # ---- Recent activity
    st.markdown("##### Recent activity")
    recent = pd.concat([
        pd.DataFrame({"when": m["when"], "Game": "Match vs " + m["opponent"].astype(str),
                      "Result": m["result"].map({"won": "Won", "lost": "Lost"}).fillna(""),
                      "Score": m["avg"].map(lambda v: f"{v:.1f} avg")}),
        pd.DataFrame({"when": practice["when"], "Game": practice["kind"], "Result": "",
                      "Score": [f"{v:.1f} avg" if u == "avg" else f"{v:.1f}% hits" if pd.notna(v) else ""
                                for v, u in zip(practice["value"], practice["unit"])]}),
    ]).dropna(subset=["when"]).sort_values("when", ascending=False).head(8)
    recent["when"] = recent["when"].dt.tz_localize(None)
    st.dataframe(recent.rename(columns={"when": "Date"}), hide_index=True, width="stretch",
                 column_config={"Date": ui_helpers.date_column("Date")})
    st.caption(f"Last synced: {last_sync}" if last_sync else "Not synced from the app yet.")
