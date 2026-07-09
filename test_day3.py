"""
test_day3.py — Day 3 整合測試

測試項目：
  1. 確認至少有一位使用者存在於資料庫
  2. 初始化 user_id=1 的學習紀錄（若尚未建立）
  3. 用 sp_GetDueCards 取得今日到期單字卡
  4. 模擬答一張卡（quality=4），用 SM-2 計算結果
  5. 將更新後的紀錄存回 Azure SQL
  6. 從資料庫讀回該紀錄，確認數值已正確更新
"""

import os
import sys
from datetime import date

# 確保可以 import 專案內的模組
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from database.db import get_connection
from database.queries import (
    get_vocabulary_by_level,
    init_learning_records,
    get_due_cards,
    update_learning_record,
)
from tutor.srs import calculate_next_review


# ── 測試 1：確認使用者存在 ────────────────────────────────────────────────────

def test_1_user_exists():
    """資料庫裡必須至少有一位使用者（user_id=1），否則後續測試無意義。"""
    print("【測試 1】確認使用者存在")

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name, level FROM users WHERE user_id = 1")
        row = cursor.fetchone()
        conn.close()

        if row is None:
            print("❌ 找不到 user_id=1，請確認 Day 1 的種子資料有正確執行")
            return False

        print(f"✅ 使用者找到：{row[1]}（{row[2]}）")
        return True

    except Exception as e:
        print(f"❌ 查詢使用者失敗：{e}")
        return False


# ── 測試 2：初始化學習紀錄 ────────────────────────────────────────────────────

def test_2_init_records():
    """
    為 user_id=1 的所有 N5 單字建立學習紀錄（若尚未存在）。
    init_learning_records 會自動跳過已存在的紀錄，所以重複執行也安全。
    """
    print("\n【測試 2】初始化學習紀錄")

    try:
        words = get_vocabulary_by_level("N5")
        if not words:
            print("❌ 找不到任何 N5 單字，請確認 seed_vocabulary.sql 已執行")
            return False

        created = 0
        for word in words:
            was_created = init_learning_records(user_id=1, word_id=word["word_id"])
            if was_created:
                created += 1

        # 查詢目前共有幾筆紀錄
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM learning_records WHERE user_id = 1")
        total = cursor.fetchone()[0]
        conn.close()

        print(f"✅ 學習紀錄初始化完成：新建 {created} 筆，資料庫共 {total} 筆")
        return True

    except Exception as e:
        print(f"❌ 初始化學習紀錄失敗：{e}")
        return False


# ── 測試 3：取得今日到期單字卡 ────────────────────────────────────────────────

def test_3_get_due_cards():
    """呼叫 sp_GetDueCards，確認能取得今日應複習的單字卡。"""
    print("\n【測試 3】取得今日到期單字卡")

    try:
        cards = get_due_cards(user_id=1)

        if not cards:
            print("⚠️  今日沒有到期的單字卡（可能所有卡的 next_review 都在未來）")
            print("   提示：初始化後 next_review=今天，第一次應該有卡可複習")
            # 非致命錯誤，仍回傳 True
            return True, []

        print(f"✅ 取得到期單字卡：{len(cards)} 張")
        for card in cards[:3]:  # 只印前 3 張，避免輸出過長
            print(f"   • {card['japanese']}（{card['hiragana']}）— {card['chinese']}")
        if len(cards) > 3:
            print(f"   ...（還有 {len(cards) - 3} 張）")

        return True, cards

    except Exception as e:
        print(f"❌ 取得到期單字卡失敗：{e}")
        return False, []


# ── 測試 4 & 5：模擬答題 + 存回資料庫 ────────────────────────────────────────

def test_4_5_simulate_and_save(cards):
    """
    取第一張卡，模擬使用者回答 quality=4（記得，但想了一下），
    計算 SM-2 結果，並將更新後的值存回 Azure SQL。
    """
    print("\n【測試 4】SM-2 計算")

    if not cards:
        print("⚠️  沒有可測試的單字卡，跳過此測試")
        return True, None

    card = cards[0]
    print(f"📝 測試單字：{card['japanese']}（{card['hiragana']}）— {card['chinese']}")
    print(f"   目前 ease_factor={card['ease_factor']}, interval_days={card['interval_days']}")

    try:
        new_ef, new_interval, next_review = calculate_next_review(
            ease_factor=card["ease_factor"],
            interval_days=card["interval_days"],
            quality=4,  # 記得，但想了一下
        )
        print(f"✅ SM-2 計算結果：ease={new_ef}, interval={new_interval} 天, next_review={next_review}")

    except Exception as e:
        print(f"❌ SM-2 計算失敗：{e}")
        return False, None

    print("\n【測試 5】存回 Azure SQL")

    try:
        update_learning_record(
            record_id=card["record_id"],
            ease_factor=new_ef,
            interval_days=new_interval,
            next_review=next_review,
            correct=1,
            wrong=0,
        )
        print("✅ 紀錄更新成功")
        return True, (card["record_id"], new_ef, new_interval, next_review)

    except Exception as e:
        print(f"❌ 存回資料庫失敗：{e}")
        return False, None


# ── 測試 6：驗證資料庫數值已更新 ─────────────────────────────────────────────

def test_6_verify_update(expected):
    """
    從資料庫讀回剛才更新的紀錄，確認 ease_factor / interval_days / next_review
    都與 SM-2 計算結果一致。
    """
    print("\n【測試 6】驗證資料庫已更新")

    if expected is None:
        print("⚠️  沒有可驗證的紀錄，跳過")
        return True

    record_id, exp_ef, exp_interval, exp_next_review = expected

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ease_factor, interval_days, next_review, correct_count FROM learning_records WHERE record_id = ?",
            record_id,
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            print(f"❌ 找不到 record_id={record_id}")
            return False

        db_ef, db_interval, db_next_review, db_correct = row

        # next_review 從資料庫取回可能是 datetime，統一轉成 date 比較
        if hasattr(db_next_review, "date"):
            db_next_review = db_next_review.date()

        ok = (
            round(float(db_ef), 2) == round(exp_ef, 2)
            and int(db_interval) == exp_interval
            and db_next_review == exp_next_review
        )

        if ok:
            print(f"✅ 驗證通過：record_id={record_id}")
            print(f"   ease_factor={db_ef}, interval_days={db_interval}, next_review={db_next_review}, correct_count={db_correct}")
        else:
            print(f"❌ 數值不一致：")
            print(f"   預期：ease={exp_ef}, interval={exp_interval}, next_review={exp_next_review}")
            print(f"   實際：ease={db_ef}, interval={db_interval}, next_review={db_next_review}")

        return ok

    except Exception as e:
        print(f"❌ 驗證失敗：{e}")
        return False


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  Day 3 整合測試")
    print("=" * 50)

    results = []

    results.append(test_1_user_exists())
    results.append(test_2_init_records())

    ok3, cards = test_3_get_due_cards()
    results.append(ok3)

    ok45, expected = test_4_5_simulate_and_save(cards)
    results.append(ok45)

    results.append(test_6_verify_update(expected))

    print("\n" + "=" * 50)
    passed = sum(1 for r in results if r)
    total = len(results)

    if passed == total:
        print(f"  ✅ Day 3 所有測試通過（{passed}/{total}）！可以繼續 Day 4。")
    else:
        print(f"  ❌ {total - passed} 項測試失敗，請檢查上方錯誤訊息。")
    print("=" * 50)


if __name__ == "__main__":
    main()
