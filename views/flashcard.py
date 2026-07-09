"""
views/flashcard.py — 單字卡頁面（依詞性分類瀏覽）

流程：
  1. 先依詞性（動詞／名詞／形容詞）分類，顯示各類的按鈕與單字數
  2. 點某個詞性 → 顯示該詞性的所有單字，做成「可翻面卡片」
       正面：日文 + 假名
       背面：中文意思（點卡片一下翻面）
  3. 「⬅️ 返回詞性選單」按鈕回到分類頁

注意：這頁純粹是「背單字/瀏覽」用，不寫任何學習紀錄，
      跟「單字小恐龍」（會存成績）是分開的。
"""

import json
import streamlit as st
import streamlit.components.v1 as components
from database.queries import get_vocabulary_by_level


# 詞性顯示用的小圖示
_CATEGORY_ICONS = {
    "動詞": "🏃",
    "名詞": "📦",
    "形容詞": "🎨",
}


@st.cache_data(ttl=600, show_spinner=False)
def _cached_vocab(level: str) -> list[dict]:
    """
    快取版的單字查詢。單字是靜態資料，不需要每次 rerun 都打 Azure SQL。
    快取 10 分鐘（ttl=600），所以「返回詞性選單」等 rerun 會直接用記憶體資料，
    不再有每次約 240ms 的雲端往返延遲。（若之後有補單字，最多 10 分鐘後自動更新。）
    """
    return get_vocabulary_by_level(level)


def show(user_id: int = 1, user_level: str = "N5"):
    """單字卡頁面入口。app.py 呼叫 flashcard.show(user_id, user_level)。"""

    st.title("🃏 單字卡")
    st.caption(f"目前程度：**{user_level}**　｜　依詞性分類瀏覽，點卡片可翻面看中文")

    words = _cached_vocab(user_level)
    if not words:
        st.warning("這個程度目前沒有單字資料。")
        return

    # 依詞性分組
    by_category: dict[str, list[dict]] = {}
    for w in words:
        by_category.setdefault(w["category"], []).append(w)

    selected = st.session_state.get("flashcard_category")

    # ── 還沒選詞性：顯示分類選單 ─────────────────────────────────────────────
    if selected not in by_category:
        st.markdown("#### 選擇想複習的詞性")
        cols = st.columns(len(by_category))
        for col, (cat, cat_words) in zip(cols, by_category.items()):
            with col:
                icon = _CATEGORY_ICONS.get(cat, "📖")
                if st.button(
                    f"{icon} {cat}\n\n{len(cat_words)} 個單字",
                    use_container_width=True,
                    key=f"cat_{cat}",
                ):
                    st.session_state.flashcard_category = cat
                    st.rerun()
        return

    # ── 已選詞性：顯示該詞性所有單字的可翻面卡片 ─────────────────────────────
    cat_words = by_category[selected]
    icon = _CATEGORY_ICONS.get(selected, "📖")

    if st.button("⬅️ 返回詞性選單", key="back_to_categories"):
        st.session_state.pop("flashcard_category", None)
        st.rerun()

    st.markdown(f"### {icon} {selected}　（{len(cat_words)} 個單字）")
    st.caption("👆 點任一張卡片翻面看中文意思")

    _render_flip_cards(cat_words)


def _render_flip_cards(cat_words: list[dict]):
    """把一組單字渲染成可點擊翻面的卡片牆（純前端 HTML/CSS/JS）。"""
    # 把單字資料轉成 JSON 餵給 JS
    cards_json = json.dumps(cat_words, ensure_ascii=False)

    # 依單字數估算需要的高度（每行約 3 張、每張連間距約 170px）
    import math
    rows = math.ceil(len(cat_words) / 3)
    height = rows * 176 + 24

    html = f"""
    <style>
      .card-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 16px;
        font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif;
      }}
      .flip-card {{
        background: transparent;
        perspective: 1000px;
        height: 150px;
        cursor: pointer;
      }}
      .flip-inner {{
        position: relative;
        width: 100%;
        height: 100%;
        transition: transform 0.5s;
        transform-style: preserve-3d;
      }}
      .flip-card.flipped .flip-inner {{ transform: rotateY(180deg); }}
      .flip-face {{
        position: absolute;
        inset: 0;
        -webkit-backface-visibility: hidden;
        backface-visibility: hidden;
        border-radius: 14px;
        border: 3px solid #1a1a1a;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
        padding: 8px;
      }}
      .flip-front {{
        background: #ffffff;
        color: #1a1a1a;
        box-shadow: 4px 4px 0px #c0392b;
      }}
      .flip-back {{
        background: #3a86e8;
        color: #ffffff;
        box-shadow: 4px 4px 0px #b03060;
        transform: rotateY(180deg);
      }}
      .jp {{ font-size: 1.5rem; font-weight: 700; }}
      .kana {{ font-size: 1rem; color: gray; margin-top: 6px; }}
      .zh {{ font-size: 1.4rem; font-weight: 700; }}
      .hint {{ font-size: 0.75rem; opacity: 0.6; margin-top: 8px; }}
    </style>

    <div class="card-grid" id="card-grid"></div>

    <script>
      (function() {{
        const cards = {cards_json};
        const grid = document.getElementById("card-grid");
        cards.forEach(function(w) {{
          const card = document.createElement("div");
          card.className = "flip-card";
          card.innerHTML =
            '<div class="flip-inner">' +
              '<div class="flip-face flip-front">' +
                '<div class="jp">' + w.japanese + '</div>' +
                '<div class="kana">' + (w.hiragana || "") + '</div>' +
                '<div class="hint">點一下看中文</div>' +
              '</div>' +
              '<div class="flip-face flip-back">' +
                '<div class="zh">' + w.chinese + '</div>' +
              '</div>' +
            '</div>';
          card.addEventListener("click", function() {{
            card.classList.toggle("flipped");
          }});
          grid.appendChild(card);
        }});
      }})();
    </script>
    """

    components.html(html, height=height, scrolling=True)
