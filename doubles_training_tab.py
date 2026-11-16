"""Doubles Training sub-tab of Practice: sessions, hit rate trend and per-double accuracy."""
import pandas as pd
import streamlit as st

import ui_helpers
from dartcounter_api import only_player


def render(player_name, player_id=None):
    from doubles_section import _load_doubles_training, _training_doubles, ranked
    from practice_tab import TREND_NOTE, session_table

    sessions, _ = _load_doubles_training()
    sessions = ui_helpers.in_period(only_player(sessions, player_id, player_name))
    if sessions is None or sessions.empty:
        st.info(f"No Doubles Training sessions in this period ({ui_helpers.period_label().lower()}).")
        return

    s = sessions.copy()
    s["datetime"] = ui_helpers.local_time(s["started_at"])
    darts = int(pd.to_numeric(s["darts_thrown"], errors="coerce").fillna(0).sum())
    hits = int(pd.to_numeric(s["darts_hit"], errors="coerce").fillna(0).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sessions", len(s))
    c2.metric("Darts at doubles", darts)
    c3.metric("Hit rate", ui_helpers.pct(hits / darts * 100) if darts else "–",
              help="Darts that landed in the double you were aiming at, divided by darts thrown.")
    c4.metric("Darts per hit", f"{darts / hits:.1f}" if hits else "–",
              help="On average, one hit every this many darts.")

    stats = _training_doubles(player_name, player_id)
    if not stats.empty:
        stats = stats.astype({"hits": float, "attempts": float})
        stats = stats[stats["attempts"] > 0].copy()
        stats["target"] = stats["target"].astype(int)
        stats["value"] = stats["hits"] / stats["attempts"]
        best = ranked(stats, 10)
        if len(best) >= 2:
            top, low = best.iloc[0], best.iloc[-1]
            st.caption(f"Best here: **{top['name']}** ({ui_helpers.pct(top['value'] * 100)}) · "
                       f"toughest: **{low['name']}** ({ui_helpers.pct(low['value'] * 100)}). "
                       "Full ranking is in the Doubles tab.")
        left, right = st.columns(2)
        with left:
            ui_helpers.dartboard_ring(stats, "Hit rate per double", prefix="D", key="dt_ring", min_n=5)
        with right:
            ui_helpers.segment_bars(stats, "Hit rate per double (D1 → D20, Bull)", prefix="D",
                                    key="dt_bars", min_n=5)

    ui_helpers.daily_trend(s, "datetime", [("hit_rate", "Hit rate", "you")],
                           "Hit rate per practice day", y_title="Hit rate", suffix="%", key="dt_trend")
    st.caption(TREND_NOTE)

    st.markdown("##### Sessions")
    session_table(s, {"datetime": "Date", "mode": "Mode", "darts_thrown": "Darts",
                      "darts_hit": "Hits", "hit_rate": "Hit rate", "result": "Result"})
