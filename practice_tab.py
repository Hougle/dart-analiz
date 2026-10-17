"""
Practice Modülü ve Alt Sekmeleri (Score Training, Around the Clock, Singles Training)
"""
import streamlit as st
import subprocess
import sys
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


def render(player_name, db_path, t_func):
    st.subheader(t_func("🎯 Practice Modülleri"))
    
    # Practice alt sekmeleri (Sub-tabs)
    sub1, sub2, sub3 = st.tabs([
        t_func("🎯 Score Training"),
        t_func("🔄 Around the Clock"),
        t_func("🎯 Singles Training")
    ])
    
    with sub1:
        st.info("Score Training verileri ve grafikleri yakında burada yer alacak.")
        
    with sub2:
        st.info("Around the Clock verileri ve grafikleri yakında burada yer alacak.")
        
    with sub3:
        render_singles_tab()