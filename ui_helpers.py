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
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        min-width: 45% !important;
        flex: 1 1 45% !important;
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


def chart(fig, key=None, height=340):
    """Render a Plotly figure with the shared, theme-aware styling."""
    c = colors()
    fig.update_layout(
        autosize=True,
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=56, b=40, l=48, r=20),
        title=dict(font=dict(size=15)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font=dict(size=11), title_text=""),
        hoverlabel=dict(font_size=12),
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, linecolor=c["grid"], tickfont=dict(color=c["muted"]))
    fig.update_yaxes(gridcolor=c["grid"], zeroline=False, tickfont=dict(color=c["muted"]))
    kwargs = {"use_container_width": True}
    if key is not None:
        kwargs["key"] = key
    st.plotly_chart(fig, **kwargs)


def rolling_trend(x, y, window=5):
    """Centred-free trailing average, ignoring gaps; used for trend lines."""
    return pd.Series(y).rolling(window, min_periods=1).mean().values


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
    kwargs = {"use_container_width": True}
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
    kwargs = {"use_container_width": True, "hide_index": True}
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
                    st.dataframe(df[others], use_container_width=True,
                                 hide_index=True)
            return
    st.dataframe(df, **kwargs)