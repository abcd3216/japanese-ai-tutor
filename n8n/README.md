# n8n 每日日誌信（選配 Optional）

> ⚠️ **這是選配功能，不影響主程式。** 只 clone 這個專案跑 `streamlit run app.py`
> 就能使用完整的網頁 app；這個 n8n 自動化是額外的「每日學習日誌信」功能，
> 需要你**自己有一台 n8n 服務**才能運作。

每天早上 7 點自動查詢前一天的「單字小恐龍」成績，整理成一封 HTML 日誌信
（含遊玩局數、正確率、以及**錯題依詞性分組**），一位學習者一封，寄到各自的 Gmail。

## 流程

```
Schedule Trigger（每天 07:00）
   → Microsoft SQL（Execute Query，撈昨天的 game_sessions）
   → Code（依 email 聚合、錯題依詞性分組、組 HTML）
   → Gmail（Send，一人一封）
```

## 檔案

| 檔案 | 對應節點 | 說明 |
|---|---|---|
| `query.sql` | Microsoft SQL 節點 | 撈昨天每一局成績的查詢 |
| `code_node.js` | Code 節點 | 聚合 + 錯題依詞性分組 + 組信；Mode 需設 **Run Once for All Items** |
| `dino_daily_log.json` | 整個 workflow | （選擇性）從 n8n 匯出的 workflow，可直接匯入 |

> 想附上完整 workflow 的話：在 n8n 打開此 workflow → 右上 `⋯` → **Download**，
> 把下載的 JSON 存成本資料夾的 `dino_daily_log.json` 再 commit。
> （匯出的 JSON **不含**帳密，n8n 憑證是分開儲存的。）

## 別人要用的話，需要自行準備

1. 一台 **n8n**（雲端 n8n Cloud 或自架）
2. **Microsoft SQL 憑證**：連到自己的 Azure SQL（TDS Version 選 `7.4`，見專案根目錄踩坑筆記）
3. **Gmail OAuth2 憑證**：用來寄信
4. 節點對照上面三個檔案設定；Gmail 的 To/Subject/Message 分別接
   `{{ $json.to }}` / `{{ $json.subject }}` / `{{ $json.html }}`，Email Type 選 HTML

## 注意

- **時區**：Azure SQL 的 `GETDATE()` 是 UTC，若「昨天」的邊界跟你所在時區對不上，
  可把 `query.sql` 改用本地時區框（例如 `DATEADD(HOUR, 8, GETDATE())`）。
- **舊紀錄沒有詞性**：早期玩的局，`wrong_words` 裡沒有 `category`，錯題會被歸到「其他」。
