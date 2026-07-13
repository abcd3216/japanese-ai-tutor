# AI 日語助教 — 專案時間線（三合一）

> 任務 / 開發日誌 / 問題追蹤 三合一精簡版，供 Notion Timeline 使用。
> 欄位對應：名稱 ｜ 日期(Year) ｜ 狀態 ｜ 備註。最後更新：2026-07-11

| 名稱 | 日期 | 狀態 | 備註 |
|---|---|---|---|
| 核心系統建置 | 2026-07 初 | 完成 | Azure SQL 資料庫、Gemini 對話（小葵老師）、RAG 文法庫、SM-2 單字卡、Streamlit 三頁整合 |
| 功能擴充 + 遊戲化 | 2026-07-09 | 完成 | 單字卡（日文發音）、單字小恐龍遊戲、單字擴到 N5/N4 各 80、RAG 加強 |
| 連線穩定性 | 2026-07-09 | 完成 | Azure 閒置喚醒：連線自動重試 + 友善等待畫面 |
| 部署上線 | 2026-07-10 | 完成 | Streamlit Cloud（FreeTDS / 防火牆 / packages 坑已解）、打 v1.0 穩定版標籤 |
| 角色化 + 語音 | 2026-07-10 | 完成 | 小葵老師角色頭像 + 回覆語音朗讀 |
| n8n 自動化週報 | 2026-07-10 | 進行中 | 每日學習日誌信、錯題依詞性分組（待實測） |
| VTuber 動態角色 | 2026-07-11 | 進行中 | 角色影片背景 Phase 1 完成；Phase 2 情緒特效、Phase 3 傳圖給 AI 待辦 |
| 效能優化 | — | 未開始 | 優化單字小恐龍載入速度 |

---

**技術棧**：Python · Gemini API · ChromaDB(RAG) · Azure SQL · Streamlit · SM-2 · n8n
**網址**：<https://japanese-ai-tutor-jjurkrpq8yym7xsramqcwj.streamlit.app>
**GitHub**：<https://github.com/abcd3216/japanese-ai-tutor>
