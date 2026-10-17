"""
Singles Training Analiz Modülü (Practice Alt Sekmesi İçin)
"""
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st
from dartcounter_api import DB_PATH, _turso_available, turso_query


@st.cache_data(ttl=60)
def load_singles_data():
    if _turso_available():
        _, sessions = turso_query("SELECT * FROM singles_sessions ORDER BY started_at ASC")
        _, targets = turso_query("SELECT * FROM singles_targets")

        s_cols = [
            "singles_user_id", "session_id", "user_id", "date", "started_at",
            "duration_sec", "mode", "training_mode", "player_name", "result",
            "total_score", "darts_thrown", "darts_hit", "hit_rate"
        ]
        t_cols = ["singles_user_id", "seq", "target", "hits", "total_score"]

        df_sessions = pd.DataFrame(sessions, columns=s_cols) if sessions else pd.DataFrame()
        df_targets = pd.DataFrame(targets, columns=t_cols) if targets else pd.DataFrame()
    else:
        conn = sqlite3.connect(DB_PATH)
        df_sessions = pd.read_sql("SELECT * FROM singles_sessions ORDER BY started_at ASC", conn)
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

    # Düzeltilmiş Zaman İçinde İsabet Oranı Grafiği
    if not df_sessions.empty:
        df_chart = df_sessions.copy()
        if "started_at" in df_chart.columns and df_chart["started_at"].notna().any():
            df_chart["datetime"] = pd.to_datetime(df_chart["started_at"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul")
            df_chart["Tarih_Format"] = df_chart["datetime"].dt.strftime("%d.%m.%Y %H:%M")
        else:
            df_chart["Tarih_Format"] = df_chart["date"].astype(str)

        fig_timeline = px.line(
            df_chart,
            x="Tarih_Format",
            y="hit_rate",
            markers=True,
            title="Zaman İçinde İsabet Oranı (%)",
            labels={"Tarih_Format": "Tarih / Saat", "hit_rate": "İsabet Oranı (%)"}
        )
        fig_timeline.update_traces(line_color="#ff6b35", marker=dict(size=8))
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
            color_continuous_scale="Oranges"
        )
        fig_targets.update_layout(template="plotly_dark", margin=dict(t=40, b=20, l=20, r=20))
        st.plotly_chart(fig_targets, use_container_width=True)

    # Geçmiş Oturumlar
    with st.expander("📋 Geçmiş Singles Oturumları Detayı"):
        display_df = df_sessions[["date", "mode", "total_score", "darts_thrown", "darts_hit", "hit_rate"]].copy()
        display_df.columns = ["Tarih", "Mod", "Toplam Skor", "Ok Sayısı", "İsabet Sayısı", "İsabet Oranı (%)"]
        st.dataframe(display_df, use_container_width=True)