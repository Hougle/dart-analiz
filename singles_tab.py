"""
Singles Training Analysis Module
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import ui_helpers
from dartcounter_api import only_player


@st.cache_data(ttl=60)
def _load_singles():
    from practice_tab import read_table  # local import: practice_tab imports this module
    return (read_table("SELECT * FROM singles_sessions ORDER BY started_at ASC"),
            read_table("SELECT * FROM singles_targets"))

def render_singles_tab(player_id=None, player_name=None):
    st.subheader("🎯 Singles Training Analysis")

    df_sessions, df_targets = _load_singles()

    # Only the connected player's sessions, and the targets that belong to them.
    df_sessions = only_player(df_sessions, player_id, player_name).copy()
    if not df_targets.empty and "singles_user_id" in df_targets.columns \
            and "singles_user_id" in df_sessions.columns:
        df_targets = df_targets[df_targets["singles_user_id"].isin(df_sessions["singles_user_id"])]

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
        ui_helpers.daily_trend(df_sessions, "datetime", [("hit_rate", "Hit rate", "you")],
                               "Hit Rate per Practice Day", y_title="Hit rate", suffix="%",
                               key="singles_trend", height=320)
        st.caption("Dot = the day's average · bar = that day's lowest to highest session · "
                   "dotted line = overall average.")

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
