
# SIDIZ Pyeongtaek Inventory & CAPA Check

Streamlit 기반 재고 과부족 및 라인 CAPA 점검 앱

## 실행방법
pip install -r requirements.txt
streamlit run app.py

## 입력 데이터
data_templates 폴더의 템플릿을 다운로드하여 사용

- item_master_template.xlsx
- scp_plan_template.xlsx
- production_actual_template.xlsx

## 주요 기능
- 라인별 재고 적정성 판정
- 품목별 과부족 분석
- CAPA 후보 자동 추출
