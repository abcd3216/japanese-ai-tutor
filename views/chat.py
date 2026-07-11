"""
pages/chat.py — AI 日語對話練習頁面

使用者可以和小葵老師（Gemini）用日文／中文對話，
固定啟用 RAG 文法知識庫，讓文法解釋更準確有依據。
"""

import base64
import json
import os
import re
import streamlit as st
import streamlit.components.v1 as components
from database.queries import get_chat_history, save_chat_message
from tutor.gemini_chat import JapaneseTutor


# 朗讀前先清掉會被念成「星號、井號」的 markdown 符號與 emoji
_SPEECH_STRIP = re.compile(r"[*#`_~>|]|📚|✨|🌸|😊|👆|🔊|🎉|💭|—|｜")


def _clean_for_speech(text: str) -> str:
    return _SPEECH_STRIP.sub("", text).strip()


def _speak_button(text: str):
    """在 AI 訊息下方放一個 🔊 朗讀鈕（用 components.html 才能真的觸發語音）。
    用瀏覽器內建語音念（zh-TW），中日混合會用中文音念，屬環境限制。"""
    payload = json.dumps(_clean_for_speech(text))  # 轉成 JS 安全字串
    html = f"""
    <button id="spk" onclick="speak()" style="
        background:transparent; border:1px solid #c0392b; color:#c0392b;
        border-radius:14px; padding:2px 12px; font-size:0.8rem; cursor:pointer;
        font-family:'Segoe UI','Microsoft JhengHei',sans-serif;">
      🔊 朗讀
    </button>
    <script>
      function speak() {{
        if (!window.speechSynthesis) return;
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance({payload});
        u.lang = "zh-TW";
        u.rate = 1.0;
        window.speechSynthesis.speak(u);
      }}
    </script>
    """
    components.html(html, height=40)


# 小葵老師角色頭像圖：assets/images/tutor.jpg
_AVATAR_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "images", "tutor.jpg"
)


@st.cache_data(show_spinner=False)
def _avatar_data_uri() -> str:
    """把角色頭像讀成 base64 data URI（快取，只讀一次）。找不到檔案就回空字串。"""
    try:
        with open(_AVATAR_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return ""


def _avatar_html(size: int = 46) -> str:
    """回傳小葵老師頭像的 <img> HTML；沒有圖片時退回櫻花 emoji。"""
    uri = _avatar_data_uri()
    if not uri:
        return f"<div style='font-size:{size/28:.1f}rem;'>🌸</div>"
    return (
        f"<img class='ja-avatar' src='{uri}' "
        f"style='width:{size}px;height:{size}px;' alt='小葵老師' />"
    )


# ── st.session_state 說明 ──────────────────────────────────────────────────
# Streamlit 每次使用者做任何互動（按按鈕、送出訊息），整個 Python 腳本都會
# 從頭重新執行。如果不把聊天記錄存進 st.session_state，每次重跑畫面就清空了。
#
# 我們用 session_state 儲存：
#   messages  — 目前顯示在畫面上的對話列表（role + content）
#   tutor     — JapaneseTutor 物件，保留對話上下文，避免每次重建
# ─────────────────────────────────────────────────────────────────────────────


def _load_history_from_db(user_id: int) -> list[dict]:
    """從 Azure SQL 讀取最近 10 筆對話紀錄，轉成畫面用的格式。"""
    rows = get_chat_history(user_id=user_id, limit=10)
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def _ai_bubble_html(content: str) -> str:
    """AI 訊息的漫畫對話框 HTML（抽出來給靜態顯示和串流顯示共用）。"""
    return f"""
    <div style='
        background: #ffffff;
        color: #1a1a1a;
        padding: 14px 20px;
        border-radius: 22px 22px 22px 6px;
        border: 3px solid #1a1a1a;
        box-shadow: 5px 5px 0px #c0392b;
        font-size: 0.95rem;
        line-height: 1.7;
        margin: 10px 0;
    '>{content}</div>
    """


def _display_message(role: str, content: str):
    """
    顯示一則對話訊息（漫畫對話框風格）：
    - 使用者訊息 → 靠右，藍底白字，粗黑框 + 紅色陰影
    - AI 訊息    → 靠左，白底深字，粗黑框 + 紅色陰影
    """
    if role == "user":
        safe = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        _, col = st.columns([2, 3])
        with col:
            st.markdown(
                f"""
                <div style='
                    background: #3a86e8;
                    color: white;
                    padding: 12px 18px;
                    border-radius: 22px 22px 6px 22px;
                    border: 3px solid #1a1a1a;
                    box-shadow: 5px 5px 0px #b03060;
                    font-size: 0.95rem;
                    line-height: 1.7;
                    margin: 10px 0;
                    word-break: break-word;
                    font-weight: 500;
                '>{safe}</div>
                """,
                unsafe_allow_html=True,
            )
    else:
        icon_col, msg_col, _ = st.columns([0.05, 0.72, 0.23])
        with icon_col:
            st.markdown(
                f"<div style='padding-top:6px;'>{_avatar_html(46)}</div>",
                unsafe_allow_html=True,
            )
        with msg_col:
            st.markdown(_ai_bubble_html(content), unsafe_allow_html=True)
            _speak_button(content)


def show(user_id: int = 1, user_name: str = "學習者", user_level: str = "N5"):
    """
    AI 對話頁面入口。app.py 呼叫 chat.show(user_id, user_name, user_level)。
    """

    st.title("🌸 小葵老師")

    # 小葵老師頭像樣式：圓形 + 紅框 + 輕微上下浮動（呼吸般的生命感）
    st.markdown(
        """
        <style>
          .ja-avatar {
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid #c0392b;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            animation: ja-float 3s ease-in-out infinite;
            display: block;
          }
          @keyframes ja-float {
            0%, 100% { transform: translateY(0); }
            50%      { transform: translateY(-5px); }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── 側邊欄 ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"### 👤 {user_name}")
        st.markdown(f"程度：**{user_level}**")
        st.divider()

        if st.button("🗑️ 清除對話紀錄", use_container_width=True):
            # 只清除畫面上的紀錄，不刪除資料庫內容
            st.session_state.messages = []
            if "tutor" in st.session_state:
                st.session_state.tutor.clear_history()
            st.rerun()

    # ── 初始化 session_state ─────────────────────────────────────────────────
    if "messages" not in st.session_state:
        # 第一次進入頁面：從資料庫載入最近的對話紀錄
        st.session_state.messages = _load_history_from_db(user_id)

    if "tutor" not in st.session_state:
        # 建立 JapaneseTutor 物件，傳入使用者程度，讓 AI 調整說明深度與 RAG 範圍
        st.session_state.tutor = JapaneseTutor(level=user_level)

    # ── 顯示對話記錄 ─────────────────────────────────────────────────────────
    chat_container = st.container()
    with chat_container:
        if not st.session_state.messages:
            st.markdown(
                "<div style='text-align:center; color:gray; padding:50px 0;'>"
                f"<div style='display:flex; justify-content:center; margin-bottom:14px;'>{_avatar_html(96)}</div>"
                "你好！我是小葵老師，有什麼日語問題都可以問我喔！"
                "</div>",
                unsafe_allow_html=True,
            )
        for msg in st.session_state.messages:
            _display_message(msg["role"], msg["content"])

    # ── 輸入區 ───────────────────────────────────────────────────────────────
    st.divider()
    with st.form(key="chat_form", clear_on_submit=True):
        col_input, col_btn = st.columns([5, 1])
        with col_input:
            user_input = st.text_input(
                label="訊息",
                placeholder="請輸入你的問題...",
                label_visibility="collapsed",
                key="chat_input",
            )
        with col_btn:
            send = st.form_submit_button("送出", use_container_width=True)

    # ── 送出邏輯 ─────────────────────────────────────────────────────────────
    if send and user_input.strip():
        # 1. 先把使用者訊息加入畫面 + 資料庫
        st.session_state.messages.append({"role": "user", "content": user_input})
        save_chat_message(user_id=user_id, role="user", content=user_input)

        # 2. 用「串流」方式即時顯示 AI 回覆：Gemini 一段一段吐出文字，
        #    畫面就跟著一段一段更新，不用像以前整段生成完才一次顯示，
        #    使用者馬上就能看到老師開始打字，體感速度快很多。
        with chat_container:
            _display_message("user", user_input)
            icon_col, msg_col, _ = st.columns([0.05, 0.72, 0.23])
            with icon_col:
                st.markdown(
                    f"<div style='padding-top:6px;'>{_avatar_html(46)}</div>",
                    unsafe_allow_html=True,
                )
            with msg_col:
                placeholder = st.empty()
                placeholder.markdown(_ai_bubble_html("💭 思考中..."), unsafe_allow_html=True)

                tutor: JapaneseTutor = st.session_state.tutor
                full_reply = ""
                for chunk_text in tutor.chat_with_rag_stream(user_input):
                    full_reply += chunk_text
                    placeholder.markdown(_ai_bubble_html(full_reply), unsafe_allow_html=True)

        # 3. 把完整的 AI 回應存進畫面紀錄跟資料庫
        st.session_state.messages.append({"role": "model", "content": full_reply})
        save_chat_message(user_id=user_id, role="model", content=full_reply)

        # 4. 重新渲染頁面，讓這則對話正式併入歷史紀錄裡
        st.rerun()
