import streamlit as st

st.set_page_config(
    page_title="CAPA Check",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 공통 스타일 ──
st.markdown("""
<style>
[data-testid="stSidebar"] { background: #1E3A5F; }
[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label { color: #93C5FD !important; }
.metric-card {
    background: white; border-radius: 10px; padding: 14px 18px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-top: 4px solid;
    margin-bottom: 8px;
}
.metric-label { font-size: 11px; color: #64748B; font-weight: 700; margin-bottom: 4px; }
.metric-value { font-size: 24px; font-weight: 900; line-height: 1.1; }
.metric-sub   { font-size: 11px; color: #94A3B8; margin-top: 2px; }
.section-header {
    font-size: 15px; font-weight: 800; color: #1E3A5F;
    border-left: 4px solid #2563EB; padding-left: 10px; margin: 16px 0 10px;
}
div[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ── 사이드바 네비게이션 ──
with st.sidebar:
    st.markdown("## ⚡ CAPA Check")
    st.markdown("### 시디즈(평택) 재고·라인 관리")
    st.markdown("---")

    page = st.radio(
        "메뉴",
        ["🏠  대시보드",
         "📂  데이터 업로드",
         "📊  재고 적정성 점검",
         "⚡  라인 CAPA 점검",
         "🔴  과소 품목 분석",
         "📋  품목별 생산실적"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("**분석 기준**")

    if "session" in st.session_state and st.session_state.session.get("loaded"):
        sess = st.session_state.session
        st.success(f"✅ 데이터 로드됨")
        st.markdown(f"- 기준월: **{sess.get('base_month','?')}**")
        st.markdown(f"- 영업일(전월): **{sess.get('wd_prev','-')}일**")
        st.markdown(f"- 영업일(당월): **{sess.get('wd_curr','-')}일**")
        st.markdown(f"- 포장라인: **{sess.get('n_lines','-')}개**")
        st.markdown(f"- 분석 품목: **{sess.get('n_items','-')}개**")
    else:
        st.warning("⚠️ 데이터를 먼저 업로드하세요")
    st.markdown("---")
    st.caption("CAPA Check v1.0")

# ── 페이지 라우팅 ──
if page == "🏠  대시보드":
    from pages import dashboard; dashboard.show()
elif page == "📂  데이터 업로드":
    from pages import upload; upload.show()
elif page == "📊  재고 적정성 점검":
    from pages import inventory; inventory.show()
elif page == "⚡  라인 CAPA 점검":
    from pages import capa; capa.show()
elif page == "🔴  과소 품목 분석":
    from pages import shortage; shortage.show()
elif page == "📋  품목별 생산실적":
    from pages import production; production.show()
