import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

"""
production.py — 품목별/라인별 생산실적 분석
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np


def show():
    st.markdown('<div class="section-header">📋 품목별 생산실적 분석</div>',
                unsafe_allow_html=True)

    if "session" not in st.session_state or not st.session_state.session.get("loaded"):
        st.info("데이터를 먼저 업로드하세요.")
        return

    sess    = st.session_state.session
    prod_df = sess.get("prod_df")
    item_df = sess["item_df"].copy()
    line_df = sess["line_df"].copy()
    wd_curr = sess["wd_curr"]
    bm      = sess["base_month"]

    if prod_df is None or prod_df.empty:
        st.warning("생산실적 파일이 업로드되지 않았습니다. 데이터 업로드 탭에서 생산실적 파일을 추가하세요.")
        _show_template()
        return

    # ── 집계 ──
    # 라인별 집계
    line_prod = prod_df.groupby("line")["qty"].sum().reset_index()
    line_prod.columns = ["line", "생산수량"]

    # 기간 정보
    has_date = "date" in prod_df.columns and (prod_df["date"] != "미지정").any()

    # ── KPI ──
    total_prod = prod_df["qty"].sum()
    n_lines    = prod_df["line"].nunique()
    n_combos   = prod_df["combo"].nunique() if "combo" in prod_df.columns else 0

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("총 생산수량", f"{total_prod:,.0f}개")
    c2.metric("생산 라인 수", f"{n_lines}개")
    c3.metric("생산 품목 수", f"{n_combos}개")
    c4.metric("일일 평균생산", f"{total_prod/wd_curr:,.0f}개/일")

    st.markdown("---")

    # ── 라인별 생산 vs 목표 ──
    st.markdown("#### 📊 라인별 생산실적 vs 목표재고")
    merged = line_df.merge(line_prod, on="line", how="left")
    merged["생산수량"] = merged["생산수량"].fillna(0)
    merged["달성률"] = np.where(
        merged["tgt_curr"] > 0,
        (merged["생산수량"] / merged["tgt_curr"] * 100).round(1),
        np.nan
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="목표재고(당월)", x=merged["line"], y=merged["tgt_curr"],
        marker_color="#93C5FD", opacity=0.7,
    ))
    fig.add_trace(go.Bar(
        name="생산실적", x=merged["line"], y=merged["생산수량"],
        marker_color=merged["달성률"].apply(
            lambda x: "#DC2626" if pd.notna(x) and x < 80
            else "#16A34A" if pd.notna(x) and x <= 120
            else "#D97706" if pd.notna(x)
            else "#94A3B8"
        ),
        text=merged["달성률"].apply(
            lambda x: f"{x:.0f}%" if pd.notna(x) else ""),
        textposition="outside",
    ))
    fig.update_layout(
        barmode="group", height=350,
        margin=dict(t=20,b=10,l=0,r=0),
        yaxis_title="수량 (개)", legend=dict(orientation="h", y=1.1),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── 라인별 상세 테이블 ──
    st.markdown("#### 📋 라인별 생산실적 vs 목표재고 상세")
    disp = merged[["line","n_items","tgt_curr","생산수량","달성률",
                   "daily_curr","n_under"]].copy()
    disp.columns = ["포장라인","품목수","당월목표","생산실적","달성률(%)",
                    f"일일부하({wd_curr}일)","과소품목"]
    disp["달성률(%)"] = disp["달성률(%)"].apply(
        lambda x: f"{x:.1f}%" if pd.notna(x) else "-")

    def clr_ach(val):
        try:
            v = float(val.replace("%",""))
            if v < 80:  return "color:#DC2626;font-weight:700"
            if v <= 120: return "color:#16A34A;font-weight:700"
            return "color:#D97706;font-weight:700"
        except: return ""

    st.dataframe(
        disp.style.applymap(clr_ach, subset=["달성률(%)"]),
        use_container_width=True, hide_index=True
    )

    # ── 시계열 (날짜 있을 때) ──
    if has_date:
        st.markdown("---")
        st.markdown("#### 📈 일별 생산실적 추이")
        try:
            prod_df["date"] = pd.to_datetime(prod_df["date"])
            daily = prod_df.groupby(["date","line"])["qty"].sum().reset_index()
            sel_lines = st.multiselect(
                "라인 선택", options=sorted(daily["line"].unique()), default=[]
            )
            if sel_lines:
                plot_d = daily[daily["line"].isin(sel_lines)]
                fig2 = px.line(plot_d, x="date", y="qty", color="line",
                               markers=True,
                               labels={"date":"날짜","qty":"생산수량","line":"포장라인"})
                fig2.update_layout(
                    height=320, margin=dict(t=10,b=10,l=0,r=0),
                    plot_bgcolor="white", paper_bgcolor="white",
                )
                st.plotly_chart(fig2, use_container_width=True)
        except Exception:
            st.info("날짜 형식을 파싱하지 못했습니다.")

    # ── 품목별 드릴다운 ──
    if "combo" in prod_df.columns and n_combos > 0:
        st.markdown("---")
        st.markdown("#### 🔍 품목별 생산실적 상세")

        sel_line3 = st.selectbox(
            "포장라인 선택",
            ["전체"] + sorted(prod_df["line"].unique().tolist()),
            key="prod_line"
        )
        combo_prod = prod_df.copy()
        if sel_line3 != "전체":
            combo_prod = combo_prod[combo_prod["line"] == sel_line3]

        combo_agg = combo_prod.groupby(["line","combo"])["qty"].sum().reset_index()
        combo_agg.columns = ["포장라인","조합코드","생산수량"]

        # 재고 적정성과 조인
        combo_agg = combo_agg.merge(
            item_df[["line","combo","name","tgt_curr","ratio","label"]],
            left_on=["포장라인","조합코드"], right_on=["line","combo"], how="left"
        )
        combo_agg["달성률"] = np.where(
            combo_agg["tgt_curr"] > 0,
            (combo_agg["생산수량"] / combo_agg["tgt_curr"] * 100).round(1), np.nan
        )
        combo_agg = combo_agg.sort_values("생산수량", ascending=False)

        disp2 = combo_agg[["포장라인","조합코드","name","생산수량","tgt_curr","달성률","label"]].copy()
        disp2.columns = ["포장라인","조합코드","품목명","생산수량","당월목표","달성률(%)","재고판정"]
        disp2["달성률(%)"] = disp2["달성률(%)"].apply(
            lambda x: f"{x:.1f}%" if pd.notna(x) else "-")
        disp2["품목명"] = disp2["품목명"].fillna("-").str[:20]

        st.dataframe(disp2, use_container_width=True, hide_index=True, height=400)

        csv = disp2.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 품목별 생산실적 다운로드",
            data=csv.encode("utf-8-sig"),
            file_name=f"품목별생산실적_{bm}.csv",
            mime="text/csv",
        )


def _show_template():
    st.markdown("#### 📄 생산실적 파일 양식 예시")
    st.markdown("아래 형식으로 준비하면 자동 인식됩니다.")
    sample = pd.DataFrame({
        "포장라인": ["T80","T80","부품포장","부품포장","TC13(조립5)"],
        "조합코드": ["T80HLDA1KK-456BK","T80HLDA1KK-451NWW",
                    "S51ND2KG-5F1","S00G1KG-SG","T61HLDAM0KK-5G1BWW"],
        "생산수량": [120, 95, 280, 310, 450],
        "일자":    ["2026-03-05","2026-03-05","2026-03-05","2026-03-05","2026-03-05"],
    })
    st.dataframe(sample, use_container_width=True, hide_index=True)

    csv = sample.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "📥 양식 다운로드",
        data=csv.encode("utf-8-sig"),
        file_name="생산실적_양식.csv",
        mime="text/csv",
    )
