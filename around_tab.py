"""
Around the Clock bölümü (Practice sekmesinin içinde gösterilir).
`t` çeviri fonksiyonudur (TR/EN).
"""
import sqlite3

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import ui_helpers

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
    # --- Yeni eklenenler ---
    "Oturum Detayı ve Karşılaştırma": "Session Detail and Comparison",
    "Bir oturum seç, diğer oturumlarla hedef hedef karşılaştır.":
        "Pick a session, compare target by target with other sessions.",
    "Oturum seç:": "Select session:",
    "Seçili oturum": "Selected session",
    "Bull'suz (seçili)": "Excl. Bull (selected)",
    "İlk 5 oturum ort.": "First 5 sessions avg.",
    "Son 5 oturum ort.": "Last 5 sessions avg.",
    "İlk 5 oturum": "First 5 sessions",
    "Son 5 oturum": "Last 5 sessions",
    "Hedef Bazlı Karşılaştırma": "Target-based Comparison",
    "Seçili": "Selected",
    "Genel": "Overall",
    "İlk 5": "First 5",
    "Son 5": "Last 5",
    "Fark": "Diff",
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

    bull_free_map = _bull_free_darts(targets, mine['atc_user_id'].tolist())
    mine['darts_bull_free'] = mine['atc_user_id'].map(bull_free_map)

    # --- Segment seçimi ---
    counts = mine['number_segment'].value_counts()
    options = ['any']
    for k in ('all', 'single', 'double'):
        if k in counts.index:
            options.append(k)
    for k in counts.index:
        if k not in options:
            options.append(k)

    seg = st.selectbox(
        tt("Segment"), options,
        index=0,
        format_func=lambda k: tt(SEG.get(k, str(k))),
        key="atc_segment",
    )

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

    bull_free_mean = df['darts_bull_free'].mean()
    ui_helpers.metric_grid([
        {"label": t("Oturum"), "value": len(df)},
        {"label": tt("En az ok"), "value": int(df['darts_thrown'].min())},
        {"label": tt("Ortalama ok"), "value": f"{df['darts_thrown'].mean():.1f}"},
        {"label": tt("Ortalama ok (Bull'suz)"),
         "value": f"{bull_free_mean:.1f}" if pd.notna(bull_free_mean) else "—"},
        {"label": t("Son oturum"), "value": last,
         "delta": delta, "delta_color": "inverse"},
    ], cols=5)

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
    step = max(1, len(df) // 10)
    fig.update_xaxes(tickmode='array', tickvals=df['no'][::step],
                     ticktext=df['label'][::step], tickangle=-45,
                     title_text=t('Oturum'), tickfont=dict(size=10))
    fig.update_yaxes(range=[max(0, lo - pad), hi + pad], title_text=t('Ok'))
    fig.update_layout(title=tt("Oturum başına ok sayısı (az = iyi)"))
    ui_helpers.chart(fig, key="atc_darts_per_session")

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
        fig2.update_xaxes(tickfont=dict(size=10))
        ui_helpers.chart(fig2, key="atc_per_target")
        st.plotly_chart(fig2, use_container_width=True)
        if len(df) < 5:
            st.caption(tt("Az oturumda hedef ortalamaları gürültülüdür, "
                          "oturum sayısı arttıkça güvenilir olur."))

    # ================================================================
    # OTURUM DETAYI VE KARŞILAŞTIRMA
    # ================================================================
    if len(df) >= 1:
        st.divider()
        st.subheader(tt("Oturum Detayı ve Karşılaştırma"))
        st.caption(tt("Bir oturum seç, diğer oturumlarla hedef hedef karşılaştır."))

        # --- Oturum seçici ---
        df_sorted = df.sort_values('started_at', ascending=False).reset_index(drop=True)
        session_options = df_sorted.apply(
            lambda r: f"{str(r['date'])[5:16]} · {int(r['darts_thrown'])} ok · "
                      f"{tt('İsabet %')}: {r['hit_rate']:.1f}",
            axis=1,
        ).tolist()
        selected_label = st.selectbox(
            tt("Oturum seç:"),
            session_options,
            key="atc_session_select",
        )
        sel_idx = session_options.index(selected_label)
        selected = df_sorted.iloc[sel_idx]
        selected_atc_id = selected['atc_user_id']

        # --- Hedef bazlı veri ---
        tg_all = targets[targets['atc_user_id'].isin(df_sorted['atc_user_id'])]
        tg_selected = tg_all[tg_all['atc_user_id'] == selected_atc_id]

        if len(df_sorted) >= 5:
            first5_ids = df_sorted.tail(5)['atc_user_id'].tolist()
            last5_ids = df_sorted.head(5)['atc_user_id'].tolist()
        else:
            first5_ids = df_sorted['atc_user_id'].tolist()
            last5_ids = df_sorted['atc_user_id'].tolist()

        def per_target_avg(ids):
            sub = tg_all[tg_all['atc_user_id'].isin(ids)]
            if sub.empty:
                return pd.DataFrame(columns=['target', 'avg_darts'])
            g = sub.groupby('target')['darts_needed'].mean().reset_index()
            g.columns = ['target', 'avg_darts']
            return g

        # Tüm hedefler 1-20 + 25 (Bull) — birleştirmede eksik olmasın diye
        all_targets = pd.DataFrame({'target': list(range(1, 21)) + [BULL_TARGET]})

        sel_avg = (tg_selected.groupby('target')['darts_needed'].mean()
                   .reset_index().rename(columns={'darts_needed': 'selected'}))
        first5_avg = per_target_avg(first5_ids).rename(columns={'avg_darts': 'first5'})
        last5_avg = per_target_avg(last5_ids).rename(columns={'avg_darts': 'last5'})
        overall_avg = (per_target_avg(df_sorted['atc_user_id'].tolist())
                       .rename(columns={'avg_darts': 'overall'}))

        comp = (all_targets
                .merge(sel_avg, on='target', how='left')
                .merge(first5_avg, on='target', how='left')
                .merge(last5_avg, on='target', how='left')
                .merge(overall_avg, on='target', how='left')
                .sort_values('target').reset_index(drop=True))
        comp['name'] = comp['target'].apply(
            lambda n: tt("Bull") if int(n) == BULL_TARGET else str(int(n)))

        # --- Üst metrikler ---
        sel_total = int(selected['darts_thrown'])
        sel_bf = selected.get('darts_bull_free')
        sel_bf = int(sel_bf) if pd.notna(sel_bf) else None
        overall_mean = float(df_sorted['darts_thrown'].mean())
        first5_mean = float(df_sorted.tail(5)['darts_thrown'].mean()) if len(df_sorted) >= 5 else overall_mean
        last5_mean = float(df_sorted.head(5)['darts_thrown'].mean()) if len(df_sorted) >= 5 else overall_mean

        ui_helpers.metric_grid([
            {"label": tt("Seçili oturum"), "value": sel_total,
             "delta": f"{sel_total - overall_mean:+.1f}",
             "delta_color": "inverse"},
            {"label": tt("Bull'suz (seçili)"),
             "value": sel_bf if sel_bf is not None else "—"},
            {"label": tt("İlk 5 oturum ort."), "value": f"{first5_mean:.1f}"},
            {"label": tt("Son 5 oturum ort."), "value": f"{last5_mean:.1f}"},
            {"label": tt("Genel ortalama"), "value": f"{overall_mean:.1f}"},
        ], cols=5)

        # --- Karşılaştırma grafiği ---
        fig_cmp = go.Figure()
        fig_cmp.add_trace(go.Bar(
            x=comp['name'], y=comp['overall'],
            name=tt("Genel ortalama"),
            marker_color='rgba(180,180,180,0.35)',
            hovertemplate="%{y:.1f} " + tt("Ok") + "<extra></extra>",
        ))
        fig_cmp.add_trace(go.Bar(
            x=comp['name'], y=comp['first5'],
            name=tt("İlk 5 oturum"),
            marker_color='rgba(78,205,196,0.55)',
            hovertemplate="%{y:.1f} " + tt("Ok") + "<extra></extra>",
        ))
        fig_cmp.add_trace(go.Bar(
            x=comp['name'], y=comp['last5'],
            name=tt("Son 5 oturum"),
            marker_color='rgba(255,159,64,0.7)',
            hovertemplate="%{y:.1f} " + tt("Ok") + "<extra></extra>",
        ))
        fig_cmp.add_trace(go.Scatter(
            x=comp['name'], y=comp['selected'],
            name=tt("Seçili oturum"),
            mode='markers+lines',
            line=dict(color='#ff6b35', width=2, dash='dot'),
            marker=dict(size=10, color='#ff6b35',
                        line=dict(width=2, color='#0e1117')),
            hovertemplate="%{y:.1f} " + tt("Ok") + "<extra></extra>",
        ))
        fig_cmp.update_layout(
            barmode='group',
            title=tt("Hedef Bazlı Karşılaştırma"),
            xaxis_title=tt('Hedef'),
            yaxis_title=t('Ok'),
            margin=dict(t=60, b=20),
            template='plotly_dark',
        )
        fig_cmp.update_xaxes(tickangle=-45, tickfont=dict(size=10))
        ui_helpers.chart(fig_cmp, key="atc_cmp")

        # --- Fark tablosu ---
        comp_tbl = comp.copy()
        comp_tbl['diff'] = (comp_tbl['selected'] - comp_tbl['overall']).round(1)
        comp_tbl['status'] = comp_tbl['diff'].apply(
            lambda d: '🟢' if pd.notna(d) and d < -1
            else ('🔴' if pd.notna(d) and d > 1 else '⚪'))
        tbl = comp_tbl[['name', 'selected', 'overall', 'first5', 'last5', 'diff', 'status']].copy()
        tbl.columns = [tt('Hedef'), tt('Seçili'), tt('Genel'),
                       tt('İlk 5'), tt('Son 5'), tt('Fark'), '']
        for c in [tt('Seçili'), tt('Genel'), tt('İlk 5'), tt('Son 5'), tt('Fark')]:
            tbl[c] = tbl[c].round(1)
        st.dataframe(tbl, use_container_width=True, hide_index=True)

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
    ui_helpers.mobile_dataframe(
        show,
        priority_cols=[t('Tarih'), tt('Rakip'), t('Ok'), tt('İsabet %')],
    )