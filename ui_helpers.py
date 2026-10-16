"""Mobil-öncelikli responsive yardımcılar."""
import streamlit as st


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


def chart(fig, key=None):
    """Plotly grafiğini responsive ayarlarla basar."""
    fig.update_layout(
        autosize=True,
        margin=dict(t=60, b=40, l=40, r=20),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(size=11),
        ),
    )
    st.plotly_chart(fig, use_container_width=True, key=key)


def mobile_dataframe(df, priority_cols=None, height=None, key=None):
    """Mobilde öncelikli kolonları gösterir; geri kalanı expander'a koyar."""
    if priority_cols:
        available = [c for c in priority_cols if c in df.columns]
        if available:
            st.dataframe(df[available], use_container_width=True,
                         hide_index=True, height=height, key=key)
            others = [c for c in df.columns if c not in available]
            if others:
                with st.expander(f"➕ Tüm kolonlar ({len(others)} ek)"):
                    st.dataframe(df[others], use_container_width=True,
                                 hide_index=True)
            return
    st.dataframe(df, use_container_width=True, hide_index=True,
                 height=height, key=key)