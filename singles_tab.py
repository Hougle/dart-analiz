"""
Streamlit için Singles Training sekmesi.
"""
import pandas as pd
import plotly.express as px
import streamlit as st
import sqlite3
from dartcounter_api import turso_query, DB_PATH, _turso_available


@st.cache_data(ttl=60)
def load_singles_data():
    if _turso_available():
        _, sessions = turso_query("SELECT * FROM singles_sessions ORDER BY started_at DESC")
        _, targets = turso_query("SELECT * FROM singles_targets")
        
        s_cols = ["singles_user_id", "session_id", "user_id", "date", "started_at", "duration_sec", "mode", "training_mode", "player_name", "result", "total_score", "darts_thrown", "darts_hit", "hit_rate"]
        t_cols = ["singles_user_id", "seq", "target", "hits", "total_score"]
        
        df_sessions = pd.DataFrame(sessions, columns=s_cols) if sessions else pd.DataFrame()
        df_targets = pd.DataFrame(targets, columns=t_cols) if targets else pd.DataFrame()
        return df_sessions, df_targets
    else:
        conn = sqlite3.connect(DB_PATH)
        df_sessions = pd.read_sql("SELECT * FROM singles_sessions ORDER BY started_at DESC", conn)
        df_targets = pd.read_sql("SELECT * FROM singles_targets", conn)
        conn.close()
        return df_sessions, df_targets


def render_singles_tab():
    st.subheader("🎯 Singles Training Analizi")

    df_sessions, df_targets = load_singles_data()

    if df_sessions.empty:
        st.info("Henüz kaydedilmiş Singles Training oturumu bulunmuyor.")
        return

    # Özet Metrikler
    total_sessions = len(df_sessions)
    avg_hit_rate = df_sessions["hit_rate"].mean() if "hit_rate" in df_sessions.columns else 0
    total_darts = df_sessions["darts_thrown"].sum() if "darts_thrown" in df_sessions.columns else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Toplam Oturum", total_sessions)
    col2.metric("Ortalama İsabet Oranı", f"%{avg_hit_rate:.1f}")
    col3.metric("Atılan Toplam Ok", total_darts)

    st.markdown("---")

    # Zaman İçindeki İsabet Oranı Grafiği
    if "date" in df_sessions.columns and not df_sessions.empty:
        df_sessions["datetime"] = pd.to_datetime(df_sessions["date"])
        fig_timeline = px.line(
            df_sessions.sort_values("datetime"),
            x="datetime",
            y="hit_rate",
            markers=True,
            title="Zaman İçinde İsabet Oranı (%)",
            labels={"datetime": "Tarih", "hit_rate": "İsabet Oranı (%)"}
        )
        fig_timeline.update_layout(template="plotly_dark", margin=dict(t=40, b=20, l=20, r=20))
        st.plotly_chart(fig_timeline, use_container_width=True)

    # Hedef Bazlı Başarı Analizi
    if not df_targets.empty and not df_sessions.empty:
        merged = pd.merge(df_targets, df_sessions[["singles_user_id", "date"]], on="singles_user_id")
        target_perf = merged.groupby("target").agg(
            total_hits=("hits", "sum"),
            avg_score=("total_score", "mean")
        ).reset_index()

        fig_targets = px.bar(
            target_perf,
            x="target",
            y="avg_score",
            title="Hedef Numaralarına Göre Ortalama Skor",
            labels={"target": "Hedef", "avg_score": "Ortalama Skor"},
            color="avg_score",
            color_continuous_scale="Viridis"
        )
        fig_targets.update_layout(template="plotly_dark", margin=dict(t=40, b=20, l=20, r=20))
        st.plotly_chart(fig_targets, use_container_width=True)

    # Oturum Listesi Tablosu
    with st.expander("📋 Geçmiş Singles Oturumları Detayı"):
        st.dataframe(df_sessions[["date", "mode", "total_score", "darts_thrown", "darts_hit", "hit_rate"]], use_container_width=True)