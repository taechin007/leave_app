# file: leave_app.py

import streamlit as st
import pandas as pd
from fpdf import FPDF
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from io import BytesIO
import json

# --- Google Sheets Setup ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("EmployeeLeaveRecords").worksheet("Records")
name_sheet = client.open("EmployeeLeaveRecords").worksheet("EmployeeNames")

# --- Helper Functions ---
def get_employee_names():
    names = [row[0] for row in name_sheet.get_all_values()[1:] if row and row[0]]
    return ["-กรุณาเลือก-"] + names

def get_remaining_leave_by_type(name):
    df = pd.DataFrame(sheet.get_all_records())
    person_df = df[df['ชื่อ'] == name].copy()
    person_df['จำนวนวันลา'] = pd.to_numeric(person_df['จำนวนวันลา'], errors='coerce')
    totals = {'ลาพักร้อน': 10, 'ลาป่วย': 30, 'ลากิจ': 6}
    used = person_df.groupby('ประเภทการลา')['จำนวนวันลา'].sum().to_dict()
    remaining = {k: totals[k] - used.get(k, 0) for k in totals}
    return remaining

def get_latest_leave(name):
    df = pd.DataFrame(sheet.get_all_records())
    person_df = df[df['ชื่อ'] == name]
    if person_df.empty:
        return "ยังไม่มีประวัติการลา"
    return person_df.iloc[-1].to_dict()

def get_leave_history_filtered(name, year, month):
    df = pd.DataFrame(sheet.get_all_records())
    df = df[df['ชื่อ'] == name].copy()
    df['วันที่เริ่ม'] = pd.to_datetime(df['วันที่เริ่ม'], errors='coerce')
    df = df.dropna(subset=['วันที่เริ่ม'])
    df = df[df['วันที่เริ่ม'].dt.year == year]
    if month != 'ทั้งหมด':
        df = df[df['วันที่เริ่ม'].dt.month == int(month)]
    return df

def calculate_leave_days(start, end, type_leave, start_time=None, end_time=None):
    if type_leave == "รายชั่วโมง":
        fmt = "%H:%M"
        time_start = datetime.datetime.strptime(start_time, fmt)
        time_end = datetime.datetime.strptime(end_time, fmt)
        hours = (time_end - time_start).seconds / 3600
        return round(hours / 8, 2)
    elif "ครึ่งวัน" in type_leave:
        return 0.5
    return (end - start).days + 1

def create_pdf(data):
    def thai_date(date_str):
        months = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.day} {months[dt.month]} {dt.year + 543}"

    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("THSarabunNew", "", "./font/THSarabunNew.ttf", uni=True)
    pdf.set_font("THSarabunNew", size=16)

    pdf.image("./logo/logo.jpeg", x=(210 - 30) / 2, y=10, w=30)
    pdf.ln(40)

    pdf.set_font_size(18)
    pdf.cell(0, 10, "บริษัท ทีไอ การบัญชีและกฎหมาย จำกัด", ln=True, align="C")
    pdf.set_font_size(12)
    pdf.cell(0, 10, "เอกสารใช้สำหรับภายในบริษัทเท่านั้น", ln=True, align="C")

    pdf.set_font_size(16)
    pdf.cell(0, 10, "ใบคำขอลาหยุดงาน", ln=True, align="C")
    pdf.set_draw_color(0, 0, 0)
    pdf.line(10, pdf.get_y() + 1, 200, pdf.get_y() + 1)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(15)

    pdf.set_font_size(16)
    col_width = 50
    for key, value in data.items():
        if "วันที่" in key and value:
            try:
                value = thai_date(value)
            except:
                pass
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(col_width, 10, key, border=1, fill=True)
        if key == "เหตุผล":
            pdf.multi_cell(0, 10, str(value), border=1)
        else:
            pdf.cell(0, 10, str(value), border=1, ln=True)

    pdf.ln(20)
    pdf.cell(0, 10, "ลงชื่อ.......................................................", ln=True, align="R")
    pdf.cell(0, 10, "(ผู้ขอลา)", ln=True, align="R")
    pdf.ln(15)
    pdf.cell(0, 10, "ลงชื่อ.......................................................", ln=True, align="R")
    pdf.cell(0, 10, "(ผู้อนุมัติ)", ln=True, align="R")

    pdf_output = BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return pdf_output

def save_to_sheet(data):
    sheet.append_row(list(data.values()))

# Expand sidebar width using HTML style
st.markdown("""
<style>
    section[data-testid="stSidebar"] {
        width: 400px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar Section: Leave History Viewer ---
st.sidebar.title("📁 ดูประวัติการลา")
names = get_employee_names()
sidebar_name = st.sidebar.selectbox("เลือกชื่อพนักงาน", names, key="sidebar_name")

if sidebar_name != "-กรุณาเลือก-":
    st.sidebar.markdown("---\n### 📊 สิทธิการลาคงเหลือ")
    remaining_by_type = get_remaining_leave_by_type(sidebar_name)
    for leave_type, days_left in remaining_by_type.items():
        st.sidebar.write(f"{leave_type}: {days_left} วัน")

    st.sidebar.markdown("---\n### 📌 การลาครั้งล่าสุด")
    latest = get_latest_leave(sidebar_name)
    if isinstance(latest, dict):
        keys_to_show = ["ชื่อ", "ลาเป็น", "ประเภทการลา", "วันที่เริ่ม", "คิดเป็นจำนวนวันลา", "เหตุผล"]
        for key in keys_to_show:
            if key in latest:
                st.sidebar.write(f"{key}: {latest[key]}")
    else:
        st.sidebar.write(latest)

    st.sidebar.markdown("---\n### 🗓️ ดูประวัติการลาทั้งหมด ตามช่วงเวลา")
    this_year = datetime.datetime.now().year
    years = list(range(this_year - 5, this_year + 1))
    months = ['ทั้งหมด'] + [str(i) for i in range(1, 13)]
    selected_year = st.sidebar.selectbox("ปี", years[::-1])
    selected_month = st.sidebar.selectbox("เดือน", months)

    history_df = get_leave_history_filtered(sidebar_name, selected_year, selected_month)
    if not history_df.empty:
        st.sidebar.dataframe(history_df)
    else:
        st.sidebar.info("ไม่พบข้อมูลการลา")

# --- Main Section: Leave Form ---

st.markdown(
    """
    <div style='color:red; font-size:16px; font-weight:bold;'>
    ***หมายเหตุ: ความสำเร็จของงานเป็นสิ่งสำคัญ***<br>
    กรุณาวางเเผนการลาของท่าน ควบคู่กับการวางเเผนการทำงานให้เสร็จตามกำหนด
    </div>
    """,
    unsafe_allow_html=True
)
st.title("📝 แบบฟอร์มการลา")
ชื่อ = st.selectbox("ชื่อ", names, key="main_name")
ลาเป็น = st.radio("ลาเป็น", ["เต็มวัน", "ครึ่งวันเช้า", "ครึ่งวันบ่าย", "รายชั่วโมง"])
ประเภทการลา = st.selectbox("ประเภทการลา", ["ลาพักร้อน", "ลาป่วย", "ลากิจ"])
start_date = st.date_input("วันที่เริ่ม")
end_date = st.date_input("วันที่สิ้นสุด")
reason = st.text_area("เหตุผลการลา")

start_time = end_time = ""
if ลาเป็น == "รายชั่วโมง":
    start_time = st.time_input("เวลาเริ่มลา", value=datetime.time(8, 30)).strftime("%H:%M")
    end_time = st.time_input("เวลาสิ้นสุดลา", value=datetime.time(17, 30)).strftime("%H:%M")
else:
    if ลาเป็น == "ครึ่งวันเช้า":
        start_time, end_time = "08:30", "12:00"
    elif ลาเป็น == "ครึ่งวันบ่าย":
        start_time, end_time = "13:00", "17:30"
    else:
        start_time, end_time = "08:30", "17:30"

is_valid = True
if ชื่อ == "-กรุณาเลือก-":
    st.warning("กรุณาเลือกชื่อพนักงานก่อนส่งแบบฟอร์ม")
    is_valid = False

if start_date < datetime.date.today():
    st.warning("วันที่เริ่มต้องเป็นวันนี้หรือในอนาคต")
    is_valid = False

if end_date < start_date:
    st.warning("วันที่สิ้นสุดต้องตรงหรือหลังจากวันที่เริ่ม")
    is_valid = False

if ประเภทการลา == "ลากิจ" and (start_date - datetime.date.today()).days < 3:
    st.warning("วันลากิจต้องส่งลาล่วงหน้าอย่างน้อย 3 วัน")
    is_valid = False

if is_valid and st.button("ส่งแบบฟอร์ม"):
    leave_days = calculate_leave_days(start_date, end_date, ลาเป็น, start_time, end_time)

    submission = {
        "ชื่อ": ชื่อ,
        "ลาเป็น": ลาเป็น,
        "ประเภทการลา": ประเภทการลา,
        "วันที่เริ่ม": str(start_date),
        "วันที่สิ้นสุด": str(end_date),
        "เวลาเริ่มลา": start_time,
        "เวลาสิ้นสุดลา": end_time,
        "คิดเป็นจำนวนวันลา": leave_days,
        "เหตุผล": reason,
        "เวลาส่ง": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    save_to_sheet(submission)
    pdf = create_pdf(submission)
    st.success("ส่งแบบฟอร์มเรียบร้อยแล้ว")

    filename = f"leave_form_{submission['ชื่อ']}_{submission['เวลาส่ง'].replace(':', '').replace(' ', '_')}.pdf"
    st.download_button(label="📄 ดาวน์โหลดแบบฟอร์ม PDF", data=pdf, file_name=filename)
