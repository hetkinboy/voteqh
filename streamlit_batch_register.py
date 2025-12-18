# streamlit_batch_register.py
# Streamlit app for batch registering via: 
# https://eventista-platform-api.1vote.vn/v1/client/auth/register
#
# Usage:
#   pip install streamlit requests pandas
#   streamlit run streamlit_batch_register.py

import streamlit as st
import requests
import time
import io
import csv
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="Batch Register — Beryland", layout="centered")

# === Constants (mặc định, không cần thay đổi) ===
# sub="giaithuongngoisaoxanh"
API_URL_DEFAULT = "https://eventista-platform-api.1vote.vn/v1/client/auth/register"
REDIRECT_TPL_DEFAULT = "https://lansongxanh.1vote.vn/xac-nhan-tai-khoan?registerStatus=1&email={email}"
# Initialize session state
if "running" not in st.session_state:
    st.session_state.running = False
if "stop_flag" not in st.session_state:
    st.session_state.stop_flag = False
if "results" not in st.session_state:
    st.session_state.results = []
if "logs" not in st.session_state:
    st.session_state.logs = []

# Helper: perform POST
def post_register(api_url, payload, timeout):
    try:
        r = requests.post(api_url, json=payload, timeout=timeout)
        return {
            "ok": 200 <= r.status_code < 300,
            "status_code": r.status_code,
            "text": r.text
        }
    except Exception as e:
        return {"ok": False, "status_code": None, "text": str(e)}

# Helper: create CSV bytes
def make_csv_bytes(results):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["email", "status", "http_code", "time_seconds", "timestamp", "response_preview"])
    for r in results:
        writer.writerow([
            r.get("email"),
            r.get("status"),
            r.get("code") if r.get("code") is not None else "",
            r.get("elapsed"),
            r.get("ts"),
            (r.get("resp") or "")[:800].replace("\n", " ")
        ])
    return buf.getvalue().encode("utf-8")

# === UI ===
st.title("✨ Batch Register — Beryland")
st.markdown(
    "Tạo nhiều tài khoản theo dạng `base+<n>@domain` (dùng cho test nội bộ). "
    "API URL và Redirect Template đã được đặt mặc định; bạn không cần thay đổi."
)

with st.form("config_form"):
    col1, col2 = st.columns([2,1])
    with col1:
        st.text_input("API URL (mặc định)", value=API_URL_DEFAULT, key="api_url_display", disabled=True)
        st.text_input("Redirect Path Template (mặc định, dùng {email})", value=REDIRECT_TPL_DEFAULT, key="redirect_display", disabled=False)
        base = st.text_input("Base (phần trước dấu +)", value="mrtienkaza", help="ví dụ: mrtienkaza")
        domain = st.text_input("Domain (không cần @)", value="gmail.com", help="ví dụ: gmail.com")
        password = st.text_input("Password cho tất cả tài khoản", value="123456")
    with col2:
        start_idx = st.number_input("Start index", min_value=0, value=1)
        end_idx = st.number_input("End index", min_value=0, value=100)
        delay_ms = st.number_input("Delay giữa 2 request (ms)", min_value=0, value=2500)
        timeout_s = st.number_input("Timeout request (s)", min_value=1, value=20)

    submitted = st.form_submit_button("Start")

# Stop button outside form
stop_clicked = st.button("Stop", type="secondary")
if stop_clicked:
    st.session_state.stop_flag = True
    st.session_state.running = False
    st.warning("⛔ Stop requested — sẽ dừng sau request đang chạy.")

# Start logic
if submitted and not st.session_state.running:
    # validation
    if end_idx < start_idx:
        st.error("End index phải lớn hơn hoặc bằng Start index.")
    else:
        st.session_state.running = True
        st.session_state.stop_flag = False
        st.session_state.results = []
        st.session_state.logs = []

        total = int(end_idx) - int(start_idx) + 1
        progress = st.progress(0)
        log_area = st.empty()
        info_area = st.empty()

        api_url = API_URL_DEFAULT
        redirect_tpl = REDIRECT_TPL_DEFAULT

        idx = int(start_idx)
        count_done = 0

        try:
            while idx <= int(end_idx):
                # check stop
                if st.session_state.stop_flag:
                    info_area.info("Đã dừng theo yêu cầu.")
                    break

                email = f"{base}+{idx}@{domain}"
                redirect = redirect_tpl.replace("{email}", email)
                payload = {"email": email, "password": password, "redirectPath": redirect}

                info_area.info(f"[{count_done+1}/{total}] Đang gửi register: {email}")
                t0 = time.time()
                res = post_register(api_url, payload, timeout_s)
                t1 = time.time()
                elapsed = round(t1 - t0, 3)

                status_text = "success" if res.get("ok") else "fail"
                code = res.get("status_code")
                resp_text = res.get("text", "")

                # store result
                rec = {
                    "email": email,
                    "status": status_text,
                    "code": code,
                    "elapsed": elapsed,
                    "ts": datetime.utcnow().isoformat(),
                    "resp": resp_text
                }
                st.session_state.results.append(rec)

                # append log
                log_line = f"[{count_done+1}/{total}] {email} -> {status_text} ({code}) [{elapsed}s]"
                st.session_state.logs.append(log_line)

                # update UI
                progress.progress((count_done+1)/total)
                # show last 200 logs
                log_area.text_area("Logs", value="\n".join(st.session_state.logs[-500:]), height=360)

                count_done += 1
                idx += 1

                # delay with stop check in small chunks
                if idx <= int(end_idx):
                    wait_s = float(delay_ms) / 1000.0
                    slept = 0.0
                    chunk = 0.3
                    while slept < wait_s:
                        if st.session_state.stop_flag:
                            break
                        time.sleep(min(chunk, wait_s - slept))
                        slept += min(chunk, wait_s - slept)

                if st.session_state.stop_flag:
                    info_area.info("Stop requested — vòng lặp dừng.")
                    break

            info_area.success("Hoàn tất (hoặc đã dừng).")
        except Exception as e:
            st.error(f"Đã xảy ra lỗi: {e}")
        finally:
            st.session_state.running = False

# Show results and download CSV
if st.session_state.results:
    st.subheader(f"Kết quả ({len(st.session_state.results)})")
    df = pd.DataFrame(st.session_state.results)
    st.dataframe(df[["email", "status", "code", "elapsed", "ts"]])

    csv_bytes = make_csv_bytes(st.session_state.results)
    st.download_button("Tải CSV kết quả", data=csv_bytes,
                       file_name=f"created_{int(time.time())}.csv",
                       mime="text/csv")

    if st.button("Xóa kết quả"):
        st.session_state.results = []
        st.session_state.logs = []
        st.experimental_rerun()

st.markdown("---")
st.caption("Beryland — tươi sáng, dễ thương, gần gũi. Dùng có trách nhiệm nhé 💛")
