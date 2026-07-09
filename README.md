# 🎌 日文學習 AI 助教系統

> **Japanese AI Tutor** — 以 Gemini API 驅動的日語學習平台

一套結合 **AI 對話教練 × RAG 文法知識庫 × 單字卡 × 單字小恐龍遊戲** 的日語學習系統，
學習紀錄即時存入 Azure SQL Server，並可搭配 n8n 做每日學習日誌信（選配）。

---

## ✨ 功能亮點

| 頁面 | 功能 |
|---|---|
| 💬 **AI 對話練習** | 與「小葵老師」（Gemini 2.5 Flash）用日文／中文對話，串流即時回覆。整合 RAG 文法知識庫做 N5/N4 文法解釋；知識庫沒有的單字／發音／翻譯也會用 AI 自身知識正確回答 |
| 🃏 **單字卡** | 依你選的程度（N5/N4）先分詞性（動詞／名詞／形容詞），點進去看該詞性所有單字的**可翻面卡片**（正面日文＋假名，點一下翻面看中文） |
| 🦖 **單字小恐龍** | 限時 60 秒的判斷遊戲：判斷障礙物上的日文是不是目標中文的意思（數字鍵 1＝對、2＝錯）。成績用 SM-2 間隔重複演算法寫回學習紀錄 |

---

## 🛠️ 技術棧

| 用途 | 技術 |
|---|---|
| AI 對話 | Google Gemini API (`gemini-2.5-flash`、`google-genai`) |
| 向量檢索 / RAG | ChromaDB + `paraphrase-multilingual-MiniLM-L12-v2` |
| 資料庫 | Azure SQL Server (`pyodbc`) + 預存程序 |
| 前端介面 | Streamlit |
| 間隔重複 | SM-2 演算法（`tutor/srs.py`） |
| 每日日誌信（選配） | n8n + Gmail |
| 機密設定 | python-dotenv (`.env`) |

---

## 📁 專案結構

```
japanese_ai_tutor/
├── app.py                       # Streamlit 主程式（頁面導航、DB 連線喚醒保護）
├── .env.example                 # 環境變數範本（複製成 .env 後填值）
├── requirements.txt
├── database/
│   ├── db.py                    # Azure SQL 連線（含閒置喚醒自動重試）
│   ├── queries.py               # 所有 SQL 查詢／寫入函式
│   ├── setup.sql                # 建立 5 張表 + 預存程序
│   ├── seed_vocabulary.sql      # 種子單字（N5 80 + N4 80，共 160 筆）
│   └── seed_vocabulary_add80.sql# 把既有 120 筆補到 160 筆的補丁（防重複）
├── tutor/
│   ├── gemini_chat.py           # JapaneseTutor — Gemini 對話類別（整合 RAG、串流）
│   └── srs.py                   # SM-2 間隔重複演算法
├── rag/
│   ├── knowledge/               # N5 / N4 文法知識庫（.txt）
│   ├── embedder.py              # 建立 ChromaDB 向量索引
│   └── retriever.py             # GrammarRetriever — 語意搜尋
├── views/
│   ├── chat.py                  # AI 對話練習頁面
│   ├── flashcard.py             # 單字卡頁面（依詞性翻面瀏覽）
│   └── dino_game.py             # 單字小恐龍遊戲頁面
├── assets/sounds/               # 遊戲音效
├── data/chroma_db/              # ChromaDB 向量資料庫（本機生成，未版控）
├── n8n/                         # 每日日誌信自動化（選配，見 n8n/README.md）
└── test_day1.py ~ test_day4.py  # 各階段整合測試
```

---

## 🚀 快速開始

### 0. 前置需求

- Python 3.10+
- **ODBC Driver 18 for SQL Server**（`pyodbc` 連 Azure SQL 必裝，
  [微軟下載頁](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)）
- 一個 **Azure SQL Database**（或其他 SQL Server）
- 一把 **Google Gemini API Key**（[Google AI Studio](https://aistudio.google.com/apikey) 免費申請）

### 1. 安裝相依套件

```bash
pip install -r requirements.txt
```

### 2. 設定 `.env`

複製範本後填入你自己的值：

```bash
cp .env.example .env      # Windows 用 copy .env.example .env
```

```env
GEMINI_API_KEY=你的_Gemini_API_Key
SQL_SERVER=your-server.database.windows.net
SQL_DATABASE=your-database
SQL_USERNAME=your-username
SQL_PASSWORD=your-password
```

> 🔒 `.env` 已被 `.gitignore` 排除，不會上傳。請用**你自己的**資料庫與 API Key。

### 3. 建立資料庫結構與種子單字

在你的 Azure SQL 執行：
1. `database/setup.sql`（建立 5 張表 + 預存程序）
2. `database/seed_vocabulary.sql`（匯入 160 筆種子單字）

### 4. 建立 ChromaDB 向量索引

```bash
python rag/embedder.py
```

首次執行會自動下載多語言 Embedding 模型（約 470 MB）。

### 5. 啟動應用

```bash
streamlit run app.py
```

瀏覽器開 `http://localhost:8501`，左側輸入名字、選程度（N5/N4），按「✅ 開始學習」。

---

## 🗄️ 資料庫結構

### 資料表

- **users** — 使用者（`user_id`, `name`, `level`, `created_at`, `email`）
- **vocabulary** — 單字（`word_id`, `japanese`, `hiragana`, `chinese`, `level`, `category`）
- **learning_records** — SM-2 學習紀錄（`record_id`, `user_id`, `word_id`, `ease_factor`, `interval_days`, `next_review`, `correct_count`, `wrong_count`）
- **chat_history** — 對話紀錄（`chat_id`, `user_id`, `role`, `content`, `grammar_topic`, `mistake_type`, `created_at`）
- **game_sessions** — 小恐龍場次（`session_id`, `user_id`, `played_at`, `score`, `total_rounds`, `wrong_words`）

---

## ☁️ 部署 / 給別人使用

- **機密**：只上傳 `.env.example`，**絕不上傳 `.env`**（含帳密與 API Key）。每個人用自己的資料庫與 Key。
- **Azure SQL Free tier 會閒置自動暫停**：第一次連線需 1～2 分鐘喚醒。本專案的 `database/db.py`
  已內建**自動重試**、`app.py` 會顯示「⏳ 喚醒資料庫中」友善等待畫面，不會噴紅色錯誤。
- 想給別人更順的體驗，也可換不會暫停的免費 DB（Supabase / Neon，需微調 `db.py` 連線）。

---

## 🤖 每日日誌信（選配）

`n8n/` 資料夾有一套 n8n 自動化：每天早上把前一天的小恐龍成績整理成 HTML 信、
**錯題依詞性分組**，一人一封寄到各自 Gmail。屬於選配功能，需自備 n8n 服務，
詳見 [`n8n/README.md`](n8n/README.md)。

---

## ⚠️ 注意事項（踩過的坑）

- 使用 `google-genai`（新版），**不是**已棄用的 `google-generativeai`。
- Gemini `AQ.` 開頭的新版 Key 需 `http_options=types.HttpOptions(api_version='v1')`；v1 API 不支援 `system_instruction` 與 `thinking_config`。
- `pyodbc` 需 **ODBC Driver 18 for SQL Server**。
- SQL 中文字串常數要加 `N` 前綴（如 `N'動詞'`），否則會變亂碼。
- Windows 終端機（cp950）用 `print()` 印 emoji 會 `UnicodeEncodeError`；跑 `embedder.py` 建議設 `PYTHONIOENCODING=utf-8`。

---

## 🔧 重建 ChromaDB 索引

```bash
rm -rf data/chroma_db/     # Windows: Remove-Item -Recurse -Force data/chroma_db
python rag/embedder.py
```

---

## 📄 授權

本專案為個人學習用途開發。
