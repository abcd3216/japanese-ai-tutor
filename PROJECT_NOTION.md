# 日語助教 — 專案管理內容分類

> 供 Notion 專案管理使用，對應三個資料庫：**任務追蹤 / 開發日誌 / 問題追蹤**。
> 最後更新：2026-07-11

---

## 1️⃣ 問題追蹤（Bug / Issue）

> 欄位：問題描述 ｜ 嚴重程度 ｜ 狀態 ｜ 解決方式

| 問題描述 | 嚴重程度 | 狀態 | 解決方式 |
|---|---|---|---|
| Azure SQL 免費版閒置暫停，第一次連線逾時噴紅色錯誤 | 中 | 已解決 | `db.py` 連線自動重試（6×10s）+ `app.py` 友善「喚醒中」等待畫面 |
| 側邊欄收起後打不開 | 高 | 已解決 | 隱藏收合鈕、固定展開；根因是整個 header 被藏、展開鈕也在裡面 |
| 部署 Streamlit Cloud：apt 套件衝突（libodbc1 vs libodbc2） | 高 | 已解決 | `packages.txt` 只留 `freetds-bin`+`tdsodbc`，移除 unixodbc |
| FreeTDS 連 Azure「Cannot open server」 | 高 | 已解決 | 帳號改帶伺服器短名 `user@servername` |
| 雲端連不進 Azure（防火牆） | 高 | 已解決 | Azure SQL 防火牆加「允許所有 IP」（Streamlit 不算 Azure 服務） |
| AI 問單字（電燈）答不出來 | 中 | 已解決 | RAG prompt 改成「輔助參考」，查不到就用 AI 自身知識回答 |
| `config.toml` 有 UTF-8 BOM 導致設定全失效 | 中 | 已解決 | 用無 BOM UTF-8 重寫 |
| `st.markdown` 把縮排 HTML 當程式碼，`</div>` 漏成文字 | 低 | 已解決 | overlay HTML 改齊左不縮排 |
| 熱重載時 `ImportError: _is_transient` | 低 | 已解決 | app.py 自帶 `_is_db_waking`，不跨檔匯入私有函式 |
| vocabulary 被重複插入變 218 筆 | 中 | 已解決 | 用交易刪除重複，還原成乾淨資料 |
| `st.markdown` 濾掉 video 的 muted → 自動播被擋 | 中 | 已解決 | 影片剪成**無音軌**，無音軌即可自動播 |
| 單字小恐龍頁面載入慢 | 中 | 處理中 | 已快取單字查詢、init 每 session 一次；仍待進一步優化 |

---

## 2️⃣ 任務追蹤（Task）

> 欄位：任務 ｜ 狀態（完成 / 進行中 / 待辦）

| 任務 | 狀態 |
|---|---|
| 建置 5 張資料表 + 預存程序（Azure SQL） | ✅ 完成 |
| Gemini 對話（小葵老師）+ 串流回覆 | ✅ 完成 |
| RAG 文法知識庫（ChromaDB 語意檢索） | ✅ 完成 |
| 單字卡：依詞性翻面 + 日文發音（Web Speech API） | ✅ 完成 |
| 單字小恐龍遊戲 + SM-2 間隔重複排程 | ✅ 完成 |
| 單字擴充到 N5/N4 各 80 字（共 160） | ✅ 完成 |
| 部署到 Streamlit Community Cloud（拿到網址） | ✅ 完成 |
| 小葵老師角色頭像 + 回覆語音朗讀 | ✅ 完成 |
| README / DEPLOY 文件 + 上 GitHub + v1.0 標籤 | ✅ 完成 |
| n8n 每日學習日誌信（錯題依詞性分組） | 🟡 進行中（待實測） |
| VTuber 動態背景 Phase 1（角色影片背景） | 🟡 進行中（待驗收） |
| VTuber Phase 2：💭思考 / ✨稱讚 情緒疊加特效 | ⬜ 待辦 |
| VTuber Phase 3：傳圖給 AI 看（多模態 vision） | ⬜ 待辦 |
| 優化單字小恐龍載入速度 | ⬜ 待辦 |
| 申請 Streamlit 自訂短網址 | ⬜ 待辦 |

---

## 3️⃣ 開發日誌（Dev Log）

> 欄位：日期 ｜ 內容

| 日期 | 內容 |
|---|---|
| Day 1~4 | 建置資料庫、Gemini 對話、RAG 知識庫、SM-2 單字卡、Streamlit 三頁整合 |
| 2026-07-09（早） | 刪學習儀表板、新增單字卡頁、小恐龍錯題存詞性、清理會爆碼的 emoji print、vocabulary 去重 |
| 2026-07-09（下午） | 連線重試+喚醒畫面、標題改「小葵老師」、RAG 加強、單字擴到各 80、側邊欄按鈕對調 |
| 2026-07-10 | **部署上線**、朋友回饋實作（小恐龍/單字卡發音/角色頭像/語音朗讀）、打 `v1.0` 穩定版標籤 |
| 2026-07-11 | 開 `feature/chat-redesign` 分支，做 VTuber 動態背景 **Phase 1**（角色靜止圖 + 回覆時播開心影片） |

---

## 技術棧（備查）

| 用途 | 技術 |
|---|---|
| AI 對話 | Google Gemini（gemini-2.5-flash） |
| RAG 檢索 | ChromaDB + Sentence-Transformers |
| 資料庫 | Azure SQL Server（pyodbc + 預存程序） |
| 前端 | Streamlit |
| 間隔重複 | SM-2 演算法 |
| 自動化 | n8n + Gmail |
| 部署 | GitHub + Streamlit Community Cloud |

- 網址：<https://japanese-ai-tutor-jjurkrpq8yym7xsramqcwj.streamlit.app>
- GitHub：<https://github.com/abcd3216/japanese-ai-tutor>
