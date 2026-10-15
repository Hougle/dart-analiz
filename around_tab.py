"""
Around the Clock bölümü (Practice sekmesinin içinde gösterilir).
`t` çeviri fonksiyonudur (TR/EN).
"""
import sqlite3

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_EN = {
    "Around the Clock verisi yok. Sidebar'dan 🎯 PRACTICE ÇEK butonuna bas.":
        "No Around the Clock data. Press the 🎯 FETCH PRACTICE button in the sidebar.",
    "'{p}' adına Around the Clock oturumu bulunamadı.":
        "No Around the Clock sessions found for '{p}'.",
    "Segment": "Segment",
    "Tümü (Tüm modlar)": "All (all modes)",
    "All": "All",
    "Single": "Single",
    "Double": "Double",
    "1'den 20'ye": "1 to 20",
    "Rastgele": "Random",
    "Solo": "Solo",
    "Mod": "Mode",
    "Rakip": "Opponent",
    "En az ok": "Fewest darts",
    "Ortalama ok": "Average darts",
    "Ortalama ok (Bull'suz)": "Average darts (excl. Bull)",
    "Bull'suz ok": "Darts excl. Bull",
    "Oturum başına ok sayısı (az = iyi)": "Darts per session (lower is better)",
    "Hedef başına ortalama ok": "Average darts per target",
    "Hedef": "Target",
    "Bull": "Bull",
    "Bull'u grafikte göster": "Show Bull in chart",
    "Süre (dk)": "Time (min)",
    "İsabet %": "Hit %",
    "Genel ortalama": "Overall average",
    "Az oturumda hedef ortalamaları gürültülüdür, oturum sayısı arttıkça güvenilir olur.":
        "With few sessions the per-target averages are noisy; they become reliable as sessions accumulate.",
}

# 'any' = tüm modlar (filtre yok), 'all' = sadece "All" modu
SEG = {
    'any': 'Tümü (Tüm modlar)',
    'all': 'All',
    'single': 'Single',
    'double': 'Double',
}
MODE = {'low_to_high': "1'den 20'ye", 'random': 'Rastgele'}
BULL_TARGET = 25  # around_targets tablosunda Bull = 25


def make_translator(t, extra):
    """Ek çeviri sözlüğünü app.py'deki `t` ile birleştirir."""
    english = t("Tarih") != "Tarih"

    def tt(s):
        if english and s in extra:
            return extra[s]
        return t(s)
    return tt


def _load(db_path):
    conn = sqlite3.connect(db_path)
    try:
        sessions = pd.read_sql_query(
            "SELECT * FROM around_sessions ORDER BY started_at", conn)
        targets = pd.read_sql_query("SELECT * FROM around_targets", conn)
    except Exception:
        sessions, targets = pd.DataFrame(), pd.DataFrame()
    conn.close()
    return sessions, targets


def _bull_free_darts(targets_df, atc_user_ids):
    """
    Verilen oturumlar için Bull (target=25) hariç toplam ok sayısını döndürür.
    Dönüş: {atc_user_id: bull_free_darts}
    """
    if targets_df.empty:
        return {}
    sub = targets_df[targets_df['atc_user_id'].isin(atc_user_ids)]
    sub = sub[sub['target'] != BULL_TARGET]
    return sub.groupby('atc_user_id')['darts_needed'].sum().to_dict()


def render(player, db_path, t=lambda s: s):
    tt = make_translator(t, _EN)
    allrows, targets = _load(db_path)
    if allrows.empty:
        st.info(tt("Around the Clock verisi yok. Sidebar'dan 🎯 PRACTICE ÇEK butonuna bas."))
        return

    cpu = (allrows[allrows['is_cpu'] == 1][['session_id', 'cpu_level']]
           .rename(columns={'cpu_level': 'opp_level'})
           .drop_duplicates('session_id'))
    mine = allrows[(allrows['player_name'] == player) &
                   (allrows['is_cpu'] == 0)].copy()
    if mine.empty:
        st.info(tt("'{p}' adına Around the Clock oturumu bulunamadı.").format(p=player))
        return
    mine = mine.merge(cpu, on='session_id', how='left')
    mine['opp'] = mine['opp_level'].apply(
        lambda v: tt("Solo") if pd.isna(v) else f"DartBot ({int(v)})")

    # --- Bull'suz ok sayısını hesapla ve mine'a ekle ---
    bull_free_map = _bull_free_darts(targets, mine['atc_user_id'].tolist())
    mine['darts_bull_free'] = mine['atc_user_id'].map(bull_free_map)

    # --- Segment seçimi ---
    # 'any' her zaman başta, sonra veritabanında bulunan segmentler
    counts = mine['number_segment'].value_counts()
    options = ['any']
    for k in ('all', 'single', 'double'):
        if k in counts.index:
            options.append(k)
    # Veritabanında başka değer varsa onları da ekle
    for k in counts.index:
        if k not in options:
            options.append(k)

    seg = st.selectbox(
        tt("Segment"), options,
        index=0,  # 'any' varsayılan
        format_func=lambda k: tt(SEG.get(k, str(k))),
        key="atc_segment",
    )

    # 'any' seçildiğinde filtre uygulanmaz — tüm modlar
    if seg == 'any':
        df = mine.reset_index(drop=True).copy()
    else:
        df = mine[mine['number_segment'] == seg].reset_index(drop=True).copy()

    if df.empty:
        st.warning(f"Bu segment için oturum yok: {seg}")
        return

    df['no'] = df.index + 1
    df['label'] = df['date'].astype(str).str[5:16]

    last = int(df['darts_thrown'].iloc[-1])
    delta = None
    if len(df) > 1:
        delta = f"{last - int(df['darts_thrown'].iloc[-2]):+d}"

    # --- Metrikler ---
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(t("Oturum"), len(df))
    c2.metric(tt("En az ok"), int(df['darts_thrown'].min()))
    c3.metric(tt("Ortalama ok"), f"{df['darts_thrown'].mean():.1f}")
    bull_free_mean = df['darts_bull_free'].mean()
    c4.metric(tt("Ortalama ok (Bull'suz)"),
              f"{bull_free_mean:.1f}" if pd.notna(bull_free_mean) else "—")
    c5.metric(t("Son oturum"), last, delta=delta, delta_color="inverse")

    # --- Oturum başına ok sayısı grafiği ---
    mean_darts = float(df['darts_thrown'].mean())
    mean_bf = float(df['darts_bull_free'].mean()) if df['darts_bull_free'].notna().any() else None
    df['mode_txt'] = df['mode'].map(lambda m: tt(MODE.get(m, str(m))))

    fig = go.Figure()
    if mean_bf is not None:
        fig.add_trace(go.Scatter(
            x=df['no'], y=df['darts_bull_free'], mode='lines+markers',
            name=tt("Bull'suz ok"),
            line=dict(color='rgba(78,205,196,0.5)', width=1.5, dash='dot'),
            marker=dict(size=7, color='#4ecdc4'),
            hovertemplate=("%{y} " + tt("Bull'suz ok") + "<extra></extra>"),
        ))
    fig.add_trace(go.Scatter(
        x=df['no'], y=df['darts_thrown'], mode='lines+markers',
        name=t("Ok"),
        line=dict(color='rgba(255,107,53,0.45)', width=1.5),
        marker=dict(size=10, color='#ff6b35'),
        customdata=df[['label', 'mode_txt', 'opp', 'hit_rate']],
        hovertemplate=("%{customdata[0]}<br>%{y} " + t("Ok") +
                       "<br>%{customdata[1]} · %{customdata[2]}"
                       "<br>" + tt("İsabet %") + ": %{customdata[3]:.1f}"
                       "<extra></extra>"),
    ))
    fig.add_hline(y=mean_darts, line_dash='dot', line_color='#ff6b35',
                  annotation_text=f"{tt('Genel ortalama')}: {mean_darts:.1f}",
                  annotation_position="top right")
    if mean_bf is not None:
        fig.add_hline(y=mean_bf, line_dash='dot', line_color='#4ecdc4',
                      annotation_text=f"Bull'suz: {mean_bf:.1f}",
                      annotation_position="bottom right")
    days = df['date'].astype(str).str[:10]
    for i in range(1, len(df)):
        if days.iloc[i] != days.iloc[i - 1]:
            fig.add_vline(x=i + 0.5, line_dash='dot',
                          line_color='gray', opacity=0.3)
    lo, hi = float(df['darts_thrown'].min()), float(df['darts_thrown'].max())
    if mean_bf is not None:
        lo = min(lo, float(df['darts_bull_free'].min()))
        hi = max(hi, float(df['darts_bull_free'].max()))
    pad = max(3.0, (hi - lo) * 0.15)
    fig.update_xaxes(tickmode='array', tickvals=df['no'],
                     ticktext=df['label'], tickangle=-90, title_text=t('Oturum'))
    fig.update_yaxes(range=[max(0, lo - pad), hi + pad], title_text=t('Ok'))
    fig.update_layout(title=tt("Oturum başına ok sayısı (az = iyi)"),
                      height=420, margin=dict(t=80, b=20),
                      legend=dict(orientation='h', yanchor='bottom',
                                  y=1.02, xanchor='right', x=1))
    st.plotly_chart(fig, use_container_width=True)

    # --- Hedef başına ortalama ok ---
    tg = targets[targets['atc_user_id'].isin(df['atc_user_id'])]
    if not tg.empty:
        show_bull = st.checkbox(tt("Bull'u grafikte göster"), value=True,
                                key="atc_show_bull")
        tg_plot = tg if show_bull else tg[tg['target'] != BULL_TARGET]
        by = (tg_plot.groupby('target')['darts_needed'].mean()
              .reset_index().sort_values('target'))
        by['name'] = by['target'].apply(
            lambda n: tt("Bull") if int(n) == BULL_TARGET else str(int(n)))
        by['is_bull'] = by['target'] == BULL_TARGET
        fig2 = px.bar(by, x='name', y='darts_needed', text_auto='.1f',
                      color='is_bull',
                      color_discrete_map={True: '#8B0000', False: '#FFD9B3'},
                      title=tt("Hedef başına ortalama ok"))
        fig2.update_traces(textposition='outside')
        fig2.update_xaxes(type='category', categoryorder='array',
                          categoryarray=list(by['name']), title_text=tt('Hedef'))
        fig2.update_yaxes(title_text=t('Ok'))
        fig2.update_layout(coloraxis_showscale=False, height=400,
                           margin=dict(t=80), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)
        if len(df) < 5:
            st.caption(tt("Az oturumda hedef ortalamaları gürültülüdür, "
                          "oturum sayısı arttıkça güvenilir olur."))

    # --- Tablo ---
    show = df[['date', 'mode_txt', 'opp', 'darts_thrown',
               'darts_bull_free', 'hit_rate', 'duration_sec']].copy()
    show['hit_rate'] = show['hit_rate'].round(1)
    show['duration_sec'] = (show['duration_sec'] / 60).round(1)
    show['darts_bull_free'] = show['darts_bull_free'].astype('Int64')
    show = show.sort_values('date', ascending=False)
    show.columns = [t('Tarih'), tt('Mod'), tt('Rakip'), t('Ok'),
                    tt("Bull'suz ok"),
                    tt('İsabet %'), tt('Süre (dk)')]
    st.dataframe(show, use_container_width=True, hide_index=True)