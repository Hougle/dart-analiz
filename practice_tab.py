"""
Practice Modülü ve Alt Sekmeleri (Score Training, Around the Clock, Singles Training)
"""
import streamlit as st
import subprocess
import sys
import pandas as pd
import sqlite3
import plotly.express as px
from singles_tab import render_singles_tab
from dartcounter_api import DB_PATH, _turso_available, turso_query


def sidebar_button(token_ok, t_func):
    if token_ok:
        if st.button(t_func("🎯 PRACTICE ÇEK"), use_container_width=True):
            with st.spinner(t_func("Practice çekiliyor...")):
                try:
                    result = subprocess.run(
                        [sys.executable, "practice_import.py"],
                        capture_output=True, text=True, timeout=60
                    )
                    if result.returncode == 0:
                        st.success(t_func("✅ Güncelleme tamamlandı!"))
                        st.rerun()
                    else:
                        st.error(t_func("❌ Hata oluştu"))
                except Exception as e:
                    st.error(f"Hata: {e}")


@st.cache_data(ttl=60)
def load_all_practice_data():
    if _turso_available():
        _, p_sessions = turso_query("SELECT * FROM practice_sessions ORDER BY date ASC")
        _, p_turns = turso_query("SELECT * FROM practice_turns")
        _, a_sessions = turso_query("SELECT * FROM around_sessions ORDER BY date ASC")
        _, a_targets = turso_query("SELECT * FROM around_targets")

        df_p_sessions = pd.DataFrame(p_sessions) if p_sessions else pd.DataFrame()
        df_p_turns = pd.DataFrame(p_turns) if p_turns else pd.DataFrame()
        df_a_sessions = pd.DataFrame(a_sessions) if a_sessions else pd.DataFrame()
        df_a_targets = pd.DataFrame(a_targets) if a_targets else pd.DataFrame()
    else:
        conn = sqlite3.connect(DB_PATH)
        df_p_sessions = pd.read_sql("SELECT * FROM practice_sessions ORDER BY date ASC", conn)
        df_p_turns = pd.read_sql("SELECT * FROM practice_turns", conn)
        df_a_sessions = pd.read_sql("SELECT * FROM around_sessions ORDER BY date ASC", conn)
        df_a_targets = pd.read_sql("SELECT * FROM around_targets", conn)
        conn.close()

    return df_p_sessions, df_p_turns, df_a_sessions, df_a_targets


def render(player_name, db_path, t_func):
    st.subheader(t_func("🎯 Practice Modülleri"))
    
    # Practice alt sekmeleri (Sub-tabs)
    sub1, sub2, sub3 = st.tabs([
        t_func("🎯 Score Training"),
        t_func("🔄 Around the Clock"),
        t_func("🎯 Singles Training")
    ])
    
    df_p_sessions, df_p_turns, df_a_sessions, df_a_targets = load_all_practice_data()
    
    # ==========================================
    # 1. SCORE TRAINING SUB-TAB
    # ==========================================
    with sub1:
        st.subheader("🎯 Score Training Analizi")
        if df_p_sessions.empty:
            st.info("Henüz kaydedilmiş Score Training oturumu bulunmuyor.")
        else:
            # Metrik Kartları
            total_sessions = len(df_p_sessions)
            total_score = df_p_sessions["total_score"].sum() if "total_score" in df_p_sessions.columns else 0
            avg_score = df_p_sessions["total_score"].mean() if "total_score" in df_p_sessions.columns else 0
            total_darts = df_p_sessions["darts_thrown"].sum() if "darts_thrown" in df_p_sessions.columns else 0
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Toplam Oturum", total_sessions)
            c2.metric("Ortalama Skor", f"{avg_score:.1f}")
            c3.metric("Toplam Skor", f"{total_score:,}")
            c4.metric("Atılan Toplam Ok", f"{total_darts:,}")

            st.markdown("---")

            # Skor Gelişim Grafiği
            df_chart = df_p_sessions.copy()
            if "started_at" in df_chart.columns and df_chart["started_at"].notna().any():
                df_chart["datetime"] = pd.to_datetime(df_chart["started_at"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul")
                df_chart["Tarih_Format"] = df_chart["datetime"].dt.strftime("%d.%m.%Y %H:%M")
            elif "date" in df_chart.columns:
                df_chart["Tarih_Format"] = df_chart["date"].astype(str)
            else:
                df_chart["Tarih_Format"] = df_chart.index.astype(str)

            fig_score = px.line(
                df_chart,
                x="Tarih_Format",
                y="total_score" if "total_score" in df_chart.columns else df_chart.columns[0],
                markers=True,
                title="Zaman İçinde Oturum Skorları",
                labels={"Tarih_Format": "Tarih / Saat", "total_score": "Toplam Skor"}
            )
            fig_score.update_traces(line_color="#ff6b35", marker=dict(size=8))
            fig_score.update_layout(template="plotly_dark", margin=dict(t=40, b=20, l=20, r=20))
            st.plotly_chart(fig_score, use_container_width=True)

            # Atış Puan Dağılımı (Tur verisi varsa)
            if not df_p_turns.empty and "score" in df_p_turns.columns:
                fig_hist = px.histogram(
                    df_p_turns,
                    x="score",
                    nbins=20,
                    title="Score Training Atış Puanı Dağılımı",
                    labels={"score": "Puan", "count": "Frekans"},
                    color_discrete_sequence=["#4ecdc4"]
                )
                fig_hist.update_layout(template="plotly_dark", margin=dict(t=40, b=20, l=20, r=20))
                st.plotly_chart(fig_hist, use_container_width=True)

            with st.expander("📋 Detaylı Score Training Geçmişi"):
                st.dataframe(df_p_sessions, use_container_width=True, hide_index=True)

    # ==========================================
    # 2. AROUND THE CLOCK SUB-TAB
    # ==========================================
    with sub2:
        st.subheader("🔄 Around the Clock Analizi")
        if df_a_sessions.empty:
            st.info("Henüz kaydedilmiş Around the Clock oturumu bulunmuyor.")
        else:
            total_a = len(df_a_sessions)
            avg_duration = df_a_sessions["duration_sec"].mean() if "duration_sec" in df_a_sessions.columns else 0
            total_a_darts = df_a_sessions["darts_thrown"].sum() if "darts_thrown" in df_a_sessions.columns else 0

            ac1, ac2, ac3 = st.columns(3)
            ac1.metric("Toplam Oturum", total_a)
            ac2.metric("Ortalama Süre", f"{avg_duration:.0f} sn")
            ac3.metric("Atılan Toplam Ok", f"{total_a_darts:,}")

            st.markdown("---")

            # ATC Performans Grafiği (Atılan ok sayısı / zaman)
            df_a_chart = df_a_sessions.copy()
            if "started_at" in df_a_chart.columns and df_a_chart["started_at"].notna().any():
                df_a_chart["datetime"] = pd.to_datetime(df_a_chart["started_at"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul")
                df_a_chart["Tarih_Format"] = df_a_chart["datetime"].dt.strftime("%d.%m.%Y %H:%M")
            elif "date" in df_a_chart.columns:
                df_a_chart["Tarih_Format"] = df_a_chart["date"].astype(str)
            else:
                df_a_chart["Tarih_Format"] = df_a_chart.index.astype(str)

            y_col = "darts_thrown" if "darts_thrown" in df_a_chart.columns else df_a_chart.columns[0]
            fig_ac = px.line(
                df_a_chart,
                x="Tarih_Format",
                y=y_col,
                markers=True,
                title="ATC Oturumlarında Atılan Ok Sayısı (Az Olması Daha İyi)",
                labels={"Tarih_Format": "Tarih / Saat", y_col: "Ok Sayısı"}
            )
            fig_ac.update_traces(line_color="#4ecdc4", marker=dict(size=8))
            fig_ac.update_layout(template="plotly_dark", margin=dict(t=40, b=20, l=20, r=20))
            st.plotly_chart(fig_ac, use_container_width=True)

            with st.expander("📋 Detaylı Around the Clock Geçmişi"):
                st.dataframe(df_a_sessions, use_container_width=True, hide_index=True)

    # ==========================================
    # 3. SINGLES TRAINING SUB-TAB
    # ==========================================
    with sub3:
        render_singles_tab()