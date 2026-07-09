"""
config.py — 統一讀取設定，讓程式同時支援兩種來源：

  1) 本機開發：讀專案根目錄的 .env 檔（透過 python-dotenv 載入成環境變數）
  2) 雲端部署：讀 Streamlit Cloud 的 Secrets（st.secrets）

呼叫 get_secret("GEMINI_API_KEY") 時，會「先找 Streamlit Secrets、找不到再找環境變數」，
所以同一份程式碼在本機（.env）和 Streamlit Cloud（Secrets）都能跑，不用改任何東西。
"""

import os
from dotenv import load_dotenv

# 本機時把 .env 載入環境變數；雲端沒有 .env 檔也不會出錯（load_dotenv 找不到就略過）
load_dotenv()


def get_secret(key: str, default=None):
    """
    依序嘗試取得設定值：
      1. Streamlit Secrets（雲端部署用）
      2. 環境變數 / .env（本機開發用）
    都沒有就回傳 default。
    """
    # 先試 Streamlit Secrets（只有在 Streamlit 雲端、且有設定 secrets 時才拿得到）
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        # 不在 Streamlit 環境，或還沒設定 secrets 檔 → 忽略，改用環境變數
        pass

    # 再退回環境變數（本機 .env）
    return os.getenv(key, default)
