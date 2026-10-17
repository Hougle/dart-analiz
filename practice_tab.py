"""
Practice Modülü ve Alt Sekmeleri (Score Training, Around the Clock, Singles Training)
Görsel hataları, Y-eksen ölçekleri ve hover formatları düzeltilmiş sürüm.
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
                df["Tarih_Format"] = df["datetime"].dt.strftime("%d.%m.%Y")
                df["Gun"] = df["datetime"].dt.strftime("%d.%m.%Y")
            else:
                df["Tarih_Format"] = df["date"].astype(str)
                df["Gun"] = df["date"].astype(str)

            df["Oyun_No"] = [f"Oyun #{i+1}" for i in range(len(df))]

            # 1. GRAFİK: Oyun bazlı toplam skor grafiği (Sıkıştırılmış Yükseklik & Temiz Hover)
            fig_game_score = px.bar(
                df,
                x="Oyun_No",
                y="total_score",
                title="🎮 Oyun Bazlı Toplam Skorlar",
                labels={"Oyun_No": "", "total_score": "Toplam Skor"},
                text="total_score"
            )
            fig_game_score.update_traces(
                marker_color="#ff6b35",
                marker_line_color="#ffa580",
                marker_line_width=1,
                opacity=0.9,
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Skor: %{y}<extra></extra>"
            )
            fig_game_score.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=340,
                margin=dict(t=40, b=20, l=10, r=10),
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="Skor")
            )
            st.plotly_chart(fig_game_score, use_container_width=True)

            st.markdown("---")

            # 2. GRAFİK: Gün bazlı ortalama (Dinamik Y-Ekseni Ölçeği & Zarif Trend)
            df_daily = df.groupby("Gun", sort=False).agg({"avg_3dart": "mean"}).reset_index()
            df_daily["avg_3dart_round"] = df_daily["avg_3dart"].round(2)

            fig_daily = px.line(
                df_daily,
                x="Gun",
                y="avg_3dart_round",
                markers=True,
                title="📅 Gün Bazlı Ortalama 3-Ok Skoru Trendi",
                labels={"Gun": "", "avg_3dart_round": "3-Ok Ort."}
            )
            fig_daily.update_traces(
                line=dict(color="#4ecdc4", width=3),
                marker=dict(size=8, color="#4ecdc4", line=dict(width=2, color="#ffffff")),
                fill="tozeroy",
                fillcolor="rgba(78, 205, 196, 0.08)",
                hovertemplate="<b>Tarih: %{x}</b><br>Ortalama: %{y}<extra></extra>"
            )
            
            # Y eksenini 0'a zorlamayarak trend dalgalanmasını net gösterme
            min_y = max(0, df_daily["avg_3dart_round"].min() - 5)
            max_y = df_daily["avg_3dart_round"].max() + 5

            fig_daily.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=340,
                margin=dict(t=40, b=20, l=10, r=10),
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", range=[min_y, max_y], title="3-Ok Ort.")
            )
            st.plotly_chart(fig_daily, use_container_width=True)

            st.markdown("---")

            # 3. GRAFİK: Atış Puanı Aralık Dağılımı
            if not df_p_turns.empty and "score" in df_p_turns.columns:
                bins = [-1, 20, 40, 60, 80, 100, 140, 180]
                labels = ['0-20', '21-40', '41-60', '61-80', '81-100', '101-140', '141-180']
                
                df_turns = df_p_turns.copy()
                df_turns['Skor_Araligi'] = pd.cut(df_turns['score'], bins=bins, labels=labels)
                dist_df = df_turns['Skor_Araligi'].value_counts().reindex(labels).reset_index()
                dist_df.columns = ['Aralık', 'Adet']

                fig_dist = px.bar(
                    dist_df,
                    x='Aralık',
                    y='Adet',
                    title="🎯 Atış Puanı Aralık Dağılımı (Dart Psikolojisi Analizi)",
                    labels={'Aralık': 'Skor Aralığı', 'Adet': 'Atış Sıklığı'},
                    text='Adet'
                )
                fig_dist.update_traces(
                    marker_color="#ffe66d",
                    marker_line_color="#fff2b2",
                    marker_line_width=1,
                    opacity=0.9,
                    textposition="outside",
                    hovertemplate="<b>Aralık: %{x}</b><br>Atış Adedi: %{y}<extra></extra>"
                )
                fig_dist.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=340,
                    margin=dict(t=40, b=20, l=10, r=10),
                    xaxis=dict(showgrid=False, title="Skor Aralığı"),
                    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="Adet")
                )
                st.plotly_chart(fig_dist, use_container_width=True)
            else:
                st.info("Atış turu (turns) verisi bulunamadığı için aralık dağılımı oluşturulamadı.")

            st.markdown("---")

            # 4. TABLO: Oyun Detayları
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
                df_a["Tarih_Format"] = df_a["datetime"].dt.strftime("%d.%m.%Y")
                df_a["Gun"] = df_a["datetime"].dt.strftime("%d.%m.%Y")
            else:
                df_a["Tarih_Format"] = df_a["date"].astype(str)
                df_a["Gun"] = df_a["date"].astype(str)

            df_a["Oyun_No"] = [f"Oyun #{i+1}" for i in range(len(df_a))]

            mode_col = "mode" if "mode" in df_a.columns else (df_a.columns[1] if len(df_a.columns) > 1 else None)
            
            if mode_col:
                available_modes = ["Tümü"] + list(df_a[mode_col].dropna().unique())
                selected_mode = st.selectbox("🎯 ATC Modu Seçin", available_modes, index=0)
                
                if selected_mode != "Tümü":
                    df_a_filtered = df_a[df_a[mode_col] == selected_mode].copy()
                else:
                    df_a_filtered = df_a.copy()
            else:
                df_a_filtered = df_a.copy()

            if df_a_filtered.empty:
                st.info(f"Seçilen '{selected_mode}' modunda henüz oturum bulunmuyor.")
            else:
                st.markdown("---")

                # 1. Grafik: Oyun bazlı atılan ok sayısı
                fig_game_darts = px.bar(
                    df_a_filtered,
                    x="Oyun_No",
                    y="darts_thrown",
                    title=f"🎯 Oyun Bazlı Atılan Toplam Ok Sayısı ({selected_mode})",
                    labels={"Oyun_No": "", "darts_thrown": "Atılan Ok"},
                    text="darts_thrown"
                )
                fig_game_darts.update_traces(
                    marker_color="#4ecdc4",
                    marker_line_color="#8cedc5",
                    marker_line_width=1,
                    opacity=0.9,
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>Ok Sayısı: %{y}<extra></extra>"
                )
                fig_game_darts.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=340,
                    margin=dict(t=40, b=20, l=10, r=10),
                    xaxis=dict(showgrid=False, title=""),
                    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="Ok Sayısı")
                )
                st.plotly_chart(fig_game_darts, use_container_width=True)

                st.markdown("---")

                # 2. Grafik: Gün bazlı isabet oranı (%)
                df_daily_a = df_a_filtered.groupby("Gun", sort=False).agg({"hit_rate": "mean"}).reset_index()
                df_daily_a["hit_rate_round"] = df_daily_a["hit_rate"].round(1)

                fig_daily_hit = px.line(
                    df_daily_a,
                    x="Gun",
                    y="hit_rate_round",
                    markers=True,
                    title=f"📈 Gün Bazlı Ortalama İsabet Oranı (%) Trendi ({selected_mode})",
                    labels={"Gun": "", "hit_rate_round": "İsabet (%)"}
                )
                fig_daily_hit.update_traces(
                    line=dict(color="#ff6b35", width=3),
                    marker=dict(size=8, color="#ff6b35", line=dict(width=2, color="#ffffff")),
                    fill="tozeroy",
                    fillcolor="rgba(255, 107, 53, 0.08)",
                    hovertemplate="<b>Tarih: %{x}</b><br>İsabet: %{y}%<extra></extra>"
                )

                min_hit = max(0, df_daily_a["hit_rate_round"].min() - 5)
                max_hit = min(100, df_daily_a["hit_rate_round"].max() + 5)

                fig_daily_hit.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=340,
                    margin=dict(t=40, b=20, l=10, r=10),
                    xaxis=dict(showgrid=False, title=""),
                    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", range=[min_hit, max_hit], title="İsabet (%)")
                )
                st.plotly_chart(fig_daily_hit, use_container_width=True)

                st.markdown("---")

                # 3. Tablo
                st.markdown("### 📋 ATC Oyun Geçmişi ve Performans Detayları")
                table_cols_a = [c for c in ["date", "mode", "total_score", "darts_thrown", "darts_hit", "hit_rate"] if c in df_a_filtered.columns]
                display_df_a = df_a_filtered[table_cols_a].copy()
                display_df_a.columns = [col.replace("date", "Tarih").replace("mode", "Mod").replace("total_score", "Skor").replace("darts_thrown", "Atılan Ok").replace("darts_hit", "İsabet").replace("hit_rate", "İsabet Oranı (%)") for col in display_df_a.columns]
                st.dataframe(display_df_a, use_container_width=True, hide_index=True)

    # ==========================================
    # 3. SINGLES TRAINING SEKMESİ
    # ==========================================
    with sub3:
        render_singles_tab()