-- n8n「Microsoft SQL」節點使用的查詢：撈「昨天」每一局單字小恐龍成績。
-- 同一個人玩多局就會有多列，交給 Code 節點依 email 聚合成一封信。
SELECT
    u.name         AS learner,
    u.email        AS email,
    g.played_at    AS played_at,
    g.score        AS score,
    g.total_rounds AS total_rounds,
    g.wrong_words  AS wrong_words
FROM game_sessions g
JOIN users u ON g.user_id = u.user_id
WHERE u.email IS NOT NULL AND u.email <> ''
  AND g.played_at >= CAST(DATEADD(DAY, -1, CAST(GETDATE() AS DATE)) AS DATETIME)
  AND g.played_at <  CAST(CAST(GETDATE() AS DATE) AS DATETIME)
ORDER BY u.email, g.played_at;
