"""
Coaching & Advanced Analytics Dashboard
"""
import streamlit as st
import pandas as pd
import ui_helpers
from practice_tab import calculate_score_metrics, load_all_practice_data
from dartcounter_api import only_player

def calculate_advanced_metrics(df_turns, df_sessions):
    if df_turns.empty:
        return 0.0, 100.0, 0.0, 0.0

    if "score" not in df_turns.columns:
        return 0.0, 100.0, 0.0, 0.0

    mean_score = df_turns["score"].mean()

    # Same per-session bounce-back / fatigue logic as the Practice tab.
    std_dev, bounce_back_rate, decay_pct = calculate_score_metrics(df_turns)

    # Consistency Index
    if mean_score > 0 and not pd.isna(std_dev):
        cv = (std_dev / mean_score) * 100
        consistency_index = max(0.0, 100.0 - cv)
    else:
        consistency_index = 0.0

    overall_avg = df_sessions["avg_3dart"].mean() if "avg_3dart" in df_sessions.columns and not df_sessions.empty else mean_score

    return consistency_index, bounce_back_rate, decay_pct, overall_avg

def _observations(consistency_idx, bounce_back, decay, best_double, worst_double):
    """Strengths and focus areas. Each focus carries a concrete drill; gap = how far below target."""
    strengths, focus = [], []
    if consistency_idx >= 75:
        strengths.append(("Steady scoring", f"Consistency index {consistency_idx:.0f}%: your visits stay close "
                                            "to your average."))
    else:
        focus.append(((75 - consistency_idx) / 75, "Steadier scoring",
                      f"Consistency index {consistency_idx:.0f}% (target 75%).",
                      "3 × 10 visits at T20. Count how many land within 20 points of your average "
                      "and try to beat that count next session."))
    if bounce_back >= 50:
        strengths.append(("Strong recovery", f"After a visit under 40 you reach your average again "
                                             f"{bounce_back:.0f}% of the time."))
    else:
        focus.append(((50 - bounce_back) / 50, "Bouncing back after a bad visit",
                      f"After a visit under 40 you reach your average {bounce_back:.0f}% of the time (target 50%).",
                      "After every visit under 40: step off, take one breath, reset your stance. "
                      "Practise it in Score Training until it's automatic."))
    if decay >= -5:
        strengths.append(("Good stamina", "You keep your level to the end of a session "
                                          f"({decay:+.1f}% last 3 vs first 3 turns)."))
    else:
        focus.append(((-5 - decay) / 20, "Holding your level late in a session",
                      f"Your last 3 turns are {abs(decay):.1f}% below your first 3.",
                      "Add 5 extra visits to the end of each Score Training session and "
                      "track only those."))
    if best_double is not None:
        strengths.append((f"{best_double['name']} is your banker",
                          f"{ui_helpers.pct(best_double['value'] * 100)} — 1 hit in "
                          f"{best_double['per_hit']:.1f} darts. Leave yourself "
                          f"{'50 (Bull)' if best_double['target'] == 25 else int(best_double['target']) * 2} "
                          "when you can."))
    if worst_double is not None and worst_double["per_hit"]:
        focus.append((0.3, f"{worst_double['name']} costs you darts",
                      f"1 hit in {worst_double['per_hit']:.1f} darts "
                      f"({ui_helpers.pct(worst_double['value'] * 100)}).",
                      f"50 darts at {worst_double['name']} at the start of each practice session, "
                      "counting hits. Aim for one more hit each week."))
    focus.sort(key=lambda f: f[0], reverse=True)
    return strengths, focus


def render_coaching_page(player_name, t_func, player_id=None, efe_throws=None):
    # Data: same cached loader as the Practice tab, limited to the connected player and the period
    df_sessions, df_turns, _, _ = load_all_practice_data()
    df_sessions = ui_helpers.in_period(only_player(df_sessions, player_id, player_name))
    if not df_turns.empty and {"session_id", "user_id"}.issubset(df_turns.columns) \
            and {"session_id", "user_id"}.issubset(df_sessions.columns):
        keys = df_sessions[["session_id", "user_id"]].drop_duplicates()
        df_turns = df_turns.merge(keys, on=["session_id", "user_id"], how="inner")

    if df_sessions.empty or df_turns.empty or "score" not in df_turns.columns:
        st.info(f"Not enough Score Training data in this period ({ui_helpers.period_label().lower()}) "
                "for coaching. Pick a longer period or play a Score Training session.")
        return

    consistency_idx, bounce_back, decay, overall_avg = calculate_advanced_metrics(df_turns, df_sessions)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Consistency", ui_helpers.pct(consistency_idx, 0),
                help="100 − coefficient of variation of turn scores. Higher = steadier scoring.")
    col2.metric("Recovery", ui_helpers.pct(bounce_back, 0),
                help="After a turn of 40 or less, how often the next turn in the same session "
                     "reaches your average turn score.")
    col3.metric("Fatigue", f"{decay:+.1f}%",
                help="Average of the last 3 turns vs the first 3 turns of each session.")
    col4.metric("Practice avg", f"{overall_avg:.1f}",
                help="Mean of your Score Training session averages.")

    best_double = worst_double = None
    if efe_throws is not None:
        from doubles_section import double_stats, ranked
        r = ranked(double_stats(efe_throws, player_name, player_id), 20)
        if len(r) >= 2:
            best_double, worst_double = r.iloc[0], r.iloc[-1]
    strengths, focus = _observations(consistency_idx, bounce_back, decay, best_double, worst_double)

    left, right = st.columns(2)
    with left:
        if strengths:
            title, text = strengths[0]
            st.success(f"**Strength — {title}**  \n{text}", icon="💪")
    with right:
        if focus:
            _, title, text, drill = focus[0]
            st.info(f"**Focus — {title}**  \n{text}  \n**Drill:** {drill}", icon="🎯")
        else:
            st.success("**No weak spot stands out.** Keep your current routine.", icon="✅")
    rest = strengths[1:] + [f[1:] for f in focus[1:]]
    if rest:
        with st.expander(f"All observations ({len(rest)} more)"):
            for item in strengths[1:]:
                st.markdown(f"💪 **{item[0]}** — {item[1]}")
            for _, title, text, drill in focus[1:]:
                st.markdown(f"🎯 **{title}** — {text}  \n*Drill:* {drill}")

    # Trends: one small chart per measure (different scales never share an axis)
    st.subheader("Are you improving?")
    turns = df_turns.copy()
    turns["score"] = pd.to_numeric(turns["score"], errors="coerce")
    if "session_id" not in turns.columns or "session_id" not in df_sessions.columns:
        st.info("Session ids are missing, so per-session trends can't be drawn.")
        return

    rows = []
    for sid, g in turns.groupby("session_id"):
        std, bb, _ = calculate_score_metrics(g)
        mean = g["score"].mean()
        ci = max(0.0, 100 - std / mean * 100) if mean and pd.notna(std) else None
        rows.append({"session_id": sid, "avg": mean, "consistency": ci,
                     "bad": int((g.sort_values("turn")["score"].shift(1) <= 40).sum()) if "turn" in g else 0})
    per = pd.DataFrame(rows)
    sess = df_sessions[["session_id", "started_at"]].merge(per, on="session_id", how="inner")
    sess["when"] = pd.to_datetime(sess["started_at"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul")
    sess = sess.sort_values("when")

    # Recovery is too noisy per 10-turn session, so it is pooled over all turns of the day.
    sess["day"] = sess["when"].dt.date
    day_of = dict(zip(sess["session_id"], sess["day"]))
    pooled = {day: calculate_score_metrics(turns[turns["session_id"].map(day_of) == day])[1]
              for day in sess["day"].unique()}
    sess["recovery"] = sess["day"].map(pooled)

    panels = [
        ("avg", "Turn average", "", 1, True),
        ("consistency", "Consistency index", "%", 0, True),
        ("recovery", "Recovery rate", "%", 0, False),
    ]
    # Stacked full-width (not 3 columns) so dates and labels stay legible; same x range for all.
    for col, title, suffix, dec, rng in panels:
        ui_helpers.daily_trend(sess, "when", [(col, title, "you")], title, suffix=suffix,
                               key=f"coach_{col}", height=240, decimals=dec, show_range=rng,
                               margin=dict(t=40, b=30, l=48, r=56))
    st.caption("Dot = the day's value · bar = that day's lowest to highest session · "
               "dotted line = overall average. Recovery is pooled over all turns of the day.")
