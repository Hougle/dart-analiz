"""
Coaching & Advanced Analytics Dashboard
"""
import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
import ui_helpers
from dartcounter_api import DB_PATH, _turso_available, turso_query
from practice_tab import calculate_score_metrics

def get_practice_turns_df():
    if _turso_available():
        cols, rows = turso_query("SELECT * FROM practice_turns")
        return pd.DataFrame(rows, columns=cols) if rows and cols else pd.DataFrame()
    else:
        try:
            conn = sqlite3.connect(DB_PATH)
            df = pd.read_sql("SELECT * FROM practice_turns", conn)
            conn.close()
            return df
        except Exception:
            return pd.DataFrame()

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

def render_coaching_page(player_name, t_func):
    st.title("🧠 Professional Coaching & Performance Analytics")
    st.markdown(f"**Player:** {player_name} | This panel deeply analyzes your game rhythm, mental recovery speed, and fatigue thresholds.")
    st.markdown("---")

    # Data Fetching
    if _turso_available():
        cols, sessions = turso_query("SELECT * FROM practice_sessions ORDER BY started_at ASC")
        df_sessions = pd.DataFrame(sessions, columns=cols) if sessions else pd.DataFrame()
    else:
        try:
            conn = sqlite3.connect(DB_PATH)
            df_sessions = pd.read_sql("SELECT * FROM practice_sessions ORDER BY started_at ASC", conn)
            conn.close()
        except Exception:
            df_sessions = pd.DataFrame()

    df_turns = get_practice_turns_df()

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
    st.subheader("📈 Are you improving? Per-session trends")
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

    # Recovery is too noisy per 10-turn session, so it is pooled over the last 5 sessions.
    recov = []
    sids = sess["session_id"].tolist()
    for i in range(len(sids)):
        window = turns[turns["session_id"].isin(sids[max(0, i - 4): i + 1])]
        recov.append(calculate_score_metrics(window)[1])
    sess["recovery"] = recov

    C = ui_helpers.colors()
    panels = [
        ("avg", "Turn average", "", "{:.1f}"),
        ("consistency", "Consistency index", "%", "{:.0f}%"),
        ("recovery", "Recovery rate (last 5 sessions)", "%", "{:.0f}%"),
    ]
    cols = st.columns(3)
    for (col, title, suffix, fmt), slot in zip(panels, cols):
        with slot:
            fig = go.Figure()
            if col != "recovery":
                fig.add_trace(go.Scatter(x=sess["when"], y=sess[col], mode="markers",
                                         marker=dict(color=C["alt"], size=7, opacity=0.55), showlegend=False,
                                         hovertemplate="%{x|%d.%m %H:%M}: %{y:.1f}" + suffix + "<extra></extra>"))
                trend = ui_helpers.rolling_trend(sess["when"], sess[col])
            else:
                trend = sess[col].to_numpy()
            fig.add_trace(go.Scatter(x=sess["when"], y=trend, mode="lines", showlegend=False,
                                     line=dict(color=C["you"], width=2.5),
                                     hovertemplate="%{x|%d.%m}: %{y:.1f}" + suffix + "<extra></extra>"))
            last = trend[-1] if len(trend) else None
            fig.update_layout(title=f"{title}<br><sup>latest: {fmt.format(last) if last is not None else '–'}</sup>",
                              yaxis=dict(ticksuffix=suffix), xaxis=dict(tickformat="%d.%m"),
                              margin=dict(t=64, b=30, l=40, r=10))
            ui_helpers.chart(fig, key=f"coach_{col}", height=260)
    st.caption("Dots = single sessions · orange line = 5-session rolling average.")
