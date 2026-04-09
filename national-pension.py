import re
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

# Graph labels are kept in English to avoid font issues on deployment.
plt.rcParams["axes.unicode_minus"] = False


class PensionData:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.pattern1 = r"(\([^)]+\))"
        self.pattern2 = r"(\[[^)]+\])"
        self.pattern3 = r"[^A-Za-z0-9가-힣]"
        self.preprocess()

    def preprocess(self):
        self.df.columns = [
            "자료생성년월", "사업장명", "사업자등록번호", "가입상태", "우편번호",
            "사업장지번상세주소", "주소", "고객법정동주소코드", "고객행정동주소코드",
            "시도코드", "시군구코드", "읍면동코드",
            "사업장형태구분코드 1 법인 2 개인", "업종코드", "업종코드명",
            "적용일자", "재등록일자", "탈퇴일자",
            "가입자수", "금액", "신규", "상실"
        ]

        df = self.df.drop(
            [
                "자료생성년월",
                "우편번호",
                "사업장지번상세주소",
                "고객법정동주소코드",
                "고객행정동주소코드",
                "사업장형태구분코드 1 법인 2 개인",
                "적용일자",
                "재등록일자",
            ],
            axis=1,
        ).copy()

        df["사업장명"] = df["사업장명"].astype(str).apply(self.clean_company_name)
        df["탈퇴일자"] = pd.to_datetime(df["탈퇴일자"], errors="coerce")
        df["탈퇴일자_연도"] = df["탈퇴일자"].dt.year
        df["탈퇴일자_월"] = df["탈퇴일자"].dt.month
        df["시도"] = df["주소"].astype(str).str.split(" ").str[0]

        df = df.loc[df["가입상태"] == 1].drop(["가입상태", "탈퇴일자"], axis=1).reset_index(drop=True)

        df["가입자수"] = pd.to_numeric(df["가입자수"], errors="coerce")
        df["금액"] = pd.to_numeric(df["금액"], errors="coerce")
        df["신규"] = pd.to_numeric(df["신규"], errors="coerce")
        df["상실"] = pd.to_numeric(df["상실"], errors="coerce")

        df = df[df["가입자수"] > 0].copy()

        df["인당금액"] = df["금액"] / df["가입자수"]
        df["월급여추정"] = df["인당금액"] / 9 * 100
        df["연간급여추정"] = df["월급여추정"] * 12

        self.df = df

    def clean_company_name(self, x):
        x = re.sub(self.pattern1, "", x)
        x = re.sub(self.pattern2, "", x)
        x = re.sub(self.pattern3, " ", x)
        x = re.sub(" +", " ", x).strip()
        return x

    def find_company(self, company_name):
        return (
            self.df.loc[
                self.df["사업장명"].str.contains(company_name, case=False, na=False),
                ["사업장명", "월급여추정", "연간급여추정", "업종코드", "가입자수"],
            ]
            .sort_values("가입자수", ascending=False)
            .reset_index(drop=True)
        )

    def compare_company(self, company_name):
        company = self.find_company(company_name)
        code = company["업종코드"].iloc[0]

        df1 = self.df.loc[self.df["업종코드"] == code, ["월급여추정", "연간급여추정"]].agg(
            ["mean", "count", "min", "max"]
        )
        df1.columns = ["업종_월급여추정", "업종_연간급여추정"]
        df1 = df1.T
        df1.columns = ["평균", "개수", "최소", "최대"]
        df1.loc["업종_월급여추정", company_name] = company["월급여추정"].values[0]
        df1.loc["업종_연간급여추정", company_name] = company["연간급여추정"].values[0]
        return df1

    def company_info(self, company_name):
        company = self.find_company(company_name)
        return self.df.loc[company.index[0]]

    def get_data(self):
        return self.df


import gdown
import os

@st.cache_data
def read_pensiondata():
    file_id = "1itux9CgrEj7oJSXIgJZiaXhn4yfdfPYD"
    output = "national-pension.csv"

    if not os.path.exists(output):
        gdown.download(
            f"https://drive.google.com/uc?id={file_id}",
            output,
            quiet=False
        )

    df = pd.read_csv(output, encoding="cp949")
    return PensionData(df)


st.set_page_config(page_title="National Pension Salary Search", layout="wide")

st.title("National Pension Salary Search")

data = read_pensiondata()
company_name = st.text_input("회사명을 입력해 주세요", placeholder="검색할 회사명 입력")

if data and company_name:
    output = data.find_company(company_name=company_name)

    if len(output) > 0:
        top_company_name = output.iloc[0]["사업장명"]
        st.subheader(top_company_name)

        info = data.company_info(company_name=company_name)
        st.markdown(
            f"""
- `{info['주소']}`
- 업종코드명 `{info['업종코드명']}`
- 총 근무자 `{int(info['가입자수']):,}` 명
- 신규 입사자 `{int(info['신규']):,}` 명
- 퇴사자 `{int(info['상실']):,}` 명
"""
        )

        col1, col2, col3 = st.columns(3)
        col1.text("Monthly Salary Estimate")
        col1.markdown(f"`{int(output.iloc[0]['월급여추정']):,}` 원")

        col2.text("Yearly Salary Estimate")
        col2.markdown(f"`{int(output.iloc[0]['연간급여추정']):,}` 원")

        col3.text("Employee Count")
        col3.markdown(f"`{int(output.iloc[0]['가입자수']):,}` 명")

        st.dataframe(output.round(0), use_container_width=True)

        comp_output = data.compare_company(company_name=company_name)
        st.dataframe(comp_output.round(0), use_container_width=True)

        st.markdown(f"### Industry Average vs {top_company_name}")

        percent_value = info["월급여추정"] / comp_output.iloc[0, 0] * 100 - 100
        diff_month = abs(comp_output.iloc[0, 0] - info["월급여추정"])
        diff_year = abs(comp_output.iloc[1, 0] - info["연간급여추정"])
        upordown = "higher" if percent_value > 0 else "lower"

        st.markdown(
            f"""
- 업종 **평균 월급여**는 `{int(comp_output.iloc[0, 0]):,}` 원, **평균 연봉**은 `{int(comp_output.iloc[1, 0]):,}` 원 입니다.
- `{top_company_name}`는 평균보다 `{int(diff_month):,}` 원, `{abs(percent_value):.2f}%` {upordown} 수준의 월급여로 추정됩니다.
- `{top_company_name}`는 평균보다 `{int(diff_year):,}` 원 {upordown} 수준의 연봉으로 추정됩니다.
"""
        )

        fig, ax = plt.subplots(1, 2, figsize=(10, 4))

        p1 = ax[0].bar(
            x=["Average", "Your Company"],
            height=(comp_output.iloc[0, 0], info["월급여추정"]),
            width=0.7,
        )
        ax[0].bar_label(p1, fmt="%.0f")
        ax[0].set_title("Monthly Salary")

        p2 = ax[1].bar(
            x=["Average", "Your Company"],
            height=(comp_output.iloc[1, 0], info["연간급여추정"]),
            width=0.7,
        )
        ax[1].bar_label(p2, fmt="%.0f")
        ax[1].set_title("Yearly Salary")

        ax[0].tick_params(axis="both", which="major", labelsize=8)
        ax[1].tick_params(axis="both", which="major", labelsize=8)

        st.pyplot(fig)

        st.markdown("### Similar Companies")
        df = data.get_data()
        st.dataframe(
            df.loc[
                df["업종코드"] == info["업종코드"],
                ["사업장명", "월급여추정", "연간급여추정", "가입자수"],
            ]
            .sort_values("연간급여추정", ascending=False)
            .head(10)
            .round(0),
            use_container_width=True,
        )

    else:
        st.subheader("검색결과가 없습니다")
