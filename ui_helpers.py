"""
Mobil-öncelikli responsive yardımcılar.
Streamlit genişliğini JS ile ölçüp kolon sayısını otomatik ayarlar.
"""
import streamlit as st
import streamlit.components.v1 as components


def get_screen_width():
    """
    Tarayıcı genişliğini px cinsinden session_state'e yazar.
    İlk çağrıda tahmini değer döner, JS yüklenince gerçek değer gelir.
    """
    if "screen_w" not in st.session_state:
        st.session_state["screen_w"] = 1200  # desktop varsayılan

    # JS ile gerçek genişliği ölç (görünmez iframe)
    components.html(
        """
        <script>
        const w = window.parent.innerWidth;
        const url = new URL(window.parent.location.href);
        // Streamlit session_state'e yazmak için query param hilesi
        if (window.parent.sessionStorage.getItem('sw') !== String(w)) {
            window.parent.sessionStorage.setItem('sw', String(w));
        }
        </script>
        """,
        height=0,
    )
    return st.session_state["screen_w"]


def is_mobile():
    """Telefon mu? (breakpoint 768px)"""
    return get_screen_width() < 768


def metric_row(metrics, mobile_per_row=2, desktop_cols=None):
    """
    Responsive metrik satırı.

    metrics: list of dict  -> [{"label": "...", "value": "...", "delta": "...", "delta_color": "..."}]
    mobile_per_row: telefonda satır başına kaç metrik
    desktop_cols: masaüstünde kaç kolon (None ise len(metrics))
    """
    n = len(metrics)
    if is_mobile():
        per_row = mobile_per_row
    else:
        per_row = desktop_cols or n

    # Kaç satıra bölünecek
    rows = [metrics[i:i + per_row] for i in range(0, n, per_row)]

    for row in rows:
        cols = st.columns(len(row))
        for col, m in zip(cols, row):
            kwargs = {"label": m["label"], "value": m["value"]}
            if m.get("delta") is not None:
                kwargs["delta"] = m["delta"]
            if m.get("delta_color"):
                kwargs["delta_color"] = m["delta_color"]
            col.metric(**kwargs)


def responsive_chart(fig, key=None):
    """
    Mobilde daha kısa grafik + daha küçük margin + legend alta.
    """
    if is_mobile():
        fig.update_layout(
            height=320,
            margin=dict(t=50, b=10, l=10, r=10),
            legend=dict(
                orientation="h",
                yanchor="top", y=-0.25,
                xanchor="center", x=0.5,
                font=dict(size=10),
            ),
            font=dict(size=10),
            title_font=dict(size=13),
        )
        fig.update_xaxes(tickfont=dict(size=9))
        fig.update_yaxes(tickfont=dict(size=9))
    else:
        fig.update_layout(height=getattr(fig.layout, "height", None) or 420)
    st.plotly_chart(fig, use_container_width=True, key=key)


def mobile_dataframe(df, priority_cols=None, key=None, height=None):
    """
    Mobilde öncelikli kolonları gösterir; geri kalanı expander içinde.
    """
    if is_mobile() and priority_cols:
        st.dataframe(
            df[priority_cols],
            use_container_width=True,
            hide_index=True,
            height=height,
            key=key,
        )
        other = [c for c in df.columns if c not in priority_cols]
        if other:
            with st.expander("➕ " + f"Diğer kolonlar ({len(other)})"):
                st.dataframe(df[other], use_container_width=True, hide_index=True)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True,
                     height=height, key=key)