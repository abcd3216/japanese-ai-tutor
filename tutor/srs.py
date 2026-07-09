"""
tutor/srs.py — SM-2 間隔重複演算法

這個檔案只做一件事：
根據使用者的答題品質（quality），計算這張單字卡的下次複習日期。
"""

from datetime import date, timedelta


def calculate_next_review(ease_factor: float, interval_days: int, quality: int):
    """
    使用 SM-2 演算法計算下一次複習排程。

    Parameters
    ----------
    ease_factor   : float — 目前難易係數（最小 1.3，初始建議 2.5）
    interval_days : int   — 目前複習間隔天數（第一張新卡請傳 0）
    quality       : int   — 答題品質，範圍 0 ~ 5
                            5 = 完全記得、非常輕鬆
                            4 = 記得，但想了一下
                            3 = 勉強記得
                            2 = 忘了，但看到答案想起來
                            1 = 完全忘記
                            0 = 腦中一片空白

    Returns
    -------
    new_ease_factor   : float — 更新後的難易係數
    new_interval_days : int   — 更新後的複習間隔天數
    next_review_date  : date  — 下次複習日期（今天 + new_interval_days）
    """

    # ── 步驟 1：更新 ease_factor ──────────────────────────────────────────────
    # SM-2 公式：新 EF = 舊 EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    #
    # 白話說明：
    #   quality = 5 → 括號內 = 0.1 - 0 * ... = +0.1   (EF 增加最多)
    #   quality = 4 → 括號內 ≈ +0.0                   (EF 幾乎不變)
    #   quality = 3 → 括號內 ≈ -0.14                  (EF 稍微下降)
    #   quality < 3 → 答錯，不更新 EF（見步驟 2）
    #
    # EF 最小值為 1.3，避免間隔縮得太短而永遠複習同一張卡。

    # Azure SQL 回傳的 DECIMAL 欄位是 decimal.Decimal 型別，統一轉成 float 才能做運算
    ease_factor = float(ease_factor)

    if quality >= 3:
        # 答對：套用 SM-2 公式更新 EF
        new_ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    else:
        # 答錯：EF 維持不變
        new_ease_factor = ease_factor

    # 確保 EF 不低於 1.3
    new_ease_factor = max(1.3, round(new_ease_factor, 2))

    # ── 步驟 2：更新 interval_days ────────────────────────────────────────────
    if quality < 3:
        # 答錯：間隔重設為 1 天（明天再複習）
        new_interval_days = 1

    elif interval_days == 0:
        # 第 1 次複習（全新的卡）：固定間隔 1 天
        new_interval_days = 1

    elif interval_days == 1:
        # 第 2 次複習（昨天剛第一次看過）：固定間隔 6 天
        new_interval_days = 6

    else:
        # 第 3 次以後：間隔 = 上次間隔 × ease_factor，四捨五入為整數
        # 例如：interval=6, EF=2.5 → 6 * 2.5 = 15 天
        new_interval_days = round(interval_days * new_ease_factor)

    # ── 步驟 3：計算下次複習日期 ──────────────────────────────────────────────
    # 今天的日期 + 間隔天數
    next_review_date = date.today() + timedelta(days=new_interval_days)

    return new_ease_factor, new_interval_days, next_review_date
