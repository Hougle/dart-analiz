"""
Dashboard'daki Practice sekmesi ve sidebar butonu.
app.py bu dosyayı import eder. `t` çeviri fonksiyonudur (TR/EN).
"""
import math
import sqlite3
import subprocess
import sys
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import around_tab
import ui_helpers
from around_tab import make_translator

# Bu sekmeye özel ek çeviriler (app.py'deki sözlükte olmayanlar)
_EN = {
    "80 hedefini göster": "Show 80 target",
    "Oturum ortalaması": "Session average",
    "5 oturum hareketli ort.": "5-session moving avg.",
    "Genel ortalama": "Overall average",
    "Hedef": "Target",
    "Son 5 oturum ort.": "Last 5 sessions avg.",
    "Turların %{a}'i 60 ve üzeri, %{b}'i 100 ve üzeri":
        "{a}% of turns scored 60+, {b}% scored 100+",
}


def _load(db_path):
    from dartcounter_api import turso_query, _turso_available
    if _turso_available():
        try:
            cols, rows = turso_query(
                "SELECT * FROM practice_sessions ORDER BY started_at")
            sessions = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame()
            cols, rows = turso_query("SELECT * FROM practice_turns")
            turns = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame()
            return sessions, turns
        except Exception as e:
            print(f"[practice_tab] Turso hata: {e}")
            return pd.DataFrame(), pd.DataFrame()

    # Lokal fallback
    conn = sqlite3.connect(db_path)
    try:
        sessions = pd.read_sql_query(
            "SELECT * FROM practice_sessions ORDER BY started_at", conn)
        turns = pd.read_sql_query("SELECT * FROM practice_turns", conn)
    except Exception:
        sessions, turns = pd.DataFrame(), pd.DataFrame()
    conn.close()
    return sessions, turns

def sidebar_button(token_ok, t=lambda s: s):
    if not token_ok:
        return
    if st.button(t("🎯 PRACTICE ÇEK"), use_container_width=True):
        errors = []
        with st.spinner(t("Practice çekiliyor...")):
            for script in ("practice_import.py", "around_import.py"):
                result = subprocess.run(
                    [sys.executable, script, str(datetime.now().year)],
                    capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    errors.append(f"{script}\n" + (result.stderr or result.stdout)[-1200:])
        if errors:
            st.error(t("❌ Hata oluştu"))
            st.code("\n\n".join(errors))
        else:
            st.cache_data.clear()
            st.rerun()
    st.divider()


def _progress_chart(s, tt, show_target):
    """Oturum ortalamaları + 5 oturumluk hareketli ortalama."""
    s = s.reset_index(drop=True).copy()
    s['no'] = s.index + 1
    s['label'] = s['date'].astype(str).str[5:16]
    s['ma5'] = s['avg_3dart'].rolling(5, min_periods=5).mean()
    mean_all = s['avg_3dart'].mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=s['no'], y=s['avg_3dart'], mode='lines+markers',
        name=tt("Oturum ortalaması"),
        line=dict(color='rgba(78,205,196,0.45)', width=1.5),
        marker=dict(size=9, color='#4ecdc4'),
        customdata=s['label'],
        hovertemplate="%{customdata}<br>%{y:.1f}<extra></extra>"))
    if s['ma5'].notna().any():
        fig.add_trace(go.Scatter(
            x=s['no'], y=s['ma5'], mode='lines',
            name=tt("5 oturum hareketli ort."),
            line=dict(color='#ff6b35', width=4),
            hovertemplate="%{y:.1f}<extra></extra>"))

    fig.add_hline(y=mean_all, line_dash='dot', line_color='gray',
                  annotation_text=f"{tt('Genel ortalama')}: {mean_all:.1f}",
                  annotation_position="bottom right")
    if show_target:
        fig.add_hline(y=80, line_dash='dash', line_color='#ffd166',
                      annotation_text=f"{tt('Hedef')}: 80",
                      annotation_position="top left")

    # Günler arasına ince ayırıcı çizgi
    days = s['date'].astype(str).str[:10]
    for i in range(1, len(s)):
        if days.iloc[i] != days.iloc[i - 1]:
            fig.add_vline(x=i + 0.5, line_dash='dot',
                          line_color='gray', opacity=0.3)

    lo = float(s['avg_3dart'].min())
    hi = 85.0 if show_target else float(s['avg_3dart'].max())
    step = max(1, math.ceil(len(s) / 30))
    fig.update_xaxes(tickmode='array', tickvals=s['no'][::step],
                     ticktext=s['label'][::step], tickangle=-90,
                     title_text=tt('Oturum'))
    fig.update_yaxes(range=[max(0, lo - 5), hi + 5], title_text=tt('Ortalama'))
    fig.update_layout(
        title=tt("Practice Ortalaması Gelişimi"), height=460,
        margin=dict(t=90, b=20), hovermode='closest',
        legend=dict(orientation='h', yanchor='bottom', y=1.02,
                    xanchor='right', x=1))
    return fig


def _histogram(turns, tt, show_target):
    scores = turns['score']
    mean_turn = float(scores.mean())
    end = max(100, int(math.ceil(scores.max() / 10.0)) * 10 + 10)
    if show_target:
        end = max(end, 90)

    fig = px.histogram(turns, x='score', text_auto=True,
                       color_discrete_sequence=['#ff6b35'],
                       title=tt("Practice Tur Skoru Dağılımı"))
    fig.update_traces(xbins=dict(start=0, end=end, size=10),
                      marker_line_color='#0e1117', marker_line_width=1.5,
                      opacity=0.92, textposition='outside')
    fig.add_vline(x=mean_turn, line_dash='dot', line_color='white',
                  annotation_text=f"{tt('Ortalama')}: {mean_turn:.1f}",
                  annotation_position="top")
    if show_target:
        fig.add_vline(x=80, line_dash='dash', line_color='#ffd166',
                      annotation_text=f"{tt('Hedef')}: 80",
                      annotation_position="top")
    fig.update_xaxes(title_text=tt('Tur skoru'), dtick=10, range=[0, end])
    fig.update_yaxes(title_text=tt('Frekans'))
    fig.update_layout(bargap=0.05, height=400, margin=dict(t=80))
    return fig


def _render_score_training(player, db_path, t, tt):
    sessions, turns = _load(db_path)
    if sessions.empty:
        st.info(t("Practice verisi yok. Sidebar'dan 🎯 PRACTICE ÇEK butonuna bas."))
        return

    sessions = sessions[sessions['player_name'] == player].copy()
    if sessions.empty:
        st.info(t("'{p}' adına practice oturumu bulunamadı.").format(p=player))
        return
    turns = turns.merge(sessions[['session_id', 'user_id']],
                        on=['session_id', 'user_id'])

    last = sessions['avg_3dart'].iloc[-1]
    delta = None
    if len(sessions) > 1:
        delta = f"{last - sessions['avg_3dart'].iloc[-2]:+.2f}"
    last5 = sessions['avg_3dart'].tail(5).mean()

    import ui_helpers
    ui_helpers.metric_grid([
        {"label": t("Oturum"), "value": len(sessions)},
        {"label": t("Ortalama (3-dart)"), "value": f"{sessions['avg_3dart'].mean():.2f}"},
        {"label": t("En iyi oturum"), "value": f"{sessions['avg_3dart'].max():.2f}"},
        {"label": t("Son oturum"), "value": f"{last:.2f}", "delta": delta},
        {"label": tt("Son 5 oturum ort."), "value": f"{last5:.2f}"},
    ], cols=5)

    show_target = st.checkbox(tt("80 hedefini göster"), value=False)

    st.plotly_chart(_progress_chart(sessions, tt, show_target),
                    use_container_width=True)

    if not turns.empty:
        st.plotly_chart(_histogram(turns, tt, show_target),
                        use_container_width=True)
        pct60 = (turns['score'] >= 60).mean() * 100
        pct100 = (turns['score'] >= 100).mean() * 100
        st.caption(tt("Turların %{a}'i 60 ve üzeri, %{b}'i 100 ve üzeri")
                   .format(a=f"{pct60:.0f}", b=f"{pct100:.0f}"))

    show = sessions[['date', 'rounds', 'total_score',
                     'darts_thrown', 'avg_3dart']].copy()
    show = show.sort_values('date', ascending=False)
    show.columns = [t('Tarih'), t('Tur sayısı'), t('Toplam'), t('Ok'), t('Ortalama')]
    st.dataframe(show, use_container_width=True, hide_index=True)


def render(player, db_path, t=lambda s: s):
    tt = make_translator(t, _EN)
    tab_score, tab_atc = st.tabs(["Score Training", "Around the Clock"])
    with tab_score:
        _render_score_training(player, db_path, t, tt)
    with tab_atc:
        around_tab.render(player, db_path, t)