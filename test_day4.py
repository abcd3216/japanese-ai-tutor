"""
test_day4.py — Day 4 整合測試

測試項目：
  1. 所有套件可正常 import
  2. Azure SQL 連線正常
  3. ChromaDB 索引存在
  4. Gemini API 有回應
  5. 資料庫至少有 1 位使用者
  6. 資料庫至少有 1 個單字
  7. chat 頁面可 import 且無錯誤
  8. 單字小恐龍頁面可 import 且無錯誤
  9. 單字卡頁面可 import 且無錯誤
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


# ── 測試 1：套件 import ───────────────────────────────────────────────────────

def test_1_imports():
    print("【測試 1】套件 import 檢查")
    try:
        import streamlit
        import pandas
        import plotly
        import pyodbc
        import chromadb
        import dotenv
        print("✅ 所有套件 import 成功")
        return True
    except ImportError as e:
        print(f"❌ 套件缺少：{e}")
        print("   請執行：python -m pip install -r requirements.txt")
        return False


# ── 測試 2：Azure SQL 連線 ────────────────────────────────────────────────────

def test_2_azure_sql():
    print("\n【測試 2】Azure SQL 連線")
    try:
        from database.db import get_connection
        conn = get_connection()
        conn.close()
        print("✅ Azure SQL 連線成功")
        return True
    except Exception as e:
        print(f"❌ 連線失敗：{e}")
        return False


# ── 測試 3：ChromaDB 索引 ─────────────────────────────────────────────────────

def test_3_chromadb():
    print("\n【測試 3】ChromaDB 索引")
    try:
        from rag.retriever import GrammarRetriever
        retriever = GrammarRetriever()

        if retriever.collection is None:
            print("❌ ChromaDB collection 為 None，請先執行 python rag/embedder.py")
            return False

        count = retriever.collection.count()
        if count == 0:
            print("❌ ChromaDB 索引是空的，請先執行 python rag/embedder.py")
            return False

        print(f"✅ ChromaDB 索引找到（{count} 筆文法文件）")
        return True
    except Exception as e:
        print(f"❌ ChromaDB 讀取失敗：{e}")
        return False


# ── 測試 4：Gemini API ────────────────────────────────────────────────────────

def test_4_gemini():
    print("\n【測試 4】Gemini API 回應")
    try:
        from tutor.gemini_chat import JapaneseTutor
        tutor = JapaneseTutor()
        reply = tutor.chat("請用一句話說你好。")
        if reply and len(reply) > 0:
            preview = reply[:60] + "..." if len(reply) > 60 else reply
            print(f"✅ Gemini API 回應正常：{preview}")
            return True
        else:
            print("❌ Gemini 回傳空回應")
            return False
    except Exception as e:
        print(f"❌ Gemini API 失敗：{e}")
        return False


# ── 測試 5：使用者存在 ────────────────────────────────────────────────────────

def test_5_user_exists():
    print("\n【測試 5】使用者資料")
    try:
        from database.queries import get_or_create_default_user
        from database.db import get_connection

        uid = get_or_create_default_user()

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, level FROM users WHERE user_id = ?", uid)
        row = cursor.fetchone()
        conn.close()

        if row:
            print(f"✅ 使用者存在：{row[0]}（{row[1]}）")
            return True
        else:
            print("❌ 找不到使用者")
            return False
    except Exception as e:
        print(f"❌ 使用者查詢失敗：{e}")
        return False


# ── 測試 6：單字資料 ──────────────────────────────────────────────────────────

def test_6_vocabulary():
    print("\n【測試 6】單字資料")
    try:
        from database.queries import get_vocabulary_by_level
        words = get_vocabulary_by_level("N5")
        if len(words) == 0:
            print("❌ 找不到 N5 單字，請確認 seed_vocabulary.sql 已執行")
            return False
        print(f"✅ 單字資料正常：找到 {len(words)} 個 N5 單字")
        return True
    except Exception as e:
        print(f"❌ 單字查詢失敗：{e}")
        return False


# ── 測試 7-9：頁面 import ─────────────────────────────────────────────────────

def test_7_chat_page():
    print("\n【測試 7】Chat 頁面 import")
    try:
        import views.chat  # noqa: F401
        print("✅ Chat 頁面 import 成功")
        return True
    except Exception as e:
        print(f"❌ Chat 頁面 import 失敗：{e}")
        return False


def test_8_dino_game_page():
    print("\n【測試 8】單字小恐龍頁面 import")
    try:
        import views.dino_game  # noqa: F401
        print("✅ 單字小恐龍頁面 import 成功")
        return True
    except Exception as e:
        print(f"❌ 單字小恐龍頁面 import 失敗：{e}")
        return False


def test_9_flashcard_page():
    print("\n【測試 9】單字卡頁面 import")
    try:
        import views.flashcard  # noqa: F401
        print("[OK] 單字卡頁面 import 成功")
        return True
    except Exception as e:
        print(f"[ERROR] 單字卡頁面 import 失敗：{e}")
        return False


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  Day 4 整合測試")
    print("=" * 55)

    results = [
        test_1_imports(),
        test_2_azure_sql(),
        test_3_chromadb(),
        test_4_gemini(),
        test_5_user_exists(),
        test_6_vocabulary(),
        test_7_chat_page(),
        test_8_dino_game_page(),
        test_9_flashcard_page(),
    ]

    print("\n" + "=" * 55)
    passed = sum(1 for r in results if r)
    total = len(results)

    if passed == total:
        print(f"  ✅ 所有測試通過（{passed}/{total}）")
        print("  執行：streamlit run app.py")
    else:
        print(f"  ❌ {total - passed} 項測試失敗，請檢查上方錯誤訊息。")
    print("=" * 55)


if __name__ == "__main__":
    main()
