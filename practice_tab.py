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


def load_practice_data(db_path):
    try:
        conn = sqlite3.connect(db_path)
        sessions = pd.read_sql("SELECT * FROM practice_sessions", conn)
        throws = pd.read_sql("SELECT * FROM practice_throws", conn)
        conn.close()
        return sessions, throws
    except Exception:
        return pd.DataFrame(), pd.DataFrame()


def render(player_name, db_path, t_func):
    st.subheader(t_func("🎯 Practice Modülleri"))
    
    # Practice alt sekmeleri (Sub-tabs)
    sub1, sub2, sub3 = st.tabs([
        t_func("🎯 Score Training"),
        t_func("🔄 Around the Clock"),
        t_func("🎯 Singles Training")
    ])
    
    sessions_df, throws_df = load_practice_data(db_path)
    
    with sub1:
        st.subheader("🎯 Score Training Analizi")
        if sessions_df.empty:
            st.info("Henüz kaydedilmiş Score Training oturumu bulunmuyor.")
        else:
            # Score training özetleri ve grafikleri
            st.dataframe(sessions_df, use_container_width=True)
            
    with sub2:
        st.subheader("🔄 Around the Clock Analizi")
        st.info("Around the Clock modülü için veri tabanı entegrasyonu hazırlanıyor.")
        
    with sub3:
        render_singles_tab()