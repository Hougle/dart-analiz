"""
Practice Module - Analyst & Athlete-Centric Performance Analyzer
Score Training & ATC Bottleneck Analytics
"""
import streamlit as st
import subprocess
import sys
from pathlib import Path
import pandas as pd
import sqlite3
import plotly.express as px
from singles_tab import render_singles_tab
from dartcounter_api import DB_PATH, _turso_available, turso_query


def sidebar_button(token_ok, t_func):
    if token_ok:
        if st.button(t_func("🎯 FETCH PRACTICE"), use_container_width=True):
            if not Path("practice_import.py").exists():
                st.error("Error: `practice_import.py` not found in the project folder.")
                return
            with st.spinner(t_func("Fetching practice data...")):
                try:
                    result = subprocess.run(
                        [sys.executable, "practice_import.py"],
                        capture_output=True, text=True, timeout=60
                    )
                    if result.returncode == 0:
                        st.success(t_func("✅ Update completed!"))
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(t_func("❌ An error occurred"))
                        if result.stderr:
                            st.code(result.stderr[-1500:])
                except Exception as e:
                    st.error(f"Error: {e}")


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


def render(player_name, db_path, t_func):
    st.subheader(t_func("🎯 Practice Modules"))
    
    sub1, sub2, sub3 = st.tabs([
        t_func("🎯 Score Training"),
        t_func("🔄 Around the Clock"),
        t_func("🎯 Singles Training")
    ])
    
    df_p_sessions, df_p_turns, df_a_sessions, df_a_targets = load_all_practice_data()
    
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
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if std_dev is not None:
                    st.metric(
                        "📊 Rhythm Fluctuation (Std Dev)",
                        f"±{std_dev:.1f} Pts",
                        delta="Low = Stable" if std_dev < 25 else "High Fluctuation",
                        delta_color="normal" if std_dev < 25 else "inverse"
                    )
                else:
                    st.metric("📊 Rhythm Fluctuation", "No Data")

            with col2:
                if bounce_back is not None:
                    st.metric(
                        "🧠 Bounce-Back Rate",
                        f"%{bounce_back:.1f}",
                        delta="Post-Pressure Reaction"
                    )
                else:
                    st.metric("🧠 Bounce-Back Rate", "No Data")

            with col3:
                if decay is not None:
                    st.metric(
                        "⚡ Fatigue Curve (Decay)",
                        f"{decay:+.1f}%",
                        delta="Late-Set Performance",
                        delta_color="normal" if decay >= 0 else "inverse"
                    )
                else:
                    st.metric("⚡ Fatigue Curve", "No Data")

            st.markdown("---")

            df_daily = df.groupby("Date", sort=False).agg({"avg_3dart": "mean"}).reset_index()
            df_daily["avg_3dart_round"] = df_daily["avg_3dart"].round(2)

            fig_daily = px.line(
                df_daily,
                x="Date",
                y="avg_3dart_round",
                markers=True,
                title="📈 Daily 3-Dart Score Trend & Rhythm Line",
                labels={"Date": "", "avg_3dart_round": "3-Dart Avg."}
            )
            fig_daily.update_traces(
                line=dict(color="#4ecdc4", width=3),
                marker=dict(size=8, color="#4ecdc4", line=dict(width=2, color="#ffffff")),
                fill="tozeroy",
                fillcolor="rgba(78, 205, 196, 0.08)",
                hovertemplate="<b>Date: %{x}</b><br>Average: %{y}<extra></extra>"
            )
            
            min_y = max(0, df_daily["avg_3dart_round"].min() - 5)
            max_y = df_daily["avg_3dart_round"].max() + 5

            fig_daily.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=320,
                margin=dict(t=40, b=20, l=10, r=10),
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", range=[min_y, max_y], title="3-Dart Avg.")
            )
            st.plotly_chart(fig_daily, use_container_width=True)

            st.markdown("---")

            if not df_p_turns.empty and "score" in df_p_turns.columns:
                bins = [-1, 20, 40, 60, 80, 100, 140, 180]
                labels = ['0-20 (Miss)', '21-40 (Weak)', '41-60 (Standard)', '61-80 (Good)', '81-100 (Very Good)', '101-140 (High)', '141-180 (Maximum)']
                
                df_turns = df_p_turns.copy()
                df_turns['Score_Range'] = pd.cut(df_turns['score'], bins=bins, labels=labels)
                dist_df = df_turns['Score_Range'].value_counts().reindex(labels).reset_index()
                dist_df.columns = ['Range', 'Count']

                fig_dist = px.bar(
                    dist_df,
                    x='Range',
                    y='Count',
                    title="🎯 Throw Score Distribution (Error & Success Profile Analysis)",
                    labels={'Range': 'Score Range', 'Count': 'Throw Count'},
                    text='Count'
                )
                fig_dist.update_traces(
                    marker_color="#ffe66d",
                    marker_line_color="#fff2b2",
                    marker_line_width=1,
                    opacity=0.9,
                    textposition="outside",
                    hovertemplate="<b>Range: %{x}</b><br>Count: %{y}<extra></extra>"
                )
                fig_dist.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=320,
                    margin=dict(t=40, b=20, l=10, r=10),
                    xaxis=dict(showgrid=False, title="Score Range"),
                    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="Count")
                )
                st.plotly_chart(fig_dist, use_container_width=True)

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
            # Leave out DartBot / opponent sessions so stats are only the player's own.
            if "player_name" in df_a.columns:
                df_a = df_a[df_a["player_name"] == player_name]
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
                avg_hit = df_a_filtered["hit_rate"].mean() if "hit_rate" in df_a_filtered.columns else 0
                avg_darts = df_a_filtered["darts_thrown"].mean() if "darts_thrown" in df_a_filtered.columns else 0

                c1, c2 = st.columns(2)
                with c1:
                    st.metric("🎯 Average Hit Rate", f"%{avg_hit:.1f}")
                with c2:
                    st.metric("🏹 Avg. Darts Spent Per Game", f"{avg_darts:.1f} Darts")

                st.markdown("---")

                darts_col = next((c for c in ("darts_needed", "darts_thrown") if c in df_a_targets.columns), None)
                targets = df_a_targets
                # Only targets from the sessions currently shown (mode + player filter).
                if not targets.empty and "atc_user_id" in targets.columns and "atc_user_id" in df_a_filtered.columns:
                    targets = targets[targets["atc_user_id"].isin(df_a_filtered["atc_user_id"])]

                if targets.empty or "target" not in targets.columns or darts_col is None:
                    st.info("No per-target data for these sessions yet, so the bottleneck chart is not available.")
                    target_stats = None
                else:
                    target_stats = targets.groupby("target")[darts_col].mean().reset_index()
                    target_stats.columns = ["Target_Segment", "Avg_Darts"]
                    target_stats["Target_Segment"] = target_stats["Target_Segment"].astype(str).replace({"25": "Bull"})

                if target_stats is not None:
                    def sort_key(val):
                        s = str(val).strip()
                        if s.isdigit():
                            return (0, int(s))
                        return (1, s)

                    target_stats["sort_col"] = target_stats["Target_Segment"].apply(sort_key)
                    target_stats = target_stats.sort_values(by="sort_col").drop(columns=["sort_col"])

                    worst_3 = target_stats.sort_values(by="Avg_Darts", ascending=False).head(3)
                    worst_list = ", ".join([f"**Segment {row['Target_Segment']}** ({row['Avg_Darts']:.1f} darts)" for _, row in worst_3.iterrows()])

                    st.warning(f"⚠️ **Bottleneck Detection:** Top 3 targets requiring the most darts: {worst_list}")

                    fig_targets = px.bar(
                        target_stats,
                        x="Target_Segment",
                        y="Avg_Darts",
                        title="🎯 Avg. Darts Spent Per Segment",
                        labels={"Target_Segment": "Target Segment", "Avg_Darts": "Avg. Darts"},
                        text="Avg_Darts"
                    )
                    fig_targets.update_traces(
                        marker_color="#ff6b35",
                        texttemplate="%{y:.1f}",
                        textposition="outside"
                    )
                    fig_targets.update_layout(
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=320,
                        margin=dict(t=40, b=20, l=10, r=10),
                        xaxis=dict(showgrid=False, type='category'),
                        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)")
                    )
                    st.plotly_chart(fig_targets, use_container_width=True)

                st.markdown("---")

                df_daily_a = df_a_filtered.groupby("Date", sort=False).agg({"hit_rate": "mean"}).reset_index()
                df_daily_a["hit_rate_round"] = df_daily_a["hit_rate"].round(1)

                fig_daily_hit = px.line(
                    df_daily_a,
                    x="Date",
                    y="hit_rate_round",
                    markers=True,
                    title=f"📈 Hit Rate (%) Trend ({selected_mode})",
                    labels={"Date": "", "hit_rate_round": "Hit (%)"}
                )
                fig_daily_hit.update_traces(
                    line=dict(color="#4ecdc4", width=3),
                    marker=dict(size=8, color="#4ecdc4", line=dict(width=2, color="#ffffff")),
                    fill="tozeroy",
                    fillcolor="rgba(78, 205, 196, 0.08)",
                    hovertemplate="<b>Date: %{x}</b><br>Hit Rate: %{y}%<extra></extra>"
                )

                min_hit = max(0, df_daily_a["hit_rate_round"].min() - 5)
                max_hit = min(100, df_daily_a["hit_rate_round"].max() + 5)

                fig_daily_hit.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=320,
                    margin=dict(t=40, b=20, l=10, r=10),
                    xaxis=dict(showgrid=False, title=""),
                    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", range=[min_hit, max_hit], title="Hit (%)")
                )
                st.plotly_chart(fig_daily_hit, use_container_width=True)

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
        render_singles_tab()