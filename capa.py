import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

"""
capa.py — 포장라인 CAPA 점검 (부하량 분석)
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np


def show():
    st.markdown('<div class="section-header">⚡ 포장라인 CAPA 점검</div>',
                unsafe_allow_html=True)

    if "session" not in st.session_state or not st.session_state.session.get("loaded"):
        st.info("데이터를 먼저 업로드하세요.")
        return

    sess    = st.session_state.session
    line_df = sess["line_df"].copy()
    item_df = sess["item_df"].copy()
    wd_prev = sess["wd_prev"]
    wd_curr = sess["wd_curr"]
    bm      = sess["base_month"]
    capa    = sess.get("capa_map", {})

    # ── CAPA 임시 수정 (사이드패널) ──
    with st.expander("⚙️ CAPA 설정 수정", expanded=False):
        st.caption("라인별 일일 CAPA(개/일)를 수정하면 가동률이 즉시 재계산됩니다.")
        capa_edit = {}
        cols = st.columns(4)
        for i, (line, cap) in enumerate(capa.items()):
            with cols[i % 4]:
                capa_edit[line] = st.number_input(line, value=int(cap), min_value=0,
                                                   step=10, key=f"capa_edit_{line}")
        if st.button("🔄 CAPA 재계산"):
            from utils.parser import calc_line_summary
            line_df = calc_line_summary(item_df, wd_prev, wd_curr, capa_edit)
            sess["line_df"] = line_df
            sess["capa_map"] = capa_edit
            st.success("재계산 완료")

    # ── KPI ──
    natural_drop = ((wd_curr - wd_prev) / wd_prev * 100)  # 영업일 증가로 인한 자연감소율
    total_prev_d = line_df["daily_prev"].sum()
    total_curr_d = line_df["daily_curr"].sum()
    global_lc    = (total_curr_d - total_prev_d) / total_prev_d * 100 if total_prev_d else 0
    alert_lines  = line_df[line_df["util_curr"] > 90] if "util_curr" in line_df.columns else pd.DataFrame()
    overload     = line_df[line_df["load_change"] > 5]

    c1,c2,c3,c4,c5 = st.columns(5)
    _kpi(c1, f"전월 전체 일일부하", f"{total_prev_d:.0f}", f"÷{wd_prev}일", "#2563EB")
    _kpi(c2, f"당월 전체 일일부하", f"{total_curr_d:.0f}", f"÷{wd_curr}일",
         "#DC2626" if global_lc > 5 else "#16A34A")
    _kpi(c3, "전체 부하 변화율", f"{global_lc:+.1f}%",
         f"자연감소 기준: {natural_drop:.1f}%",
         "#DC2626" if global_lc > 5 else "#16A34A")
    _kpi(c4, "⚠️ 부하 증가 라인", f"{len(overload)}개",
         ", ".join(overload["line"].tolist()[:3]) or "없음", "#D97706")
    _kpi(c5, "🚨 CAPA 초과 위험", f"{len(alert_lines)}개",
         "가동률 90% 초과", "#DC2626")

    st.markdown(f"""
    <div style="background:#EFF6FF;border-left:4px solid #2563EB;padding:10px 14px;
    border-radius:0 8px 8px 0;font-size:12px;color:#1E40AF;margin:12px 0">
    💡 <b>부하량 해석 기준</b>: 당월 영업일({wd_curr}일)이 전월({wd_prev}일)보다 
    {wd_curr-wd_prev:+d}일 많으면 동일 물량 기준 일일부하는 
    <b>{natural_drop:.1f}%</b> 자연 감소. 이보다 더 크게 감소하면 실질 물량 감소.
    </div>""", unsafe_allow_html=True)

    # ── 부하량 차트 ──
    st.markdown("#### 📊 라인별 일일 부하량 비교 (전월 vs 당월)")
    _load_chart(line_df, wd_prev, wd_curr)

    # ── CAPA 가동률 차트 ──
    if "util_curr" in line_df.columns:
        st.markdown("---")
        st.markdown("#### 🏭 CAPA 대비 가동률")
        _util_chart(line_df)

    # ── 라인별 상세 테이블 ──
    st.markdown("---")
    st.markdown("#### 📋 라인별 부하량 상세")

    disp_cols = ["line","n_items","tgt_prev","daily_prev","tgt_curr","daily_curr",
                 "load_change","delta","ratio","n_under","n_ok","n_over"]
    if "util_curr" in line_df.columns:
        disp_cols += ["capa_daily","util_prev","util_curr"]

    disp = line_df[disp_cols].copy()
    col_names = {
        "line":"포장라인","n_items":"품목수",
        "tgt_prev":"전월목표","daily_prev":f"전월일일\n({wd_prev}일)",
        "tgt_curr":"당월목표","daily_curr":f"당월일일\n({wd_curr}일)",
        "load_change":"부하변화율","delta":"목표증감",
        "ratio":"재고비율","n_under":"과소","n_ok":"적정","n_over":"과다",
        "capa_daily":"CAPA(일)","util_prev":"전월가동률","util_curr":"당월가동률",
    }
    disp.rename(columns={k:v for k,v in col_names.items() if k in disp.columns}, inplace=True)

    def color_change(val):
        try:
            v = float(str(val).replace("%",""))
            if v > 5:   return "color:#DC2626;font-weight:700"
            if v > 0:   return "color:#D97706;font-weight:700"
            if v > -20: return "color:#16A34A;font-weight:700"
            return "color:#2563EB;font-weight:700"
        except: return ""

    pct_cols = [c for c in disp.columns if "부하변화율" in c or "가동률" in c or "재고비율" in c]
    for c in pct_cols:
        disp[c] = disp[c].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "-")

    num_cols = ["전월목표","당월목표","목표증감",f"전월일일\n({wd_prev}일)",f"당월일일\n({wd_curr}일)"]
    for c in num_cols:
        if c in disp.columns:
            disp[c] = disp[c].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "-")

    change_col = "부하변화율"
    if change_col in disp.columns:
        st.dataframe(
            disp.style.applymap(color_change, subset=[change_col]),
            use_container_width=True, hide_index=True
        )
    else:
        st.dataframe(disp, use_container_width=True, hide_index=True)

    # ── 품목별 드릴다운 ──
    st.markdown("---")
    sel_line2 = st.selectbox("품목 상세 확인 (포장라인 선택)",
                              ["선택하세요"] + line_df["line"].tolist())
    if sel_line2 != "선택하세요":
        items = item_df[item_df["line"] == sel_line2].sort_values("ratio")
        st.markdown(f"**{sel_line2}** — {len(items)}개 품목")
        disp2 = items[["combo","name","tgt_prev","tgt_curr","actual_prev",
                        "half_actual","ratio","label","avg3m"]].copy()
        disp2.columns = ["조합코드","품목명","전월목표","당월목표","전월실적",
                         "2주치","비율(%)","판정","3개월평출"]
        disp2["비율(%)"] = disp2["비율(%)"].apply(lambda x: f"{x:.1f}%")
        def clr(val):
            c = {"과소":"color:#DC2626","적정":"color:#16A34A",
                 "다소과다":"color:#D97706","과다":"color:#BE123C"}.get(val,"")
            return f"{c};font-weight:700"
        st.dataframe(
            disp2.style.applymap(clr, subset=["판정"]),
            use_container_width=True, hide_index=True
        )


def _kpi(col, label, value, sub, color):
    col.markdown(f"""
    <div class="metric-card" style="border-top-color:{color}">
        <div class="metric-label">{label}</div>
        <div class="metric-value" style="color:{color}">{value}</div>
        <div class="metric-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)


def _load_chart(line_df, wd_prev, wd_curr):
    df = line_df.sort_values("daily_curr", ascending=False)
    bar_colors = df["load_change"].apply(
        lambda x: "#DC2626" if x > 5 else "#16A34A" if x > -20 else "#2563EB"
    )
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name=f"전월({wd_prev}일)", x=df["line"], y=df["daily_prev"],
        marker_color="#93C5FD", opacity=0.8,
        text=df["daily_prev"].round(0).astype(int), textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name=f"당월({wd_curr}일)", x=df["line"], y=df["daily_curr"],
        marker_color=bar_colors,
        text=df["load_change"].apply(lambda x: f"{x:+.1f}%"), textposition="outside",
    ))
    fig.update_layout(
        barmode="group", height=350,
        margin=dict(t=30,b=10,l=0,r=0),
        yaxis_title="일일 부하량 (개/일)",
        legend=dict(orientation="h", y=1.1),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)


def _util_chart(line_df):
    df = line_df[line_df["capa_daily"] > 0].sort_values("util_curr", ascending=False)
    if df.empty:
        st.info("CAPA 설정된 라인이 없습니다.")
        return

    colors = df["util_curr"].apply(
        lambda x: "#DC2626" if x > 90 else "#D97706" if x > 75 else "#16A34A"
    )
    fig = go.Figure(go.Bar(
        x=df["line"], y=df["util_curr"],
        marker_color=colors,
        text=df["util_curr"].apply(lambda x: f"{x:.1f}%"),
        textposition="outside",
    ))
    fig.add_hline(y=90, line_dash="dash", line_color="#DC2626",
                  annotation_text="위험 (90%)")
    fig.add_hline(y=75, line_dash="dash", line_color="#D97706",
                  annotation_text="주의 (75%)")
    fig.update_layout(
        height=300, margin=dict(t=20,b=10,l=0,r=0),
        yaxis_title="CAPA 가동률 (%)", yaxis_range=[0, 120],
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)
