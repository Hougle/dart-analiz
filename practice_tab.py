"""
Practice Modülü ve Alt Sekmeleri (Score Training, Around the Clock, Singles Training)
Tamamen kullanıcı isteklerine göre yeniden tasarlandı.
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
        p_cols, p_sessions = turso_query("SELECT * FROM practice_sessions ORDER BY started_at ASC")
        p_turn_cols, p_turns = turso_query("SELECT * FROM practice_turns")
        a_cols, a_sessions = turso_query("SELECT * FROM around_sessions ORDER BY started_at ASC")
        a_target_cols, a_targets = turso_query("SELECT * FROM around_targets")

        df_p_sessions = pd.DataFrame(p_sessions, columns=p_cols) if p_sessions and p_cols else pd.DataFrame()
        df_p_turns = pd.DataFrame(p_turns, columns=p_turn_cols) if p_turns and p_turn_cols else pd.DataFrame()
        df_a_sessions = pd.DataFrame(a_sessions, columns=a_cols) if a_sessions and a_cols else pd.DataFrame()
        df_a_targets = pd.DataFrame(a_targets, columns=a_target_cols) if a_targets and a_target_cols else pd.DataFrame()
    else:
        conn = sqlite3.connect(DB_PATH)
        df_p_sessions = pd.read_sql("SELECT * FROM practice_sessions ORDER BY started_at ASC", conn)
        df_p_turns = pd.read_sql("SELECT * FROM practice_turns", conn)
        df_a_sessions = pd.read_sql("SELECT * FROM around_sessions ORDER BY started_at ASC", conn)
        df_a_targets = pd.read_sql("SELECT * FROM around_targets", conn)
        conn.close()

    return df_p_sessions, df_p_turns, df_a_sessions, df_a_targets


def render(player_name, db_path, t_func):
    st.subheader(t_func("🎯 Practice Modülleri"))
    
    sub1, sub2, sub3 = st.tabs([
        t_func("🎯 Score Training"),
        t_func("🔄 Around the Clock"),
        t_func("🎯 Singles Training")
    ])
    
    df_p_sessions, df_p_turns, df_a_sessions, df_a_targets = load_all_practice_data()
    
    # ==========================================
    # 1. SCORE TRAINING SEKMESİ
    # ==========================================
    with sub1:
        st.subheader("🎯 Score Training Detaylı Analiz")
        if df_p_sessions.empty:
            st.info("Henüz kaydedilmiş Score Training oturumu bulunmuyor.")
        else:
            df = df_p_sessions.copy()
            if "started_at" in df.columns and df["started_at"].notna().any():
                df["datetime"] = pd.to_datetime(df["started_at"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul")
                df["Tarih_Format"] = df["datetime"].dt.strftime("%d.%m.%Y %H:%M")
                df["Gun"] = df["datetime"].dt.strftime("%Y-%m-%d")
            else:
                df["Tarih_Format"] = df["date"].astype(str)
                df["Gun"] = df["date"].astype(str)

            # 1. Grafik: Oyun bazlı toplam skor grafiği
            fig_game_score = px.bar(
                df,
                x=df.index,
                y="total_score",
                title="🎮 Oyun Bazlı Toplam Skorlar",
                labels={"x": "Oyun Sırası / İndeks", "total_score": "Toplam Skor"},
                text="total_score"
            )
            fig_game_score.update_traces(marker_color="#ff6b35", textposition="outside")
            fig_game_score.update_layout(template="plotly_dark", margin=dict(t=40, b=20, l=20, r=20))
            st.plotly_chart(fig_game_score, use_container_width=True)

            st.markdown("---")

            # 2. Grafik: Gün bazlı ortalama skoru (Günlük gruplama)
            df_daily = df.groupby("Gun").agg({"avg_3dart": "mean", "total_score": "mean"}).reset_index()
            fig_daily = px.line(
                df_daily,
                x="Gun",
                y="avg_3dart",
                markers=True,
                title="📅 Gün Bazlı Ortalama 3-Ok Skoru Trendi",
                labels={"Gun": "Tarih (Gün)", "avg_3dart": "Günlük Ortalama (3-Ok)"}
            )
            fig_daily.update_traces(line_color="#4ecdc4", marker=dict(size=10))
            fig_daily.update_layout(template="plotly_dark", margin=dict(t=40, b=20, l=20, r=20))
            st.plotly_chart(fig_daily, use_container_width=True)

            st.markdown("---")

            # 3. Grafik: Atılan skorların aralıklı sayısı (Dart Psikolojisi Aralıkları)
            if not df_p_turns.empty and "score" in df_p_turns.columns:
                bins = [-1, 20, 40, 60, 80, 100, 140, 180]
                labels = ['0-20 (Kaçak/Alt)', '21-40 (Klasik/Zayıf)', '41-60 (Standart)', '61-80 (İyi)', '81-100 (Çok İyi)', '101-140 (Yüksek)', '141-180 (Maximum/T19-T20)']
                
                df_turns = df_p_turns.copy()
                df_turns['Skor_Araligi'] = pd.cut(df_turns['score'], bins=bins, labels=labels)
                dist_df = df_turns['Skor_Araligi'].value_counts().reindex(labels).reset_index()
                dist_df.columns = ['Aralık', 'Adet']

                fig_dist = px.bar(
                    dist_df,
                    x='Aralık',
                    y='Adet',
                    title="🎯 Atış Puanı Aralık Dağılımı (Dart Psikolojisi Analizi)",
                    labels={'Aralık': 'Skor Aralığı', 'Adet': 'Atış Sıklığı (Frekans)'},
                    text='Adet'
                )
                fig_dist.update_traces(marker_color="#ffe66d", textposition="outside")
                fig_dist.update_layout(template="plotly_dark", margin=dict(t=40, b=20, l=20, r=20))
                st.plotly_chart(fig_dist, use_container_width=True)
            else:
                st.info("Atış turu (turns) verisi bulunamadığı için aralık dağılımı oluşturulamadı.")

            st.markdown("---")

            # 4. Tablo: Oyunların avg'ı ve total scoreları
            st.markdown("### 📋 Oyun Detayları (Ortalama & Toplam Skor)")
            table_cols = [c for c in ["date", "training_mode", "total_score", "avg_3dart", "darts_thrown", "rounds"] if c in df.columns]
            display_df = df[table_cols].copy()
            display_df.columns = [col.replace("date", "Tarih").replace("training_mode", "Mod").replace("total_score", "Toplam Skor").replace("avg_3dart", "3-Ok Ort.").replace("darts_thrown", "Ok Sayısı").replace("rounds", "Tur") for col in display_df.columns]
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ==========================================
    # 2. AROUND THE CLOCK SEKMESİ
    # ==========================================
    with sub2:
        st.subheader("🔄 Around the Clock (ATC) Detaylı Analiz")
        if df_a_sessions.empty:
            st.info("Henüz kaydedilmiş Around the Clock oturumu bulunmuyor.")
        else:
            df_a = df_a_sessions.copy()
            if "started_at" in df_a.columns and df_a["started_at"].notna().any():
                df_a["datetime"] = pd.to_datetime(df_a["started_at"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul")
                df_a["Tarih_Format"] = df_a["datetime"].dt.strftime("%d.%m.%Y %H:%M")
                df_a["Gun"] = df_a["datetime"].dt.strftime("%Y-%m-%d")
            else:
                df_a["Tarih_Format"] = df_a["date"].astype(str)
                df_a["Gun"] = df_a["date"].astype(str)

            # 1. Grafik: Oyun bazlı atılan ok sayısı
            fig_game_darts = px.bar(
                df_a,
                x=df_a.index,
                y="darts_thrown",
                title="🎯 Oyun Bazlı Atılan Toplam Ok Sayısı (Düşük = İyi)",
                labels={"x": "Oyun Sırası / İndeks", "darts_thrown": "Atılan Ok Sayısı"},
                text="darts_thrown"
            )
            fig_game_darts.update_traces(marker_color="#4ecdc4", textposition="outside")
            fig_game_darts.update_layout(template="plotly_dark", margin=dict(t=40, b=20, l=20, r=20))
            st.plotly_chart(fig_game_darts, use_container_width=True)

            st.markdown("---")

            # 2. Grafik: Gün bazlı ortalama isabet oranı (%) trendi
            df_daily_a = df_a.groupby("Gun").agg({"hit_rate": "mean", "darts_thrown": "mean"}).reset_index()
            fig_daily_hit = px.line(
                df_daily_a,
                x="Gun",
                y="hit_rate",
                markers=True,
                title="📈 Gün Bazlı Ortalama İsabet Oranı (%) Trendi",
                labels={"Gun": "Tarih (Gün)", "hit_rate": "Ortalama İsabet Oranı (%)"}
            )
            fig_daily_hit.update_traces(line_color="#ff6b35", marker=dict(size=10))
            fig_daily_hit.update_layout(template="plotly_dark", margin=dict(t=40, b=20, l=20, r=20))
            st.plotly_chart(fig_daily_hit, use_container_width=True)

            st.markdown("---")

            # 3. Grafik: Süre ve Verimlilik Dağılımı
            if "duration_sec" in df_a.columns and df_a["duration_sec"].notna().any():
                fig_duration = px.scatter(
                    df_a,
                    x="darts_thrown",
                    y="duration_sec",
                    color="hit_rate",
                    size="hit_rate",
                    title="⏱️ Ok Sayısı vs Süre & İsabet İlişkisi (Hız & Verimlilik)",
                    labels={"darts_thrown": "Atılan Ok", "duration_sec": "Süre (Saniye)", "hit_rate": "İsabet Oranı (%)"},
                    color_continuous_scale="Viridis"
                )
                fig_duration.update_layout(template="plotly_dark", margin=dict(t=40, b=20, l=20, r=20))
                st.plotly_chart(fig_duration, use_container_width=True)

            st.markdown("---")

            # 4. Tablo: Oyun Geçmişi
            st.markdown("### 📋 ATC Oyun Geçmişi ve Performans Detayları")
            table_cols_a = [c for c in ["date", "mode", "total_score", "darts_thrown", "darts_hit", "hit_rate", "duration_sec"] if c in df_a.columns]
            display_df_a = df_a[table_cols_a].copy()
            display_df_a.columns = [col.replace("date", "Tarih").replace("mode", "Mod").replace("total_score", "Skor").replace("darts_thrown", "Atılan Ok").replace("darts_hit", "İsabet").replace("hit_rate", "İsabet Oranı (%)").replace("duration_sec", "Süre (sn)") for col in display_df_a.columns]
            st.dataframe(display_df_a, use_container_width=True, hide_index=True)

    # ==========================================
    # 3. SINGLES TRAINING SEKMESİ
    # ==========================================
    with sub3:
        render_singles_tab()