"""
app.py — Streamlit 主程式入口

負責：
  1. 從資料庫載入使用者清單，讓使用者在側邊欄選擇帳號
  2. 在側邊欄提供頁面導航（對話 / 單字卡 / 儀表板）
  3. 根據選擇呼叫對應頁面的 show() 函式

Streamlit 多頁面架構說明：
  Streamlit 有兩種多頁面做法：
    A. 官方 pages/ 資料夾自動路由（每個 .py 各自獨立，無法共享 sidebar）
    B. 手動在 app.py 用 sidebar radio 切換，呼叫各頁面的 show() 函式
  本專案用 B 方案，這樣側邊欄的使用者選擇器可以跨頁共用。
"""

import streamlit as st
import pyodbc
from database.queries import get_or_create_default_user
from database.db import get_connection


# ── 判斷是不是「資料庫喚醒中的暫時性連線錯誤」（值得顯示等待畫面並重試）──────
# 這裡自成一個函式（不從 database.db 匯入），避免 Streamlit 熱重載時
# 因為 db.py 尚未重新載入而發生 ImportError。
_DB_WAKING_HINTS = (
    "08001", "HYT00", "HYT01",
    "40613", "40197", "40501", "49918", "49919", "49920",
    "登入逾時", "login timeout", "currently unavailable",
    "無法開啟", "無法建立", "逾時",
)


def _is_db_waking(err: Exception) -> bool:
    msg = str(err)
    return any(hint in msg for hint in _DB_WAKING_HINTS)
import views.chat as chat_page
import views.dino_game as dino_game_page
import views.flashcard as flashcard_page


# ── 頁面基本設定 ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI 日語助教",
    page_icon="🎌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 隱藏 Streamlit 預設的頂部工具列（Stop、Deploy、三點選單）
st.markdown(
    """
    <style>
        /* 隱藏整個頂部 header（含右上角所有圖示） */
        header[data-testid="stHeader"]       { display: none !important; }
        #MainMenu                             { display: none !important; }
        .stDeployButton                       { display: none !important; }
        [data-testid="stStatusWidget"]        { display: none !important; }
        [data-testid="stToolbar"]             { display: none !important; }
        [data-testid="stDecoration"]          { display: none !important; }
        [data-testid="stAppDeployButton"]     { display: none !important; }
        /* Streamlit 1.30+ 的 header 容器 */
        div[class*="appview-container"] > header { display: none !important; }
        /* 隱藏所有輸入框的 "Press Enter to apply" 提示 */
        [data-testid="InputInstructions"] { display: none !important; }

        /* ── 移除「收合側邊欄」功能 ──────────────────────────────
           因為我們把頂部 header 藏起來了，Streamlit「重新展開側邊欄」的箭頭
           也在 header 裡被一起藏住，導致一旦收起就打不開。
           直接把收合鈕拿掉，讓側邊欄永遠固定展開，就不會卡住。 */
        [data-testid="stSidebarCollapseButton"]  { display: none !important; }
        [data-testid="stSidebarCollapsedControl"]{ display: none !important; }
        [data-testid="collapsedControl"]         { display: none !important; }
        /* 保險：強制側邊欄一直顯示、不被收合狀態隱藏 */
        section[data-testid="stSidebar"] {
            display: block !important;
            visibility: visible !important;
            transform: none !important;
        }
        section[data-testid="stSidebar"][aria-expanded="false"] {
            margin-left: 0 !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── 輔助函式：載入所有使用者 ─────────────────────────────────────────────────

@st.cache_data(ttl=30)
def _get_all_users() -> list[dict]:
    """
    從 users 表取得所有使用者，回傳 list of dict。
    @st.cache_data(ttl=30) 表示結果快取 30 秒，避免每次點按都重查資料庫，加快頁面速度。
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name, level, email FROM users ORDER BY user_id")
        rows = cursor.fetchall()
        conn.close()
        return [{"user_id": r[0], "name": r[1], "level": r[2], "email": r[3]} for r in rows]
    except Exception:
        return []


def _find_or_create_user(name: str, level: str, email: str = "") -> dict | None:
    """
    依名字 + 程度找使用者。
    找到 → 若 email 有變更就順便更新，再回傳；找不到 → 自動建立（含 email）再回傳。
    """
    email = email.strip() or None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, name, level, email FROM users WHERE name = ? AND level = ?",
            name, level
        )
        row = cursor.fetchone()
        if row:
            user_id, existing_email = row[0], row[3]
            if email != existing_email:
                cursor.execute(
                    "UPDATE users SET email = ? WHERE user_id = ?", email, user_id
                )
                conn.commit()
                _get_all_users.clear()
            conn.close()
            return {"user_id": user_id, "name": row[1], "level": row[2], "email": email}

        # 不存在則建立
        cursor.execute(
            "INSERT INTO users (name, level, email) OUTPUT INSERTED.user_id VALUES (?, ?, ?)",
            name, level, email
        )
        new_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        _get_all_users.clear()
        return {"user_id": new_id, "name": name, "level": level, "email": email}
    except Exception as e:
        st.error(f"操作失敗：{e}")
        return None


# ── 啟動時確保至少有一個使用者（只執行一次，結果快取到 server 關閉）────────
@st.cache_resource
def _ensure_default_user():
    get_or_create_default_user()


def _loading_overlay_html(icon: str, title: str, subtitle: str = "") -> str:
    """
    組出置中的全螢幕載入 / 喚醒畫面 HTML。

    注意：回傳的 HTML 每一行都必須「齊左、不縮排」。
    因為 st.markdown() 會先跑一次 Markdown 解析，若某行以 4 個以上空白開頭，
    會被當成「程式碼區塊」，導致像 </div> 這種結尾標籤被當成純文字顯示在灰底框裡。
    """
    sub = (
        f"<div style=\"font-size:0.95rem; color:#aaa; margin-top:14px; line-height:1.6;\">{subtitle}</div>"
        if subtitle else ""
    )
    style = (
        "<style>"
        'header[data-testid="stHeader"],'
        '[data-testid="stStatusWidget"],'
        '[data-testid="stToolbar"],'
        '[data-testid="stDecoration"],'
        '[data-testid="stAppDeployButton"],'
        "#MainMenu,.stDeployButton{display:none !important;}"
        "@keyframes ja-pulse{0%,100%{opacity:1;}50%{opacity:0.35;}}"
        "</style>"
    )
    overlay = (
        '<div style="position:fixed;inset:0;display:flex;justify-content:center;'
        'align-items:center;background:var(--background-color,#0e1117);z-index:9999;">'
        '<div style="text-align:center;max-width:420px;padding:0 24px;">'
        f'<div style="font-size:4rem;margin-bottom:20px;animation:ja-pulse 1.4s ease-in-out infinite;">{icon}</div>'
        f'<div style="font-size:1.6rem;font-weight:700;color:#fff;letter-spacing:0.05em;">{title}</div>'
        f"{sub}"
        "</div></div>"
    )
    return style + overlay


# 第一次載入時顯示置中提示，避免空白頁面讓人以為當機。
# 若 Azure SQL Free tier 正在從暫停喚醒（db.py 已自動重試仍未醒），
# 就顯示友善的「喚醒中」畫面並自動再試一次，而不是噴紅色 traceback。
if "app_loaded" not in st.session_state:
    placeholder = st.empty()
    placeholder.markdown(
        _loading_overlay_html("🎌", "連線中請稍後"),
        unsafe_allow_html=True,
    )
    try:
        _ensure_default_user()
        _get_all_users()
        placeholder.empty()
        st.session_state.app_loaded = True
    except Exception:
        # 資料庫仍在喚醒（閒置自動暫停），顯示友善畫面後自動重試
        placeholder.markdown(
            _loading_overlay_html(
                "⏳",
                "喚醒資料庫中，請稍候…",
                "雲端資料庫閒置後會自動休眠，第一次連線需要 1～2 分鐘喚醒。<br>"
                "畫面會自動重試，不用重新整理。",
            ),
            unsafe_allow_html=True,
        )
        import time as _time
        _time.sleep(8)
        st.rerun()


# ── 側邊欄 ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎌 AI 日語助教")
    # 隱藏標記：Streamlit 套件的 index.html 會偵測這個元素出現才移除
    # 「連線中請稍後」載入畫面，確保 overlay 一路撐到 app 真正的內容 render 出來
    st.markdown('<div id="ja-app-ready" style="display:none"></div>', unsafe_allow_html=True)
    st.divider()

    # ── 使用者輸入區 ──────────────────────────────────────────────────────────
    st.markdown("#### 👤 學習者")

    input_name = st.text_input(
        "名字",
        value=st.session_state.get("user_name", ""),
        placeholder="輸入你的名字",
        label_visibility="collapsed",
    )
    input_level = st.radio(
        "程度",
        options=["N5", "N4"],
        index=0 if st.session_state.get("user_level", "N5") == "N5" else 1,
        horizontal=True,
        label_visibility="collapsed",
    )
    input_email = st.text_input(
        "Email",
        value=st.session_state.get("user_email") or "",
        placeholder="Gmail（用來收單字小恐龍日誌）",
        label_visibility="collapsed",
    )

    if st.button("✅ 開始學習", use_container_width=True):
        if input_name.strip():
            user = _find_or_create_user(input_name.strip(), input_level, input_email)
            if user:
                is_new_user = st.session_state.get("user_id") != user["user_id"]
                st.session_state.user_id = user["user_id"]
                st.session_state.user_name = user["name"]
                st.session_state.user_level = user["level"]
                st.session_state.user_email = user["email"]
                if is_new_user:
                    for key in ["messages", "tutor", "cards", "card_index", "show_answer", "last_result"]:
                        st.session_state.pop(key, None)
                st.rerun()
        else:
            st.warning("請輸入名字")

    # ── 目前登入狀態 ──────────────────────────────────────────────────────────
    if "user_id" in st.session_state:
        level = st.session_state.user_level
        badge_color = "#2e86de" if level == "N5" else "#8e44ad"
        email_hint = st.session_state.get("user_email") or "尚未設定"
        st.markdown(
            f"<div style='margin-top:8px; font-size:0.85rem; color:gray;'>目前：</div>"
            f"<span style='background:{badge_color}; color:white; padding:3px 12px; "
            f"border-radius:12px; font-size:0.9rem;'>"
            f"{st.session_state.user_name} &nbsp;{level}</span>"
            f"<div style='margin-top:6px; font-size:0.8rem; color:gray;'>📧 {email_hint}</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── 頁面導航 ─────────────────────────────────────────────────────────────
    page = st.radio(
        "📌 選擇頁面",
        options=["💬 AI 對話練習", "🃏 單字卡", "🦖 單字小恐龍"],
        label_visibility="collapsed",
    )


# ── 主區域：根據選擇渲染對應頁面 ─────────────────────────────────────────────

# 尚未輸入名字並按「開始學習」前，user_id 不存在，顯示引導畫面
if "user_id" not in st.session_state:
    st.markdown(
        "<div style='text-align:center; padding: 120px 0;'>"
        "<div style='font-size:3rem;'>🎌</div>"
        "<div style='font-size:1.5rem; margin-top:16px;'>請在左側輸入名字並選擇程度</div>"
        "<div style='font-size:1rem; color:gray; margin-top:8px;'>按下「✅ 開始學習」即可進入</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

uid = st.session_state.user_id
uname = st.session_state.user_name
ulevel = st.session_state.user_level

# 用 try/except 包住頁面渲染：若使用中資料庫剛好從閒置暫停被喚醒（db.py 重試仍未醒），
# 就顯示友善的「喚醒中」畫面並自動重試，而不是讓整頁跳出紅色 traceback。
# 只攔截「喚醒中的暫時性連線錯誤」，其他錯誤照常拋出以便 debug。
try:
    if page == "💬 AI 對話練習":
        chat_page.show(user_id=uid, user_name=uname, user_level=ulevel)

    elif page == "🦖 單字小恐龍":
        dino_game_page.show(user_id=uid, user_level=ulevel)

    elif page == "🃏 單字卡":
        flashcard_page.show(user_id=uid, user_level=ulevel)

except pyodbc.Error as e:
    if _is_db_waking(e):
        st.markdown(
            _loading_overlay_html(
                "⏳",
                "喚醒資料庫中，請稍候…",
                "雲端資料庫閒置後會自動休眠，正在重新連線。<br>"
                "畫面會自動重試，不用重新整理。",
            ),
            unsafe_allow_html=True,
        )
        import time as _time
        _time.sleep(8)
        st.rerun()
    else:
        raise
