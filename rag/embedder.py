"""
embedder.py — 將文法知識庫建立成 ChromaDB 向量索引

【什麼是 Embedding（嵌入）？】
把一段文字轉換成一串數字（向量），讓電腦能比較兩段文字的「意思有多接近」。
例如「〜ている 表示進行」和「正在做某事的語法」，意思相近，向量也會很接近。

【什麼是向量資料庫（Vector Database）？】
存放這些「文字向量」的資料庫。搜尋時不是比對關鍵字，而是找「意思最接近」的文件。
這讓使用者可以用自然語言提問，就算用詞和原文不同，也能找到相關資料。

【為什麼用 --- 分割？】
每個文法條目之間用 --- 分隔，方便我們把每一則文法當作獨立的「知識片段」存入資料庫。
如果整個檔案存成一筆，搜尋時就無法精確找到特定文法了。
"""

import os
import chromadb
from chromadb.utils import embedding_functions

# ── 路徑設定 ──────────────────────────────────────────────
# 取得這個檔案（embedder.py）所在的資料夾，再往上一層是專案根目錄
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 知識庫資料夾：rag/knowledge/
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "rag", "knowledge")

# ChromaDB 儲存位置：data/chroma_db/
CHROMA_DIR = os.path.join(BASE_DIR, "data", "chroma_db")

# ChromaDB collection 名稱（像資料表的名字）
COLLECTION_NAME = "japanese_grammar"

# 使用支援中日文的多語言 Embedding 模型
# paraphrase-multilingual-MiniLM-L12-v2 支援 50+ 語言，包含中文和日文
# 第一次執行會自動下載模型（約 470MB），之後會快取在本機
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL
)


def load_knowledge_files():
    """
    讀取 rag/knowledge/ 底下所有 .txt 文法知識檔案。

    回傳：
        entries (list)：每個元素是一則文法條目（字串）
        ids (list)：每個條目的唯一 ID（例如 "n5_grammar_0"）
        metadatas (list)：每個條目的來源資訊（檔案名稱）
    """
    entries = []    # 每一則文法的文字內容
    ids = []        # 每一則文法的唯一 ID
    metadatas = []  # 每一則文法的附加資訊（來源檔案）

    print("📚 Loading knowledge files...")

    # 取得資料夾內所有 .txt 檔案，並排序（確保順序一致）
    txt_files = sorted([f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith(".txt")])

    for filename in txt_files:
        filepath = os.path.join(KNOWLEDGE_DIR, filename)

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 用 --- 分割成多個條目，並過濾掉空白條目
        raw_entries = content.split("---")
        clean_entries = [e.strip() for e in raw_entries if e.strip()]

        # 將每個條目加入清單
        # 從檔名推斷程度：n5_grammar.txt → N5，n4_grammar.txt → N4
        level = "N5" if filename.startswith("n5") else "N4"

        for i, entry in enumerate(clean_entries):
            entry_id = f"{filename.replace('.txt', '')}_{i}"  # 例如 "n5_grammar_0"
            entries.append(entry)
            ids.append(entry_id)
            # 加入 level 欄位，讓 retriever 可以依程度篩選
            metadatas.append({"source": filename, "level": level})

        print(f"✅ Loaded {filename} — {len(clean_entries)} entries")

    return entries, ids, metadatas


def build_index(entries, ids, metadatas):
    """
    將所有文法條目存入 ChromaDB 向量索引。

    ChromaDB 會自動把每個條目的文字轉成向量（Embedding），
    讓我們之後可以用語意搜尋找到最相關的文法。

    參數：
        entries：文法條目文字清單
        ids：每個條目的唯一 ID
        metadatas：每個條目的附加資訊
    """
    # 建立 ChromaDB 客戶端，資料會永久存在 CHROMA_DIR 資料夾裡
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # 檢查 collection 是否已存在，避免重複建立
    existing = [c.name for c in client.list_collections()]
    if COLLECTION_NAME in existing:
        print(f"\n⚠️  Collection '{COLLECTION_NAME}' already exists. Skipping re-index.")
        print("   若要重新建立，請先刪除 data/chroma_db/ 資料夾。")
        return

    print(f"\n🔄 Building ChromaDB index...")

    # 建立新的 collection，指定多語言 Embedding 模型
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )

    # 批次寫入所有條目（ChromaDB 會自動產生 Embedding）
    collection.add(
        documents=entries,
        ids=ids,
        metadatas=metadatas,
    )

    print(f"✅ ChromaDB index built successfully. {len(entries)} documents stored.")
    print(f"   儲存位置：{CHROMA_DIR}")


def main():
    # 步驟 1：讀取所有文法知識檔案
    entries, ids, metadatas = load_knowledge_files()

    if not entries:
        print("[ERROR] 沒有找到任何知識檔案，請確認 rag/knowledge/ 資料夾內有 .txt 檔案。")
        return

    # 步驟 2：建立向量索引
    build_index(entries, ids, metadatas)


if __name__ == "__main__":
    main()
