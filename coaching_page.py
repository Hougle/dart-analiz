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

def render_coaching_page(player_name, t_func, player_id=None):
    st.subheader("🧠 Professional Coaching & Performance Analytics")
    st.markdown(f"**Player:** {player_name} | This panel deeply analyzes your game rhythm, mental recovery speed, and fatigue thresholds.")
    st.markdown("---")

    # Data: same cached loader as the Practice tab, limited to the connected player
    df_sessions, df_turns, _, _ = load_all_practice_data()
    df_sessions = only_player(df_sessions, player_id, player_name)
    if not df_turns.empty and {"session_id", "user_id"}.issubset(df_turns.columns) \
            and {"session_id", "user_id"}.issubset(df_sessions.columns):
        keys = df_sessions[["session_id", "user_id"]].drop_duplicates()
        df_turns = df_turns.merge(keys, on=["session_id", "user_id"], how="inner")

    if df_sessions.empty or df_turns.empty:
        st.warning("Not enough practice data to generate coaching analysis. Try doing some Score Training first!")
        return

    if "score" not in df_turns.columns:
        st.error(f"Score column could not be found. Available columns in practice_turns: {list(df_turns.columns)}")
        return

    score_col = "score"

    # Calculate Metrics
    consistency_idx, bounce_back, decay, overall_avg = calculate_advanced_metrics(df_turns, df_sessions)

    # Top Metric Cards (explanations live in the ⓘ tooltip, not in fake deltas)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎯 Consistency Index", ui_helpers.pct(consistency_idx),
                help="100 − coefficient of variation of turn scores. Higher = steadier scoring.")
    col2.metric("🧠 Recovery Rate", ui_helpers.pct(bounce_back),
                help="After a turn of 40 or less, how often the next turn in the same session "
                     "reaches your average turn score.")
    col3.metric("⚡ Fatigue Curve", f"{decay:+.1f}%",
                help="Average of the last 3 turns vs the first 3 turns of each session.")
    col4.metric("📊 Overall 3-Dart Avg.", f"{overall_avg:.1f}",
                help="Mean of your Score Training session averages.")

    st.markdown("---")

    # Coaching observations, shown with status colour + icon + label
    st.subheader("💡 Coaching Observations & Recommendations")
    if consistency_idx >= 75:
        st.success("**Great Consistency:** Your throws are highly stabilized with minimal score fluctuations.", icon="✅")
    else:
        st.warning("**Volatile Rhythm:** Sharp fluctuations detected in your scores. Focus on routine "
                   "training to build mechanical consistency.", icon="⚠️")
    if bounce_back >= 50:
        st.success("**Strong Recovery:** You often bounce back after low-scoring turns (≤ 40).", icon="✅")
    else:
        st.error("**Weak Bounce-Back:** Struggling to reach your average in the turn after a bad one. "
                 "Practise a reset routine between visits.", icon="🔴")
    if decay < -5:
        st.warning("**Fatigue:** Scores drop towards the end of sessions. Stamina training is recommended.", icon="⚠️")
    else:
        st.success("**Good Stamina:** You keep your level to the end of the session.", icon="✅")

    st.markdown("---")

    # Trends: one small chart per measure (different scales never share an axis)
    st.subheader("📈 Are you improving? Trends per practice day")
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
