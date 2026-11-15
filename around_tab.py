"""
Around the Clock (ATC) Analiz Modülü
"""
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from dartcounter_api import DB_PATH, _turso_available, turso_query

def render_atc_tab():
    st.subheader("🔄 Around the Clock - Darboğaz & Zayıf Halka Analizi")
    
    # Veri Çekme
    if _turso_available():
        _, sessions = turso_query("SELECT * FROM around_sessions ORDER BY started_at ASC")
        _, targets = turso_query("SELECT * FROM around_targets")
        df_a = pd.DataFrame(sessions) if sessions else pd.DataFrame()
        df_targets = pd.DataFrame(targets) if targets else pd.DataFrame()
    else:
        conn = sqlite3.connect(DB_PATH)
        df_a = pd.read_sql("SELECT * FROM around_sessions ORDER BY started_at ASC", conn)
        df_targets = pd.read_sql("SELECT * FROM around_targets", conn)
        conn.close()

    if df_a.empty:
        st.info("Henüz kaydedilmiş Around the Clock oturumu bulunmuyor.")
        return

    # Tarih formatı
    if "started_at" in df_a.columns and df_a["started_at"].notna().any():
        df_a["datetime"] = pd.to_datetime(df_a["started_at"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul")
        df_a["Gun"] = df_a["datetime"].dt.strftime("%d.%m.%Y")
    else:
        df_a["Gun"] = df_a["date"].astype(str)

    # Segment Filtresi (Daha önce düzelttiğimiz number_segment yapısı)
    atc_modes = ["Hepsi", "all", "single", "double", "treble"]
    selected_mode = st.selectbox("🎯 ATC Modu Seçin", atc_modes, index=0, key="atc_mode_select")

    mode_col = "number_segment" if "number_segment" in df_a.columns else "mode"
    if selected_mode != "Hepsi" and mode_col in df_a.columns:
        df_a_filtered = df_a[df_a[mode_col].astype(str).str.lower() == selected_mode.lower()].copy()
    else:
        df_a_filtered = df_a.copy()

    if df_a_filtered.empty:
        st.info(f"Seçilen '{selected_mode}' modunda henüz antrenman verisi bulunmuyor.")
        return

    avg_hit = df_a_filtered["hit_rate"].mean() if "hit_rate" in df_a_filtered.columns else 0
    avg_darts = df_a_filtered["darts_thrown"].mean() if "darts_thrown" in df_a_filtered.columns else 0

    c1, c2 = st.columns(2)
    with c1:
        st.metric("🎯 Ortalama İsabet Oranı", f"%{avg_hit:.1f}")
    with c2:
        st.metric("🏹 Oyun Başı Ort. Harcanan Ok", f"{avg_darts:.1f} Ok")

    st.markdown("---")

    # Grafik ve Trendler
    df_daily_a = df_a_filtered.groupby("Gun", sort=False).agg({"hit_rate": "mean"}).reset_index()
    df_daily_a["hit_rate_round"] = df_daily_a["hit_rate"].round(1)

    fig_daily_hit = px.line(
        df_daily_a, x="Gun", y="hit_rate_round", markers=True,
        title=f"📈 İsabet Oranı (%) Trendi ({selected_mode})",
        labels={"Gun": "", "hit_rate_round": "İsabet (%)"}
    )
    fig_daily_hit.update_traces(line=dict(color="#4ecdc4", width=3), marker=dict(size=8))
    fig_daily_hit.update_layout(template="plotly_dark", height=320, margin=dict(t=40, b=20, l=10, r=10))
    st.plotly_chart(fig_daily_hit, use_container_width=True)

    st.markdown("### 📋 ATC Oyun Geçmişi")
    table_cols_a = [c for c in ["date", mode_col, "total_score", "darts_thrown", "darts_hit", "hit_rate"] if c in df_a_filtered.columns]
    display_df_a = df_a_filtered[table_cols_a].copy()
    st.dataframe(display_df_a, use_container_width=True, hide_index=True)