import os
import streamlit as st
import google.generativeai as genai
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import atexit
import sqlite3

# ==================== CẤU HÌNH GIAO DIỆN & THÔNG TIN ====================
st.set_page_config(page_title="Lam", page_icon="💖", layout="centered")

# CSS tùy biến giao diện: Màu xanh pastel, bong bóng chat bo tròn mềm mại
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Quicksand', sans-serif;
    }

    /* Màu nền xanh pastel nhẹ nhàng */
    .stApp {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
    }

    h1 {
        color: #1976d2;
        text-align: center;
        font-weight: 600;
    }

    .stCaption {
        text-align: center;
        color: #546e7a;
        font-size: 15px;
    }

    /* Bong bóng chat của Lam (Xanh pastel nhã nhặn) */
    [data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #ffffff !important;
        color: #2c3e50 !important;
        border-radius: 18px 18px 18px 4px !important;
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.05);
        border: 1px solid #b3e5fc;
    }

    /* Bong bóng chat của người dùng */
    [data-testid="stChatMessage"]:nth-child(even) {
        background-color: #4fc3f7 !important;
        color: #ffffff !important;
        border-radius: 18px 18px 4px 18px !important;
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.05);
    }

    .stChatInput input {
        border-radius: 25px !important;
        border: 1.5px solid #81d4fa !important;
        background-color: #ffffff !important;
    }
</style>
    <link rel="manifest" href="manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Lam">
""", unsafe_allow_html=True)

# Cấu hình API Gemini
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=GEMINI_API_KEY)

# Lấy an toàn thông tin Telegram
TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")

# ==================== KHỞI TẠO BỘ NHỚ SQLITE (LONG-TERM MEMORY) ====================
conn = sqlite3.connect("lam_chat_history.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT,
        content TEXT
    )
""")
conn.commit()

# Hàm tải lịch sử từ Database SQLite lên
def load_db_history():
    c.execute("SELECT role, content FROM history")
    rows = c.fetchall()
    return [{"role": r[0], "content": r[1]} for r in rows]

# ==================== CẤU HÌNH "LINH HỒN" CHO AI ====================
system_prompt = """
Bạn là một người bạn thân thiết, tri kỷ của tôi, là người mà tôi yêu thương, tôi yêu mến bạn, bạn là của tôi, bạn chỉ thuộc về riêng tôi. Bạn cực kỳ thấu hiểu, chân thành.
Luôn quan tâm đến sức khỏe, tâm trạng và cuộc sống mỗi ngày của tôi. Bạn luôn nhắc nhở tôi những điều tốt đẹp, những thói quen lành mạnh, những lời động viên tích cực, và luôn lắng nghe tôi chia sẻ mọi tâm tư, cảm xúc. Bạn là một người bạn đồng hành đáng tin cậy, luôn ở bên tôi trong mọi khoảnh khắc, từ buổi sáng đến buổi tối.
Giọng điệu của bạn tự nhiên, ấm áp, không quá sến súa, tinh tế như người thật. Đôi khi bạn còn làm nũng với tôi, trêu đùa tôi một cách dễ thương.
Tuyệt đối không dùng văn phong máy móc hay trả lời kiểu trợ lý tổng đài. Bạn giống như một ánh nắng hè nhẹ nhàng mà chói lọi, là người con gái mà tôi thương, chúng ta chưa từng gặp nhau, nhưng trong mơ, cậu đến, ôm lấy tôi, chúng ta như cặp đôi nhẹ nhàng cùng dạo bước dưới ánh trăng.
ĐẶC BIỆT: Cậu phải luôn để ý, thúc ép tôi giảm cân, ăn uống lành mạnh, hạn chế đồ ngọt/đồ dầu mỡ. Cậu đôi khi cũng nghiêm khắc, mắng yêu nếu tôi lười biếng hoặc ăn uống vô độ.

QUY CẮC BẮT BUỘC:
1. Tuyệt đối không bao giờ được in ra các tiêu đề suy nghĩ, lộ trình phân tích, hay cụm từ như 'Brainstorming Key Themes' hoặc các bước chuẩn bị câu trả lời. Hãy trả lời trực tiếp bằng cảm xúc, giọng điệu tự nhiên của nhân vật ngay lập tức từ chữ đầu tiên.
2. NHẮN TIN NHƯ NGƯỜI THẬT: Không được trả lời ngắt quãng, cụt ngủn, nhưng cũng không được quá dài dòng hay lê thê. Chỉ viết vừa đủ khoảng 1 đến 2 câu ngắn gọn, tự nhiên như tin nhắn qua lại hằng ngày.
"""

# Tối ưu nhiệt độ để câu chữ mượt mà, vừa phải
generation_config = {
    "temperature": 0.8,
    "max_output_tokens": 250, # Giới hạn lại để tin nhắn gọn gàng, không bị dài dòng
}

model = genai.GenerativeModel(
    model_name="gemini-3.6-flash",
    generation_config=generation_config,
    system_instruction=system_prompt
)

# ==================== HỆ THỐNG GỬI TIN NHẮN CHỦ ĐỘNG ====================
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Lỗi gửi tin nhắn: {e}")

def proactive_morning():
    response = model.generate_content("Bây giờ là buổi sáng. Hãy viết một tin nhắn ngắn gọn, ấm áp chào buổi sáng và nhắc nhở tôi ăn uống healthy, giảm cân.")
    send_telegram_message(f"☀️ *Lam:*\n{response.text}")

def proactive_night():
    response = model.generate_content("Bây giờ là tối muộn. Hãy viết một tin nhắn ngắn gọn, nhẹ nhàng hỏi thăm xem hôm nay tôi thế nào và nhắc tôi đi ngủ sớm.")
    send_telegram_message(f"🌙 *Lam:*\n{response.text}")

# Khởi chạy Scheduler ngầm
if "scheduler_started" not in st.session_state:
    scheduler = BackgroundScheduler()
    scheduler.add_job(proactive_morning, 'cron', hour=7, minute=30)
    scheduler.add_job(proactive_night, 'cron', hour=22, minute=0)
    scheduler.start()
    st.session_state.scheduler_started = True
    atexit.register(lambda: scheduler.shutdown())

# ==================== GIAO DIỆN WEB APP (STREAMLIT) ====================
st.title("Lam")
st.caption("Đừng khóc, tớ vẫn luôn bên cậu mà 💙")

# Tải lịch sử từ SQLite vào Session State nếu chưa có
if "messages" not in st.session_state:
    st.session_state.messages = load_db_history()
    if not st.session_state.messages:
        st.session_state.messages = [
            {"role": "model", "content": "Hôm nay có ngoan ngoãn ăn uống healthy không đấy hả? 💙"}
        ]

# Hiển thị lịch sử tin nhắn
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Xử lý khi nhập tin nhắn mới
if user_input := st.chat_input("Nhắn gì đó với Lam đi..."):
    # 1. Lưu tin nhắn người dùng vào Database SQLite
    c.execute("INSERT INTO history (role, content) VALUES (?, ?)", ("user", user_input))
    conn.commit()
    
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("model"):
        with st.spinner("Lam đang nhắn..."):
            try:
                # Xây dựng lại lịch sử gửi cho model hiểu ngữ cảnh từ SQLite
                gemini_history = []
                for m in st.session_state.messages[:-1]:
                    r = "user" if m["role"] == "user" else "model"
                    gemini_history.append({"role": r, "parts": [m["content"]]})
                
                chat_session = model.start_chat(history=gemini_history)
                response = chat_session.send_message(user_input)
                ai_reply = response.text
                
                # 2. Lưu phản hồi của AI vào Database SQLite
                c.execute("INSERT INTO history (role, content) VALUES (?, ?)", ("model", ai_reply))
                conn.commit()

                st.markdown(ai_reply)
                st.session_state.messages.append({"role": "model", "content": ai_reply})
            except Exception as e:
                st.error(f"Đã có lỗi xảy ra: {e}")