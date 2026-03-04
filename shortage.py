import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

"""
shortage.py — 과소 품목 상세 분석 + 한 줄평 자동 생성
"""
import streamlit as st
import pandas as pd
import plotly.express as px


def show():
    st.markdown('<div class="section-header">🔴 과소 품목 분석</div>',
                unsafe_allow_html=True)

    if "session" not in st.session_state or not st.session_state.session.get("loaded"):
        st.info("데이터를 먼저 업로드하세요.")
        return

    sess    = st.session_state.session
    item_df = sess["item_df"].copy()
    bm      = sess["base_month"]
    wd_curr = sess["wd_curr"]

    under = item_df[item_df["label"] == "과소"].sort_values("ratio").copy()

    if under.empty:
        st.success("✅ 과소 판정 품목이 없습니다!")
        return

    # ── KPI ──
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("과소 품목 수", f"{len(under)}개")
    c2.metric("과소 라인 수", f"{under['line'].nunique()}개")
    c3.metric("평균 비율",    f"{under['ratio'].mean():.1f}%")
    c4.metric("합계 목표재고 부족", f"{under['excess'].sum():+,.0f}개")

    # ── 자동 한 줄평 생성 ──
    under["한줄평"] = under.apply(_auto_comment, axis=1)

    # ── 라인별 집계 ──
    col_l, col_r = st.columns([2, 3])
    with col_l:
        st.markdown("#### 라인별 과소 품목 수")
        line_cnt = under.groupby("line").agg(
            품목수=("combo","count"),
            평균비율=("ratio","mean"),
            총과부족=("excess","sum"),
        ).reset_index().sort_values("품목수", ascending=False)
        line_cnt["평균비율"] = line_cnt["평균비율"].apply(lambda x: f"{x:.1f}%")
        line_cnt["총과부족"] = line_cnt["총과부족"].apply(lambda x: f"+{x:,.0f}" if x>=0 else f"{x:,.0f}")
        st.dataframe(line_cnt, use_container_width=True, hide_index=True)

    with col_r:
        st.markdown("#### 과소 비율 분포 (산점도)")
        fig = px.scatter(
            under, x="avg3m", y="ratio", color="line",
            size="tgt_curr", hover_name="combo",
            hover_data={"name": True, "tgt_curr": True, "half_actual": True},
            labels={"avg3m":"3개월 평출", "ratio":"3월/2주치 비율(%)"},
        )
        fig.add_hline(y=80, line_dash="dash", line_color="#DC2626",
                      annotation_text="과소 기준(80%)")
        fig.update_layout(height=320, margin=dict(t=10,b=10,l=0,r=0),
                          plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)

    # ── 품목별 상세 + 한 줄평 ──
    st.markdown("---")
    st.markdown("#### 📋 과소 품목 상세 (한 줄평 포함)")

    # 필터
    lines = ["전체"] + sorted(under["line"].unique().tolist())
    sel_line = st.selectbox("포장라인 필터", lines, key="short_line")
    view = under if sel_line == "전체" else under[under["line"] == sel_line]

    disp = view[["line","combo","name","tgt_prev","tgt_curr","delta",
                 "actual_prev","half_actual","ratio","excess",
                 "avg3m","avg12m","한줄평"]].copy()
    disp.columns = ["포장라인","조합코드","품목명","전월목표","당월목표","증감",
                    "전월실적","2주치기준","비율(%)","과부족",
                    "3개월평출","1년평출","💬 과소 판단 근거 한 줄평"]
    disp["비율(%)"] = disp["비율(%)"].apply(lambda x: f"{x:.1f}%")
    disp["과부족"]  = disp["과부족"].apply(lambda x: f"+{x:,.0f}" if x>=0 else f"{x:,.0f}")
    disp["증감"]    = disp["증감"].apply(lambda x: f"+{x:,.0f}" if x>=0 else f"{x:,.0f}")
    disp["3개월평출"] = disp["3개월평출"].apply(lambda x: f"{x:.1f}" if x>0 else "-")
    disp["1년평출"] = disp["1년평출"].apply(lambda x: f"{x:.1f}" if x>0 else "-")

    st.dataframe(disp, use_container_width=True, hide_index=True, height=520)

    # ── 다운로드 ──
    csv = disp.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "📥 과소 품목 다운로드 (CSV)",
        data=csv.encode("utf-8-sig"),
        file_name=f"과소품목_{bm}.csv",
        mime="text/csv",
    )


def _auto_comment(row) -> str:
    """수치 기반 자동 한 줄평 생성"""
    tgt  = row["tgt_curr"]
    half = row["half_actual"]
    a3   = row["avg3m"]
    a12  = row["avg12m"]
    rat  = row["ratio"]
    prev = row["actual_prev"]
    name = row["name"][:12] if pd.notna(row["name"]) else ""

    # 케이스 분류
    if tgt == 0:
        if a3 > 0:
            return f"3월 목표 0개 미설정. 3개월 평출 {a3:.0f}개로 수요 존재 → 즉시 목표 설정 필요"
        return "3월 목표 0개 미설정 + 최근 수요 없음. A/S 최소 재고 설정 여부 검토"

    if half == 0:
        if a3 > 0:
            return f"2월 실적 없으나 3개월 평출 {a3:.0f}개. 3월 목표 {tgt}개가 평출 대비 과소인지 재확인"
        return "2월 실적 및 최근 평출 모두 미미. 수요 재검토 후 목표 설정 필요"

    pct_of_a3  = tgt / a3 * 100  if a3  > 0 else None
    pct_of_a12 = tgt / a12 * 100 if a12 > 0 else None
    trend = ""
    if a3 and a12 and a3 > a12 * 1.3:
        trend = f"최근 3개월({a3:.0f}개) 수요가 1년 평출({a12:.0f}개) 대비 급증 추세. "
    elif a3 and a12 and a3 < a12 * 0.7:
        trend = f"최근 3개월({a3:.0f}개) 수요가 1년 평출({a12:.0f}개) 대비 감소세. "

    if rat < 30:
        ref = a3 if a3 > 0 else prev
        ref_label = "3개월 평출" if a3 > 0 else "2월 실적"
        return (f"{trend}3월 목표 {tgt}개는 {ref_label} {ref:.0f}개의 "
                f"{tgt/ref*100:.0f}%로 심각한 과소 → 즉시 상향 조정 필요")

    if rat < 50:
        msg = f"3월 목표 {tgt}개가 2주치 기준({half}개)의 {rat:.0f}%. "
        if pct_of_a3:
            msg += f"3개월 평출({a3:.0f}개) 대비도 {pct_of_a3:.0f}% 수준. "
        return msg + trend + "목표 대폭 상향 검토"

    if rat < 80:
        msg = f"2주치({half}개) 대비 {rat:.0f}%로 월중 재고 소진 가능성. "
        if trend:
            msg += trend
        elif pct_of_a3:
            msg += f"3개월 평출 대비 {pct_of_a3:.0f}%. "
        return msg + "목표 재검토 권고"

    return f"2주치 대비 {rat:.0f}%로 과소 판정 (80% 미만). 수요 추이 모니터링 필요"
