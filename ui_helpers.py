"""Mobil-öncelikli responsive yardımcılar + ortak grafik paleti."""
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ------------------------------------------------------------------ PALETTE
# One fixed palette for every chart (validated for colour-blind separation
# on both light and dark surfaces). Roles, not raw hex, are used in charts:
#   you      -> the player (Efe) / adjusted average / highlighted marks
#   alt      -> the second series (raw average, per-session dots)
#   neutral  -> opponents and context
#   good/bad -> wins / losses (always paired with an icon or label)
_SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

# Dartboard segment order, clockwise from the top.
BOARD_ORDER = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]


def is_dark():
    try:
        return st.context.theme.type != "light"
    except Exception:
        return True


def colors():
    dark = is_dark()
    return {
        "you": "#d95926" if dark else "#eb6834",
        "alt": "#3987e5" if dark else "#2a78d6",
        "neutral": "#8a8984",
        "good": "#0ca30c",
        "bad": "#d03b3b",
        "text": "#e6e9ef" if dark else "#0f172a",
        "muted": "#98a2b3" if dark else "#5b6576",
        "grid": "rgba(148,163,184,0.12)" if dark else "rgba(15,23,42,0.07)",
        "empty": "#2a313c" if dark else "#e3e7ec",
        "card": "#11151c" if dark else "#ffffff",
        "border": "#232a35" if dark else "#e1e5eb",
    }


def categorical():
    """Five categorical colours in fixed order (validated for colour-blind separation,
    adjacent pairs, on both card surfaces). Light-mode slots 3-5 are under 3:1 contrast,
    so charts using them also need a legend and a table view."""
    if is_dark():
        return ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"]
    return ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]


def seq_scale():
    """Single-hue sequential scale: low values recede toward the page surface."""
    ramp = _SEQ_BLUE[::-1] if is_dark() else _SEQ_BLUE
    n = len(ramp) - 1
    return [[i / n, c] for i, c in enumerate(ramp)]


SCORE_BAND_EDGES = [0, 20, 40, 60, 80, 100, 120, 140, 160, 181]
SCORE_BAND_LABELS = ["0–19", "20–39", "40–59", "60–79", "80–99",
                     "100–119", "120–139", "140–159", "160–180"]


def score_bands(scores):
    """Equal-width 20-point bands (the last one includes 180)."""
    return pd.cut(pd.to_numeric(scores, errors="coerce"), bins=SCORE_BAND_EDGES,
                  labels=SCORE_BAND_LABELS, right=False)


# ------------------------------------------------------------------ PERIOD
TZ = "Europe/Istanbul"
PERIODS = {"7d": ("Last 7 days", 7), "30d": ("Last 30 days", 30),
           "90d": ("Last 90 days", 90), "all": ("All time", None)}


def period_picker():
    """One period control for the whole app (stored in st.session_state['period'])."""
    st.segmented_control("Period", options=list(PERIODS), format_func=lambda k: PERIODS[k][0],
                         default="all", key="period", label_visibility="collapsed")


def period_label():
    return PERIODS[st.session_state.get("period") or "all"][0]


def period_start():
    """Start of the selected period as a tz-aware Timestamp, or None for all time."""
    days = PERIODS[st.session_state.get("period") or "all"][1]
    if days is None:
        return None
    return pd.Timestamp.now(tz=TZ).normalize() - pd.Timedelta(days=days - 1)


def local_time(unix_seconds):
    return pd.to_datetime(pd.to_numeric(unix_seconds, errors="coerce"), unit="s", utc=True).dt.tz_convert(TZ)


def match_time(date_strings):
    """Match dates are stored as local 'YYYY-MM-DD HH:MM' strings."""
    return pd.to_datetime(date_strings, errors="coerce").dt.tz_localize(TZ, ambiguous="NaT",
                                                                        nonexistent="NaT")


def in_period(df, unix_col="started_at", date_col=None, start=None):
    """Rows inside the selected period. Practice tables use Unix seconds, matches use date strings."""
    start = start if start is not None else period_start()
    if start is None or df is None or df.empty:
        return df
    if date_col and date_col in df.columns:
        when = match_time(df[date_col])
    elif unix_col in df.columns:
        when = local_time(df[unix_col])
    else:
        return df
    return df[when >= start]


def date_column(label="Date"):
    """Readable, still sortable date column for st.dataframe: '13 Nov 2026, 16:58'."""
    return st.column_config.DatetimeColumn(label, format="D MMM YYYY, HH:mm")


def pct(v, digits=1):
    """Consistent percent formatting: 31.8%."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v:.{digits}f}%"


# ------------------------------------------------------------------ THEME
# Surface tokens per mode. Base colours and fonts come from .streamlit/config.toml;
# this layer adds cards, tab styles, the page header and phone tweaks.
_TOKENS = {
    "dark": dict(bg="#0b0e13", card="#11151c", card2="#161b23", border="#232a35",
                 text="#e6e9ef", muted="#98a2b3", faint="#6b7585", accent="#4f8ff7",
                 accent_soft="rgba(79,143,247,0.14)", shadow="none"),
    "light": dict(bg="#f6f7f9", card="#ffffff", card2="#f1f3f6", border="#e1e5eb",
                  text="#0f172a", muted="#5b6576", faint="#8a93a3", accent="#2563eb",
                  accent_soft="rgba(37,99,235,0.08)",
                  shadow="0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.06)"),
}


def tokens():
    return _TOKENS["dark" if is_dark() else "light"]


_THEME_CSS = """
<style>
:root {{
    --da-bg: {bg}; --da-card: {card}; --da-card2: {card2}; --da-border: {border};
    --da-text: {text}; --da-muted: {muted}; --da-faint: {faint};
    --da-accent: {accent}; --da-accent-soft: {accent_soft}; --da-shadow: {shadow};
}}

/* ---------- page frame */
div[data-testid="stElementContainer"]:has(iframe[title*="theme_watch"]),
div.element-container:has(iframe[title*="theme_watch"]) {{
    position: absolute !important; width: 0 !important; height: 0 !important;
    overflow: hidden !important; margin: 0 !important; padding: 0 !important;
}}
header[data-testid="stHeader"] {{
    background: color-mix(in srgb, var(--da-bg) 88%, transparent);
    backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
}}
[data-testid="stAppDeployButton"], [data-testid="stHeaderActionElements"] {{ display: none !important; }}
div[data-testid="stMainBlockContainer"] {{
    max-width: 1240px; padding-top: 2.75rem; padding-bottom: 4rem;
}}
[data-testid="stMetricValue"], [data-testid="stDataFrame"], .da-num {{
    font-variant-numeric: tabular-nums;
}}

/* ---------- page header */
.da-header {{
    display: flex; align-items: center; justify-content: space-between; gap: 1rem;
    flex-wrap: wrap; margin: 0 0 0.9rem 0;
}}
.da-brand {{ display: flex; align-items: center; gap: 0.8rem; }}
.da-mark {{
    width: 40px; height: 40px; border-radius: 11px; flex: none;
    display: grid; place-items: center;
    background: var(--da-accent); box-shadow: 0 4px 14px var(--da-accent-soft);
}}
.da-title {{
    font-family: "Inter Tight", "Inter", sans-serif; font-weight: 700;
    font-size: 1.45rem; letter-spacing: -0.02em; line-height: 1.1; color: var(--da-text);
}}
.da-sub {{ color: var(--da-muted); font-size: 0.85rem; margin-top: 2px; }}
.da-pill {{
    display: inline-flex; align-items: center; gap: 0.45rem;
    padding: 0.32rem 0.7rem; border-radius: 999px;
    border: 1px solid var(--da-border); background: var(--da-card);
    color: var(--da-muted); font-size: 0.78rem; white-space: nowrap;
}}
.da-dot {{ width: 7px; height: 7px; border-radius: 50%; background: #22c55e; }}

/* ---------- cards: metrics, charts, tables, expanders */
div[data-testid="stMetric"] {{
    background: var(--da-card); border: 1px solid var(--da-border);
    border-radius: 12px; padding: 0.85rem 1rem 0.8rem; box-shadow: var(--da-shadow);
    height: 100%;
}}
/* Metric cards in one row share the tallest card's height. */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) {{ align-items: stretch; }}
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div[data-testid="stColumn"] > div,
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) div[data-testid="stElementContainer"]:has(> div[data-testid="stMetric"]),
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) div[data-testid="stElementContainer"]:has(> div > div[data-testid="stMetric"]) {{
    height: 100%;
}}
div[data-testid="stMetricLabel"] p {{
    color: var(--da-muted); font-size: 0.78rem; font-weight: 500; letter-spacing: 0.01em;
}}
div[data-testid="stMetricValue"] {{ letter-spacing: -0.02em; }}
div[data-testid="stPlotlyChart"] {{
    background: var(--da-card); border: 1px solid var(--da-border);
    border-radius: 12px; padding: 0.5rem 0.6rem 0.2rem; box-shadow: var(--da-shadow);
}}
div[data-testid="stDataFrame"] {{
    border-radius: 12px; overflow: hidden; box-shadow: var(--da-shadow);
}}
div[data-testid="stExpander"] details {{
    background: var(--da-card); border-color: var(--da-border); border-radius: 12px;
}}
div[data-testid="stAlert"] > div {{ border-radius: 10px; }}

/* ---------- HTML chart legend (ui_helpers.html_legend) */
.da-legend {{ display: flex; flex-wrap: wrap; gap: 0.35rem 1rem; margin: -0.35rem 0 0.4rem 0.2rem; }}
.da-key {{ display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; color: var(--da-muted); }}
.da-key i {{ width: 10px; height: 10px; border-radius: 3px; display: inline-block; }}

/* ---------- coaching: level card, plan blocks */
.da-level {{
    background: var(--da-card); border: 1px solid var(--da-border); border-radius: 12px;
    padding: 1rem 1.1rem; box-shadow: var(--da-shadow); margin-bottom: 0.9rem;
}}
.da-level-k {{ color: var(--da-muted); font-size: 0.78rem; font-weight: 500; }}
.da-level-v {{ font-family: "Inter Tight", "Inter", sans-serif; font-weight: 700; font-size: 1.6rem;
              letter-spacing: -0.02em; color: var(--da-text); line-height: 1.2; }}
.da-level-s {{ color: var(--da-muted); font-size: 0.85rem; margin: 0.15rem 0 0.7rem; }}
.da-level-s b {{ color: var(--da-text); }}
.da-bar {{ height: 8px; border-radius: 999px; background: var(--da-card2); overflow: hidden;
          border: 1px solid var(--da-border); }}
.da-bar span {{ display: block; height: 100%; border-radius: 999px; background: var(--da-accent); }}
.da-bar-l {{ display: flex; justify-content: space-between; gap: 0.5rem; margin-top: 0.35rem;
            color: var(--da-muted); font-size: 0.75rem; }}
.da-bar-l span:nth-child(2) {{ color: var(--da-text); font-weight: 600; }}
.da-big {{ font-size: 1.5rem; font-weight: 650; letter-spacing: -0.02em; color: var(--da-text); }}
.da-muted {{ color: var(--da-muted); font-size: 0.85rem; }}
.da-block {{ padding: 0.55rem 0; border-top: 1px solid var(--da-border); }}
.da-block:first-of-type {{ border-top: none; }}
.da-block-t {{ display: flex; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap;
              color: var(--da-text); font-size: 0.9rem; }}
.da-block-t .da-muted {{ margin-left: auto; white-space: nowrap; }}

/* ---------- headings */
h3 {{ letter-spacing: -0.015em; }}
h4, h5 {{
    font-family: "Inter", sans-serif !important; font-weight: 600 !important;
    font-size: 0.95rem !important; letter-spacing: 0 !important;
    color: var(--da-text) !important; margin-top: 0.6rem !important;
}}
div[data-testid="stCaptionContainer"] {{ color: var(--da-muted); }}

/* ---------- main tabs: underline nav (role selectors work across Streamlit versions) */
div[data-testid="stTabs"] [role="tablist"] {{ gap: 0.15rem; }}
div[data-testid="stTabs"] .react-aria-SelectionIndicator {{ display: none; }}
div[data-testid="stTabs"] [role="tab"] {{
    padding: 0.5rem 0.8rem !important; height: auto !important; border-radius: 0;
    color: var(--da-muted) !important;
}}
div[data-testid="stTabs"] [role="tab"] p {{ font-weight: 500; font-size: 0.92rem; }}
div[data-testid="stTabs"] [role="tab"]:hover {{ color: var(--da-text) !important; }}
div[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    color: var(--da-text) !important; box-shadow: inset 0 -2px 0 var(--da-accent);
}}
div[data-testid="stTabs"] [role="tab"][aria-selected="true"] p {{ font-weight: 600; }}
div[data-testid="stTabs"] [role="tab"][aria-selected="true"] [data-testid="stIconMaterial"] {{
    color: var(--da-accent);
}}

/* ---------- sub-tabs (tabs inside a tab): pill switcher */
div[data-testid="stTabs"] [role="tabpanel"] div[data-testid="stTabs"] [role="tablist"] {{
    display: inline-flex; width: auto; max-width: 100%; gap: 2px; padding: 3px;
    background: var(--da-card2); border: 1px solid var(--da-border); border-radius: 10px;
}}
div[data-testid="stTabs"] [role="tabpanel"] div[data-testid="stTabs"] [role="tablist"]::after {{ display: none; }}
div[data-testid="stTabs"] [role="tabpanel"] div[data-testid="stTabs"] [role="tab"] {{
    padding: 0.3rem 0.8rem !important; border-radius: 7px; box-shadow: none;
}}
div[data-testid="stTabs"] [role="tabpanel"] div[data-testid="stTabs"] [role="tab"] p {{ font-size: 0.85rem; }}
div[data-testid="stTabs"] [role="tabpanel"] div[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    background: var(--da-card); box-shadow: 0 1px 2px rgba(0,0,0,0.18); color: var(--da-text) !important;
}}

/* ---------- sidebar */
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {{
    font-size: 0.8rem !important; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--da-muted) !important; font-family: "Inter", sans-serif !important;
}}

/* ---------- phones */
@media (max-width: 768px) {{
    div[data-testid="stMainBlockContainer"] {{
        padding-top: 3.2rem !important; padding-left: 1rem !important; padding-right: 1rem !important;
    }}
    div[data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; gap: 0.5rem !important; }}
    /* Metric rows: two per row instead of one. Rows of charts keep stacking full width. */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div[data-testid="stColumn"],
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div[data-testid="column"] {{
        min-width: calc(50% - 0.25rem) !important; width: calc(50% - 0.25rem) !important;
        flex: 1 1 calc(50% - 0.25rem) !important;
    }}
    div[data-testid="stMetric"] {{ padding: 0.65rem 0.75rem; }}
    div[data-testid="stMetricValue"] {{ font-size: 1.2rem !important; }}
    /* Long values (e.g. "Doubles accuracy") wrap instead of being cut off with "…". */
    div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] > div {{
        white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
        line-height: 1.25;
    }}
    div[data-testid="stMetricLabel"] p {{ font-size: 0.72rem !important; }}
    div[data-testid="stButtonGroup"] button {{ padding: 0.25rem 0.55rem !important; min-height: 2rem !important; }}
    div[data-testid="stButtonGroup"] button p {{ font-size: 0.8rem !important; }}
    div[data-testid="stTabs"] [role="tablist"] {{ overflow-x: auto !important; flex-wrap: nowrap !important; scrollbar-width: none; }}
    div[data-testid="stTabs"] [role="tab"] {{ padding: 0.45rem 0.6rem !important; white-space: nowrap; }}
    div[data-testid="stTabs"] [role="tab"] p {{ font-size: 0.85rem; }}
    div[data-testid="stPlotlyChart"] {{ padding: 0.3rem 0.2rem 0; }}
    .js-plotly-plot .plotly .modebar {{ display: none !important; }}
    .da-title {{ font-size: 1.2rem; }}
    .da-mark {{ width: 34px; height: 34px; border-radius: 9px; }}
    h1 {{ font-size: 1.4rem !important; }}
    h2 {{ font-size: 1.15rem !important; }}
    h3 {{ font-size: 1.02rem !important; }}
}}
</style>
"""

# Simple dartboard mark for the header (white on the accent tile).
_MARK = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" '
         'stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/>'
         '<circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2" fill="white" stroke="none"/>'
         '<path d="M12 3v3M12 18v3M3 12h3M18 12h3"/></svg>')


_theme_watch = None


def watch_theme():
    """Rerun when the viewer switches light/dark after the page loaded.

    Streamlit doesn't rerun on a theme switch, so CSS and charts built for the old
    theme would stay. The invisible theme_watch component reports the new theme,
    which reruns the script with st.context.theme updated.
    """
    global _theme_watch
    try:
        if _theme_watch is None:
            import os
            import streamlit.components.v1 as components
            _theme_watch = components.declare_component(
                "theme_watch", path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme_watch"))
        _theme_watch(server="dark" if is_dark() else "light", key="theme_watch", default=None)
    except Exception:
        pass  # without it, a theme switch just waits for the next rerun


def inject_theme_css():
    """Call once at the top of the page, after st.set_page_config."""
    st.markdown(_THEME_CSS.format(**tokens()), unsafe_allow_html=True)
    watch_theme()


inject_mobile_css = inject_theme_css  # old name


def page_header(player, last_sync=None):
    """Brand mark, title and the player / last-sync line at the top of the page."""
    from html import escape
    sync = (f'<span class="da-pill"><span class="da-dot"></span>Synced {escape(last_sync)}</span>'
            if last_sync else "")
    st.markdown(
        f'<div class="da-header"><div class="da-brand"><div class="da-mark">{_MARK}</div>'
        f'<div><div class="da-title">DartAnaliz</div>'
        f'<div class="da-sub">{escape(player)} · DartCounter performance</div></div></div>'
        f'{sync}</div>', unsafe_allow_html=True)


def metric_grid(metrics, cols=7, key=None):
    """Metrikleri mobil uyumlu şekilde gösterir."""
    columns = st.columns(cols)
    for col, m in zip(columns, metrics):
        kwargs = {"label": m["label"], "value": m["value"]}
        if m.get("delta") is not None:
            kwargs["delta"] = m["delta"]
        if m.get("delta_color"):
            kwargs["delta_color"] = m["delta_color"]
        col.metric(**kwargs)


CHART_FONT = "Inter, -apple-system, Segoe UI, sans-serif"


def html_legend(items):
    """Legend as wrapping HTML chips, for charts with many series: Plotly sizes legend
    entries from the plot width, so on a phone they stack one per row and squeeze the plot.

    items: list of (label, colour).
    """
    from html import escape
    chips = "".join(f'<span class="da-key"><i style="background:{col}"></i>{escape(lab)}</span>'
                    for lab, col in items)
    st.markdown(f'<div class="da-legend">{chips}</div>', unsafe_allow_html=True)


def chart(fig, key=None, height=340, margin=None):
    """Render a Plotly figure with the shared, theme-aware styling."""
    c = colors()
    fig.update_layout(
        autosize=True,
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=CHART_FONT, size=12, color=c["muted"]),
        margin=margin or dict(t=60, b=40, l=52, r=20),
        title=dict(font=dict(family=CHART_FONT, size=14, color=c["text"], weight=600),
                   x=0, xref="container", xanchor="left", y=0.98, yanchor="top", pad=dict(l=12)),
        # Legend at the bottom left of the card: on a phone it wraps into extra rows,
        # and down here those rows push the plot up instead of colliding with the title.
        legend=dict(orientation="h", yref="container", yanchor="bottom", y=0.01, xanchor="left", x=0,
                    font=dict(size=11, color=c["muted"]), title_text="", bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=c["card"], bordercolor=c["border"],
                        font=dict(family=CHART_FONT, size=12, color=c["text"])),
        bargap=0.3,
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor=c["border"], ticks="",
                     tickfont=dict(color=c["muted"], size=11), title_font=dict(color=c["muted"], size=12))
    fig.update_yaxes(gridcolor=c["grid"], zeroline=False, showline=False, ticks="",
                     tickfont=dict(color=c["muted"], size=11), title_font=dict(color=c["muted"], size=12))
    kwargs = {"width": "stretch"}
    if key is not None:
        kwargs["key"] = key
    st.plotly_chart(fig, **kwargs)


def daily_trend(df, when, series, title, y_title="", suffix="", unit="sessions",
                key=None, height=340, decimals=1, show_range=True, show_mean=True, margin=None):
    """Readable trend chart: one point per day instead of a cloud of same-day dots.

    df:     one row per session / match, with a datetime column `when`.
    series: list of (column, label, colour role) — e.g. [("avg_3dart", "3-dart avg", "you")].
    Each day shows the day's mean, joined by a straight line. With a single series,
    a thin bar marks the day's lowest and highest session, the dashed line is the
    overall mean and the latest day is labelled.
    """
    c = colors()
    d = df.dropna(subset=[when]).copy()
    if d.empty:
        st.info("No dated data for this chart yet.")
        return
    d["day"] = pd.to_datetime(d[when]).dt.tz_localize(None).dt.normalize() + pd.Timedelta(hours=12)
    single = len(series) == 1
    fmt = f"%{{y:.{decimals}f}}{suffix}"
    fig = go.Figure()
    for col, label, role in series:
        vals = pd.to_numeric(d[col], errors="coerce")
        g = vals.groupby(d["day"]).agg(["mean", "min", "max", "count"]).dropna().reset_index()
        if g.empty:
            continue
        color = c[role]
        rng = show_range and single
        custom = list(zip(g["count"], g["min"].round(decimals), g["max"].round(decimals)))
        hover = ("%{x|%a %d %b}<br><b>" + label + ": " + fmt + "</b><br>%{customdata[0]} " + unit
                 + (f"<br>range %{{customdata[1]}}{suffix} – %{{customdata[2]}}{suffix}" if rng else "")
                 + "<extra></extra>")
        fig.add_trace(go.Scatter(
            x=g["day"], y=g["mean"], mode="lines+markers", name=label, customdata=custom,
            line=dict(color=color, width=2),
            marker=dict(color=color, size=9, line=dict(color=c["card"], width=2)),
            error_y=dict(type="data", symmetric=False, array=g["max"] - g["mean"],
                         arrayminus=g["mean"] - g["min"], color=c["neutral"], thickness=1.5, width=6)
            if rng else None,
            hovertemplate=hover))
        if single:
            last = g.iloc[-1]
            fig.add_annotation(x=last["day"], y=last["mean"], text=f"<b>{last['mean']:.{decimals}f}{suffix}</b>",
                               showarrow=False, xanchor="left", xshift=10, font=dict(color=c["text"], size=13))
            if show_mean:
                overall = vals.mean()
                fig.add_hline(y=overall, line=dict(color=c["muted"], width=1, dash="dot"),
                              annotation_text=f"overall {overall:.{decimals}f}{suffix}",
                              annotation_position="top left", annotation_font=dict(color=c["muted"], size=11))
    fig.update_layout(title=title, showlegend=not single, hovermode="closest",
                      yaxis=dict(title=y_title, ticksuffix=suffix),
                      xaxis=dict(title="", tickformat="%d %b", hoverformat="%d %b"))
    # Room on the right for the latest-value label.
    chart(fig, key=key, height=height, margin=margin or dict(t=56, b=40, l=48, r=56 if single else 20))


def dartboard_ring(stats, title, prefix="", value_label="Hit rate", key=None, min_n=5):
    """Dartboard-shaped heatmap: one ring cell per segment plus the bull in the centre.

    stats: DataFrame with columns target (1-20, 25 = bull), hits, attempts.
    Cells with fewer than `min_n` attempts are drawn as 'not enough data'.
    """
    c = colors()
    s = stats.set_index("target") if not stats.empty else pd.DataFrame(columns=["hits", "attempts"])
    vmax = 0
    for t in s.index:
        if s.loc[t, "attempts"] >= min_n:
            vmax = max(vmax, s.loc[t, "hits"] / s.loc[t, "attempts"])
    vmax = max(vmax, 0.05)

    fig = go.Figure()

    def cell(t):
        if t in s.index and s.loc[t, "attempts"] > 0:
            h, a = int(s.loc[t, "hits"]), int(s.loc[t, "attempts"])
            return h, a, h / a, a >= min_n
        return 0, 0, None, False

    def add(theta, r, base, width, targets):
        ok = [cell(t) for t in targets]
        lab = [f"{prefix}{'Bull' if t == 25 else t}" for t in targets]
        rated = [i for i, v in enumerate(ok) if v[3]]
        sparse = [i for i, v in enumerate(ok) if not v[3]]
        for idx, is_rated in ((rated, True), (sparse, False)):
            if not idx:
                continue
            custom = [[lab[i], ok[i][0], ok[i][1],
                       pct(ok[i][2] * 100) if ok[i][2] is not None else "no data"] for i in idx]
            marker = (dict(color=[ok[i][2] for i in idx], coloraxis="coloraxis",
                           line=dict(color=c["card"], width=2))
                      if is_rated else dict(color=c["empty"], line=dict(color=c["card"], width=2)))
            note = "" if is_rated else f"<br><i>fewer than {min_n} attempts</i>"
            fig.add_trace(go.Barpolar(
                theta=[theta[i] for i in idx], r=[r] * len(idx), base=[base] * len(idx),
                width=[width] * len(idx), marker=marker, customdata=custom, showlegend=False,
                hovertemplate="<b>%{customdata[0]}</b><br>" + value_label +
                              ": %{customdata[3]}<br>%{customdata[1]} / %{customdata[2]}" + note +
                              "<extra></extra>",
            ))

    add([i * 18 for i in range(20)], 0.38, 0.62, 17.2, BOARD_ORDER)
    add([0], 0.2, 0, 360, [25])

    fig.update_layout(
        title=dict(text=title, font=dict(family=CHART_FONT, size=14, color=c["text"], weight=600),
                   x=0, xref="container", xanchor="left", y=0.98, yanchor="top", pad=dict(l=12)),
        font=dict(family=CHART_FONT, size=12, color=c["muted"]),
        hoverlabel=dict(bgcolor=c["card"], bordercolor=c["border"],
                        font=dict(family=CHART_FONT, size=12, color=c["text"])),
        coloraxis=dict(colorscale=seq_scale(), cmin=0, cmax=vmax,
                       colorbar=dict(title=dict(text=value_label, side="right"), tickformat=".0%",
                                     thickness=12, len=0.75, outlinewidth=0,
                                     tickfont=dict(color=c["muted"]))),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            hole=0,
            radialaxis=dict(visible=False, range=[0, 1]),
            angularaxis=dict(rotation=90, direction="clockwise", showgrid=False, showline=False,
                             ticks="", tickmode="array", tickvals=[i * 18 for i in range(20)],
                             ticktext=[f"{prefix}{t}" for t in BOARD_ORDER],
                             tickfont=dict(size=11, color=c["muted"])),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=56, b=24, l=24, r=24),
        height=420,
    )
    kwargs = {"width": "stretch"}
    if key is not None:
        kwargs["key"] = key
    st.plotly_chart(fig, **kwargs)


def segment_bars(stats, title, prefix="", value_label="Hit rate", key=None, min_n=5,
                 higher_is_better=True, value_fmt="pct"):
    """Bar per segment in numeric order (1-20, Bull); the 3 weakest are highlighted.

    stats: DataFrame with target, value, attempts (value already computed).
    """
    c = colors()
    if stats.empty:
        st.info("No data for this chart yet.")
        return
    df = stats.copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["attempts"] = pd.to_numeric(df["attempts"], errors="coerce").fillna(0)
    df["order"] = df["target"].apply(lambda t: 21 if t == 25 else t)
    df = df.sort_values("order")
    df["label"] = df["target"].apply(lambda t: f"{prefix}{'Bull' if t == 25 else t}")
    rated = df[df["attempts"] >= min_n]
    weakest = (rated.nsmallest(3, "value") if higher_is_better else rated.nlargest(3, "value"))["target"]
    df["flag"] = df["target"].isin(weakest)
    df["color"] = df.apply(lambda r: c["you"] if r["flag"] else
                           (c["alt"] if r["attempts"] >= min_n else c["empty"]), axis=1)
    fmt = (lambda v: pct(v * 100, 0)) if value_fmt == "pct" else (lambda v: f"{v:.1f}")
    fig = go.Figure(go.Bar(
        x=df["label"], y=df["value"], marker=dict(color=df["color"], cornerradius=4),
        text=[fmt(v) if f else "" for v, f in zip(df["value"], df["flag"])],
        textposition="outside", textfont=dict(color=c["text"], size=11),
        customdata=list(zip(df["attempts"], [fmt(v) for v in df["value"]])),
        hovertemplate="<b>%{x}</b><br>" + value_label + ": %{customdata[1]}"
                      "<br>Attempts: %{customdata[0]}<extra></extra>",
    ))
    fig.update_layout(title=title, showlegend=False,
                      xaxis=dict(type="category", title=""),
                      yaxis=dict(title=value_label, tickformat=".0%" if value_fmt == "pct" else None))
    chart(fig, key=key, height=360)
    st.caption(f"Orange bars are the 3 weakest segments. Grey bars have fewer than {min_n} attempts (not rated).")


def mobile_dataframe(df, priority_cols=None, height=None, key=None):
    """Mobilde öncelikli kolonları gösterir; geri kalanı expander'a koyar."""
    kwargs = {"width": "stretch", "hide_index": True}
    if height is not None:
        kwargs["height"] = height
    if key is not None:
        kwargs["key"] = key

    if priority_cols:
        available = [c for c in priority_cols if c in df.columns]
        if available:
            st.dataframe(df[available], **kwargs)
            others = [c for c in df.columns if c not in available]
            if others:
                with st.expander(f"➕ Tüm kolonlar ({len(others)} ek)"):
                    st.dataframe(df[others], width="stretch",
                                 hide_index=True)
            return
    st.dataframe(df, **kwargs)