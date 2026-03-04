"""
parser.py — SCP / 생산실적 / 출고량 파일 파싱 유틸리티
"""
import io
import re
import pandas as pd
import numpy as np
from typing import Optional

# ────────────────────────────────────────────
# 포장라인 매핑 (조합코드 접두어 → 포장라인)
# ────────────────────────────────────────────
# 기존 분석에서 확인된 매핑 (사용자가 UI에서 수정 가능)
DEFAULT_LINE_MAP = {
    # 단품코드 접두어: 포장라인
    "G10": "가죽", "G20": "T40_FKD", "GC": "가죽",
    "T80": "T80", "T90": "T80",
    "T61": "TC13(조립5)", "T60": "TC13(조립5)",
    "S60": "T50-2", "CHA4301": "T50-2",
    "CHA4300": "T50-1",
    "S40": "M02", "DHMN": "M02", "MN0": "M02", "UCHNA": "M02",
    "CH001": "도장(외부출고)", "CH0015": "도장(외부출고)",
    "HCH29": "플라이트", "TXNA": "플라이트", "DHT3": "플라이트", "CH48": "플라이트",
    "CH002": "후레임2", "DHM1": "후레임2", "DHM7": "후레임2",
    "UCHN": "후레임3", "HCH30": "후레임3",
    "CHN62": "벌크", "CHA62": "벌크", "TNB": "벌크", "TNA": "벌크",
    "CHN64": "TC13(조립5)", "CHN65": "TC13(조립5)",
    "CHN42": "TC13(조립5)", "CHN43": "TC13(조립5)",
    "CHN47": "T80",
    "CH49": "T40_FKD",
    "CHN67": "T40_FKD",
    "CH53": "T55", "CHN08": "T55", "CHN33": "가죽",
    "CH34": "가죽", "CH43": "T55",
    "S51": "부품포장", "S50": "부품포장", "S00": "부품포장",
    "HCX": "부품포장", "HCH00": "부품포장", "T00": "부품포장",
    "T61X": "부품포장",
    "S509": "A/S포장", "FH": "A/S포장",
    "PCOT": "T40-2_F", "CHN62": "T40-2_F",
    "ITY": "T40-2_F",
    "VTNF": "벌크",
}

LINES_ALL = sorted(set(DEFAULT_LINE_MAP.values()))

# 포장라인별 기본 CAPA (일/일) — 사용자 설정으로 덮어쓰기 가능
DEFAULT_CAPA = {
    "도장(외부출고)": 300, "벌크": 250, "T50-2": 200,
    "부품포장": 400, "TC13(조립5)": 200, "T40_FKD": 150,
    "M02": 150, "T80": 120, "후레임2": 200,
    "T55": 120, "후레임3": 180, "T50-1": 150,
    "플라이트": 120, "T40-2_F": 100, "가죽": 80, "A/S포장": 50,
}

def get_line(combo: str, custom_map: dict = None) -> str:
    """조합코드로 포장라인 추정"""
    m = custom_map or DEFAULT_LINE_MAP
    code = combo.split("-")[0]
    # 긴 접두어부터 매칭
    for length in range(min(8, len(code)), 1, -1):
        prefix = code[:length]
        if prefix in m:
            return m[prefix]
    return "미분류"


# ────────────────────────────────────────────
# SCP 파싱
# ────────────────────────────────────────────
def parse_scp(file_bytes: bytes, filename: str,
              sheet_hint: str = "시디즈") -> Optional[pd.DataFrame]:
    """
    SCP xlsx 파싱.
    반환: combo, name, series, supplier, grade,
          tgt_prev(전월), tgt_curr(당월), tgt_next(익월),
          avg12m(최근1년평출)
    """
    try:
        xl = pd.ExcelFile(io.BytesIO(file_bytes))
    except Exception as e:
        return None, f"파일 열기 실패: {e}"

    # 시디즈 의자 SCP 시트 찾기
    sheet = None
    for s in xl.sheet_names:
        if sheet_hint in s and "의자" in s:
            sheet = s
            break
    if sheet is None:
        for s in xl.sheet_names:
            if sheet_hint in s:
                sheet = s
                break
    if sheet is None:
        return None, f"시트를 찾을 수 없습니다. 시트 목록: {xl.sheet_names}"

    raw = xl.parse(sheet, header=None, dtype=str)

    # 헤더 행 탐지 (단품코드 or 운영코드조합 포함 행)
    header_row = None
    combo_col = None
    name_col = None
    for i in range(min(5, len(raw))):
        row = raw.iloc[i].tolist()
        for j, v in enumerate(row):
            if str(v).strip() in ("운영코드조합", "코드조합"):
                header_row = i
                combo_col = j
            if str(v).strip() == "단품명칭(한글)":
                name_col = j

    if header_row is None:
        return None, "SCP 헤더 구조를 인식하지 못했습니다."

    headers = [str(v).strip() for v in raw.iloc[header_row]]

    # 목표재고(예상기말재고) 컬럼 위치 탐지
    # row(header_row-1)에 월 정보가 있는 경우가 많음
    month_row = header_row - 1 if header_row > 0 else None
    month_labels = {}
    if month_row is not None:
        for j, v in enumerate(raw.iloc[month_row]):
            s = str(v).strip()
            m = re.search(r"(\d+)월", s)
            if m:
                month_labels[j] = int(m.group(1))

    # 예상기말재고 컬럼 찾기 (월 순서대로)
    tgt_cols = {}
    for j, h in enumerate(headers):
        if "예상기말재고" in h and "검증" not in h and "금액" not in h:
            mon = month_labels.get(j)
            if mon:
                tgt_cols[mon] = j

    # 최근1년평출 컬럼
    avg12_col = None
    for j, h in enumerate(headers):
        if "최근1년평출" in h and "금액" not in h:
            avg12_col = j
            break

    # 공급업체 컬럼
    supplier_col = None
    for j, h in enumerate(headers):
        if "공급업체" in h:
            supplier_col = j
            break

    # 공급단 컬럼
    supply_unit_col = None
    for j, h in enumerate(headers):
        if h == "공급단":
            supply_unit_col = j
            break

    # 시리즈 컬럼
    series_col = None
    for j, h in enumerate(headers):
        if "시리즈" in h:
            series_col = j
            break

    data_rows = raw.iloc[header_row + 1:].copy()
    data_rows = data_rows[data_rows.iloc[:, combo_col].notna()]
    data_rows = data_rows[~data_rows.iloc[:, combo_col].isin(["nan", "", "운영코드조합", "코드조합"])]

    records = []
    for _, row in data_rows.iterrows():
        combo = str(row.iloc[combo_col]).strip()
        if not combo or combo == "nan":
            continue
        name = str(row.iloc[name_col]).strip() if name_col is not None else "-"
        series = str(row.iloc[series_col]).strip() if series_col is not None else "-"
        supplier = str(row.iloc[supplier_col]).strip() if supplier_col is not None else "-"
        supply_unit = str(row.iloc[supply_unit_col]).strip() if supply_unit_col is not None else "-"
        avg12m = _to_num(row.iloc[avg12_col]) if avg12_col is not None else 0

        tgts = {}
        for mon, col in tgt_cols.items():
            tgts[f"tgt_{mon:02d}"] = _to_num(row.iloc[col])

        records.append({
            "combo": combo, "name": name, "series": series,
            "supplier": supplier, "supply_unit": supply_unit,
            "avg12m": avg12m,
            **tgts,
        })

    df = pd.DataFrame(records)
    return df, None


# ────────────────────────────────────────────
# 출고량(실적) CSV 파싱
# ────────────────────────────────────────────
def parse_shipment_csv(file_bytes: bytes) -> tuple:
    """
    그룹사_의자_출고량 CSV 파싱.
    반환: DataFrame(combo, name, brand, supplier, 월별 컬럼들...)
    """
    for enc in ["utf-16", "utf-8-sig", "cp949"]:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding=enc,
                             sep="\t", dtype=str, header=None)
            if df.shape[1] > 5:
                break
        except Exception:
            continue
    else:
        return None, "파일 인코딩을 인식하지 못했습니다."

    # 1행이 헤더
    raw_headers = [str(v).strip() for v in df.iloc[0]]
    df = df.iloc[1:].copy()
    df.columns = raw_headers
    df = df[df["CODE"].notna() & (df["CODE"] != "CODE")].copy()

    # 월 컬럼 탐지: YYYY년 MM월 → yyyymm
    month_cols = {}
    for col in df.columns:
        m = re.match(r"(\d{4})년\s*(\d+)월", col)
        if m:
            key = f"{m.group(1)}{int(m.group(2)):02d}"
            month_cols[col] = key

    df.rename(columns=month_cols, inplace=True)
    numeric_cols = list(month_cols.values())
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    df.rename(columns={"CODE": "combo", "단품명(최신)": "name",
                        "브랜드": "brand", "공급처(최신) (그룹)": "supplier"}, inplace=True)
    df["combo"] = df["combo"].str.strip()
    keep = ["combo", "name", "brand", "supplier"] + numeric_cols
    df = df[[c for c in keep if c in df.columns]].copy()
    return df, None


# ────────────────────────────────────────────
# 생산실적 파싱 (라인별 / 품목별)
# ────────────────────────────────────────────
def parse_production(file_bytes: bytes, filename: str) -> tuple:
    """
    생산실적 Excel/CSV 파싱.
    기대 컬럼: 포장라인, 조합코드(or combo), 생산수량, 일자(or 연월)
    반환: DataFrame(line, combo, qty, date or yyyymm)
    """
    fname = filename.lower()
    try:
        if fname.endswith(".csv"):
            for enc in ["utf-8-sig", "cp949", "utf-16"]:
                try:
                    df = pd.read_csv(io.BytesIO(file_bytes), encoding=enc, dtype=str)
                    break
                except Exception:
                    continue
        else:
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
    except Exception as e:
        return None, f"파일 열기 실패: {e}"

    # 컬럼 표준화
    col_map = {}
    for col in df.columns:
        c = str(col).strip()
        if any(k in c for k in ["포장라인", "라인", "LINE", "Line"]):
            col_map[col] = "line"
        elif any(k in c for k in ["조합코드", "COMBO", "combo", "단품코드"]):
            col_map[col] = "combo"
        elif any(k in c for k in ["생산수량", "수량", "QTY", "qty", "실적"]):
            col_map[col] = "qty"
        elif any(k in c for k in ["일자", "날짜", "DATE", "date", "연월", "기간"]):
            col_map[col] = "date"
    df.rename(columns=col_map, inplace=True)

    required = {"line", "qty"}
    missing = required - set(df.columns)
    if missing:
        return None, f"필수 컬럼 없음: {missing}. 현재 컬럼: {df.columns.tolist()}"

    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0)
    if "combo" not in df.columns:
        df["combo"] = "-"
    if "date" not in df.columns:
        df["date"] = "미지정"

    df["line"] = df["line"].str.strip()
    df["combo"] = df["combo"].str.strip()
    return df, None


# ────────────────────────────────────────────
# 재고 적정성 계산 엔진
# ────────────────────────────────────────────
def calc_adequacy(scp_df: pd.DataFrame,
                  shipment_df: pd.DataFrame,
                  prev_month_col: str,    # e.g. "202602"
                  curr_month_tgt: str,    # e.g. "tgt_03"
                  prev_month_tgt: str,    # e.g. "tgt_02"
                  line_map: dict = None,
                  filter_supplier: str = None) -> pd.DataFrame:
    """
    재고 적정성 계산.
    - 2주치 기준 = 전월 실적 / 2
    - 비율 = 당월 목표재고 / 2주치 * 100
    - 판정: <80 과소 / 80~120 적정 / 120~200 다소과다 / >200 과다
    """
    if filter_supplier:
        scp_df = scp_df[scp_df["supplier"] == filter_supplier].copy()

    # 출고량 집계 (combo 기준 합산)
    num_cols = [c for c in shipment_df.columns
                if re.match(r"^\d{6}$", c)]
    ship_agg = shipment_df.groupby("combo")[num_cols].sum().reset_index()

    # SCP와 출고량 병합
    df = scp_df.merge(ship_agg, on="combo", how="left")
    df[num_cols] = df[num_cols].fillna(0)

    # 전월 실적
    if prev_month_col in df.columns:
        df["actual_prev"] = df[prev_month_col]
    else:
        df["actual_prev"] = 0

    # 2주치 기준
    df["half_actual"] = (df["actual_prev"] / 2).round(0).astype(int)

    # 당월/전월 목표재고
    df["tgt_curr"] = pd.to_numeric(df.get(curr_month_tgt, 0), errors="coerce").fillna(0)
    df["tgt_prev"] = pd.to_numeric(df.get(prev_month_tgt, 0), errors="coerce").fillna(0)
    df["delta"]    = df["tgt_curr"] - df["tgt_prev"]

    # 비율 계산
    df["ratio"] = np.where(
        df["half_actual"] > 0,
        (df["tgt_curr"] / df["half_actual"] * 100).round(1),
        np.where(df["tgt_curr"] > 0, 999.0, 0.0)
    )
    df["excess"] = df["tgt_curr"] - df["half_actual"]

    # 판정
    def judge(r):
        if r < 80:   return "과소"
        if r <= 120: return "적정"
        if r <= 200: return "다소과다"
        return "과다"
    df["label"] = df["ratio"].apply(judge)

    # 포장라인 매핑
    df["line"] = df["combo"].apply(lambda c: get_line(c, line_map))

    # 최근 3개월 평출 계산 (prev_month_col 기준 3개월)
    prev_ym = int(prev_month_col)
    months_3 = _prev_months(prev_ym, 3)
    months_12 = _prev_months(prev_ym, 12)

    cols_3  = [str(m) for m in months_3  if str(m) in df.columns]
    cols_12 = [str(m) for m in months_12 if str(m) in df.columns]

    df["avg3m"]  = df[cols_3].mean(axis=1).round(1)  if cols_3  else 0
    df["avg12m"] = df[cols_12].mean(axis=1).round(1) if cols_12 else 0

    return df


def calc_line_summary(item_df: pd.DataFrame,
                      wd_prev: int, wd_curr: int,
                      capa_map: dict = None) -> pd.DataFrame:
    """
    라인별 집계 (재고 적정성 + 부하량 + CAPA 여유)
    """
    capa = capa_map or DEFAULT_CAPA
    grp = item_df.groupby("line").agg(
        n_items   = ("combo", "nunique"),
        tgt_prev  = ("tgt_prev", "sum"),
        tgt_curr  = ("tgt_curr", "sum"),
        actual_prev = ("actual_prev", "sum"),
        half_actual = ("half_actual", "sum"),
        n_under   = ("label", lambda x: (x == "과소").sum()),
        n_ok      = ("label", lambda x: (x == "적정").sum()),
        n_over    = ("label", lambda x: x.isin(["다소과다","과다"]).sum()),
    ).reset_index()

    grp["delta"] = grp["tgt_curr"] - grp["tgt_prev"]
    grp["delta_rate"] = (grp["delta"] / grp["tgt_prev"].replace(0, np.nan) * 100).round(1)
    grp["ratio"] = np.where(
        grp["half_actual"] > 0,
        (grp["tgt_curr"] / grp["half_actual"] * 100).round(1), 0
    )
    grp["label"] = grp["ratio"].apply(
        lambda r: "과소" if r < 80 else "적정" if r <= 120
        else "다소과다" if r <= 200 else "과다"
    )
    grp["daily_prev"] = (grp["tgt_prev"] / wd_prev).round(1)
    grp["daily_curr"] = (grp["tgt_curr"] / wd_curr).round(1)
    grp["load_change"] = (
        (grp["daily_curr"] - grp["daily_prev"])
        / grp["daily_prev"].replace(0, np.nan) * 100
    ).round(1)

    # CAPA 대비 가동률
    grp["capa_daily"] = grp["line"].map(capa).fillna(0)
    grp["util_prev"]  = np.where(
        grp["capa_daily"] > 0,
        (grp["daily_prev"] / grp["capa_daily"] * 100).round(1), np.nan
    )
    grp["util_curr"]  = np.where(
        grp["capa_daily"] > 0,
        (grp["daily_curr"] / grp["capa_daily"] * 100).round(1), np.nan
    )
    return grp


# ────────────────────────────────────────────
# 헬퍼
# ────────────────────────────────────────────
def _to_num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return 0.0

def _prev_months(yyyymm: int, n: int) -> list:
    """n개월 이전까지의 yyyymm 리스트 (내림차순)"""
    result = []
    y, m = divmod(yyyymm, 100)
    for _ in range(n):
        result.append(y * 100 + m)
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return result

LABEL_COLOR = {
    "과소":   ("#FEE2E2", "#DC2626"),
    "적정":   ("#DCFCE7", "#16A34A"),
    "다소과다": ("#FEF9C3", "#D97706"),
    "과다":   ("#FFE4E6", "#BE123C"),
}
