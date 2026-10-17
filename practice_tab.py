"""
Practice Modülü - Analist & Sporcu Odaklı Performans Analizörü
Score Training: Istikrar, Yorulma Egrisi (Round Decay) ve Bounce-back Analizi
Around the Clock: Bottleneck (Zayif Halka) & Segment Analizi
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


def calculate_score_metrics(df_turns):
    """Sporcu & Analist Odaklı Metrik Hesaplamaları"""
    if df_turns.empty or "score" not in df_turns.columns:
        return None, None, None

    # 1. Istikrar (Standart Sapma)
    std_dev = df_turns["score"].std()

    # 2. Bounce-back Rate (Kotu atis sonrasi toparlanma)
    df_turns["prev_score"] = df_turns["score"].shift(1)
    bad_turns = df_turns[df_turns["prev_score"] <= 40]
    
    if len(bad_turns) > 0:
        avg_score = df_turns["score"].mean()
        recovered_turns = bad_turns[bad_turns["score"] >= avg_score]
        bounce_back_rate = (len(recovered_turns) / len(bad_turns)) * 100
    else:
        bounce_back_rate = 100.0

    # 3. Yorulma Egrisi (Round Decay Analysis)
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

    return std_dev, bounce_back_rate, decay_pct


def render(player_name, db_path, t_func):
    st.subheader(t_func("🎯 Practice Modülleri"))
    
    sub1, sub2, sub3 = st.tabs([
        t_func("🎯 Score Training"),
        t_func("🔄 Around the Clock"),
        t_func("🎯 Singles Training")
    ])
    
    df_p_sessions, df_p_turns, df_a_sessions, df_a_targets = load_all_practice_data()
    
    # ==========================================
    # 1. SCORE TRAINING SEKMESİ (PERFORMANCE ENGINE)
    # ==========================================
    with sub1:
        st.subheader("🎯 Score Training - Performans & Ritim Analizi")
        if df_p_sessions.empty:
            st.info("Henüz kaydedilmiş Score Training oturumu bulunmuyor.")
        else:
            df = df_p_sessions.copy()
            if "started_at" in df.columns and df["started_at"].notna().any():
                df["datetime"] = pd.to_datetime(df["started_at"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul")
                df["Gun"] = df["datetime"].dt.strftime("%d.%m.%Y")
            else:
                df["Gun"] = df["date"].astype(str)

            df["Oyun_No"] = [f"Oyun #{i+1}" for i in range(len(df))]

            # Analist KPI Kartları
            std_dev, bounce_back, decay = calculate_score_metrics(df_p_turns)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if std_dev is not None:
                    st.metric(
                        "📊 Ritim Dalgalanması (Std Sapma)",
                        f"±{std_dev:.1f} Puan",
                        delta="Düşük = İstikrarlı" if std_dev < 25 else "Yüksek Dalgalanma",
                        delta_color="normal" if std_dev < 25 else "inverse"
                    )
                else:
                    st.metric("📊 Ritim Dalgalanması", "Veri Yok")

            with col2:
                if bounce_back is not None:
                    st.metric(
                        "🧠 Bounce-Back (Toparlanma Hızı)",
                        f"%{bounce_back:.1f}",
                        delta="Baskı Sonrası Reaksiyon"
                    )
                else:
                    st.metric("🧠 Bounce-Back Rate", "Veri Yok")

            with col3:
                if decay is not None:
                    st.metric(
                        "⚡ Yorulma Eğrisi (Decay)",
                        f"{decay:+.1f}%",
                        delta="Set Sonu Performansı",
                        delta_color="normal" if decay >= 0 else "inverse"
                    )
                else:
                    st.metric("⚡ Yorulma Eğrisi", "Veri Yok")

            st.markdown("---")

            # 1. Grafik: Gün bazlı ortalama (Dinamik Y-Ekseni Ölçeği)
            df_daily = df.groupby("Gun", sort=False).agg({"avg_3dart": "mean"}).reset_index()
            df_daily["avg_3dart_round"] = df_daily["avg_3dart"].round(2)

            fig_daily = px.line(
                df_daily,
                x="Gun",
                y="avg_3dart_round",
                markers=True,
                title="📈 Günlük 3-Ok Skor Trendi & Ritim Çizgisi",
                labels={"Gun": "", "avg_3dart_round": "3-Ok Ort."}
            )
            fig_daily.update_traces(
                line=dict(color="#4ecdc4", width=3),
                marker=dict(size=8, color="#4ecdc4", line=dict(width=2, color="#ffffff")),
                fill="tozeroy",
                fillcolor="rgba(78, 205, 196, 0.08)",
                hovertemplate="<b>Tarih: %{x}</b><br>Ortalama: %{y}<extra></extra>"
            )
            
            min_y = max(0, df_daily["avg_3dart_round"].min() - 5)
            max_y = df_daily["avg_3dart_round"].max() + 5

            fig_daily.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=320,
                margin=dict(t=40, b=20, l=10, r=10),
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", range=[min_y, max_y], title="3-Ok Ort.")
            )
            st.plotly_chart(fig_daily, use_container_width=True)

            st.markdown("---")

            # 2. Grafik: Atış Puanı Aralık Dağılımı (Dart Psikolojisi)
            if not df_p_turns.empty and "score" in df_p_turns.columns:
                bins = [-1, 20, 40, 60, 80, 100, 140, 180]
                labels = ['0-20 (Kaçak)', '21-40 (Zayıf)', '41-60 (Standart)', '61-80 (İyi)', '81-100 (Çok İyi)', '101-140 (Yüksek)', '141-180 (Maximum)']
                
                df_turns = df_p_turns.copy()
                df_turns['Skor_Araligi'] = pd.cut(df_turns['score'], bins=bins, labels=labels)
                dist_df = df_turns['Skor_Araligi'].value_counts().reindex(labels).reset_index()
                dist_df.columns = ['Aralık', 'Adet']

                fig_dist = px.bar(
                    dist_df,
                    x='Aralık',
                    y='Adet',
                    title="🎯 Atış Puanı Dağılımı (Hata & Başarı Profil Analizi)",
                    labels={'Aralık': 'Skor Aralığı', 'Adet': 'Atış Adedi'},
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
                    height=320,
                    margin=dict(t=40, b=20, l=10, r=10),
                    xaxis=dict(showgrid=False, title="Skor Aralığı"),
                    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="Adet")
                )
                st.plotly_chart(fig_dist, use_container_width=True)

            st.markdown("---")

            # 3. Tablo: Oyun Detayları
            st.markdown("### 📋 Oyun Performans Logları")
            table_cols = [c for c in ["date", "training_mode", "total_score", "avg_3dart", "darts_thrown", "rounds"] if c in df.columns]
            display_df = df[table_cols].copy()
            display_df.columns = [col.replace("date", "Tarih").replace("training_mode", "Mod").replace("total_score", "Toplam Skor").replace("avg_3dart", "3-Ok Ort.").replace("darts_thrown", "Ok Sayısı").replace("rounds", "Tur") for col in display_df.columns]
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ==========================================
    # 2. AROUND THE CLOCK SEKMESİ (BOTTLENECK ANALYTICS)
    # ==========================================
    with sub2:
        st.subheader("🔄 Around the Clock - Darboğaz & Zayıf Halka Analizi")
        if df_a_sessions.empty:
            st.info("Henüz kaydedilmiş Around the Clock oturumu bulunmuyor.")
        else:
            df_a = df_a_sessions.copy()
            if "started_at" in df_a.columns and df_a["started_at"].notna().any():
                df_a["datetime"] = pd.to_datetime(df_a["started_at"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul")
                df_a["Gun"] = df_a["datetime"].dt.strftime("%d.%m.%Y")
            else:
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

                # Segment Başına Harcanan Ok Analizi (Zayıf Halka)
                if not df_a_targets.empty and "target" in df_a_targets.columns and "darts_thrown" in df_a_targets.columns:
                    target_stats = df_a_targets.groupby("target")["darts_thrown"].mean().reset_index()
                    target_stats.columns = ["Hedef_Segment", "Ortalama_Ok"]
                    target_stats = target_stats.sort_values(by="Hedef_Segment")

                    worst_targets = target_stats.sort_values(by="Ortalama_Ok", ascending=False).head(3)
                    worst_list = ", ".join([f"**Segment {row['Hedef_Segment']}** ({row['Ortalama_Ok']:.1f} ok)" for _, row in worst_targets.iterrows()])

                    st.warning(f"⚠️ **Zayıf Halka (Bottleneck) Tespiti:** En çok zaman/ok harcadığın 3 hedef: {worst_list}. Antrenman odağını bu segmentlere kaydırmalısın.")

                    fig_targets = px.bar(
                        target_stats,
                        x="Hedef_Segment",
                        y="Ortalama_Ok",
                        title="🎯 Segment Başına Ort. Harcanan Ok Sayısı (Yüksek Barlar = Zayıf Nokta)",
                        labels={"Hedef_Segment": "Hedef Segment", "Ortalama_Ok": "Ort. Ok Sayısı"},
                        text="Ortalama_Ok"
                    )
                    fig_targets.update_traces(
                        marker_color="#ff6b35",
                        texttemplate="%{y:.1f}",
                        textposition="outside"
                    )
                    fig_targets.update_layout(
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=320,
                        margin=dict(t=40, b=20, l=10, r=10),
                        xaxis=dict(showgrid=False, dtick=1),
                        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)")
                    )
                    st.plotly_chart(fig_targets, use_container_width=True)

                    st.markdown("---")

                # 1. Grafik: Gün bazlı isabet oranı (%)
                df_daily_a = df_a_filtered.groupby("Gun", sort=False).agg({"hit_rate": "mean"}).reset_index()
                df_daily_a["hit_rate_round"] = df_daily_a["hit_rate"].round(1)

                fig_daily_hit = px.line(
                    df_daily_a,
                    x="Gun",
                    y="hit_rate_round",
                    markers=True,
                    title=f"📈 İsabet Oranı (%) Trendi ({selected_mode})",
                    labels={"Gun": "", "hit_rate_round": "İsabet (%)"}
                )
                fig_daily_hit.update_traces(
                    line=dict(color="#4ecdc4", width=3),
                    marker=dict(size=8, color="#4ecdc4", line=dict(width=2, color="#ffffff")),
                    fill="tozeroy",
                    fillcolor="rgba(78, 205, 196, 0.08)",
                    hovertemplate="<b>Tarih: %{x}</b><br>İsabet: %{y}%<extra></extra>"
                )

                min_hit = max(0, df_daily_a["hit_rate_round"].min() - 5)
                max_hit = min(100, df_daily_a["hit_rate_round"].max() + 5)

                fig_daily_hit.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=320,
                    margin=dict(t=40, b=20, l=10, r=10),
                    xaxis=dict(showgrid=False, title=""),
                    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", range=[min_hit, max_hit], title="İsabet (%)")
                )
                st.plotly_chart(fig_daily_hit, use_container_width=True)

                st.markdown("---")

                # 2. Tablo
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