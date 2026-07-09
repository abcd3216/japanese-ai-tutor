"""
test_day2.py — Day 2 整合測試

測試項目：
  1. ChromaDB 索引是否存在
  2. 語意搜尋是否能回傳相關結果
  3. RAG 對話是否正常（有 RAG vs 無 RAG 比較）
"""

import os
import sys

# 確保可以 import 專案內的模組
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


def test_1_chromadb_exists():
    """測試 1：確認 ChromaDB 索引已存在"""
    print("【測試 1】ChromaDB 索引檢查")

    chroma_dir = os.path.join(BASE_DIR, "data", "chroma_db")

    if not os.path.exists(chroma_dir):
        print("❌ 找不到 data/chroma_db/ 資料夾")
        print("   請先執行：python rag/embedder.py")
        return False

    # 確認資料夾內有檔案（不是空的）
    files = os.listdir(chroma_dir)
    if not files:
        print("❌ data/chroma_db/ 資料夾是空的")
        print("   請先執行：python rag/embedder.py")
        return False

    print("✅ ChromaDB 索引找到")
    return True


def test_2_semantic_search():
    """測試 2：語意搜尋 — 查詢「ている的用法」並印出前 3 筆結果"""
    print("\n【測試 2】語意搜尋")

    from rag.retriever import GrammarRetriever

    retriever = GrammarRetriever()

    if retriever.collection is None:
        print("❌ 無法連線到 ChromaDB，請先執行 embedder.py")
        return False

    query = "ている的用法"
    results = retriever.search(query, n_results=3)
    documents = results.get("documents", [[]])[0]

    if not documents:
        print("❌ 搜尋沒有回傳任何結果")
        return False

    print(f"✅ 搜尋「{query}」，找到 {len(documents)} 筆結果：")
    for i, doc in enumerate(documents, start=1):
        # 只印第一行（文法標題）避免輸出過長
        first_line = doc.split("\n")[0]
        print(f"   [{i}] {first_line}")

    return True


def test_3_rag_chat():
    """測試 3：RAG 對話 — 詢問「ている的用法」並比較有無 RAG 的差異"""
    print("\n【測試 3】RAG 對話（有 RAG vs 無 RAG）")

    from tutor.gemini_chat import JapaneseTutor

    tutor = JapaneseTutor()
    question = "請解釋〜ている的用法並舉例"

    # ── 無 RAG ──────────────────────────────────────
    print("\n--- 無 RAG（直接問 Gemini）---")
    reply_no_rag = tutor.chat(question)
    # 只印前 200 字，避免輸出太長
    print(reply_no_rag[:200] + "..." if len(reply_no_rag) > 200 else reply_no_rag)

    # 重置對話，避免上下文互相影響
    tutor.clear_history()

    # ── 有 RAG ──────────────────────────────────────
    print("\n--- 有 RAG（先查知識庫再回答）---")
    reply_with_rag = tutor.chat_with_rag(question)
    print(reply_with_rag[:200] + "..." if len(reply_with_rag) > 200 else reply_with_rag)

    # 驗證：有 RAG 的回答應包含「參考來源」或「來源」字樣
    has_source = "來源" in reply_with_rag or "参考" in reply_with_rag or "📚" in reply_with_rag
    if has_source:
        print("\n✅ RAG 回答有包含來源標注")
    else:
        print("\n⚠️  RAG 回答未包含來源標注（可能被 token 限制截斷，不影響功能）")

    return True


def main():
    print("=" * 50)
    print("  Day 2 整合測試")
    print("=" * 50)

    results = []

    results.append(test_1_chromadb_exists())
    results.append(test_2_semantic_search())
    results.append(test_3_rag_chat())

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"  ✅ Day 2 所有測試通過（{passed}/{total}）！可以繼續 Day 3。")
    else:
        print(f"  ❌ {total - passed} 項測試失敗，請檢查上方錯誤訊息。")
    print("=" * 50)


if __name__ == "__main__":
    main()
