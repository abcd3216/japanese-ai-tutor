# 🚀 部署到 Streamlit Cloud（讓別人打開網址就能用）

這份是給「**你**（架設者）」看的。照著做一次，你會得到一個網址，
之後任何人打開網址就能直接用，**不用裝任何東西、不用設定資料庫**。

> 別人只要「用」→ 給他們網址就好。
> 只有「你」需要做下面這些一次性的部署設定。

---

## 事前準備

- 程式碼已經在 GitHub（我們已經推上去了 ✅）
- 你自己的 **Gemini API Key** 和 **Azure SQL 帳密**（就是 `.env` 裡那些）
- 資料庫已經建好表格、匯入單字（`setup.sql` + `seed_vocabulary.sql` 已執行過 ✅）

---

## 步驟

### 1. 登入 Streamlit Cloud

到 **[share.streamlit.io](https://share.streamlit.io)**，用你的 **GitHub 帳號**登入授權。

### 2. 建立新 App

- 按 **「Create app」→「Deploy a public app from GitHub」**
- **Repository**：選 `abcd3216/japanese-ai-tutor`
- **Branch**：`main`
- **Main file path**：`app.py`
- 先不要按 Deploy，點下面的 **「Advanced settings」**

### 3. 填入 Secrets（重要！這是雲端版的 .env）

在 Advanced settings 的 **Secrets** 欄位，貼上以下內容（把值換成你自己的，
就是 `.env` 裡那些；格式參考 `.streamlit/secrets.toml.example`）：

```toml
GEMINI_API_KEY = "你的_Gemini_金鑰"
SQL_SERVER   = "你的伺服器.database.windows.net"
SQL_DATABASE = "你的資料庫名稱"
SQL_USERNAME = "你的資料庫帳號"
SQL_PASSWORD = "你的資料庫密碼"
```

> 🔒 Secrets 存在 Streamlit 那邊，不會進到程式碼、也不會公開。

### 4. 按 Deploy

等幾分鐘（第一次比較久，要裝套件 + 下載語言模型），
完成後會得到一個網址，例如：

```
https://japanese-ai-tutor.streamlit.app
```

把這個網址傳給任何人，他們打開就能用了 🎉

### 5. 開放 Azure SQL 防火牆讓雲端連得進來

Streamlit Cloud 的伺服器 IP 不固定，要讓它連到你的 Azure SQL：

- 到 Azure Portal → 你的 SQL Server → **網路 / 防火牆**
- 勾選 **「允許 Azure 服務和資源存取此伺服器」**
  （或加一條 `0.0.0.0 - 255.255.255.255` 的規則；方便但較寬鬆，看你取捨）

---

## 部署後如果連不上資料庫

雲端 Linux 是用 **FreeTDS** 驅動連 Azure SQL（`packages.txt` 會自動安裝）。
如果 App 畫面一直卡在喚醒、或 log 出現連線錯誤，依序檢查：

1. **Secrets 有沒有填對**（帳號不用加 `@伺服器` 後綴）
2. **Azure 防火牆**有沒有照步驟 5 開放
3. 若還是不行，在 Secrets 加一行指定驅動再重部署：
   ```toml
   SQL_ODBC_DRIVER = "FreeTDS"
   ```
4. 看 Streamlit App 右下角 **「Manage app」→ log**，把錯誤訊息貼出來對症下藥

---

## 費用提醒

- **Streamlit Cloud**：公開 App 免費。
- **Gemini API**：大家共用你的金鑰，聊天用越多、帳單越高（有免費額度）。給幾個朋友玩通常還好。
- **Azure SQL**：大家共用你的資料庫（本來就是用「輸入名字」分使用者，沒問題）。
