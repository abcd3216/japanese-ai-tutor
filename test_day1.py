"""
test_day1.py
Day 1 整合測試腳本。
依序測試：資料庫連線、Gemini API、寫入對話紀錄、讀取對話紀錄。
"""

from database.db import get_connection
from database.queries import save_chat_message, get_chat_history
from tutor.gemini_chat import JapaneseTutor

print("=" * 50)
print("  Day 1 整合測試")
print("=" * 50)

# ── 測試 1：Azure SQL 連線 ────────────────────────
print("\n【測試 1】Azure SQL 連線")
try:
    conn = get_connection()
    conn.close()
    print("✅ 資料庫連線成功")
except Exception as e:
    print(f"❌ 資料庫連線失敗：{e}")
    exit(1)  # 資料庫連不上就直接停止，後面的測試沒意義

# ── 測試 2：Gemini API ────────────────────────────
print("\n【測試 2】Gemini API 對話")
try:
    tutor = JapaneseTutor()
    reply = tutor.chat("你好，請用繁體中文回覆我，說一句鼓勵學日文的話。")
    print(f"✅ Gemini 回應成功：\n{reply}")
except Exception as e:
    print(f"❌ Gemini API 失敗：{e}")
    exit(1)

# ── 測試 3：寫入對話紀錄到 chat_history ──────────
print("\n【測試 3】寫入對話紀錄")
try:
    # 先確認 users 表裡有 user_id=1，沒有的話先建一個
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE user_id = 1")
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.execute(
            "INSERT INTO users (name, level) VALUES (N'測試學習者', 'N5')"
        )
        conn.commit()
        print("  → 建立測試使用者 user_id=1")
    conn.close()

    # 寫入一筆使用者訊息
    save_chat_message(
        user_id=1,
        role="user",
        content="你好，請用繁體中文回覆我，說一句鼓勵學日文的話。"
    )
    # 寫入一筆 AI 回應
    save_chat_message(
        user_id=1,
        role="model",
        content=reply
    )
    print("✅ 對話紀錄寫入成功（2 筆）")
except Exception as e:
    print(f"❌ 寫入對話紀錄失敗：{e}")
    exit(1)

# ── 測試 4：讀取對話紀錄 ─────────────────────────
print("\n【測試 4】讀取對話紀錄")
try:
    history = get_chat_history(user_id=1, limit=5)
    if len(history) > 0:
        print(f"✅ 讀取成功，共 {len(history)} 筆紀錄：")
        for row in history:
            content_preview = row['content'][:30] + "..." if len(row['content']) > 30 else row['content']
            print(f"   [{row['role']}] {content_preview}")
    else:
        print("❌ 沒有讀到任何紀錄，請確認 save_chat_message 有正常執行")
except Exception as e:
    print(f"❌ 讀取對話紀錄失敗：{e}")
    exit(1)

# ── 全部通過 ──────────────────────────────────────
print("\n" + "=" * 50)
print("  ✅ Day 1 所有測試通過！可以繼續 Day 2。")
print("=" * 50)
