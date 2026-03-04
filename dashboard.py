"""
dashboard.py — 전체 현황 요약 대시보드
"""
import streamlit as st
import pandas as pd


def show():
    st.markdown('<div class="section-header">🏠 전체 현황 대시보드</div>',
                unsafe_allow_html=True)

    if "session" not in st.session_state or not st.session_state.session.get("loaded"):
        st.info("👆 먼저 **데이터 업로드** 메뉴에서 파일을 업로드하고 분석을 실행하세요.")
        _show_guide()
        return

    sess = st.session_state.session
    item_df = sess["item_df"]
    line_df = sess["line_df"]
    bm      = sess["base_month"]
    wd_prev = sess["wd_prev"]
    wd_curr = sess["wd_curr"]

    # ── KPI 카드 ──
    total_prev = item_df["tgt_prev"].sum()
    total_curr = item_df["tgt_curr"].sum()
    delta      = total_curr - total_prev
    delta_rate = delta / total_prev * 100 if total_prev else 0
    n_under    = (item_df["label"] == "과소").sum()
    n_ok       = (item_df["label"] == "적정").sum()
    n_over     = item_df["label"].isin(["다소과다","과다"]).sum()
    line_under = (line_df["label"] == "과소").sum()

    bm_disp = f"{bm[:4]}년 {bm[4:]}월"
    prev_bm = _prev_month_disp(bm)

    st.markdown(f"**분석 기준: {bm_disp}** | 전월: {prev_bm} ({wd_prev}일) → 당월 ({wd_curr}일)")

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    _kpi(c1, f"{prev_bm} 목표재고", f"{total_prev:,.0f}", "전월", "#2563EB")
    _kpi(c2, f"{bm_disp} 목표재고", f"{total_curr:,.0f}",
         f"{'+' if delta>=0 else ''}{delta:,.0f} ({delta_rate:+.1f}%)",
         "#7C3AED")
    _kpi(c3, "🔴 과소 품목", f"{n_under}개", f"라인 {line_under}개 위험", "#DC2626")
    _kpi(c4, "🟢 적정 품목", f"{n_ok}개", f"전체의 {n_ok/len(item_df)*100:.0f}%", "#16A34A")
    _kpi(c5, "🟡 과다 품목", f"{n_over}개", "재고 조정 검토 필요", "#D97706")
    _kpi(c6, "분석 품목", f"{len(item_df)}개", f"{len(line_df)}개 포장라인", "#0891B2")

    # ── 라인별 현황 요약 ──
    st.markdown("---")
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("#### 📊 포장라인별 적정성 현황")
        _line_table(line_df)

    with col_right:
        st.markdown("#### 🔴 즉시 조치 필요 (과소 품목 TOP)")
        under_items = item_df[item_df["label"] == "과소"].sort_values("ratio")
        if len(under_items):
            disp = under_items[["line","combo","name","tgt_curr","half_actual",
                                 "ratio","avg3m"]].head(10).copy()
            disp.columns = ["라인","조합코드","품목명","3월목표","2주치","비율(%)","3개월평출"]
            disp["비율(%)"] = disp["비율(%)"].apply(lambda x: f"{x:.1f}%")
            disp["품목명"] = disp["품목명"].str[:16]
            st.dataframe(disp, use_container_width=True, hide_index=True)
        else:
            st.success("✅ 과소 품목 없음")

    # ── 부하량 변화 요약 ──
    st.markdown("---")
    st.markdown("#### ⚡ 라인별 일일 부하량 변화")
    _load_bars(line_df, wd_prev, wd_curr)


def _kpi(col, label, value, sub, color):
    col.markdown(f"""
    <div class="metric-card" style="border-top-color:{color}">
        <div class="metric-label">{label}</div>
        <div class="metric-value" style="color:{color}">{value}</div>
        <div class="metric-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)


def _line_table(line_df):
    COLORS = {"과소":"🔴","적정":"🟢","다소과다":"🟡","과다":"🟠"}
    rows = []
    for _, r in line_df.sort_values("ratio").iterrows():
        rows.append({
            "라인": r["line"],
            "품목": int(r["n_items"]),
            "전월목표": f"{r['tgt_prev']:,.0f}",
            "당월목표": f"{r['tgt_curr']:,.0f}",
            "비율": f"{r['ratio']:.1f}%",
            "판정": f"{COLORS.get(r['label'],'')} {r['label']}",
            "과소": int(r["n_under"]),
            "적정": int(r["n_ok"]),
            "과다": int(r["n_over"]),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _load_bars(line_df, wd_prev, wd_curr):
    import plotly.graph_objects as go
    df = line_df.sort_values("daily_curr", ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name=f"전월 ({wd_prev}일)", x=df["line"], y=df["daily_prev"],
        marker_color="#93C5FD", text=df["daily_prev"].round(0).astype(int),
        textposition="outside"
    ))
    fig.add_trace(go.Bar(
        name=f"당월 ({wd_curr}일)", x=df["line"], y=df["daily_curr"],
        marker_color=df["load_change"].apply(
            lambda x: "#DC2626" if x>5 else "#16A34A" if x>-20 else "#2563EB"),
        text=df["daily_curr"].round(0).astype(int),
        textposition="outside"
    ))
    fig.update_layout(
        barmode="group", height=320,
        margin=dict(t=20, b=20, l=0, r=0),
        legend=dict(orientation="h", y=1.1),
        yaxis_title="일일 부하량 (개/일)",
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)


def _show_guide():
    st.markdown("""
    ### 📖 사용 가이드

    #### 필요 파일
    | 파일 | 설명 | 필수 |
    |------|------|------|
    | **SCP 계획 파일** | 시디즈 의자 SCP xlsx (월별 목표재고 포함) | ✅ |
    | **출고량 실적 파일** | 그룹사 의자 출고량 CSV (월별 출고 실적) | ✅ |
    | **생산실적 파일** | 라인별/품목별 생산실적 xlsx or csv | 선택 |

    #### 분석 흐름
    ```
    SCP 목표재고 ÷ (전월실적 ÷ 2주치) → 적정성 비율 산출
    전월/당월 목표재고 ÷ 영업일수 → 일일 부하량 → CAPA 대비 가동률
    ```

    #### 판정 기준
    - 🔴 **과소**: 비율 < 80% (재고 부족 위험)
    - 🟢 **적정**: 80% ≤ 비율 ≤ 120%
    - 🟡 **다소과다**: 120% < 비율 ≤ 200%
    - 🟠 **과다**: 비율 > 200%
    """)


def _prev_month_disp(yyyymm: str) -> str:
    y, m = int(yyyymm[:4]), int(yyyymm[4:])
    m -= 1
    if m == 0: m = 12; y -= 1
    return f"{y}년 {m:02d}월"
