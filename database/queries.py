from database.db import get_connection
from datetime import date
import json


def get_or_create_default_user() -> int:
    """
    確保資料庫裡至少有一位使用者。
    若沒有任何使用者，自動建立預設帳號：name='學習者', level='N5'。
    回傳 user_id（int）。
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT TOP 1 user_id FROM users ORDER BY user_id")
        row = cursor.fetchone()

        if row:
            conn.close()
            return int(row[0])

        # 沒有使用者，建立預設帳號
        cursor.execute(
            "INSERT INTO users (name, level) OUTPUT INSERTED.user_id VALUES (N'學習者', 'N5')"
        )
        new_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return int(new_id)

    except Exception as e:
        print(f"[ERROR] get_or_create_default_user 失敗：{e}")
        raise

# ============================================================
# queries.py
# 所有資料庫查詢與寫入函式都集中在這裡。
# 其他模組只需 from database.queries import XXX 來呼叫。
# ============================================================


def get_due_cards(user_id):
    """
    呼叫預存程序 sp_GetDueCards，取得今天該複習的單字卡清單。

    參數：
        user_id (int)：使用者 ID

    回傳：
        list of dict，每個 dict 代表一張單字卡，例如：
        [{'word_id': 1, 'japanese': '食べる', 'hiragana': 'たべる', ...}, ...]
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 呼叫預存程序的方式：EXEC 程序名稱 @參數名稱 = 值
        # pyodbc 用 ? 當作佔位符（placeholder），防止 SQL injection
        cursor.execute("EXEC sp_GetDueCards @user_id = ?", user_id)

        # fetchall() 取回所有結果列
        rows = cursor.fetchall()

        # cursor.description 包含每個欄位的名稱，
        # 用來把每一列資料轉成 dict，這樣呼叫端可以用 row['japanese'] 取值
        columns = [col[0] for col in cursor.description]
        result = [dict(zip(columns, row)) for row in rows]

        conn.close()
        return result

    except Exception as e:
        print(f"[ERROR] get_due_cards 失敗：{e}")
        raise


def save_chat_message(user_id, role, content, grammar_topic=None, mistake_type=None):
    """
    把一句對話存進 chat_history 表。

    參數：
        user_id       (int)：使用者 ID
        role          (str)：說話角色，'user' 或 'model'
        content       (str)：對話內容
        grammar_topic (str)：涉及的文法主題，可以不填
        mistake_type  (str)：錯誤類型，可以不填
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # INSERT 語法：用 ? 佔位符帶入值（安全做法，避免 SQL injection）
        cursor.execute(
            """
            INSERT INTO chat_history (user_id, role, content, grammar_topic, mistake_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            user_id, role, content, grammar_topic, mistake_type
        )

        # commit() 是「確認送出」，如果沒有 commit，資料不會真正寫進資料庫
        conn.commit()
        conn.close()

    except Exception as e:
        print(f"[ERROR] save_chat_message 失敗：{e}")
        raise


def get_chat_history(user_id, limit=10):
    """
    取得某位使用者最近的對話紀錄。

    參數：
        user_id (int)：使用者 ID
        limit   (int)：最多取幾筆，預設 10

    回傳：
        list of dict，依時間從舊到新排列
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # TOP ? 取前 N 筆，ORDER BY created_at DESC 先取最新的，
        # 再用子查詢反轉順序，讓最終結果從舊到新（方便顯示對話）
        cursor.execute(
            """
            SELECT * FROM (
                SELECT TOP (?) chat_id, user_id, role, content,
                               grammar_topic, mistake_type, created_at
                FROM chat_history
                WHERE user_id = ?
                ORDER BY created_at DESC
            ) AS recent
            ORDER BY created_at ASC
            """,
            limit, user_id
        )

        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        result = [dict(zip(columns, row)) for row in rows]

        conn.close()
        return result

    except Exception as e:
        print(f"[ERROR] get_chat_history 失敗：{e}")
        raise


def get_vocabulary_by_level(level):
    """
    取得指定程度的所有單字。

    參數：
        level (str)：'N5' 或 'N4'

    回傳：
        list of dict，每個 dict 代表一個單字，例如：
        [{'word_id': 1, 'japanese': '食べる', 'hiragana': 'たべる',
          'chinese': '吃', 'level': 'N5', 'category': '動詞'}, ...]
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT word_id, japanese, hiragana, chinese, level, category FROM vocabulary WHERE level = ?",
            level
        )

        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        result = [dict(zip(columns, row)) for row in rows]

        conn.close()
        return result

    except Exception as e:
        print(f"[ERROR] get_vocabulary_by_level 失敗：{e}")
        raise


def init_learning_records(user_id, word_id):
    """
    若 learning_records 中尚無此 (user_id, word_id) 的紀錄，則建立一筆新紀錄。
    初始值：ease_factor=2.5, interval_days=0, next_review=今天。

    參數：
        user_id (int)：使用者 ID
        word_id (int)：單字 ID

    回傳：
        True  — 成功建立新紀錄
        False — 紀錄已存在，無需建立
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 先檢查是否已有紀錄，避免重複建立
        cursor.execute(
            "SELECT record_id FROM learning_records WHERE user_id = ? AND word_id = ?",
            user_id, word_id
        )
        existing = cursor.fetchone()

        if existing:
            conn.close()
            return False  # 已存在，不需要新增

        # 不存在則插入一筆初始紀錄
        # next_review 設為今天，代表這張卡今天就該開始複習
        cursor.execute(
            """
            INSERT INTO learning_records
                (user_id, word_id, ease_factor, interval_days, next_review, correct_count, wrong_count)
            VALUES (?, ?, 2.5, 0, ?, 0, 0)
            """,
            user_id, word_id, date.today()
        )

        conn.commit()
        conn.close()
        return True  # 成功建立

    except Exception as e:
        print(f"[ERROR] init_learning_records 失敗：{e}")
        raise


def init_learning_records_bulk(user_id, level):
    """
    一次把某個 user 在某個 level 底下「還沒有學習紀錄」的單字全部初始化。

    跟 init_learning_records() 一個一個單字開連線檢查、插入不同，
    這裡全程只開一條連線：先各查一次「這個等級有哪些單字」和
    「這個使用者已經有哪些紀錄」，在 Python 裡算出差集，
    再用 executemany 一次寫入，大幅減少 Azure SQL 的來回次數。

    參數：
        user_id (int)：使用者 ID
        level   (str)：'N5' 或 'N4'

    回傳：
        int：本次新建的紀錄筆數
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 這個等級所有單字的 word_id
        cursor.execute("SELECT word_id FROM vocabulary WHERE level = ?", level)
        all_word_ids = {row[0] for row in cursor.fetchall()}

        # 這個使用者已經有紀錄的 word_id（只挑這個等級範圍內的即可）
        cursor.execute(
            """
            SELECT lr.word_id
            FROM learning_records lr
            JOIN vocabulary v ON lr.word_id = v.word_id
            WHERE lr.user_id = ? AND v.level = ?
            """,
            user_id, level
        )
        existing_word_ids = {row[0] for row in cursor.fetchall()}

        missing_word_ids = all_word_ids - existing_word_ids
        if not missing_word_ids:
            conn.close()
            return 0

        today = date.today()
        rows = [(user_id, word_id, today) for word_id in missing_word_ids]
        cursor.executemany(
            """
            INSERT INTO learning_records
                (user_id, word_id, ease_factor, interval_days, next_review, correct_count, wrong_count)
            VALUES (?, ?, 2.5, 0, ?, 0, 0)
            """,
            rows
        )

        conn.commit()
        conn.close()
        return len(missing_word_ids)

    except Exception as e:
        print(f"[ERROR] init_learning_records_bulk 失敗：{e}")
        raise


def get_learning_stats(user_id):
    """
    取得使用者的整體學習統計數據。

    參數：
        user_id (int)：使用者 ID

    回傳：
        dict，包含以下欄位：
        {
            'total_studied'  : int   — 已學過的單字總數（有紀錄的）
            'total_correct'  : int   — 累計答對次數
            'total_wrong'    : int   — 累計答錯次數
            'accuracy_rate'  : float — 答對率（0.0 ~ 1.0），若無作答則為 0.0
        }
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                COUNT(*)                                          AS total_studied,
                -- 實際有作答過的單字數（correct + wrong > 0）
                COUNT(CASE WHEN correct_count + wrong_count > 0 THEN 1 END)
                                                                 AS practiced_count,
                COALESCE(SUM(correct_count), 0)                  AS total_correct,
                COALESCE(SUM(wrong_count), 0)                    AS total_wrong,
                CASE
                    WHEN SUM(correct_count) + SUM(wrong_count) = 0 THEN 0.0
                    ELSE CAST(SUM(correct_count) AS FLOAT)
                         / (SUM(correct_count) + SUM(wrong_count))
                END                                              AS accuracy_rate
            FROM learning_records
            WHERE user_id = ?
            """,
            user_id
        )

        row = cursor.fetchone()
        columns = [col[0] for col in cursor.description]
        result = dict(zip(columns, row))

        conn.close()
        return result

    except Exception as e:
        print(f"[ERROR] get_learning_stats 失敗：{e}")
        raise


def update_learning_record(record_id, ease_factor, interval_days, next_review, correct, wrong):
    """
    更新單字的學習紀錄（SM-2 演算法計算後呼叫此函式）。

    參數：
        record_id     (int)  ：要更新的紀錄 ID
        ease_factor   (float)：新的難易係數
        interval_days (int)  ：新的複習間隔天數
        next_review   (date) ：下次複習日期
        correct       (int)  ：這次答對幾次（0 或 1）
        wrong         (int)  ：這次答錯幾次（0 或 1）
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE learning_records
            SET ease_factor   = ?,
                interval_days = ?,
                next_review   = ?,
                correct_count = correct_count + ?,
                wrong_count   = wrong_count   + ?
            WHERE record_id = ?
            """,
            ease_factor, interval_days, next_review, correct, wrong, record_id
        )

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"[ERROR] update_learning_record 失敗：{e}")
        raise


def get_learning_records_by_word_ids(user_id, word_ids):
    """
    一次查出這個使用者、指定一批 word_id 的學習紀錄。
    給「單字小恐龍」遊戲結束後批次套用 SM-2 用，避免一個單字查一次連線。

    參數：
        user_id  (int)      ：使用者 ID
        word_ids (list[int])：要查詢的單字 ID 清單

    回傳：
        dict：{word_id: {"record_id": int, "ease_factor": float, "interval_days": int}}
    """
    if not word_ids:
        return {}
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 用 IN (?, ?, ...) 一次撈出這批單字的紀錄
        placeholders = ",".join(["?"] * len(word_ids))
        cursor.execute(
            f"""
            SELECT word_id, record_id, ease_factor, interval_days
            FROM learning_records
            WHERE user_id = ? AND word_id IN ({placeholders})
            """,
            user_id, *word_ids
        )
        rows = cursor.fetchall()
        conn.close()

        return {
            row[0]: {"record_id": row[1], "ease_factor": row[2], "interval_days": row[3]}
            for row in rows
        }

    except Exception as e:
        print(f"[ERROR] get_learning_records_by_word_ids 失敗：{e}")
        raise


def save_game_session(user_id, score, total_rounds, wrong_words):
    """
    儲存一局「單字小恐龍」的遊玩結果。

    參數：
        user_id      (int)       ：使用者 ID
        score        (int)       ：本局答對題數
        total_rounds (int)       ：本局總共判斷了幾題
        wrong_words  (list[dict])：答錯的單字，例如 [{"japanese": "食べる", "chinese": "吃"}, ...]
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO game_sessions (user_id, score, total_rounds, wrong_words)
            VALUES (?, ?, ?, ?)
            """,
            user_id, score, total_rounds, json.dumps(wrong_words, ensure_ascii=False)
        )

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"[ERROR] save_game_session 失敗：{e}")
        raise


def get_dino_stats(user_id):
    """
    彙總這位使用者所有「單字小恐龍」場次的對錯統計，給學習儀表板用。

    參數：
        user_id (int)：使用者 ID

    回傳：
        dict：
        {
            'session_count'  : int — 總共玩了幾局
            'total_correct'  : int — 累計判斷對幾題（= 各局 score 加總）
            'total_wrong'    : int — 累計判斷錯幾題（= 各局 total_rounds - score 加總）
        }
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                COUNT(*)                                      AS session_count,
                COALESCE(SUM(score), 0)                       AS total_correct,
                COALESCE(SUM(total_rounds - score), 0)        AS total_wrong
            FROM game_sessions
            WHERE user_id = ?
            """,
            user_id,
        )
        row = cursor.fetchone()
        conn.close()

        return {
            "session_count": row[0],
            "total_correct": row[1],
            "total_wrong": row[2],
        }

    except Exception as e:
        print(f"[ERROR] get_dino_stats 失敗：{e}")
        raise
