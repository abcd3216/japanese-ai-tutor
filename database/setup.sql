-- ============================================================
-- setup.sql
-- 日文學習 AI 助教系統 — 資料庫建置腳本
-- 請在 VS Code（MSSQL 擴充套件）連線到你的資料庫後執行此腳本
-- ============================================================


-- ============================================================
-- 資料表 1：users（使用者）
-- 儲存每個學習者的基本資料
-- ============================================================
CREATE TABLE users (
    user_id    INT PRIMARY KEY IDENTITY(1,1),  -- 自動遞增的唯一 ID（IDENTITY 表示由資料庫自動產生）
    name       NVARCHAR(50)  NOT NULL,          -- 使用者名稱（NVARCHAR 可存中文/日文）
    level      NVARCHAR(5)   DEFAULT 'N5',      -- JLPT 等級，預設從 N5 開始
    created_at DATETIME      DEFAULT GETDATE(), -- 建立時間，GETDATE() = 現在時間
    email      NVARCHAR(100) NULL               -- 選填，n8n 週報寄送用
);

GO  -- 批次分隔符號：告訴 SQL Server 上面的指令是一個批次，到這裡結束

-- ============================================================
-- 資料表 2：vocabulary（單字庫）
-- 儲存所有日文單字資料
-- ============================================================
CREATE TABLE vocabulary (
    word_id   INT PRIMARY KEY IDENTITY(1,1),  -- 單字唯一 ID
    japanese  NVARCHAR(50)  NOT NULL,          -- 日文（漢字形式），例如：食べる
    hiragana  NVARCHAR(50),                    -- 平假名讀音，例如：たべる
    chinese   NVARCHAR(100),                   -- 中文意思，例如：吃
    level     NVARCHAR(5),                     -- JLPT 等級：N5 / N4
    category  NVARCHAR(50)                     -- 詞性分類：動詞 / 名詞 / 形容詞
);

GO

-- ============================================================
-- 資料表 3：learning_records（學習紀錄）
-- 儲存每個使用者對每個單字的複習狀況（SM-2 間隔重複演算法）
-- ============================================================
CREATE TABLE learning_records (
    record_id     INT PRIMARY KEY IDENTITY(1,1),
    user_id       INT FOREIGN KEY REFERENCES users(user_id),      -- 關聯到 users 表
    word_id       INT FOREIGN KEY REFERENCES vocabulary(word_id),  -- 關聯到 vocabulary 表
    ease_factor   DECIMAL(4,2) DEFAULT 2.5,  -- 難易係數（越高表示越熟悉，最低 1.3）
    interval_days INT          DEFAULT 1,     -- 下次複習間隔天數
    next_review   DATE,                       -- 下次該複習的日期
    correct_count INT          DEFAULT 0,     -- 累計答對次數
    wrong_count   INT          DEFAULT 0      -- 累計答錯次數
);

GO

-- ============================================================
-- 資料表 4：chat_history（對話紀錄）
-- 儲存使用者與 AI 老師的每一句對話
-- ============================================================
CREATE TABLE chat_history (
    chat_id       INT PRIMARY KEY IDENTITY(1,1),
    user_id       INT FOREIGN KEY REFERENCES users(user_id),  -- 關聯到 users 表
    role          NVARCHAR(10),    -- 說話的角色：'user'（使用者）或 'model'（AI）
    content       NVARCHAR(MAX),   -- 對話內容（MAX 表示沒有長度上限）
    grammar_topic NVARCHAR(100),   -- 這句話涉及的文法主題（可為空）
    mistake_type  NVARCHAR(100),   -- 使用者犯的錯誤類型（可為空）
    created_at    DATETIME DEFAULT GETDATE()  -- 對話時間
);

GO

-- ============================================================
-- 資料表 5：game_sessions（單字小恐龍遊戲紀錄）
-- 每玩一局存一筆，供 n8n 週報統計本週的遊戲成績
-- ============================================================
CREATE TABLE game_sessions (
    session_id   INT PRIMARY KEY IDENTITY(1,1),
    user_id      INT FOREIGN KEY REFERENCES users(user_id),  -- 關聯到 users 表
    played_at    DATETIME DEFAULT GETDATE(),  -- 遊玩時間
    score        INT NOT NULL,                -- 本次答對題數
    total_rounds INT NOT NULL,                -- 本次總共判斷了幾題
    wrong_words  NVARCHAR(MAX)                -- 答錯的單字，JSON 陣列字串
);

GO  -- CREATE PROCEDURE 前必須有 GO，否則會報錯

-- ============================================================
-- 預存程序 1：sp_GetDueCards
-- 查出某位使用者今天（或逾期）該複習的單字卡
-- 使用方式：EXEC sp_GetDueCards @user_id = 1
-- ============================================================
CREATE PROCEDURE sp_GetDueCards
    @user_id INT  -- 傳入參數：使用者 ID
AS
BEGIN
    SELECT
        v.word_id,
        v.japanese,
        v.hiragana,
        v.chinese,
        v.category,
        r.ease_factor,
        r.interval_days,
        r.record_id
    FROM learning_records r
    JOIN vocabulary v ON r.word_id = v.word_id  -- 把學習紀錄和單字表合併
    WHERE r.user_id = @user_id
      AND r.next_review <= CAST(GETDATE() AS DATE)  -- 只取今天或更早應複習的
    ORDER BY r.next_review;  -- 最舊的優先複習
END;

GO  -- 兩個預存程序之間也需要 GO 分隔

-- ============================================================
-- 預存程序 2：sp_GetWeakCategories
-- 統計每個分類的答對/答錯次數，找出弱點分類
-- 使用方式：EXEC sp_GetWeakCategories @user_id = 1
-- ============================================================
CREATE PROCEDURE sp_GetWeakCategories
    @user_id INT
AS
BEGIN
    SELECT
        v.category,                            -- 分類名稱（動詞 / 名詞 / 形容詞）
        SUM(r.wrong_count)   AS total_wrong,   -- 該分類總答錯次數
        SUM(r.correct_count) AS total_correct  -- 該分類總答對次數
    FROM learning_records r
    JOIN vocabulary v ON r.word_id = v.word_id
    WHERE r.user_id = @user_id
    GROUP BY v.category        -- 依分類分組統計
    ORDER BY total_wrong DESC;  -- 答錯最多的分類排最前面
END;

GO
