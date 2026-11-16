"""
Practice Module - Analyst & Athlete-Centric Performance Analyzer
Score Training & ATC Bottleneck Analytics
"""
import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
import ui_helpers
from singles_tab import render_singles_tab
from dartcounter_api import DB_PATH, _turso_available, turso_query, only_player


def read_table(sql):
    """Run a SELECT on Turso or local SQLite. Returns an empty frame if the table is missing."""
    try:
        if _turso_available():
            cols, rows = turso_query(sql)
            return pd.DataFrame(rows, columns=cols) if cols else pd.DataFrame()
        conn = sqlite3.connect(DB_PATH)
        try:
            return pd.read_sql(sql, conn)
        finally:
            conn.close()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60)
def load_all_practice_data():
    df_p_sessions = read_table("SELECT * FROM practice_sessions ORDER BY started_at ASC")
    df_p_turns = read_table("SELECT * FROM practice_turns")
    df_a_sessions = read_table("SELECT * FROM around_sessions ORDER BY started_at ASC")
    df_a_targets = read_table("SELECT * FROM around_targets")
    return df_p_sessions, df_p_turns, df_a_sessions, df_a_targets


def _turn_col(df):
    for c in ("turn", "turn_index", "round"):
        if c in df.columns:
            return c
    return None


def calculate_score_metrics(df_turns):
    """Std dev, bounce-back rate and fatigue decay, computed per session."""
    if df_turns.empty or "score" not in df_turns.columns:
        return None, None, None

    df = df_turns.copy()
    turn_col = _turn_col(df)
    group_col = "session_id" if "session_id" in df.columns else None
    sort_cols = [c for c in (group_col, turn_col) if c]
    if sort_cols:
        df = df.sort_values(sort_cols)

    std_dev = df["score"].std()
    avg_score = df["score"].mean()

    # Previous turn within the same session only.
    df["prev_score"] = df.groupby(group_col)["score"].shift(1) if group_col else df["score"].shift(1)
    bad_turns = df[df["prev_score"] <= 40]
    if len(bad_turns) > 0:
        bounce_back_rate = (bad_turns["score"] >= avg_score).mean() * 100
    else:
        bounce_back_rate = 100.0

    # Fatigue: first 3 turns vs last 3 turns of each session (sessions of 6+ turns).
    decay_pct = 0.0
    if turn_col:
        last_turn = df.groupby(group_col)[turn_col].transform("max") if group_col else df[turn_col].max()
        long_enough = last_turn >= 6
        first_phase = df[long_enough & (df[turn_col] <= 3)]["score"].mean()
        last_phase = df[long_enough & (df[turn_col] >= last_turn - 2)]["score"].mean()
        if pd.notna(first_phase) and pd.notna(last_phase) and first_phase > 0:
            decay_pct = (last_phase - first_phase) / first_phase * 100

    return std_dev, bounce_back_rate, decay_pct


def render(player_name, db_path, t_func, player_id=None):
    st.subheader(t_func("🎯 Practice Modules"))
    
    sub1, sub2, sub3 = st.tabs([
        t_func("🎯 Score Training"),
        t_func("🔄 Around the Clock"),
        t_func("🎯 Singles Training")
    ])
    
    df_p_sessions, df_p_turns, df_a_sessions, df_a_targets = load_all_practice_data()

    # Only the connected player's own sessions (versus games also store opponents).
    df_p_sessions = only_player(df_p_sessions, player_id, player_name)
    if not df_p_turns.empty and {"session_id", "user_id"}.issubset(df_p_turns.columns) \
            and {"session_id", "user_id"}.issubset(df_p_sessions.columns):
        keys = df_p_sessions[["session_id", "user_id"]].drop_duplicates()
        df_p_turns = df_p_turns.merge(keys, on=["session_id", "user_id"], how="inner")
    df_a_sessions = only_player(df_a_sessions, player_id, player_name)
    
    # ==========================================
    # 1. SCORE TRAINING TAB
    # ==========================================
    with sub1:
        st.subheader("🎯 Score Training - Performance & Rhythm Analysis")
        if df_p_sessions.empty:
            st.info("No recorded Score Training sessions found yet.")
        else:
            df = df_p_sessions.copy()
            if "started_at" in df.columns and df["started_at"].notna().any():
                df["datetime"] = pd.to_datetime(df["started_at"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul")
                df["Date"] = df["datetime"].dt.strftime("%d.%m.%Y")
            else:
                df["Date"] = df["date"].astype(str)

            df["Game_No"] = [f"Game #{i+1}" for i in range(len(df))]

            std_dev, bounce_back, decay = calculate_score_metrics(df_p_turns)
            
            C = ui_helpers.colors()
            col1, col2, col3 = st.columns(3)
            col1.metric("📊 Rhythm Fluctuation (Std Dev)",
                        f"±{std_dev:.1f} pts" if pd.notna(std_dev) else "No Data",
                        help="Standard deviation of turn scores. Lower = steadier; under 25 is stable.")
            col2.metric("🧠 Bounce-Back Rate",
                        ui_helpers.pct(bounce_back) if pd.notna(bounce_back) else "No Data",
                        help="After a turn of 40 or less, how often the next turn (same session) "
                             "reaches your average turn score.")
            col3.metric("⚡ Fatigue Curve (Decay)",
                        f"{decay:+.1f}%" if pd.notna(decay) else "No Data",
                        help="Last 3 turns vs first 3 turns of each session. Negative = you drop off late.")

            st.markdown("---")

            if "datetime" in df.columns:
                ui_helpers.daily_trend(df, "datetime", [("avg_3dart", "3-dart avg", "you")],
                                       "📈 3-Dart Average per Practice Day", y_title="3-dart average",
                                       key="score_trend")
                st.caption("Dot = the day's average · bar = that day's lowest to highest session · "
                           "dotted line = overall average.")

            st.markdown("---")

            if not df_p_turns.empty and "score" in df_p_turns.columns:
                bands = ui_helpers.score_bands(df_p_turns["score"])
                dist_df = bands.value_counts().reindex(ui_helpers.SCORE_BAND_LABELS, fill_value=0).reset_index()
                dist_df.columns = ["Range", "Count"]
                fig_dist = go.Figure(go.Bar(
                    x=dist_df["Range"], y=dist_df["Count"], marker=dict(color=C["alt"], cornerradius=4),
                    text=dist_df["Count"], textposition="outside", textfont=dict(color=C["text"]),
                    hovertemplate="%{x}: %{y} turns<extra></extra>"))
                fig_dist.update_layout(title="🎯 Turn Score Distribution (20-point bands)",
                                       xaxis_title="Score per turn", yaxis_title="Turns")
                ui_helpers.chart(fig_dist, key="score_dist")
                s = pd.to_numeric(df_p_turns["score"], errors="coerce")
                st.caption(f"100+: {int((s >= 100).sum())} · 140+: {int((s >= 140).sum())} · "
                           f"180: {int((s == 180).sum())} · of {int(s.notna().sum())} turns")

            st.markdown("---")

            st.markdown("### 📋 Game Performance Logs")
            table_cols = [c for c in ["date", "training_mode", "total_score", "avg_3dart", "darts_thrown", "rounds"] if c in df.columns]
            display_df = df[table_cols].copy()
            display_df.columns = [col.replace("date", "Date").replace("training_mode", "Mode").replace("total_score", "Total Score").replace("avg_3dart", "3-Dart Avg.").replace("darts_thrown", "Darts Thrown").replace("rounds", "Rounds") for col in display_df.columns]
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ==========================================
    # 2. AROUND THE CLOCK TAB
    # ==========================================
    with sub2:
        st.subheader("🔄 Around the Clock - Bottleneck & Weak Link Analysis")
        if df_a_sessions.empty:
            st.info("No recorded Around the Clock sessions found yet.")
        else:
            df_a = df_a_sessions.copy()
            # Leave out DartBot sessions (already limited to the connected player above).
            if "is_cpu" in df_a.columns:
                df_a = df_a[df_a["is_cpu"].fillna(0).astype(int) == 0]
            if "started_at" in df_a.columns and df_a["started_at"].notna().any():
                df_a["datetime"] = pd.to_datetime(df_a["started_at"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul")
                df_a["Date"] = df_a["datetime"].dt.strftime("%d.%m.%Y")
            else:
                df_a["Date"] = df_a["date"].astype(str)

            atc_modes = ["All", "all", "single", "double", "treble"]
            mode_labels = {"All": "All sessions", "all": "All segments (any ring)",
                           "single": "Singles", "double": "Doubles", "treble": "Trebles"}
            selected_mode = st.selectbox("🎯 Select ATC Mode", atc_modes, index=0,
                                         format_func=lambda m: mode_labels.get(m, m))

            mode_col = "number_segment" if "number_segment" in df_a.columns else ("mode" if "mode" in df_a.columns else None)

            if selected_mode != "All" and mode_col:
                df_a_filtered = df_a[df_a[mode_col].astype(str).str.lower() == selected_mode.lower()].copy()
            else:
                df_a_filtered = df_a.copy()

            if df_a_filtered.empty:
                st.info(f"No training data found in mode '{selected_mode}'.")
            else:
                C = ui_helpers.colors()
                avg_hit = df_a_filtered["hit_rate"].mean() if "hit_rate" in df_a_filtered.columns else 0
                avg_darts = df_a_filtered["darts_thrown"].mean() if "darts_thrown" in df_a_filtered.columns else 0

                c1, c2, c3 = st.columns(3)
                c1.metric("🎯 Average Hit Rate", ui_helpers.pct(avg_hit),
                          help="Darts that hit the current target, divided by darts thrown.")
                c2.metric("🏹 Avg. Darts Spent Per Game", f"{avg_darts:.1f}")
                c3.metric("📅 Sessions", len(df_a_filtered))

                st.markdown("---")

                darts_col = next((c for c in ("darts_needed", "darts_thrown") if c in df_a_targets.columns), None)
                targets = df_a_targets
                # Only targets from the sessions currently shown (mode + player filter).
                if not targets.empty and "atc_user_id" in targets.columns and "atc_user_id" in df_a_filtered.columns:
                    targets = targets[targets["atc_user_id"].isin(df_a_filtered["atc_user_id"])]

                if targets.empty or "target" not in targets.columns or darts_col is None:
                    st.info("No per-target data for these sessions yet, so the segment charts are not available.")
                else:
                    seg = targets.assign(hits=1, attempts=pd.to_numeric(targets[darts_col], errors="coerce"))
                    seg = seg.groupby("target")[["hits", "attempts"]].sum().reset_index()
                    seg["target"] = seg["target"].astype(int)
                    seg["value"] = seg["hits"] / seg["attempts"]
                    prefix = {"double": "D", "treble": "T"}.get(selected_mode, "")

                    rated = seg[seg["attempts"] >= 5]
                    worst = rated.nsmallest(3, "value")
                    if not worst.empty:
                        names = ", ".join(
                            f"**{prefix}{'Bull' if r['target'] == 25 else int(r['target'])}** "
                            f"({r['attempts'] / r['hits']:.1f} darts per hit)" for _, r in worst.iterrows())
                        st.warning(f"⚠️ **Bottleneck:** hardest targets in this selection: {names}")

                    left, right = st.columns(2)
                    with left:
                        ui_helpers.dartboard_ring(seg, "Hit rate per segment", prefix=prefix,
                                                  key=f"atc_ring_{selected_mode}")
                    with right:
                        ui_helpers.segment_bars(seg, "Hit rate per segment (1 → 20, Bull)", prefix=prefix,
                                                key=f"atc_bars_{selected_mode}")

                st.markdown("---")

                if "datetime" in df_a_filtered.columns and "hit_rate" in df_a_filtered.columns:
                    ui_helpers.daily_trend(
                        df_a_filtered, "datetime", [("hit_rate", "Hit rate", "you")],
                        f"📈 Hit Rate per Practice Day ({mode_labels.get(selected_mode, selected_mode)})",
                        y_title="Hit rate", suffix="%", key=f"atc_trend_{selected_mode}")
                    st.caption("Dot = the day's average · bar = that day's lowest to highest session · "
                               "dotted line = overall average.")

                st.markdown("---")

                st.markdown("### 📋 ATC Game History and Performance Details")
                table_cols_a = [c for c in ["date", "mode", "total_score", "darts_thrown", "darts_hit", "hit_rate"] if c in df_a_filtered.columns]
                display_df_a = df_a_filtered[table_cols_a].copy()
                display_df_a.columns = [col.replace("date", "Date").replace("mode", "Mode").replace("total_score", "Score").replace("darts_thrown", "Darts Thrown").replace("darts_hit", "Hits").replace("hit_rate", "Hit Rate (%)") for col in display_df_a.columns]
                st.dataframe(display_df_a, use_container_width=True, hide_index=True)

    # ==========================================
    # 3. SINGLES TRAINING TAB
    # ==========================================
    with sub3:
        render_singles_tab(player_id=player_id, player_name=player_name)