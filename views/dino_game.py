"""
views/dino_game.py — 單字小恐龍遊戲頁面

玩法：
  1. 畫面上方顯示一個中文目標詞（例如「貓」）
  2. 小恐龍前方會跑來一個障礙物，上面寫著一個日文單字
  3. 玩家判斷這個日文單字是不是目標詞的意思：
       1 = 判定「對」
       2 = 判定「錯」
  4. 判斷正確得 1 分，判斷錯誤（或來不及判斷）算一次錯題
  5. 限時 60 秒，時間到自動結束

遊戲本體（Canvas + JS）在瀏覽器端獨立跑完 60 秒，跟 Python 之間沒有即時連線；
結束後把結果暫存在瀏覽器的 localStorage，玩家按下方「📤 送出成績」按鈕時，
才用 streamlit_javascript 讀回 Python，套用 SM-2 更新學習紀錄、存一筆 game_sessions。
"""

import base64
import json
import os
import streamlit as st
import streamlit.components.v1 as components
from streamlit_javascript import st_javascript
from database.queries import (
    get_vocabulary_by_level,
    init_learning_records_bulk,
    get_learning_records_by_word_ids,
    update_learning_record,
    save_game_session,
)
from tutor.srs import calculate_next_review

# 音效檔位置：專案根目錄下的 assets/sounds/
_SOUNDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sounds")


@st.cache_data(ttl=600, show_spinner=False)
def _cached_vocab(level: str) -> list[dict]:
    """
    快取版的單字查詢（與單字卡共用同一份 vocabulary，出題一致）。
    靜態資料快取 10 分鐘，避免每次 rerun 都打 Azure SQL 造成卡頓。
    """
    return get_vocabulary_by_level(level)


def _audio_data_uri(filename: str) -> str:
    """
    把音效檔讀成 base64，包成 data URI 字串，直接嵌進 HTML/JS 裡。
    這樣遊戲的 iframe 不用另外架靜態檔案伺服器就能播放音效。
    """
    path = os.path.join(_SOUNDS_DIR, filename)
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:audio/mpeg;base64,{b64}"


def show(user_id: int = 1, user_level: str = "N5"):
    """單字小恐龍頁面入口。app.py 呼叫 dino_game.show(user_id, user_level)。"""

    st.title("🦖 單字小恐龍")
    st.caption(f"目前程度：**{user_level}**　｜　限時 60 秒　｜　數字鍵 1 判定對　數字鍵 2 判定錯")

    # 確保這個程度的單字都已經有學習紀錄（沿用單字練習頁面同一套邏輯）。
    # 只在每個 session「第一次進入這個 user+level」時做一次，
    # 之後 rerun 不再重跑（省下每次約 480ms 的 Azure 往返，避免卡頓）。
    _init_key = f"dino_init_{user_id}_{user_level}"
    if not st.session_state.get(_init_key):
        init_learning_records_bulk(user_id, user_level)
        st.session_state[_init_key] = True

    words = _cached_vocab(user_level)
    if not words:
        st.warning("這個程度目前沒有單字資料，無法開始遊戲。")
        return

    # 把單字清單轉成 JSON，餵給遊戲用的 JavaScript
    words_json = json.dumps(words, ensure_ascii=False)
    correct_sound_uri = _audio_data_uri("correct.mp3")
    wrong_sound_uri = _audio_data_uri("wrong.mp3")

    game_html = f"""
    <div id="dino-root" style="font-family: 'Segoe UI', sans-serif; text-align:center; color:#eee;">

      <div id="hud" style="display:flex; justify-content:space-between; align-items:center;
                            max-width:700px; margin:0 auto 8px auto; font-size:1.1rem;">
        <div>⏱️ <span id="timer">60</span> 秒</div>
        <div id="target-box" style="font-size:0.95rem; font-weight:bold; color:#ffd166;">
          🔼黃字中文 = 🔽白字日文 的意思嗎？
        </div>
        <div>✅ <span id="score">0</span> / <span id="rounds">0</span></div>
      </div>

      <div id="focus-hint" style="color:#f39c12; font-size:0.85rem; margin-bottom:4px;">
        🖱️ 如果按數字鍵沒反應，先點一下下面的遊戲畫面再試　｜　📥 記得下滑儲存成績喔！
      </div>

      <canvas id="dino-canvas" width="700" height="260" tabindex="0"
              style="background:#1b1f27; border:3px solid #444; border-radius:10px; max-width:100%; outline:none;">
      </canvas>

      <div id="result-box" style="display:none; margin-top:14px; font-size:1.1rem;"></div>
    </div>

    <script>
    (function() {{
        const words = {words_json};
        const canvas = document.getElementById("dino-canvas");
        const ctx = canvas.getContext("2d");
        const W = canvas.width, H = canvas.height;
        const GROUND_Y = H - 40;
        const DINO_X = 80;

        // 小恐龍是嵌在獨立 iframe 裡的，鍵盤事件只有在這個 iframe 拿到焦點時
        // 才收得到，所以載入時主動搶一次焦點，並讓玩家點擊畫面也能重新取得焦點。
        canvas.addEventListener("click", function() {{ canvas.focus(); }});
        window.focus();
        canvas.focus();

        // 音效：答對播 correctSound，答錯／撞到播 wrongSound
        const correctSound = new Audio("{correct_sound_uri}");
        const wrongSound = new Audio("{wrong_sound_uri}");
        function playSound(audio) {{
            audio.currentTime = 0;
            audio.play().catch(function() {{}}); // 使用者還沒跟頁面互動過時瀏覽器可能擋播放，忽略即可
        }}

        // 這些變數會在 startGame() 裡重設，restart 按鈕重新呼叫 startGame() 就能重玩
        let score, rounds, wrongWords, allRounds, timeLeft, gameOver;
        let target, obstacle;
        let dinoState;      // run | jump | duck | hit
        let dinoAnimTimer;
        let countdownInterval;

        function pickTargetAndObstacle() {{
            const targetWord = words[Math.floor(Math.random() * words.length)];
            const isMatch = Math.random() < 0.5;
            let obsWord = targetWord;
            if (!isMatch) {{
                // 找一個跟目標不同意思的單字當作錯誤選項
                do {{
                    obsWord = words[Math.floor(Math.random() * words.length)];
                }} while (obsWord.chinese === targetWord.chinese && words.length > 1);
            }}
            target = targetWord;
            obstacle = {{ word: obsWord, x: W + 20, isMatch: isMatch, resolved: false }};
        }}

        // outcome: "correct"（判斷對）| "wrong"（按鍵判斷錯）| "collision"（來不及判斷、撞到）
        function resolveRound(outcome) {{
            if (obstacle.resolved) return;
            obstacle.resolved = true;
            obstacle.outcome = outcome;
            rounds++;
            const isCorrect = (outcome === "correct");

            // 不管對錯，每一題都要記下來，之後才能一次更新每個單字的複習排程
            allRounds.push({{ word_id: obstacle.word.word_id, correct: isCorrect }});

            if (isCorrect) {{
                score++;
                dinoState = "jump";
                playSound(correctSound);
            }} else {{
                wrongWords.push({{
                    japanese: obstacle.word.japanese,
                    chinese: obstacle.word.chinese,
                    category: obstacle.word.category
                }});
                dinoState = (outcome === "collision") ? "hit" : "duck";
                playSound(wrongSound);
            }}
            dinoAnimTimer = 18;
            document.getElementById("score").innerText = score;
            document.getElementById("rounds").innerText = rounds;
            setTimeout(pickTargetAndObstacle, 400);
        }}

        function handleKey(e) {{
            if (gameOver || !obstacle || obstacle.resolved) return;
            if (e.key === "1") {{
                e.preventDefault();
                resolveRound(obstacle.isMatch === true ? "correct" : "wrong");
            }} else if (e.key === "2") {{
                e.preventDefault();
                resolveRound(obstacle.isMatch === false ? "correct" : "wrong");
            }}
        }}
        window.addEventListener("keydown", handleKey);

        function drawDino() {{
            let yOffset = 0;
            let xOffset = 0;
            let fontSize = 42;
            let emoji = "🦖";

            if (dinoState === "jump") {{
                // 答對：往上跳
                yOffset = -30;
            }} else if (dinoState === "duck") {{
                // 判斷錯（有按鍵但按錯）：蹲下、變矮
                yOffset = 14;
                fontSize = 34;
            }} else if (dinoState === "hit") {{
                // 撞到題目（來不及判斷）：左右震動 + 顯示撞擊效果
                xOffset = Math.sin(dinoAnimTimer * 1.6) * 6;
            }}

            if (dinoState === "hit" && dinoAnimTimer > 0) {{
                ctx.font = "26px serif";
                ctx.fillText("💥", DINO_X + 8, GROUND_Y - 34);
            }}

            // 恐龍預設面向左邊，這裡水平翻轉讓牠面向右邊（障礙物來的方向）
            ctx.save();
            ctx.font = fontSize + "px serif";
            const dx = DINO_X - 20 + xOffset;
            const dy = GROUND_Y + yOffset;
            ctx.translate(dx, dy);
            ctx.scale(-1, 1);
            ctx.fillText(emoji, 0, 0);
            ctx.restore();

            if (dinoAnimTimer > 0) {{
                dinoAnimTimer--;
                if (dinoAnimTimer === 0) dinoState = "run";
            }}
        }}

        function drawObstacle() {{
            if (!obstacle) return;
            const boxW = 90, boxH = 46;
            const bx = obstacle.x, by = GROUND_Y - boxH + 6;
            ctx.fillStyle = obstacle.resolved
                ? (obstacle.outcome === "correct" ? "#2ecc71" : "#e74c3c")
                : "#3a86e8";
            ctx.strokeStyle = "#111";
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.roundRect(bx, by, boxW, boxH, 8);
            ctx.fill();
            ctx.stroke();
            ctx.fillStyle = "#fff";
            ctx.font = "bold 20px sans-serif";
            ctx.textAlign = "center";
            ctx.fillText(obstacle.word.japanese, bx + boxW / 2, by + boxH / 2 + 7);
            ctx.textAlign = "left";
        }}

        function drawGround() {{
            ctx.strokeStyle = "#555";
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(0, GROUND_Y + 6);
            ctx.lineTo(W, GROUND_Y + 6);
            ctx.stroke();
        }}

        // 題目（中文）畫在遊戲框內部的上方，讓玩家不用把視線移出畫面
        function drawTarget() {{
            if (!target) return;
            ctx.fillStyle = "#ffd166";
            ctx.font = "bold 30px sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("題目：" + target.chinese, W / 2, 46);
            ctx.textAlign = "left";
        }}

        function loop() {{
            ctx.clearRect(0, 0, W, H);
            drawGround();
            drawTarget();
            drawDino();

            if (obstacle) {{
                if (!obstacle.resolved) {{
                    obstacle.x -= 3.2;
                    if (obstacle.x <= DINO_X - 10) {{
                        // 撞到恐龍還沒判斷 → 算撞到
                        resolveRound("collision");
                    }}
                }}
                drawObstacle();
            }}

            if (!gameOver) {{
                requestAnimationFrame(loop);
            }}
        }}

        function endGame() {{
            gameOver = true;
            clearInterval(countdownInterval);
            window.removeEventListener("keydown", handleKey);

            const resultBox = document.getElementById("result-box");
            resultBox.style.display = "block";
            let wrongListHtml = wrongWords.length
                ? "<ul style='text-align:left; display:inline-block;'>" +
                  wrongWords.map(w => `<li>${{w.japanese}}（${{w.chinese}}）</li>`).join("") +
                  "</ul>"
                : "<p>本局全對，太厲害了！🎉</p>";
            resultBox.innerHTML = `
                <h3>⏰ 時間到！本局結果</h3>
                <p>✅ 答對 ${{score}} / ${{rounds}} 題</p>
                ${{wrongListHtml}}
                <button id="restart-btn" style="
                    margin-top:10px; padding:8px 24px; font-size:1rem; font-weight:bold;
                    background:#3a86e8; color:white; border:none; border-radius:8px; cursor:pointer;
                ">🔄 重新開始</button>
            `;
            document.getElementById("restart-btn").addEventListener("click", startGame);

            window.__dinoResult = {{
                score: score,
                totalRounds: rounds,
                wrongWords: wrongWords,
                rounds: allRounds
            }};
            try {{
                localStorage.setItem("dino_result", JSON.stringify(window.__dinoResult));
            }} catch (e) {{}}
        }}

        function startGame() {{
            score = 0;
            rounds = 0;
            wrongWords = [];
            allRounds = [];
            timeLeft = 60;
            gameOver = false;
            target = null;
            obstacle = null;
            dinoState = "run";
            dinoAnimTimer = 0;

            document.getElementById("score").innerText = "0";
            document.getElementById("rounds").innerText = "0";
            document.getElementById("timer").innerText = "60";
            document.getElementById("result-box").style.display = "none";
            document.getElementById("result-box").innerHTML = "";

            window.removeEventListener("keydown", handleKey);
            window.addEventListener("keydown", handleKey);

            clearInterval(countdownInterval);
            countdownInterval = setInterval(function() {{
                if (gameOver) {{ clearInterval(countdownInterval); return; }}
                timeLeft--;
                document.getElementById("timer").innerText = timeLeft;
                if (timeLeft <= 0) {{
                    endGame();
                }}
            }}, 1000);

            pickTargetAndObstacle();
            loop();
        }}

        startGame();
    }})();
    </script>
    """

    components.html(game_html, height=420)

    st.divider()
    st.caption("玩完一局後，記得按下面的按鈕把成績存起來，才會反映在小恐龍日誌裡。")

    if st.button("📤 送出本局成績", use_container_width=True):
        # st_javascript 是雙向元件，第一次呼叫會先回傳 0，等它準備好真正的值
        # 之後才會「自動」觸發一次 Streamlit 重新執行；用 session_state 記住
        # 「正在等待送出」的狀態，這樣才不會因為按鈕的按下狀態沒有跨到那次
        # 自動重新執行，而讀不到最終結果。
        st.session_state.dino_submit_pending = True

    if st.session_state.get("dino_submit_pending"):
        _submit_result(user_id)


def _submit_result(user_id: int):
    """
    從瀏覽器的 localStorage 讀回小恐龍的遊戲結果，套用 SM-2 更新學習紀錄，
    並存一筆 game_sessions 紀錄。
    """
    raw = st_javascript("localStorage.getItem('dino_result')")

    # st_javascript 第一次執行時，JS 橋接還沒建立好會先回傳 0，
    # 這時先不要下任何結論，等它自動觸發下一次重新執行再檢查一次。
    if raw == 0:
        st.info("讀取中，請稍候...")
        return

    st.session_state.dino_submit_pending = False

    if not raw:
        st.warning("目前沒有偵測到新的遊戲結果，請先玩完一局小恐龍再送出。")
        return

    try:
        result = json.loads(raw)
    except (TypeError, ValueError):
        st.error("讀取遊戲結果失敗，請重新玩一局再試。")
        return

    rounds = result.get("rounds", [])
    if not rounds:
        st.warning("這局還沒有任何作答紀錄。")
        return

    # 套用 SM-2：一次查出這批單字現有的學習紀錄，再逐一計算新排程並寫回
    word_ids = list({r["word_id"] for r in rounds})
    records = get_learning_records_by_word_ids(user_id, word_ids)

    for r in rounds:
        record = records.get(r["word_id"])
        if not record:
            continue  # 理論上不會發生，保險起見跳過
        quality = 5 if r["correct"] else 1
        new_ef, new_interval, next_review = calculate_next_review(
            ease_factor=record["ease_factor"],
            interval_days=record["interval_days"],
            quality=quality,
        )
        update_learning_record(
            record_id=record["record_id"],
            ease_factor=new_ef,
            interval_days=new_interval,
            next_review=next_review,
            correct=1 if r["correct"] else 0,
            wrong=0 if r["correct"] else 1,
        )

    save_game_session(
        user_id=user_id,
        score=result.get("score", 0),
        total_rounds=result.get("totalRounds", len(rounds)),
        wrong_words=result.get("wrongWords", []),
    )

    # 存完後清掉 localStorage，避免同一局成績被重複送出
    st_javascript("localStorage.removeItem('dino_result')")

    st.success(f"✅ 成績已記錄！本局答對 {result.get('score', 0)} / {result.get('totalRounds', len(rounds))} 題")
