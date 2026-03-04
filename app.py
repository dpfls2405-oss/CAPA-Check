import streamlit as st
import pandas as pd

# 앱 제목 및 설정
st.set_page_config(page_title="시디즈 평택 재고/CAPA 점검 시스템", layout="wide")
st.title("📦 시디즈(평택) 통합 재고 점검 및 CAPA 분석")

# 1. 데이터 업로드 섹션 (사이드바)
with st.sidebar:
    st.header("파일 업로드")
    scp_file = st.file_uploader("다음달 SCP 계획 업로드", type=['xlsx', 'csv'])
    line_perf_file = st.file_uploader("라인별 생산실적 업로드", type=['xlsx', 'csv'])
    item_perf_file = st.file_uploader("품목별 생산실적 업로드", type=['xlsx', 'csv'])
    
    working_days = st.number_input("차월 영업일수 설정", value=21)

# 2. 데이터 처리 및 분석 로직
if scp_file and line_perf_file and item_perf_file:
    # 데이터 로드 (예시)
    df_scp = pd.read_excel(scp_file)
    df_line = pd.read_excel(line_perf_file)
    df_item = pd.read_excel(item_perf_file)

    # [로직 계산] 
    # 1. 라인별 부하 계산 (Daily Load)
    df_line['daily_load'] = df_line['target_qty'] / working_days
    
    # 2. 재고 적정성 계산
    # (HTML 로직 참고: 익월 목표 / 2주치 실적)
    # df_item['ratio'] = (df_item['next_target'] / df_item['half_actual']) * 100

    # 3. 화면 구성 (Tabs)
    tab1, tab2 = st.tabs(["📊 재고 과부족 점검", "⚡ 라인 CAPA 분석"])

    with tab1:
        st.subheader("품목별 재고 건전성")
        # 데이터프레임 시각화 (조건부 서식 적용 가능)
        st.dataframe(df_item.style.background_gradient(subset=['ratio'], cmap='RdYlGn_r'))

    with tab2:
        st.subheader("라인별 생산 부하 현황")
        # 차트 또는 지표로 표시
        for index, row in df_line.iterrows():
            col1, col2 = st.columns([1, 3])
            col1.metric(row['line_name'], f"{row['daily_load']:.1f}대/일")
            col2.progress(min(row['daily_load'] / 100, 1.0), text=f"부하율: {row['daily_load']}%")

else:
    st.info("사이드바에서 SCP 계획 및 실적 파일을 업로드해주세요.")
    # 기본 예시 데이터나 도움말 표시
