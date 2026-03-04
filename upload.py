"""
upload.py — 파일 업로드 및 세션 초기화
"""
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.parser import (
    parse_scp, parse_shipment_csv, parse_production,
    calc_adequacy, calc_line_summary,
    DEFAULT_LINE_MAP, DEFAULT_CAPA, LINES_ALL
)


def show():
    st.markdown('<div class="section-header">📂 데이터 업로드</div>', unsafe_allow_html=True)
    st.markdown("분석에 필요한 파일 3종을 업로드하세요. 매월 새 파일로 교체하면 자동 재계산됩니다.")

    # ── 기본 설정 ──
    with st.expander("⚙️ 분석 기준 설정", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            base_month = st.text_input("기준월 (YYYYMM)", value="202603",
                                        help="분석 대상 월 (당월 SCP 기준)")
        with col2:
            wd_prev = st.number_input("전월 영업일", min_value=1, max_value=31,
                                       value=19, step=1)
        with col3:
            wd_curr = st.number_input("당월 영업일", min_value=1, max_value=31,
                                       value=21, step=1)
        with col4:
            supplier_filter = st.selectbox("공급업체 필터",
                ["시디즈제품", "전체"], index=0)

    # ── 파일 업로드 ──
    st.markdown("---")
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.markdown("#### 1️⃣ SCP 계획 파일")
        st.caption("시디즈 의자 SCP xlsx (월별 목표재고 포함)")
        scp_file = st.file_uploader("SCP 파일 업로드", type=["xlsx", "xls"],
                                     key="scp_upload",
                                     label_visibility="collapsed")
        if scp_file:
            st.success(f"✅ {scp_file.name}")

    with col_b:
        st.markdown("#### 2️⃣ 출고량 실적 파일")
        st.caption("그룹사_의자_출고량 CSV (월별 출고 실적)")
        ship_file = st.file_uploader("출고량 파일 업로드", type=["csv", "txt"],
                                      key="ship_upload",
                                      label_visibility="collapsed")
        if ship_file:
            st.success(f"✅ {ship_file.name}")

    with col_c:
        st.markdown("#### 3️⃣ 생산실적 파일 (선택)")
        st.caption("라인별/품목별 생산실적 xlsx or csv")
        prod_file = st.file_uploader("생산실적 파일 업로드",
                                      type=["xlsx", "xls", "csv"],
                                      key="prod_upload",
                                      label_visibility="collapsed")
        if prod_file:
            st.success(f"✅ {prod_file.name}")

    # ── 포장라인 매핑 설정 ──
    with st.expander("🗺️ 포장라인 매핑 설정 (고급)", expanded=False):
        st.caption("단품코드 접두어 → 포장라인 매핑. 기본값을 사용하거나 직접 수정하세요.")
        st.info("형식: 접두어,포장라인  (한 줄에 하나씩)")
        default_text = "\n".join(f"{k},{v}" for k, v in DEFAULT_LINE_MAP.items())
        line_map_text = st.text_area("매핑 규칙", value=default_text, height=200)

        # CAPA 설정
        st.markdown("**포장라인별 일일 CAPA (개/일)**")
        capa_cols = st.columns(4)
        capa_inputs = {}
        for i, (line, cap) in enumerate(DEFAULT_CAPA.items()):
            with capa_cols[i % 4]:
                capa_inputs[line] = st.number_input(
                    line, value=cap, min_value=0, step=10, key=f"capa_{line}")

    # ── 분석 실행 ──
    st.markdown("---")
    run_btn = st.button("🚀 분석 실행", type="primary", use_container_width=True)

    if run_btn:
        if not scp_file:
            st.error("SCP 파일은 필수입니다.")
            return
        if not ship_file:
            st.error("출고량 파일은 필수입니다.")
            return

        with st.spinner("데이터 파싱 중..."):
            # 1. 라인 매핑 파싱
            custom_map = {}
            for line in line_map_text.strip().split("\n"):
                parts = line.strip().split(",")
                if len(parts) == 2:
                    custom_map[parts[0].strip()] = parts[1].strip()

            # 2. SCP 파싱
            scp_bytes = scp_file.read()
            scp_df, scp_err = parse_scp(scp_bytes, scp_file.name)
            if scp_err:
                st.error(f"SCP 파싱 오류: {scp_err}")
                return

            # 3. 출고량 파싱
            ship_bytes = ship_file.read()
            ship_df, ship_err = parse_shipment_csv(ship_bytes)
            if ship_err:
                st.error(f"출고량 파싱 오류: {ship_err}")
                return

            # 4. 생산실적 파싱 (선택)
            prod_df = None
            if prod_file:
                prod_bytes = prod_file.read()
                prod_df, prod_err = parse_production(prod_bytes, prod_file.name)
                if prod_err:
                    st.warning(f"생산실적 파싱 경고: {prod_err}")
                    prod_df = None

            # 5. 분석 기준 컬럼명 설정
            bm = base_month  # e.g. "202603"
            prev_m = _prev_month_str(bm)  # e.g. "202602"
            prev_tgt_col = f"tgt_{prev_m[4:]}"   # e.g. "tgt_02"
            curr_tgt_col = f"tgt_{bm[4:]}"         # e.g. "tgt_03"

            # 6. 재고 적정성 계산
            sf = supplier_filter if supplier_filter != "전체" else None
            item_df = calc_adequacy(
                scp_df=scp_df,
                shipment_df=ship_df,
                prev_month_col=prev_m,
                curr_month_tgt=curr_tgt_col,
                prev_month_tgt=prev_tgt_col,
                line_map=custom_map,
                filter_supplier=sf,
            )

            # 7. 라인별 요약
            line_df = calc_line_summary(
                item_df, wd_prev=wd_prev, wd_curr=wd_curr,
                capa_map=capa_inputs
            )

            # 8. 세션 저장
            st.session_state.session = {
                "loaded": True,
                "base_month": bm,
                "prev_month": prev_m,
                "wd_prev": wd_prev,
                "wd_curr": wd_curr,
                "supplier_filter": supplier_filter,
                "n_lines": len(line_df),
                "n_items": len(item_df),
                "item_df": item_df,
                "line_df": line_df,
                "prod_df": prod_df,
                "ship_df": ship_df,
                "capa_map": capa_inputs,
            }

        st.success(f"✅ 분석 완료! 품목 {len(item_df)}개 / 포장라인 {len(line_df)}개")

        # 미리보기
        st.markdown("### 📋 파싱 결과 미리보기")
        t1, t2 = st.tabs(["SCP 데이터", "출고량 데이터"])
        with t1:
            st.dataframe(scp_df.head(10), use_container_width=True)
        with t2:
            st.dataframe(ship_df.head(10), use_container_width=True)

        st.info("👈 왼쪽 메뉴에서 분석 탭으로 이동하세요.")

    # ── 파일 포맷 안내 ──
    with st.expander("📌 생산실적 파일 포맷 안내"):
        st.markdown("""
        생산실적 파일은 아래 컬럼을 포함해야 합니다 (컬럼명 유사하면 자동 인식):

        | 컬럼 | 필수 | 예시 |
        |------|------|------|
        | 포장라인 | ✅ | T80, 부품포장 |
        | 조합코드 | 권장 | T80HLDA1KK-456BK |
        | 생산수량 | ✅ | 120 |
        | 일자 / 연월 | 권장 | 2026-03-01, 202603 |

        - Excel(xlsx) 또는 CSV(utf-8) 모두 지원
        - 라인별 집계 파일 / 품목별 일일 파일 모두 가능
        """)


def _prev_month_str(yyyymm: str) -> str:
    y, m = int(yyyymm[:4]), int(yyyymm[4:])
    m -= 1
    if m == 0:
        m = 12; y -= 1
    return f"{y}{m:02d}"
