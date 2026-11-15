"""
Singles Training Analysis Module
"""
import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
import ui_helpers
from dartcounter_api import DB_PATH, _turso_available, turso_query

def render_singles_tab():
    st.subheader("🎯 Singles Training Analysis")

    if _turso_available():
        s_cols, sessions = turso_query("SELECT * FROM singles_sessions ORDER BY started_at ASC")
        t_cols, targets = turso_query("SELECT * FROM singles_targets")
        df_sessions = pd.DataFrame(sessions, columns=s_cols) if sessions else pd.DataFrame()
        df_targets = pd.DataFrame(targets, columns=t_cols) if targets else pd.DataFrame()
    else:
        conn = sqlite3.connect(DB_PATH)
        df_sessions = pd.read_sql("SELECT * FROM singles_sessions ORDER BY started_at ASC", conn)
        df_targets = pd.read_sql("SELECT * FROM singles_targets", conn)
        conn.close()

    if df_sessions.empty:
        st.info("No recorded Singles Training sessions found yet.")
        return

    # Column Controls & Fallbacks
    if "started_at" in df_sessions.columns:
        df_sessions["datetime"] = pd.to_datetime(df_sessions["started_at"], unit="s", utc=True, errors="coerce").dt.tz_convert("Europe/Istanbul")
        df_sessions["Date_Format"] = df_sessions["datetime"].dt.strftime("%d.%m.%Y %H:%M")
        df_sessions["Date_Display"] = df_sessions["datetime"].dt.strftime("%d.%m.%Y %H:%M")
    elif "date" in df_sessions.columns:
        df_sessions["Date_Format"] = df_sessions["date"].astype(str)
        df_sessions["Date_Display"] = df_sessions["date"].astype(str)
    else:
        df_sessions["Date_Format"] = [f"Session {i+1}" for i in range(len(df_sessions))]
        df_sessions["Date_Display"] = "Unknown"

    if "hit_rate" not in df_sessions.columns:
        if "darts_hit" in df_sessions.columns and "darts_thrown" in df_sessions.columns:
            df_sessions["hit_rate"] = (df_sessions["darts_hit"] / df_sessions["darts_thrown"].replace(0, 1)) * 100
        else:
            df_sessions["hit_rate"] = 0.0

    C = ui_helpers.colors()

    # Summary Metrics
    total_sessions = len(df_sessions)
    avg_hit_rate = df_sessions["hit_rate"].mean() if "hit_rate" in df_sessions.columns else 0
    total_darts = int(df_sessions["darts_thrown"].sum()) if "darts_thrown" in df_sessions.columns else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Sessions", total_sessions)
    col2.metric("Average Hit Rate", ui_helpers.pct(avg_hit_rate),
                help="Darts that hit the called number, divided by darts thrown.")
    col3.metric("Total Darts Thrown", total_darts)

    st.markdown("---")

    # Per-number accuracy: 3 darts are thrown at every target.
    if not df_targets.empty and {"target", "hits"}.issubset(df_targets.columns):
        seg = df_targets.assign(attempts=3)
        seg = seg.groupby("target")[["hits", "attempts"]].sum().reset_index()
        seg["target"] = seg["target"].astype(int)
        seg["value"] = seg["hits"] / seg["attempts"]
        left, right = st.columns(2)
        with left:
            ui_helpers.dartboard_ring(seg, "Hit rate per number", key="singles_ring", min_n=6)
        with right:
            ui_helpers.segment_bars(seg, "Hit rate per number (1 → 20, Bull)", key="singles_bars", min_n=6)
        st.markdown("---")

    # Hit Rate per session on a real time axis
    if "datetime" in df_sessions.columns and df_sessions["datetime"].notna().any():
        sess = df_sessions.sort_values("datetime")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=sess["datetime"], y=sess["hit_rate"], mode="markers+lines", name="Session",
            line=dict(color=C["alt"], width=2), marker=dict(color=C["alt"], size=9),
            hovertemplate="%{x|%d.%m %H:%M}<br>Hit rate: %{y:.1f}%<extra></extra>"))
        fig.update_layout(title="Hit Rate per Session", yaxis=dict(title="Hit rate (%)", ticksuffix="%"),
                          xaxis_title="", showlegend=False)
        ui_helpers.chart(fig, key="singles_trend", height=300)

    st.markdown("### 📋 Past Singles Sessions")
    
    available_cols = []
    col_names_map = {}
    
    if "Date_Display" in df_sessions.columns:
        available_cols.append("Date_Display")
        col_names_map["Date_Display"] = "Date"
    elif "date" in df_sessions.columns:
        available_cols.append("date")
        col_names_map["date"] = "Date"
        
    for col, display_name in [("mode", "Mode"), ("total_score", "Total Score"), ("darts_thrown", "Darts Thrown"), ("darts_hit", "Darts Hit"), ("hit_rate", "Hit Rate (%)")]:
        if col in df_sessions.columns:
            available_cols.append(col)
            col_names_map[col] = display_name

    display_df = df_sessions[available_cols].copy()
    display_df.rename(columns=col_names_map, inplace=True)
    st.dataframe(display_df, use_container_width=True, hide_index=True)
