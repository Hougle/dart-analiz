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
def load_practice_data():
    if _turso_available():
        _, sessions = turso_query("SELECT * FROM practice_sessions ORDER BY date DESC")
        _, turns = turso_query("SELECT * FROM practice_turns")
        
        df_sessions = pd.DataFrame(sessions) if sessions else pd.DataFrame()
        df_turns = pd.DataFrame(turns) if turns else pd.DataFrame()
        return df_sessions, df_turns
    else:
        conn = sqlite3.connect(DB_PATH)
        df_sessions = pd.read_sql("SELECT * FROM practice_sessions ORDER BY date DESC", conn)
        df_turns = pd.read_sql("SELECT * FROM practice_turns", conn)
        conn.close()
        return df_sessions, df_turns


def render(player_name, db_path, t_func):
    st.subheader(t_func("🎯 Practice Modülleri"))
    
    # Practice alt sekmeleri (Sub-tabs)
    sub1, sub2, sub3 = st.tabs([
        t_func("🎯 Score Training"),
        t_func("🔄 Around the Clock"),
        t_func("🎯 Singles Training")
    ])
    
    sessions_df, throws_df = load_practice_data()
    
    with sub1:
        st.subheader("🎯 Score Training Analizi")
        if sessions_df.empty:
            st.info("Henüz kaydedilmiş Score Training oturumu bulunmuyor.")
        else:
            # Özet metrikler
            total_sessions = len(sessions_df)
            avg_score = sessions_df["total_score"].mean() if "total_score" in sessions_df.columns else 0
            
            c1, c2 = st.columns(2)
            c1.metric("Toplam Oturum", total_sessions)
            c2.metric("Ortalama Skor", f"{avg_score:.1f}")
            
            st.markdown("---")
            
            # Oturum Listesi Tablosu
            st.dataframe(sessions_df, use_container_width=True, hide_index=True)
            
    with sub2:
        st.subheader("🔄 Around the Clock Analizi")
        st.info("Around the Clock modülü için veri tabanı entegrasyonu hazırlanıyor.")
        
    with sub3:
        render_singles_tab()