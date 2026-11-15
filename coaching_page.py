"""
Coaching & Advanced Analytics Dashboard
"""
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
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

    # Top Metric Cards
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎯 Consistency Index", f"%{consistency_idx:.1f}", delta="Stability Score")
    col2.metric("🧠 Recovery Speed", f"%{bounce_back:.1f}", delta="Post-Pressure Reaction")
    col3.metric("⚡ Fatigue Curve", f"{decay:+.1f}%", delta="Late-Set Performance")
    col4.metric("📊 Overall 3-Dart Avg.", f"{overall_avg:.1f}", delta="Scoring Power")

    st.markdown("---")

    # AI Coaching Observations & Recommendations
    st.subheader("💡 AI Coaching Observations & Recommendations")
    
    insights = []
    if consistency_idx >= 75:
        insights.append("🟢 **Great Consistency:** Your throws are highly stabilized with minimal score fluctuations.")
    else:
        insights.append("🟡 **Volatile Rhythm:** Sharp fluctuations detected in your scores. Focus on routine training to build mechanical consistency.")

    if bounce_back >= 50:
        insights.append("🟢 **Strong Mental Resilience:** Excellent recovery rate after low scoring turns (<=40). You handle pressure well.")
    else:
        insights.append("🔴 **Critical Weakness (Bounce-Back):** Struggling to bounce back in the turn following a bad throw. Mental focus exercises can help.")

    if decay < -5:
        insights.append("⚠️ **Physical / Mental Fatigue:** A performance drop is noticeable towards the end of sets (later turns). Stamina training is recommended.")
    else:
        insights.append("🟢 **Good Stamina:** You maintain your performance throughout the set with minimal fatigue effects.")

    for insight in insights:
        st.info(insight)

    st.markdown("---")

    # Detailed Score Distribution Chart
    st.subheader("📈 Score Distribution and Trend Analysis")
    
    if "started_at" in df_sessions.columns and df_sessions["started_at"].notna().any():
        df_sessions["datetime"] = pd.to_datetime(df_sessions["started_at"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul")
        df_sessions["Date"] = df_sessions["datetime"].dt.strftime("%d.%m.%Y")
    elif "date" in df_sessions.columns:
        df_sessions["Date"] = df_sessions["date"].astype(str)
    else:
        df_sessions["Date"] = [f"Session {i+1}" for i in range(len(df_sessions))]

    fig = px.box(
        df_turns, y=score_col, 
        title="🎛️ Turn Score Distribution (Box Plot)",
        labels={score_col: "Turn Score"}
    )
    fig.update_layout(template="plotly_dark", height=350)
    st.plotly_chart(fig, use_container_width=True)