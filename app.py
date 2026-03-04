
import streamlit as st
import pandas as pd
import yaml
from src.logic import judge_ratio

st.set_page_config(page_title="SIDIZ Pyeongtaek Inventory & CAPA", layout="wide")

st.title("📦 시디즈 평택 재고 점검 & CAPA 시스템")

# Load settings
with open("config/settings.yaml","r",encoding="utf-8") as f:
    settings = yaml.safe_load(f)

coverage_days = settings["coverage_days"]
low_th = settings["low_threshold"]
high_th = settings["high_threshold"]
over_th = settings["over_threshold"]

st.sidebar.header("기준 설정")
st.sidebar.write(f"기준 소진일수: {coverage_days}일")

# Upload files
master_file = st.file_uploader("품목 마스터 업로드", type=["xlsx","csv"])
plan_file = st.file_uploader("SCP 계획 업로드", type=["xlsx","csv"])
actual_file = st.file_uploader("생산실적 업로드", type=["xlsx","csv"])

def read_any(file):
    if file is None:
        return None
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

master = read_any(master_file)
plan = read_any(plan_file)
actual = read_any(actual_file)

if master is None or plan is None or actual is None:
    st.info("파일을 모두 업로드하면 계산이 시작됩니다.")
    st.stop()

# 최근 실적 평균 계산
actual["date"] = pd.to_datetime(actual["date"])
daily_avg = actual.groupby("item_code", as_index=False)["actual_qty"].mean()
daily_avg["baseline_qty"] = daily_avg["actual_qty"] * coverage_days

# 다음달 계획
plan_sum = plan.groupby(["line","item_code"], as_index=False)["plan_qty"].sum()
plan_sum.rename(columns={"plan_qty":"target_qty"}, inplace=True)

df = plan_sum.merge(master, on="item_code", how="left")
df = df.merge(daily_avg[["item_code","baseline_qty"]], on="item_code", how="left")

df["ratio"] = (df["target_qty"] / df["baseline_qty"]) * 100
df["status"] = df["ratio"].apply(lambda r: judge_ratio(r, low_th, high_th, over_th))

st.subheader("라인별 요약")
line_summary = df.groupby("line").agg(
    target_qty=("target_qty","sum"),
    baseline_qty=("baseline_qty","sum")
).reset_index()

line_summary["ratio"] = (line_summary["target_qty"]/line_summary["baseline_qty"])*100
line_summary["status"] = line_summary["ratio"].apply(lambda r: judge_ratio(r, low_th, high_th, over_th))

st.dataframe(line_summary, use_container_width=True)

st.subheader("품목 상세")
st.dataframe(df, use_container_width=True)
