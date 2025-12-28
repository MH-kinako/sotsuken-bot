import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEYが設定されていません")

client = genai.Client(api_key=api_key)

def analyze_message(text: str, history: list = None, existing_topics: list = None):
    """
    Geminiを使ってメッセージを解析する
    Args:
        text: 今回のユーザー発言
        history: 直近の会話ログ
        existing_topics: 現在進行中のプロジェクト名リスト（カンニングペーパー）
    """
    if history is None:
        history = []
    if existing_topics is None:
        existing_topics = []

    history_text = ""
    for h in history:
        role_label = "家族" if h['role'] == "user" else "Bot"
        history_text += f"- {role_label}: {h['content']}\n"

    today_str = datetime.now().strftime("%Y-%m-%d")

    system_prompt = f"""
    あなたは家族のチャットから「やるべきこと(Task)」を抽出するAIです。
    会話の流れを読んで、適切なカテゴリと具体的なタスク名を生成してください。
    
    ### 今日の日付
    {today_str}

    ### 📁 現在進行中のプロジェクト名（表記ゆれ防止用リスト）
    {existing_topics}
    
    ### ⚠️ トピック名（プロジェクト名）の決定ルール
    1. **最優先:** 上記のリストの中に、今回の会話に関連するものがあれば、**一字一句変えずにその名前を使用すること。**
       （例：リストに「京都旅行」があり、会話が「宿どうする？」なら、トピックは「京都旅行」にする。「京都の宿」などと勝手に変えない）
    2. 新規: リストに関連するものがない場合のみ、新しい具体的なイベント名を生成する。（例：「お父さんの誕生日会」「新潟旅行」）
    3. 禁止: 「旅行」「食事」のような抽象的な大分類は禁止。

    ### ⚠️ タスク名（summary）の生成ルール
    1. **「〜を〜する」という命令形・行動ベースにすること。**
       - ❌ 悪い例：「京都旅行の日程について話している」「宿をどうするか相談」
       - ⭕️ 良い例：「京都旅行の日程を決める」「宿を予約する」「候補地をリストアップする」
    2. 会話の状況説明ではなく、ユーザーが**次にアクションできる言葉**に変換すること。

    ### 直近の会話ログ
    {history_text}

    ### 分類カテゴリー
    - "task": 明確な行動、買い物、予約、調べること。（※担当者はここでは決めない）
    - "accept": 直前のタスクや提案に対する「引き受け」「了解」「私がやる」という意思表示。
    - "idea": 旅行の相談、提案、まだ決まっていないメモ。（※これも行動ベースの名前にする。「〜を考える」など）
    - null: ただの相槌、完了報告、雑談、同意のみの場合。

    ### 出力フォーマット (JSON)
    {{
        "category": "task" or "idea" or "accept" or null,
        "topic": "プロジェクト名",
        "summary": "タスクの内容（動詞で終わる短いフレーズ）",
        "due_date": "YYYY-MM-DD(なければnull)",
        "assignee": "null" 
    }}
    """

    try:
        # ご指定の gemini-2.5-flash を使用
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=f"{system_prompt}\n\nユーザーの最新メッセージ: {text}",
            config=types.GenerateContentConfig(
                response_mime_type='application/json'
            )
        )
        return json.loads(response.text)

    except Exception as e:
        print(f"Gemini Error: {e}")
        # 万が一 2.5 がまだAPIで通らない場合のフォールバックなどを検討する場合はここ
        return {"category": None}