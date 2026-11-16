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
        "text": "#f0efec" if dark else "#0b0b0b",
        "muted": "#c3c2b7" if dark else "#52514e",
        "grid": "rgba(255,255,255,0.07)" if dark else "rgba(0,0,0,0.07)",
        "empty": "#383835" if dark else "#e4e3df",
    }


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


MOBILE_CSS = """
<style>
@media (max-width: 768px) {
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 0.4rem !important;
    }
    /* Metric rows: two per row on phones instead of one ("column" = Streamlit < 1.40).
       Rows of charts keep stacking full width. */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div[data-testid="stColumn"],
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div[data-testid="column"] {
        min-width: calc(50% - 0.4rem) !important;
        width: calc(50% - 0.4rem) !important;
        flex: 1 1 calc(50% - 0.4rem) !important;
    }
    /* Less empty space above the title. */
    div[data-testid="stMainBlockContainer"], .block-container {
        padding-top: 3.2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    /* Period picker: all four choices on one line. */
    div[data-testid="stButtonGroup"] button {
        padding: 0.25rem 0.55rem !important;
        min-height: 2rem !important;
    }
    div[data-testid="stButtonGroup"] button p {
        font-size: 0.8rem !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.1rem !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
    }
    div[data-baseweb="tab-list"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        scrollbar-width: thin;
    }
    div[data-baseweb="tab"] {
        white-space: nowrap !important;
        font-size: 0.85rem !important;
        padding: 0.4rem 0.6rem !important;
    }
    div[data-testid="stDataFrame"] {
        font-size: 0.75rem !important;
    }
    .js-plotly-plot .plotly .modebar {
        display: none !important;
    }
    section[data-testid="stSidebar"] button {
        width: 100% !important;
    }
    h1 { font-size: 1.4rem !important; }
    h2 { font-size: 1.15rem !important; }
    h3 { font-size: 1rem !important; }
}
</style>
"""


def inject_mobile_css():
    """Her sayfa başında bir kez çağır."""
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)


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


def chart(fig, key=None, height=340, margin=None):
    """Render a Plotly figure with the shared, theme-aware styling."""
    c = colors()
    fig.update_layout(
        autosize=True,
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=margin or dict(t=56, b=40, l=48, r=20),
        title=dict(font=dict(size=15)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font=dict(size=11), title_text=""),
        hoverlabel=dict(font_size=12),
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, linecolor=c["grid"], tickfont=dict(color=c["muted"]))
    fig.update_yaxes(gridcolor=c["grid"], zeroline=False, tickfont=dict(color=c["muted"]))
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
            line=dict(color=color, width=2.5),
            marker=dict(color=color, size=10),
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
                           line=dict(color=c["grid"], width=1.5))
                      if is_rated else dict(color=c["empty"], line=dict(color=c["grid"], width=1.5)))
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
        title=title,
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
    st.caption(f"Orange = the 3 weakest segments. Grey = fewer than {min_n} attempts (not rated).")


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