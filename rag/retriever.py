"""
retriever.py — 從 ChromaDB 向量索引進行語意搜尋

【語意搜尋 vs 關鍵字搜尋】
  關鍵字搜尋：逐字比對，搜尋「進行」就只能找到有「進行」這兩個字的文件。
  語意搜尋：比較「意思」，搜尋「正在做某事」也能找到「〜ている 表示進行」，
            因為兩者的向量很接近，即使用字完全不同。

這讓學生可以用自然語言提問，不需要知道正確的文法術語。
"""

import os
import chromadb
from chromadb.utils import embedding_functions

try:
    import streamlit as st
    _cache = st.cache_resource
except Exception:
    # 在 Streamlit 環境外執行時（如 test_day2.py）不套用快取
    _cache = lambda f: f

# ── 路徑設定 ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = os.path.join(BASE_DIR, "data", "chroma_db")
COLLECTION_NAME = "japanese_grammar"

# 必須與 embedder.py 使用同一個模型，否則向量無法比較
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL
)


@_cache
def get_retriever() -> "GrammarRetriever":
    """
    回傳全域共用的 GrammarRetriever 實例。
    @st.cache_resource 讓整個 Streamlit server 只建立一次，
    避免每次渲染頁面都重新載入 470MB 的 SentenceTransformer 模型。
    """
    return GrammarRetriever()


class GrammarRetriever:
    """
    從 ChromaDB 文法知識庫進行語意搜尋的類別。

    使用方式：
        retriever = GrammarRetriever()
        results = retriever.search("ている的用法")
        context = retriever.format_context(results)
    """

    def __init__(self):
        """
        初始化：連線到 ChromaDB collection。
        若索引還不存在（例如雲端首次啟動，chroma_db 沒放進 repo），
        會自動呼叫 embedder 建立一次；建立失敗時 collection 保持 None，
        RAG 搜尋會回傳空結果（AI 仍能用自身知識回答，不會整個壞掉）。
        """
        self.collection = None

        # 若索引不存在就自動建立（雲端部署首次啟動時會用到）
        need_build = not os.path.exists(CHROMA_DIR)
        if not need_build:
            client = chromadb.PersistentClient(path=CHROMA_DIR)
            if COLLECTION_NAME not in [c.name for c in client.list_collections()]:
                need_build = True

        if need_build:
            print("[INFO] 找不到向量索引，正在自動建立（首次啟動會下載模型、較久）…")
            try:
                from rag import embedder
                embedder.main()
            except Exception as e:
                print(f"[ERROR] 自動建立向量索引失敗：{e}")
                return

        # 連線到 ChromaDB 並取得 collection
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        if COLLECTION_NAME not in [c.name for c in client.list_collections()]:
            print(f"[ERROR] 建立後仍找不到 collection '{COLLECTION_NAME}'。")
            return

        self.collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
        )

    def search(self, query: str, n_results: int = 3, level: str = None) -> dict:
        """
        用自然語言搜尋最相關的文法條目。

        參數：
            query      - 搜尋問題，例如「ている的用法是什麼？」
            n_results  - 回傳幾筆結果（預設 3 筆）
            level      - 篩選程度，'N5' 或 'N4'；None 表示不篩選（搜全部）

        回傳：
            ChromaDB 的查詢結果 dict，包含：
              results["documents"]  - 文法條目文字（list of list）
              results["metadatas"]  - 來源資訊（list of list）
              results["distances"]  - 語意距離，越小表示越相關（list of list）
        """
        if self.collection is None:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

        # where 是 ChromaDB 的 metadata 篩選條件
        # {"level": "N5"} 表示只搜尋 level 欄位等於 N5 的文件
        where = {"level": level} if level else None

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return results

    def format_context(self, results: dict) -> str:
        """
        將搜尋結果整理成乾淨的字串，方便直接塞進 AI 的 prompt。

        參數：
            results - search() 回傳的 dict

        回傳：
            格式化後的字串，包含每筆結果的文法內容與來源
        """
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        if not documents:
            return "（找不到相關文法資料）"

        lines = []
        for i, (doc, meta) in enumerate(zip(documents, metadatas), start=1):
            source = meta.get("source", "未知來源")
            lines.append(f"【參考資料 {i}】（來源：{source}）")
            lines.append(doc)
            lines.append("")  # 空行分隔

        return "\n".join(lines).strip()


# ── 單獨執行時的快速測試 ──────────────────────────────────
if __name__ == "__main__":
    retriever = GrammarRetriever()

    if retriever.collection is None:
        exit(1)

    query = "ている的用法"
    print(f"🔍 搜尋：「{query}」\n")

    results = retriever.search(query, n_results=3)
    context = retriever.format_context(results)

    print(context)
