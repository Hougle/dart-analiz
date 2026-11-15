"""
Score Training Analiz ve Performans Modülü
"""
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from dartcounter_api import DB_PATH, _turso_available, turso_query

def calculate_score_metrics(df_turns):
    if df_turns.empty or "score" not in df_turns.columns:
        return None, None, None, 0.0

    std_dev = df_turns["score"].std()
    mean_score = df_turns["score"].mean()

    # İstikrar Endeksi (Consistency Index) Hesaplama
    if mean_score > 0 and not pd.isna(std_dev):
        cv = (std_dev / mean_score) * 100
        consistency_index = max(0.0, 100.0 - cv)
    else:
        consistency_index = 0.0

    df_turns["prev_score"] = df_turns["score"].shift(1)
    bad_turns = df_turns[df_turns["prev_score"] <= 40]
    
    if len(bad_turns) > 0:
        recovered_turns = bad_turns[bad_turns["score"] >= mean_score]
        bounce_back_rate = (len(recovered_turns) / len(bad_turns)) * 100
    else:
        bounce_back_rate = 100.0

    if "turn_index" in df_turns.columns or "round" in df_turns.columns:
        turn_col = "turn_index" if "turn_index" in df_turns.columns else "round"
        max_turn = df_turns[turn_col].max()
        if max_turn >= 6:
            first_phase = df_turns[df_turns[turn_col] <= 3]["score"].mean()
            last_phase = df_turns[df_turns[turn_col] >= (max_turn - 2)]["score"].mean()
            decay_pct = ((last_phase - first_phase) / first_phase) * 100 if first_phase > 0 else 0
        else:
            decay_pct = 0.0
    else:
        decay_pct = 0.0

    return std_dev, bounce_back_rate, decay_pct, consistency_index

def render_score_training_tab():
    st.subheader("🎯 Score Training - Performans & Ritim Analizi")
    
    # Veri Çekme
    if _turso_available():
        _, sessions = turso_query("SELECT * FROM practice_sessions ORDER BY started_at ASC")
        _, turns = turso_query("SELECT * FROM practice_turns")
        df_p_sessions = pd.DataFrame(sessions) if sessions else pd.DataFrame()
        df_p_turns = pd.DataFrame(turns) if turns else pd.DataFrame()
    else:
        conn = sqlite3.connect(DB_PATH)
        df_p_sessions = pd.read_sql("SELECT * FROM practice_sessions ORDER BY started_at ASC", conn)
        df_p_turns = pd.read_sql("SELECT * FROM practice_turns", conn)
        conn.close()

    if df_p_sessions.empty:
        st.info("Henüz kaydedilmiş Score Training oturumu bulunmuyor.")
        return

    # Tarih formatı
    if "started_at" in df_p_sessions.columns and df_p_sessions["started_at"].notna().any():
        df_p_sessions["datetime"] = pd.to_datetime(df_p_sessions["started_at"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul")
        df_p_sessions["Gun"] = df_p_sessions["datetime"].dt.strftime("%d.%m.%Y")
    else:
        df_p_sessions["Gun"] = df_p_sessions["date"].astype(str)

    # Koçluk Metrikleri Hesaplama
    std_dev, bounce_back, decay, consistency_idx = calculate_score_metrics(df_p_turns)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if std_dev is not None:
            st.metric("📊 Dalgalanma", f"±{std_dev:.1f}", delta="Std Sapma")
        else:
            st.metric("📊 Dalgalanma", "Veri Yok")

    with col2:
        if bounce_back is not None:
            st.metric("🧠 Toparlanma", f"%{bounce_back:.1f}", delta="Bounce-Back")
        else:
            st.metric("🧠 Toparlanma", "Veri Yok")

    with col3:
        if decay is not None:
            st.metric("⚡ Yorulma", f"{decay:+.1f}%", delta="Set Sonu")
        else:
            st.metric("⚡ Yorulma", "Veri Yok")

    with col4:
        st.metric("🎯 İstikrar", f"%{consistency_idx:.1f}", delta="Stabilite Puanı")

    st.markdown("---")

    # Günlük Trend Grafiği
    df_daily = df_p_sessions.groupby("Gun", sort=False).agg({"avg_3dart": "mean"}).reset_index()
    df_daily["avg_3dart_round"] = df_daily["avg_3dart"].round(2)

    fig_daily = px.line(
        df_daily, x="Gun", y="avg_3dart_round", markers=True,
        title="📈 Günlük 3-Ok Skor Trendi & Ritim Çizgisi",
        labels={"Gun": "", "avg_3dart_round": "3-Ok Ort."}
    )
    fig_daily.update_traces(line=dict(color="#4ecdc4", width=3), marker=dict(size=8))
    fig_daily.update_layout(template="plotly_dark", height=320, margin=dict(t=40, b=20, l=10, r=10))
    st.plotly_chart(fig_daily, use_container_width=True)

    st.markdown("### 📋 Oyun Geçmişi")
    table_cols = [c for c in ["date", "training_mode", "total_score", "avg_3dart", "darts_thrown", "rounds"] if c in df_p_sessions.columns]
    display_df = df_p_sessions[table_cols].copy()
    st.dataframe(display_df, use_container_width=True, hide_index=True)