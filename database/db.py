import pyodbc
import os
import sys
import time
import platform

# 讓「from config import get_secret」在各種執行方式下都找得到專案根目錄
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_secret


# ── 哪些錯誤代表「資料庫還在喚醒中」，值得自動重試 ───────────────────────────
# Azure SQL Free tier 閒置會自動暫停，下次連線要 1~2 分鐘喚醒，
# 喚醒期間第一次連線常見以下幾種「暫時性」錯誤：
#   08001 → 建立連線逾時 / 找不到伺服器（喚醒中最常見）
#   HYT00 → 連線逾時
#   40613 → Database ... is currently unavailable（正在上線）
#   40197 / 40501 / 49918 / 49919 / 49920 → Azure 端忙碌 / 節流
# 這些錯誤「等一下再試」就會好，所以自動重試；
# 帳號密碼錯、防火牆擋 IP（40615）這類「重試也沒用」的錯誤則不重試，直接拋出。
_TRANSIENT_HINTS = (
    "08001", "HYT00", "HYT01",
    "40613", "40197", "40501", "49918", "49919", "49920",
    "登入逾時", "login timeout", "currently unavailable",
    "無法開啟", "無法建立", "逾時",
)


def _is_transient(err: Exception) -> bool:
    """判斷一個連線錯誤是不是「喚醒中的暫時性錯誤」（值得重試）。"""
    msg = str(err)
    return any(hint in msg for hint in _TRANSIENT_HINTS)


def _default_driver() -> str:
    """
    依作業系統選預設 ODBC 驅動程式：
      - Windows（本機開發）→ 微軟官方「ODBC Driver 18 for SQL Server」
      - 其他（Linux，如 Streamlit Cloud）→ 「FreeTDS」（用 packages.txt 安裝）
    也可用 SQL_ODBC_DRIVER 這個設定覆蓋。
    """
    if platform.system() == "Windows":
        return "ODBC Driver 18 for SQL Server"
    return "FreeTDS"


def _build_connection_string() -> str:
    """組出 pyodbc 用的連線字串（值來自 .env 或 Streamlit Secrets）。"""
    server   = get_secret("SQL_SERVER")
    database = get_secret("SQL_DATABASE")
    username = get_secret("SQL_USERNAME")
    password = get_secret("SQL_PASSWORD")
    driver   = get_secret("SQL_ODBC_DRIVER") or _default_driver()

    if "freetds" in driver.lower():
        # FreeTDS（Linux / Streamlit Cloud）連 Azure SQL：
        # 用 PORT + TDS_Version=7.4，不能帶微軟驅動專用的 Encrypt/TrustServerCertificate 參數
        return (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};PORT=1433;"
            f"DATABASE={database};"
            f"UID={username};PWD={password};"
            f"TDS_Version=7.4;"
        )

    # 微軟官方 ODBC Driver 18（Windows 本機）
    # Encrypt=yes：連線加密（Azure SQL 強制要求）
    # TrustServerCertificate=no：不跳過憑證驗證（安全設定）
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
    )


def get_connection(max_retries: int = 6, retry_delay: int = 10):
    """
    建立並回傳一個 Azure SQL Server 的資料庫連線物件。
    呼叫端用完後應該呼叫 conn.close() 關閉連線。

    自動重試：Azure SQL Free tier 閒置會自動暫停，喚醒要 1~2 分鐘。
    若遇到「喚醒中的暫時性錯誤」，會每隔 retry_delay 秒重試一次，
    最多 max_retries 次（預設 6 次 × 10 秒 ≈ 涵蓋 1 分鐘的喚醒期）。
    帳密錯誤、防火牆擋 IP 這種「重試也沒用」的錯誤則會立刻拋出，不浪費時間。

    參數：
        max_retries：最多嘗試幾次（含第一次）。設 1 代表不重試。
        retry_delay：每次重試之間等待幾秒。
    """
    connection_string = _build_connection_string()
    last_err = None

    for attempt in range(1, max_retries + 1):
        try:
            # timeout=30：單次登入逾時上限 30 秒（喚醒中的連線不會卡太久就會逾時進入重試）
            conn = pyodbc.connect(connection_string, timeout=30)
            if attempt > 1:
                print(f"[INFO] 資料庫在第 {attempt} 次嘗試後連線成功（喚醒完成）")
            return conn

        except pyodbc.Error as e:
            last_err = e
            # 還有重試機會，且是「喚醒中」的暫時性錯誤 → 等一下再試
            if attempt < max_retries and _is_transient(e):
                print(f"[WAKE] 資料庫喚醒中，第 {attempt}/{max_retries} 次連線失敗，"
                      f"{retry_delay} 秒後重試…")
                time.sleep(retry_delay)
                continue
            # 沒有重試機會，或是「重試也沒用」的錯誤 → 跳出迴圈往下拋
            break

    # 全部重試用完仍失敗，印出清楚的錯誤訊息並把錯誤往上拋
    print(f"[ERROR] 資料庫連線失敗：{last_err}")
    print("請確認：")
    print("  1. .env 裡的帳號密碼正確")
    print("  2. Azure SQL Server 防火牆已開放你的 IP")
    print("  3. 電腦已安裝 ODBC Driver 18 for SQL Server")
    print("  4. （Free tier）資料庫是否仍在喚醒中，可稍後再試")
    raise last_err
