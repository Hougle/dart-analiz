"""
Singles Training Analysis Module
"""
import streamlit as st
import pandas as pd
import ui_helpers
from dartcounter_api import only_player


@st.cache_data(ttl=60)
def _load_singles():
    from practice_tab import read_table  # local import: practice_tab imports this module
    return (read_table("SELECT * FROM singles_sessions ORDER BY started_at ASC"),
            read_table("SELECT * FROM singles_targets"))


def render_singles_tab(player_id=None, player_name=None):
    from practice_tab import TREND_NOTE, session_table

    df_sessions, df_targets = _load_singles()

    # Only the connected player's sessions in the period, and the targets that belong to them.
    df_sessions = ui_helpers.in_period(only_player(df_sessions, player_id, player_name)).copy()
    if not df_targets.empty and "singles_user_id" in df_targets.columns \
            and "singles_user_id" in df_sessions.columns:
        df_targets = df_targets[df_targets["singles_user_id"].isin(df_sessions["singles_user_id"])]

    if df_sessions.empty:
        st.info(f"No Singles Training sessions in this period ({ui_helpers.period_label().lower()}).")
        return

    if "started_at" in df_sessions.columns:
        df_sessions["datetime"] = ui_helpers.local_time(df_sessions["started_at"])
    if "hit_rate" not in df_sessions.columns:
        if {"darts_hit", "darts_thrown"}.issubset(df_sessions.columns):
            df_sessions["hit_rate"] = df_sessions["darts_hit"] / df_sessions["darts_thrown"].replace(0, 1) * 100
        else:
            df_sessions["hit_rate"] = 0.0

    col1, col2, col3 = st.columns(3)
    col1.metric("Sessions", len(df_sessions))
    col2.metric("Hit rate", ui_helpers.pct(df_sessions["hit_rate"].mean()),
                help="Darts that hit the called number, divided by darts thrown.")
    col3.metric("Darts thrown",
                int(df_sessions["darts_thrown"].sum()) if "darts_thrown" in df_sessions.columns else 0)

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

    if "datetime" in df_sessions.columns and df_sessions["datetime"].notna().any():
        ui_helpers.daily_trend(df_sessions, "datetime", [("hit_rate", "Hit rate", "you")],
                               "Hit rate per practice day", y_title="Hit rate", suffix="%",
                               key="singles_trend", height=320)
        st.caption(TREND_NOTE)

    st.markdown("##### Sessions")
    session_table(df_sessions, {"datetime": "Date", "mode": "Mode", "total_score": "Score",
                                "darts_thrown": "Darts", "darts_hit": "Hits", "hit_rate": "Hit rate"})
