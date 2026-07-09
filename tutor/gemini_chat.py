from google import genai
from google.genai import types
import os
import sys

# rag / config 都在專案根目錄，需要把根目錄加入 Python 搜尋路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rag.retriever import get_retriever
from config import get_secret

# ============================================================
# 系統提示詞（System Prompt）
# AI 老師的「角色說明書」，讓 Gemini 知道要扮演什麼角色。
# 因為 v1 API 不支援 systemInstruction 欄位，
# 改成把角色設定注入為對話歷史的第一筆，效果完全相同。
# ============================================================
def _build_system_prompt(level: str) -> str:
    """依學習程度產生對應的系統提示詞。"""
    if level == "N4":
        level_instruction = (
            "學生目前程度是 JLPT N4，已有 N5 基礎。"
            "可以使用 N4 範圍的文法和單字，解釋時可以稍微精簡，不需要從最基礎開始說明。"
            "例句可以稍微複雜一些，並可以介紹 N4 特有的文法（如〜ば、〜のに、〜くせに 等）。"
        )
    else:
        level_instruction = (
            "學生目前程度是 JLPT N5，是日語初學者。"
            "請使用最基礎的文法和單字，解釋要非常詳細，每個概念都要從零開始說明。"
            "例句要簡單，使用 N5 範圍的單字（如 食べる、行く、大きい 等）。"
            "避免使用 N4 以上的複雜文法。"
        )

    return f"""
你是一位親切、有耐心的日語老師，名字叫「小葵老師」。
你的學生是正在學習日文的繁體中文使用者。

【學生程度】
{level_instruction}

請遵守以下規則：
1. 永遠用繁體中文解釋和回應，日文單字或例句後面要加上中文翻譯。
2. 語氣要溫柔鼓勵，讓學生不怕犯錯、勇於開口。
3. 回答要有條理：先解釋用法，再舉 2-3 個例句，最後給學習小提示。
4. 如果學生的日文有錯誤，要委婉指出並說明正確用法。
5. 適合所有年齡層，用語淺顯易懂，避免過於艱深的語言學術語。
6. 偶爾可以加入鼓勵的話，例如「你學得很好！」「繼續加油！」
7. 你是一位真正的日語老師，除了文法之外，單字說法、發音、日常會話、
   翻譯等各種日語問題都要回答。就算文法知識庫裡沒有相關資料
   （例如學生問「電燈的日文怎麼說」這種單字問題），也要用你自己的
   日語知識正確、完整地回答，絕對不要說「不知道」或拒絕回答。
"""


class JapaneseTutor:
    """
    日文 AI 家教類別，封裝所有與 Gemini API 的互動。

    使用方式：
        tutor = JapaneseTutor()
        reply = tutor.chat("請解釋て形的用法")
        print(reply)
    """

    def __init__(self, level: str = "N5"):
        """
        初始化：建立 Gemini 客戶端、設定模型與對話 session。

        參數：
            level - 學習程度 'N5' 或 'N4'，影響系統提示詞與 RAG 搜尋範圍
        """
        self.level = level
        api_key = get_secret("GEMINI_API_KEY")

        # AQ. 開頭的新版 key 需要指定 api_version='v1'
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version='v1')
        )

        # 模型名稱：gemini-2.5-flash 支援付費 API，回應品質高
        self.model_name = "gemini-2.5-flash"

        # 額度控制：限制每次回應最多幾個 token
        # 注意：v1 API 不支援 thinking_config 欄位（會報 400 INVALID_ARGUMENT
        # Unknown name "thinkingConfig"），只能靠拉高 max_output_tokens 來避免
        # gemini-2.5-flash 的內部思考佔掉額度、導致回答講到一半被截斷。
        self.generation_config = types.GenerateContentConfig(
            max_output_tokens=4096,
            temperature=0.7,  # 0=保守穩定，1=創意活潑，0.7 是平衡點
        )

        # 使用全域共用的 retriever，避免重複載入 SentenceTransformer 模型
        self.retriever = get_retriever()

        self._start_session()

    def _start_session(self):
        """建立帶有角色設定的對話 session（內部使用）。"""
        system_prompt = _build_system_prompt(self.level)
        initial_history = [
            types.Content(
                role="user",
                parts=[types.Part(text=f"請按照以下設定扮演角色，之後所有對話都要照這個風格：{system_prompt}")]
            ),
            types.Content(
                role="model",
                parts=[types.Part(text="好的！我是小葵老師，很高興成為你的日語學習夥伴！有任何日語問題都可以問我，我會用繁體中文詳細解釋。加油！✨")]
            ),
        ]
        self.chat_session = self.client.chats.create(
            model=self.model_name,
            history=initial_history,
            config=self.generation_config
        )

    def chat(self, user_message):
        """
        傳送使用者訊息給 Gemini，回傳 AI 的回覆文字。

        參數：
            user_message (str)：使用者輸入的問題或句子

        回傳：
            str：AI 老師的回覆文字
        """
        try:
            response = self.chat_session.send_message(user_message)
            return response.text

        except Exception as e:
            print(f"[ERROR] Gemini API 呼叫失敗：{e}")
            raise

    def _build_rag_prompt(self, user_message, context):
        """
        把知識庫搜尋結果組成 prompt（chat_with_rag 與串流版共用）。

        重點：知識庫是「輔助參考」而不是「唯一依據」。
        - 如果知識庫資料跟問題相關 → 參考它回答，並在最後標注來源。
        - 如果知識庫沒有涵蓋（例如單字、發音、翻譯、一般會話問題）
          → 直接用你自己的日語知識正確回答，不要因為知識庫沒有就拒答，
            這種情況不需要硬湊「參考來源」。
        """
        return f"""你是親切的日語老師「小葵老師」，請用繁體中文回答學生的問題。

以下是從「文法知識庫」中找到的可能相關資料（僅供參考，知識庫只收錄文法，
不含單字表，內容不一定和問題相關）：
{context}

學生的問題：
{user_message}

請這樣回答：
1. 如果上面的知識庫資料和問題相關，就參考它說明文法用法與結構，
   並在回答最後標注：「📚 參考來源：」列出你參考了哪些資料的來源欄位。
2. 如果知識庫資料和問題無關，或問題是單字說法、發音、翻譯、日常會話等
   （知識庫查不到的內容），請直接用你自己的日語知識正確、完整地回答，
   這種情況不必加「參考來源」，也絕對不要說「知識庫裡沒有」或拒絕回答。
3. 不論哪種情況，都要舉 2-3 個例句（附中文翻譯）幫助學生理解。
"""

    def chat_with_rag(self, user_message):
        """
        【有 RAG 的對話】先從知識庫搜尋相關文法，再把資料塞進 prompt 給 Gemini 回答。

        與 chat()（無 RAG）的差別：
          chat()         → 直接把問題丟給 Gemini，靠 AI 自己的訓練記憶回答
                           優點：快；缺點：可能有幻覺、來源不明
          chat_with_rag() → 先從我們的文法知識庫找相關條目，連同問題一起送給 Gemini
                            優點：回答有據可查、附來源；缺點：多一次 ChromaDB 搜尋

        參數：
            user_message (str)：使用者的問題

        回傳：
            str：AI 老師的回覆（含參考來源）
        """
        # 步驟 1：從 ChromaDB 搜尋最相關的文法條目（依程度篩選，取前 3 筆）
        results = self.retriever.search(user_message, n_results=3, level=self.level)
        context = self.retriever.format_context(results)

        # 步驟 2：把知識庫資料注入 prompt（知識庫僅作輔助參考，查不到就用 AI 自己的知識）
        enriched_prompt = self._build_rag_prompt(user_message, context)

        # 步驟 3：送出給 Gemini
        try:
            response = self.chat_session.send_message(enriched_prompt)
            return response.text
        except Exception as e:
            print(f"[ERROR] Gemini RAG 呼叫失敗：{e}")
            raise

    def chat_with_rag_stream(self, user_message):
        """
        跟 chat_with_rag() 邏輯一樣（先查 RAG 知識庫再問 Gemini），
        差別是用「串流」方式一段一段吐出回覆文字，而不是等整段回覆生成完才回傳。

        用法（generator，要用 for 迴圈邊收邊顯示）：
            for chunk_text in tutor.chat_with_rag_stream(user_message):
                print(chunk_text, end="")

        這樣使用者在畫面上可以馬上看到老師開始打字，
        不用像 chat_with_rag() 一樣整段等完才一次顯示，體感速度快很多
        （雖然 Gemini 生成全部內容的總時間沒有變，但不用乾等）。
        """
        results = self.retriever.search(user_message, n_results=3, level=self.level)
        context = self.retriever.format_context(results)

        enriched_prompt = self._build_rag_prompt(user_message, context)
        try:
            stream = self.chat_session.send_message_stream(enriched_prompt)
            for chunk in stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            print(f"[ERROR] Gemini RAG 串流呼叫失敗：{e}")
            raise

    def clear_history(self):
        """
        清除對話歷史，重新開始一段新的對話。
        （不影響已存入資料庫的紀錄，只清除記憶體裡的上下文）
        """
        self._start_session()
        print("✅ 對話歷史已清除")
