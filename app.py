import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai

app = Flask(__name__)

# Renderの環境変数から鍵を読み込む
CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# LINE Botの設定
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Geminiの設定
genai.configure(api_key=GEMINI_API_KEY)

# AIへの指示書（プロンプト）
SYSTEM_PROMPT = """
あなたは家族の会話を分析するバックグラウンドシステムです。
ユーザーのメッセージを分析し、以下のJSON形式で出力してください。
雑談や挨拶の場合は、typeを"null"にしてください。

【出力フォーマット】
{
    "type": "task" または "event" または "null",
    "summary": "タスクの内容（例：牛乳を買う）",
    "date": "日付があれば（例：明日、日曜日、2025-12-01）"
}

【例1】
入力: "帰りに牛乳買ってきて"
出力: {"type": "task", "summary": "牛乳を買う", "date": "今日"}

【例2】
入力: "来週の日曜、11時に駅前集合ね"
出力: {"type": "event", "summary": "駅前集合", "date": "来週の日曜日 11:00"}

【例3】
入力: "おはよー"
出力: {"type": "null", "summary": "", "date": ""}
"""

# モデル設定（JSONモードを有効化）
# ※ここにさっきの gemini-2.0-flash を使います
model = genai.GenerativeModel(
    'models/gemini-2.0-flash',
    system_instruction=SYSTEM_PROMPT,
    generation_config={"response_mime_type": "application/json"}
)

# ▲▲▲ 書き換えここまで ▲▲▲

def home():
    return "Hello, AI Bot is running!"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    
    try:
        # Geminiにメッセージを投げて、返事をもらう
        response = model.generate_content(user_message)
        ai_reply = response.text
        
        # LINEに返信する
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=ai_reply)
        )
    except Exception as e:
        # エラーが起きたらとりあえずログに出す
        print(f"Error: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="ごめんね、ちょっと調子が悪いみたい。")
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)