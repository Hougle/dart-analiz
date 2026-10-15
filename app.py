import re
import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import subprocess
import sys
from pathlib import Path
from datetime import datetime

import practice_tab

DB_PATH = "dart.db"
ENV_FILE = ".env"
PLAYER = "Efe"

st.set_page_config(page_title="Dart Analiz", page_icon="🎯", layout="wide")

# ---------------------------------------------------------------- DİL / LANGUAGE
LANG = st.sidebar.radio("🌐 Dil / Language", ["TR", "EN"], horizontal=True, key="lang")

EN = {
    "🎯 DartCounter Analiz Panosu": "🎯 DartCounter Analysis Dashboard",
    # token yardımı
    "⚠️ DartCounter token'ı bulunamadı veya geçersiz.": "⚠️ DartCounter token not found or invalid.",
    "### 🔑 Token Nasıl Alınır?": "### 🔑 How to get the token",
    "**1.** Tarayıcıda DartCounter'a giriş yap: `https://app.dartcounter.net`": "**1.** Log in to DartCounter in your browser: `https://app.dartcounter.net`",
    "**2.** Herhangi bir maç sayfasını aç (Statistics → bir maç)": "**2.** Open any match page (Statistics → a match)",
    "**3.** `F12` ile Developer Tools'u aç": "**3.** Open Developer Tools with `F12`",
    "**4.** **Network** sekmesine tıkla": "**4.** Click the **Network** tab",
    "**5.** **Fetch/XHR** filtresini seç": "**5.** Select the **Fetch/XHR** filter",
    "**6.** Sayfayı yenile (Cmd+R)": "**6.** Refresh the page (Cmd+R)",
    "**7.** Listede `api.dartcounter.net` içeren bir istek bul": "**7.** Find a request containing `api.dartcounter.net`",
    "**8.** Sağ tıkla → Copy → Copy as cURL": "**8.** Right-click → Copy → Copy as cURL",
    "**9.** `Bearer ` sonrası senin token'ındır": "**9.** The part after `Bearer ` is your token",
    "**10.** Proje klasöründeki `.env` dosyasına yaz: `DARTCOUNTER_TOKEN=37520203|AbCdEf...`": "**10.** Put it in the `.env` file in the project folder: `DARTCOUNTER_TOKEN=37520203|AbCdEf...`",
    "**11.** Kaydet ve sayfayı yenile.": "**11.** Save and refresh the page.",
    "💡 Token'ı bir kere aldıktan sonra uzun süre kullanabilirsin.": "💡 Once you have the token you can use it for a long time.",
    # sidebar
    "🔑 Token Nasıl Alınır?": "🔑 How to get the token",
    "✅ Token aktif": "✅ Token active",
    "⚙️ İşlemler": "⚙️ Actions",
    "🔄 YENİ MAÇLARI ÇEK": "🔄 FETCH NEW MATCHES",
    "maçları çekiliyor...": "matches are being fetched...",
    "(çıktı yok)": "(no output)",
    "✅ Güncelleme tamamlandı!": "✅ Update completed!",
    "Güncelleme tamamlandı!": "Update completed!",
    "❌ Hata oluştu": "❌ An error occurred",
    "Hata oluştu": "An error occurred",
    "Hata": "Error",
    "📥 URL ile Maç Ekle": "📥 Add Match by URL",
    "DartCounter maç URL'si:": "DartCounter match URL:",
    "Bu Maçı Ekle": "Add This Match",
    "Önce token gerekli.": "A token is required first.",
    "İndiriliyor...": "Downloading...",
    "Maç eklendi!": "Match added!",
    "URL boş.": "URL is empty.",
    "🔄 Belirli Yılı Çek": "🔄 Fetch a Specific Year",
    "Yıl:": "Year:",
    "Bu Yılın Maçlarını Çek": "Fetch This Year's Matches",
    "Oyuncu": "Player",
    "Veritabanı": "Database",
    "Henüz veri yok. Sidebar'dan 🔄 YENİ MAÇLARI ÇEK butonuna bas.": "No data yet. Press the 🔄 FETCH NEW MATCHES button in the sidebar.",
    # metrikler
    "Toplam Maç": "Total Matches",
    "Galibiyet": "Wins",
    "Mağlubiyet": "Losses",
    "Kazanma %": "Win %",
    "Ham Ort.": "Raw Avg.",
    "Adjusted": "Adjusted",
    "180 / 100+": "180s / 100+",
    # sekmeler
    "📊 Genel Bakış": "📊 Overview",
    "📈 Gelişim": "📈 Progress",
    "👥 Rakipler": "👥 Opponents",
    "🎯 Double Trouble": "🎯 Double Trouble",
    "🏆 En İyi / En Kötü": "🏆 Best / Worst",
    "📋 Maç Listesi": "📋 Match List",
    "🎯 Practice": "🎯 Practice",
    # ortak sütunlar
    "Tarih": "Date",
    "Rakip": "Opponent",
    "Sonuç": "Result",
    "Rakip Ort.": "Opp. Avg.",
    "Maç": "Match",
    "Ortalama": "Average",
    "✅ Kazandı": "✅ Won",
    "❌ Kaybetti": "❌ Lost",
    # genel bakış
    "Son 10 Maç": "Last 10 Matches",
    "Atış Puanı Dağılımı": "Throw Score Distribution",
    "Tüm Atışların Puan Dağılımı": "Score Distribution of All Throws",
    "Puan": "Score",
    "Frekans": "Frequency",
    # gelişim
    "Zaman İçinde Ortalama — Ham vs Adjusted": "Average Over Time — Raw vs Adjusted",
    "Ham Ortalama Gelişimi": "Raw Average Progress",
    "Adjusted Ortalama Gelişimi": "Adjusted Average Progress",
    "Adjusted Ortalama": "Adjusted Average",
    "Tur Bazlı Ortalama Performans": "Average Performance by Turn",
    "Tur Numarasına Göre Ortalama Puan": "Average Score by Turn Number",
    "Tur": "Turn",
    "Ortalama Puan": "Average Score",
    # rakipler
    "Rakip Bazlı İstatistik": "Stats by Opponent",
    "Rakip Bazlı Ortalamam": "My Average by Opponent",
    # double
    "🎯 Double Deneme Analizi": "🎯 Double Attempt Analysis",
    "Double denemesi: Kalan puan ≤ 40 ve çift sayı veya 50 (bull).": "Double attempt: remaining score ≤ 40 and even, or 50 (bull).",
    "Toplam Double Denemesi": "Total Double Attempts",
    "Başarısız Double": "Failed Doubles",
    "Double Başarı %": "Double Success %",
    "Maç Bazlı Double Deneme": "Double Attempts by Match",
    "Double Deneme": "Double Attempts",
    "Başarısız": "Failed",
    "Fark": "Diff",
    "Ham vs Adjusted Karşılaştırma": "Raw vs Adjusted Comparison",
    "Maç Bazlı Ham vs Adjusted": "Raw vs Adjusted by Match",
    "Ham": "Raw",
    "Tip": "Type",
    # en iyi / en kötü
    "🏆 En İyi 5 Maç (Ham Ortalamaya Göre)": "🏆 Top 5 Matches (by Raw Average)",
    "💀 En Kötü 5 Maç (Ham Ortalamaya Göre)": "💀 Bottom 5 Matches (by Raw Average)",
    "🏆 En İyi 5 Maç (Adjusted Ortalamaya Göre)": "🏆 Top 5 Matches (by Adjusted Average)",
    # maç listesi
    "Tüm Maçlar": "All Matches",
    "Sonuç:": "Result:",
    "Rakip:": "Opponent:",
    "Gösterilen": "Showing",
    "maç": "matches",
    "🎯 Maç Detayı": "🎯 Match Detail",
    "Filtrelere uyan maç yok.": "No matches fit the filters.",
    "Maç seç:": "Select match:",
    "Bu maçın leg bilgisi yok.": "This match has no leg data.",
    "Bu maç **{n} leg** içeriyor.": "This match has **{n} legs**.",
    "Kazanan": "Winner",
    "**{p}** — {n} tur": "**{p}** — {n} turns",
    "Başlangıç": "Start",
    "Atış": "Throw",
    "Kalan": "Remaining",
    # practice
    "🎯 PRACTICE ÇEK": "🎯 FETCH PRACTICE",
    "Practice çekiliyor...": "Fetching practice...",
    "Practice verisi yok. Sidebar'dan 🎯 PRACTICE ÇEK butonuna bas.": "No practice data. Press the 🎯 FETCH PRACTICE button in the sidebar.",
    "'{p}' adına practice oturumu bulunamadı.": "No practice sessions found for '{p}'.",
    "Oturum": "Session",
    "Ortalama (3-dart)": "Average (3-dart)",
    "En iyi oturum": "Best session",
    "Son oturum": "Latest session",
    "Practice Ortalaması Gelişimi": "Practice Average Progress",
    "Practice Tur Skoru Dağılımı": "Practice Turn Score Distribution",
    "Tur skoru": "Turn score",
    "Tur sayısı": "Rounds",
    "Toplam": "Total",
    "Ok": "Darts",
}


def t(s):
    return EN.get(s, s) if LANG == "EN" else s


st.title(t("🎯 DartCounter Analiz Panosu"))


def check_token():
    # 1) Streamlit Cloud (st.secrets) — öncelikli
    try:
        import streamlit as st
        if "DARTCOUNTER_TOKEN" in st.secrets:
            token = str(st.secrets["DARTCOUNTER_TOKEN"]).strip()
            if token and len(token) > 20:
                return True, "ok"
    except Exception:
        pass

    # 2) Lokal .env dosyası
    env_path = Path(ENV_FILE)
    if not env_path.exists():
        return False, "no_file"
    try:
        content = env_path.read_text()
    except Exception:
        return False, "read_error"
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("DARTCOUNTER_TOKEN="):
            token = line.split("=", 1)[1].strip()
            if token and len(token) > 20:
                return True, "ok"
            return False, "empty"
    return False, "no_token"


def show_token_help():
    st.error(t("⚠️ DartCounter token'ı bulunamadı veya geçersiz."))
    st.markdown(t("### 🔑 Token Nasıl Alınır?"))
    st.markdown(t("**1.** Tarayıcıda DartCounter'a giriş yap: `https://app.dartcounter.net`"))
    st.markdown(t("**2.** Herhangi bir maç sayfasını aç (Statistics → bir maç)"))
    st.markdown(t("**3.** `F12` ile Developer Tools'u aç"))
    st.markdown(t("**4.** **Network** sekmesine tıkla"))
    st.markdown(t("**5.** **Fetch/XHR** filtresini seç"))
    st.markdown(t("**6.** Sayfayı yenile (Cmd+R)"))
    st.markdown(t("**7.** Listede `api.dartcounter.net` içeren bir istek bul"))
    st.markdown(t("**8.** Sağ tıkla → Copy → Copy as cURL"))
    st.markdown(t("**9.** `Bearer ` sonrası senin token'ındır"))
    st.markdown(t("**10.** Proje klasöründeki `.env` dosyasına yaz: `DARTCOUNTER_TOKEN=37520203|AbCdEf...`"))
    st.markdown(t("**11.** Kaydet ve sayfayı yenile."))
    st.info(t("💡 Token'ı bir kere aldıktan sonra uzun süre kullanabilirsin."))


def load_data():
    conn = sqlite3.connect(DB_PATH)
    matches = pd.read_sql_query("SELECT * FROM matches ORDER BY date DESC", conn)
    throws = pd.read_sql_query("SELECT * FROM throws", conn)
    legs = pd.read_sql_query("SELECT * FROM legs", conn)
    conn.close()
    return matches, throws, legs


def make_label(date, opponent, n=12):
    opp = re.sub(r'-[0-9a-f]{8}-[0-9a-f-]{20,}$', '', str(opponent))
    if len(opp) > n:
        opp = opp[:n - 1] + "…"
    return f"{str(date)[5:16]} {opp}"


def refresh_cache():
    st.cache_data.clear()


def is_double_attempt(remaining_before):
    if remaining_before is None:
        return False
    try:
        rb = int(remaining_before)
    except (ValueError, TypeError):
        return False
    if rb > 0 and rb <= 40 and rb % 2 == 0:
        return True
    if rb == 50:
        return True
    return False


def adjusted_stats(throws_df):
    if throws_df.empty:
        return 0, 0, 0, 0, 0
    total_score = throws_df['score_thrown'].sum()
    total_darts = throws_df['darts_thrown'].sum()
    normal_avg = (total_score / total_darts * 3) if total_darts > 0 else 0
    tdf = throws_df.copy()
    tdf['is_dbl'] = tdf['remaining_before'].apply(is_double_attempt)
    num_dbl = int(tdf['is_dbl'].sum())
    num_failed = int(((tdf['is_dbl']) & (tdf['score_thrown'] == 0)).sum())
    filtered = tdf[~tdf['is_dbl']]
    if filtered.empty or filtered['darts_thrown'].sum() == 0:
        return normal_avg, 0, num_dbl, num_failed, normal_avg
    adj_avg = (filtered['score_thrown'].sum() / filtered['darts_thrown'].sum()) * 3
    return adj_avg, int(filtered['darts_thrown'].sum()), num_dbl, num_failed, normal_avg


with st.sidebar:
    token_ok, token_status = check_token()
    if not token_ok:
        with st.expander(t("🔑 Token Nasıl Alınır?"), expanded=True):
            show_token_help()
        st.divider()
    else:
        st.success(t("✅ Token aktif"))

    st.header(t("⚙️ İşlemler"))

    if token_ok:
        if st.button(t("🔄 YENİ MAÇLARI ÇEK"), use_container_width=True, type="primary"):
            with st.spinner(f"{datetime.now().year} {t('maçları çekiliyor...')}"):
                try:
                    result = subprocess.run(
                        [sys.executable, "list_all_matches.py", str(datetime.now().year)],
                        capture_output=True, text=True, timeout=900
                    )
                    st.code(result.stdout[-2500:] if result.stdout else t("(çıktı yok)"))
                    if result.returncode == 0:
                        st.success(t("✅ Güncelleme tamamlandı!"))
                        refresh_cache()
                        st.rerun()
                    else:
                        st.error(t("❌ Hata oluştu"))
                        if result.stderr:
                            st.code(result.stderr[-1000:])
                except Exception as e:
                    st.error(f"{t('Hata')}: {e}")
        st.divider()

    practice_tab.sidebar_button(token_ok, t)

    st.subheader(t("📥 URL ile Maç Ekle"))
    url_input = st.text_input(
        t("DartCounter maç URL'si:"),
        placeholder="https://app.dartcounter.net/statistics/match/games/...",
        key="url_input"
    )
    if st.button(t("Bu Maçı Ekle"), use_container_width=True):
        if not token_ok:
            st.error(t("Önce token gerekli."))
        elif url_input.strip():
            with st.spinner(t("İndiriliyor...")):
                try:
                    result = subprocess.run(
                        [sys.executable, "dartcounter_api.py", url_input.strip()],
                        capture_output=True, text=True, timeout=60
                    )
                    st.code(result.stdout or t("(çıktı yok)"))
                    if result.returncode == 0 and "✅" in result.stdout:
                        st.success(t("Maç eklendi!"))
                        refresh_cache()
                        st.rerun()
                    else:
                        st.error(t("Hata oluştu"))
                        if result.stderr:
                            st.code(result.stderr[-1500:])
                except Exception as e:
                    st.error(f"{t('Hata')}: {e}")
        else:
            st.warning(t("URL boş."))

    st.divider()
    st.subheader(t("🔄 Belirli Yılı Çek"))
    year = st.number_input(t("Yıl:"), min_value=2020, max_value=2030,
                           value=datetime.now().year, step=1)
    if st.button(t("Bu Yılın Maçlarını Çek"), use_container_width=True):
        if not token_ok:
            st.error(t("Önce token gerekli."))
        else:
            with st.spinner(f"{year} {t('maçları çekiliyor...')}"):
                try:
                    result = subprocess.run(
                        [sys.executable, "list_all_matches.py", str(year)],
                        capture_output=True, text=True, timeout=900
                    )
                    st.code(result.stdout[-4000:] if result.stdout else t("(çıktı yok)"))
                    if result.returncode == 0:
                        st.success(t("Güncelleme tamamlandı!"))
                        refresh_cache()
                        st.rerun()
                    else:
                        st.error(t("Hata"))
                        if result.stderr:
                            st.code(result.stderr[-1500:])
                except Exception as e:
                    st.error(f"{t('Hata')}: {e}")

    st.divider()
    st.caption(f"{t('Oyuncu')}: **{PLAYER}**")
    st.caption(f"{t('Veritabanı')}: `{DB_PATH}`")


matches, throws, legs = load_data()
if matches.empty:
    st.warning(t("Henüz veri yok. Sidebar'dan 🔄 YENİ MAÇLARI ÇEK butonuna bas."))
    st.stop()

efe_matches = matches[
    (matches['player1_name'] == PLAYER) | (matches['player2_name'] == PLAYER)
].copy()


def get_efe_result(row):
    return row['p1_result'] if row['player1_name'] == PLAYER else row['p2_result']


def get_opponent(row):
    return row['player2_name'] if row['player1_name'] == PLAYER else row['player1_name']


def get_opponent_avg(row):
    return row['p2_avg_3dart'] if row['player1_name'] == PLAYER else row['p1_avg_3dart']


efe_matches['result'] = efe_matches.apply(get_efe_result, axis=1)
efe_matches['opponent'] = efe_matches.apply(get_opponent, axis=1)
efe_matches['opp_avg'] = efe_matches.apply(get_opponent_avg, axis=1)

efe_throws = throws[throws['player_name'] == PLAYER].copy()

match_rows = []
for match_id in efe_matches['match_id']:
    mt = efe_throws[efe_throws['match_id'] == match_id]
    adj_avg, adj_darts, num_dbl, num_fail, normal_avg = adjusted_stats(mt)
    match_rows.append({
        'match_id': match_id,
        'calculated_avg': normal_avg,
        'adjusted_avg': adj_avg,
        'num_double_attempts': num_dbl,
        'num_failed_doubles': num_fail,
    })

match_stats_df = pd.DataFrame(match_rows)
efe_matches = efe_matches.merge(match_stats_df, on='match_id', how='left')
efe_matches['avg'] = efe_matches['calculated_avg'].fillna(0).round(2)
efe_matches['adjusted_avg'] = efe_matches['adjusted_avg'].fillna(0).round(2)
efe_matches['opp_avg'] = efe_matches['opp_avg'].fillna(0).round(2)
efe_complete = efe_matches[efe_matches['result'].notna()].copy()

wins = (efe_complete['result'] == 'won').sum()
losses = (efe_complete['result'] == 'lost').sum()
total_matches = len(efe_complete)
win_rate = (wins / total_matches * 100) if total_matches > 0 else 0

total_score = efe_throws['score_thrown'].sum()
total_darts = efe_throws['darts_thrown'].sum()
overall_avg = (total_score / total_darts * 3) if total_darts > 0 else 0
adj_avg_all, adj_darts_all, total_dbl, total_failed, _ = adjusted_stats(efe_throws)
efe_180s = len(efe_throws[efe_throws['score_thrown'] == 180])
efe_100s = len(efe_throws[efe_throws['score_thrown'] >= 100])

# Ortak çeviriler / shared translations
RESULT_TXT = {'won': t('✅ Kazandı'), 'lost': t('❌ Kaybetti')}
RESULT_ICON = {'won': '✅', 'lost': '❌'}
MAIN_COLS = [t('Tarih'), t('Rakip'), t('Sonuç'), t('Ham Ort.'), t('Adjusted'), t('Rakip Ort.')]
RAW_COLS = ['date', 'opponent', 'result', 'avg', 'adjusted_avg', 'opp_avg']

col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
col1.metric(t("Toplam Maç"), total_matches)
col2.metric(t("Galibiyet"), wins)
col3.metric(t("Mağlubiyet"), losses)
col4.metric(t("Kazanma %"), f"{win_rate:.1f}%")
col5.metric(t("Ham Ort."), f"{overall_avg:.2f}")
col6.metric(t("Adjusted"), f"{adj_avg_all:.2f}",
            delta=f"+{adj_avg_all - overall_avg:.2f}")
col7.metric(t("180 / 100+"), f"{efe_180s} / {efe_100s}")

st.divider()

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    t("📊 Genel Bakış"), t("📈 Gelişim"), t("👥 Rakipler"),
    t("🎯 Double Trouble"), t("🏆 En İyi / En Kötü"), t("📋 Maç Listesi"), t("🎯 Practice")
])

with tab1:
    st.subheader(t("Son 10 Maç"))
    recent = efe_complete.head(10)[['date', 'opponent', 'result', 'avg', 'opp_avg']].copy()
    recent['result'] = recent['result'].map(RESULT_TXT)
    recent.columns = [t('Tarih'), t('Rakip'), t('Sonuç'), t('Ham Ort.'), t('Rakip Ort.')]
    st.dataframe(recent, use_container_width=True, hide_index=True)
    st.subheader(t("Atış Puanı Dağılımı"))
    fig = px.histogram(efe_throws, x='score_thrown', nbins=30,
                       title=t("Tüm Atışların Puan Dağılımı"),
                       labels={'score_thrown': t('Puan'), 'count': t('Frekans')},
                       color_discrete_sequence=['#ff6b35'])
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader(t("Zaman İçinde Ortalama — Ham vs Adjusted"))
    efe_sorted = efe_complete.sort_values('date').copy()
    efe_sorted['label'] = efe_sorted.apply(
        lambda r: make_label(r['date'], r['opponent']), axis=1)
    if not efe_sorted.empty:
        fig = px.line(efe_sorted, x='label', y='avg', markers=True,
                      title=f"{PLAYER} — {t('Ham Ortalama Gelişimi')}",
                      labels={'label': t('Maç'), 'avg': t('Ortalama')})
        fig.update_traces(line_color='#ff6b35', marker=dict(size=10))
        fig.update_xaxes(tickangle=-90)
        st.plotly_chart(fig, use_container_width=True)
        fig2 = px.line(efe_sorted, x='label', y='adjusted_avg', markers=True,
                       title=f"{PLAYER} — {t('Adjusted Ortalama Gelişimi')}",
                       labels={'label': t('Maç'), 'adjusted_avg': t('Adjusted Ortalama')})
        fig2.update_traces(line_color='#4ecdc4', marker=dict(size=10))
        fig2.update_xaxes(tickangle=-90)
        st.plotly_chart(fig2, use_container_width=True)
    st.subheader(t("Tur Bazlı Ortalama Performans"))
    turn_avg = efe_throws.groupby('turn')['score_thrown'].mean().reset_index()
    turn_avg['score_thrown'] = turn_avg['score_thrown'].round(2)
    fig3 = px.bar(turn_avg, x='turn', y='score_thrown',
                  title=t("Tur Numarasına Göre Ortalama Puan"),
                  labels={'turn': t('Tur'), 'score_thrown': t('Ortalama Puan')},
                  color='score_thrown', color_continuous_scale='Oranges')
    st.plotly_chart(fig3, use_container_width=True)

with tab3:
    st.subheader(t("Rakip Bazlı İstatistik"))
    opp_stats = efe_complete.groupby('opponent').agg(
        Mac=('match_id', 'count'),
        Galibiyet=('result', lambda x: (x == 'won').sum()),
        Maglubiyet=('result', lambda x: (x == 'lost').sum()),
        Ham_Ort=('avg', 'mean'),
        Adjusted=('adjusted_avg', 'mean'),
        Rakip_Ort=('opp_avg', 'mean')
    ).reset_index()
    opp_stats['Kazanma_Yuzde'] = (opp_stats['Galibiyet'] / opp_stats['Mac'] * 100).round(1)
    opp_stats['Ham_Ort'] = opp_stats['Ham_Ort'].round(2)
    opp_stats['Adjusted'] = opp_stats['Adjusted'].round(2)
    opp_stats['Rakip_Ort'] = opp_stats['Rakip_Ort'].round(2)
    opp_stats = opp_stats.sort_values('Mac', ascending=False)
    opp_display = opp_stats.rename(columns={
        'opponent': t('Rakip'), 'Mac': t('Maç'), 'Galibiyet': t('Galibiyet'),
        'Maglubiyet': t('Mağlubiyet'), 'Ham_Ort': t('Ham Ort.'),
        'Adjusted': t('Adjusted'), 'Rakip_Ort': t('Rakip Ort.'),
        'Kazanma_Yuzde': t('Kazanma %')})
    st.dataframe(opp_display, use_container_width=True, hide_index=True)
    st.subheader(t("Rakip Bazlı Ortalamam"))
    fig = px.bar(opp_stats, x='opponent', y='Ham_Ort',
                 color='Ham_Ort', color_continuous_scale='Oranges',
                 text='Ham_Ort', labels={'opponent': t('Rakip'), 'Ham_Ort': t('Ortalama')})
    fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader(t("🎯 Double Deneme Analizi"))
    st.caption(t("Double denemesi: Kalan puan ≤ 40 ve çift sayı veya 50 (bull)."))
    col1, col2, col3 = st.columns(3)
    col1.metric(t("Toplam Double Denemesi"), int(total_dbl))
    col2.metric(t("Başarısız Double"), int(total_failed))
    success_rate = ((total_dbl - total_failed) / total_dbl * 100) if total_dbl > 0 else 0
    col3.metric(t("Double Başarı %"), f"{success_rate:.1f}%")
    st.subheader(t("Maç Bazlı Double Deneme"))
    dbl_df = efe_complete[['date', 'opponent', 'avg', 'adjusted_avg',
                            'num_double_attempts', 'num_failed_doubles', 'result']].copy()
    dbl_df['fark'] = (dbl_df['adjusted_avg'] - dbl_df['avg']).round(2)
    dbl_df['result'] = dbl_df['result'].map(RESULT_ICON)
    dbl_df.columns = [t('Tarih'), t('Rakip'), t('Ham Ort.'), t('Adjusted'),
                      t('Double Deneme'), t('Başarısız'), t('Sonuç'), t('Fark')]
    st.dataframe(dbl_df, use_container_width=True, hide_index=True)
    st.subheader(t("Ham vs Adjusted Karşılaştırma"))
    comp_df = efe_complete[['date', 'opponent', 'avg', 'adjusted_avg']].copy()
    comp_df['label'] = comp_df.apply(
        lambda r: make_label(r['date'], r['opponent']), axis=1)
    comp_df = comp_df.melt(id_vars=['label'], value_vars=['avg', 'adjusted_avg'],
                           var_name='Tip', value_name='Ortalama')
    comp_df['Tip'] = comp_df['Tip'].map({'avg': t('Ham'), 'adjusted_avg': t('Adjusted')})
    fig = px.bar(comp_df, x='label', y='Ortalama', color='Tip', barmode='group',
                 title=t("Maç Bazlı Ham vs Adjusted"),
                 labels={'label': t('Maç'), 'Ortalama': t('Ortalama'), 'Tip': t('Tip')})
    fig.update_xaxes(tickangle=-90)
    st.plotly_chart(fig, use_container_width=True)

with tab5:
    st.subheader(t("🏆 En İyi 5 Maç (Ham Ortalamaya Göre)"))
    best = efe_complete.nlargest(5, 'avg')[RAW_COLS].copy()
    best['result'] = best['result'].map(RESULT_ICON)
    best.columns = MAIN_COLS
    st.dataframe(best, use_container_width=True, hide_index=True)
    st.subheader(t("💀 En Kötü 5 Maç (Ham Ortalamaya Göre)"))
    worst = efe_complete.nsmallest(5, 'avg')[RAW_COLS].copy()
    worst['result'] = worst['result'].map(RESULT_ICON)
    worst.columns = MAIN_COLS
    st.dataframe(worst, use_container_width=True, hide_index=True)
    st.subheader(t("🏆 En İyi 5 Maç (Adjusted Ortalamaya Göre)"))
    best_adj = efe_complete.nlargest(5, 'adjusted_avg')[RAW_COLS].copy()
    best_adj['result'] = best_adj['result'].map(RESULT_ICON)
    best_adj.columns = MAIN_COLS
    st.dataframe(best_adj, use_container_width=True, hide_index=True)

with tab6:
    st.subheader(f"{t('Tüm Maçlar')} ({len(efe_complete)})")
    col1, col2 = st.columns(2)
    with col1:
        result_filter = st.multiselect(t("Sonuç:"), options=['won', 'lost'],
                                       default=['won', 'lost'],
                                       format_func=lambda x: RESULT_TXT[x])
    with col2:
        all_opponents = sorted(efe_complete['opponent'].unique())
        opponent_filter = st.multiselect(t("Rakip:"), all_opponents, default=all_opponents)
    filtered = efe_complete[
        (efe_complete['result'].isin(result_filter)) &
        (efe_complete['opponent'].isin(opponent_filter))
    ].copy()
    display_df = filtered[RAW_COLS].copy()
    display_df['result'] = display_df['result'].map(RESULT_TXT)
    display_df['avg'] = display_df['avg'].round(2)
    display_df['adjusted_avg'] = display_df['adjusted_avg'].round(2)
    display_df['opp_avg'] = display_df['opp_avg'].round(2)
    display_df.columns = MAIN_COLS
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.caption(f"{t('Gösterilen')}: {len(filtered)} {t('maç')}")
    st.divider()
    st.subheader(t("🎯 Maç Detayı"))
    match_options = filtered.apply(lambda r: f"{r['date']} — vs {r['opponent']}", axis=1).tolist()
    if not match_options:
        st.info(t("Filtrelere uyan maç yok."))
    else:
        selected = st.selectbox(t("Maç seç:"), match_options)
        idx = match_options.index(selected)
        selected_match_id = filtered.iloc[idx]['match_id']
        match_legs = legs[legs['match_id'] == selected_match_id].sort_values('leg_no')
        num_legs = len(match_legs)
        if num_legs == 0:
            st.warning(t("Bu maçın leg bilgisi yok."))
        else:
            st.caption(t("Bu maç **{n} leg** içeriyor.").format(n=num_legs))
            for _, leg_row in match_legs.iterrows():
                leg_id = leg_row['leg_id']
                leg_no = leg_row['leg_no']
                winner = leg_row['winner_name'] or "?"
                st.markdown(f"### Leg {leg_no} — {t('Kazanan')}: **{winner}**")
                leg_throws = throws[throws['leg_id'] == leg_id].copy()
                leg_throws = leg_throws.sort_values(['player_name', 'turn'])
                players_in_leg = [PLAYER] + [
                    p for p in leg_throws['player_name'].unique() if p != PLAYER][:2]
                if len(players_in_leg) == 2:
                    cols = st.columns(2)
                    for i, player in enumerate(players_in_leg):
                        p_throws = leg_throws[leg_throws['player_name'] == player].copy()
                        if p_throws.empty:
                            continue
                        with cols[i]:
                            st.write(t("**{p}** — {n} tur").format(p=player, n=len(p_throws)))
                            p_throws['Dbl'] = p_throws['remaining_before'].apply(
                                lambda x: '🎯' if is_double_attempt(x) else '')
                            p_display = p_throws[
                                ['turn', 'remaining_before', 'score_thrown', 'remaining_after', 'Dbl']].copy()
                            p_display.columns = [t('Tur'), t('Başlangıç'), t('Atış'), t('Kalan'), '🎯']
                            st.dataframe(p_display, use_container_width=True,
                                         hide_index=True, height=400)
                else:
                    p_display = leg_throws[
                        ['player_name', 'turn', 'remaining_before', 'score_thrown', 'remaining_after']].copy()
                    p_display.columns = [t('Oyuncu'), t('Tur'), t('Başlangıç'), t('Atış'), t('Kalan')]
                    st.dataframe(p_display, use_container_width=True, hide_index=True)

with tab7:
    practice_tab.render(PLAYER, DB_PATH, t)