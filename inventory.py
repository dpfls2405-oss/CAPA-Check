import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

"""
inventory.py — 포장라인별 재고 적정성 점검 (드릴다운)
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


LABEL_COLOR = {
    "과소":    ("#DC2626", "#FEE2E2"),
    "적정":    ("#16A34A", "#DCFCE7"),
    "다소과다": ("#D97706", "#FEF9C3"),
    "과다":    ("#BE123C", "#FFE4E6"),
}


def show():
    st.markdown('<div class="section-header">📊 포장라인별 재고 적정성 점검</div>',
                unsafe_allow_html=True)

    if "session" not in st.session_state or not st.session_state.session.get("loaded"):
        st.info("데이터를 먼저 업로드하세요.")
        return

    sess    = st.session_state.session
    item_df = sess["item_df"].copy()
    line_df = sess["line_df"].copy()
    bm      = sess["base_month"]

    # ── 상단 필터 ──
    col1, col2, col3 = st.columns([2, 2, 3])
    with col1:
        lines = ["전체"] + sorted(line_df["line"].tolist())
        sel_line = st.selectbox("포장라인 선택", lines)
    with col2:
        labels = ["전체", "과소", "적정", "다소과다", "과다"]
        sel_label = st.selectbox("판정 필터", labels)
    with col3:
        search = st.text_input("조합코드/품목명 검색", placeholder="예: T80, 링고, S51...")

    # 필터 적용
    filtered = item_df.copy()
    if sel_line != "전체":
        filtered = filtered[filtered["line"] == sel_line]
    if sel_label != "전체":
        filtered = filtered[filtered["label"] == sel_label]
    if search:
        mask = (filtered["combo"].str.contains(search, case=False, na=False) |
                filtered["name"].str.contains(search, case=False, na=False))
        filtered = filtered[mask]

    # ── 라인별 요약 테이블 ──
    st.markdown(f"#### 포장라인별 요약 ({bm[:4]}년 {bm[4:]}월 기준)")
    _line_summary_table(line_df)

    # ── 비율 차트 ──
    st.markdown("---")
    col_chart, col_pie = st.columns([3, 1])

    with col_chart:
        st.markdown("#### 라인별 3월/2주치 비율")
        _ratio_bar_chart(line_df)

    with col_pie:
        st.markdown("#### 판정 분포")
        _label_pie(item_df)

    # ── 품목 상세 테이블 ──
    st.markdown("---")
    total = len(filtered)
    st.markdown(f"#### 품목 상세 ({total}개 표시)")

    if total == 0:
        st.warning("조건에 맞는 품목이 없습니다.")
        return

    # 정렬: 과소 → 비율 오름차순
    sort_map = {"과소": 0, "적정": 1, "다소과다": 2, "과다": 3}
    filtered["_sort"] = filtered["label"].map(sort_map).fillna(4)
    filtered = filtered.sort_values(["_sort", "ratio"])

    disp = filtered[["line","combo","name","tgt_prev","tgt_curr","delta",
                      "actual_prev","half_actual","ratio","excess",
                      "avg3m","avg12m","label"]].copy()
    disp.columns = ["포장라인","조합코드","품목명","전월목표","당월목표","증감",
                    "전월실적","2주치기준","비율(%)","과부족",
                    "3개월평출","1년평출","판정"]

    # 판정 컬럼 스타일링
    def color_label(val):
        c = LABEL_COLOR.get(val, ("#64748B","#F1F5F9"))
        return f"color:{c[0]};background:{c[1]};font-weight:700;border-radius:4px;padding:2px 6px"
    def color_ratio(val):
        try:
            v = float(val.replace("%",""))
            if v < 80: return "color:#DC2626;font-weight:700"
            if v <= 120: return "color:#16A34A;font-weight:700"
            if v <= 200: return "color:#D97706;font-weight:700"
            return "color:#BE123C;font-weight:700"
        except: return ""

    disp["비율(%)"] = disp["비율(%)"].apply(lambda x: f"{x:.1f}%")
    disp["증감"] = disp["증감"].apply(lambda x: f"+{x:,.0f}" if x >= 0 else f"{x:,.0f}")
    disp["과부족"] = disp["과부족"].apply(lambda x: f"+{x:,.0f}" if x >= 0 else f"{x:,.0f}")
    disp["3개월평출"] = disp["3개월평출"].apply(lambda x: f"{x:.1f}" if x > 0 else "-")
    disp["1년평출"] = disp["1년평출"].apply(lambda x: f"{x:.1f}" if x > 0 else "-")

    st.dataframe(
        disp.style
            .applymap(color_label, subset=["판정"])
            .applymap(color_ratio, subset=["비율(%)"]),
        use_container_width=True, hide_index=True, height=500
    )

    # ── 다운로드 ──
    csv = disp.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "📥 Excel 다운로드 (CSV)",
        data=csv.encode("utf-8-sig"),
        file_name=f"재고적정성_{bm}.csv",
        mime="text/csv",
    )


def _line_summary_table(line_df):
    ICON = {"과소":"🔴","적정":"🟢","다소과다":"🟡","과다":"🟠"}
    rows = []
    for _, r in line_df.sort_values("ratio").iterrows():
        rows.append({
            "포장라인": r["line"],
            "품목수": int(r["n_items"]),
            "전월목표": f"{r['tgt_prev']:,.0f}",
            "당월목표": f"{r['tgt_curr']:,.0f}",
            "증감": f"{'+' if r['delta']>=0 else ''}{r['delta']:,.0f}",
            "비율": f"{r['ratio']:.1f}%",
            "판정": f"{ICON.get(r['label'],'')} {r['label']}",
            "🔴과소": int(r["n_under"]),
            "🟢적정": int(r["n_ok"]),
            "🟡과다": int(r["n_over"]),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _ratio_bar_chart(line_df):
    df = line_df.sort_values("ratio")
    colors = df["label"].map({
        "과소":"#DC2626","적정":"#16A34A","다소과다":"#D97706","과다":"#BE123C"
    }).fillna("#94A3B8")
    fig = go.Figure(go.Bar(
        x=df["line"], y=df["ratio"],
        marker_color=colors,
        text=df["ratio"].apply(lambda x: f"{x:.1f}%"),
        textposition="outside",
    ))
    fig.add_hline(y=80,  line_dash="dash", line_color="#DC2626",
                  annotation_text="과소 기준 (80%)", annotation_position="left")
    fig.add_hline(y=120, line_dash="dash", line_color="#D97706",
                  annotation_text="과다 기준 (120%)", annotation_position="right")
    fig.add_hline(y=200, line_dash="dot",  line_color="#BE123C",
                  annotation_text="과다 (200%)", annotation_position="right")
    fig.update_layout(
        height=320, margin=dict(t=20,b=20,l=0,r=0),
        yaxis_title="3월/2주치 비율 (%)",
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)


def _label_pie(item_df):
    cnts = item_df["label"].value_counts()
    COLORS = {"과소":"#DC2626","적정":"#16A34A","다소과다":"#D97706","과다":"#BE123C"}
    fig = px.pie(
        values=cnts.values, names=cnts.index,
        color=cnts.index,
        color_discrete_map=COLORS,
        hole=0.45,
    )
    fig.update_layout(height=280, margin=dict(t=10,b=10,l=0,r=0),
                      showlegend=True,
                      legend=dict(orientation="h", y=-0.1))
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)
