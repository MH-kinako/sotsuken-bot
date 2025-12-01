import os
import json
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai
from supabase import create_client, Client

app = Flask(__name__)

# --- 環境変数の読み込み ---
CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

# --- 各種クライアント設定 ---
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

genai.configure(api_key=GEMINI_API_KEY)
# Supabaseへの接続
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- AIへの指示書（JSONモード） ---
SYSTEM_PROMPT = """
あなたは家族の会話を分析するシステムです。
入力されたメッセージが「タスク（買い物や作業）」や「予定（イベント）」である場合のみ、
以下のJSON形式で出力してください。
ただの雑談や挨拶の場合は、必ず type を "null" にしてください。

【JSONフォーマット】
{
    "type": "task" または "event" または "null",
    "summary": "タスクの内容を短く（例：牛乳を買う）",
    "date": "日付情報があれば（例：明日、2025/12/01）。なければ空文字"
}
"""

model = genai.GenerativeModel(
    'models/gemini-2.0-flash',
    system_instruction=SYSTEM_PROMPT,
    generation_config={"response_mime_type": "application/json"}
)

@app.route("/")
def home():
    return "Bot is running!"

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
    user_msg = event.message.text
    
    try:
        # 1. AIに分析させる
        response = model.generate_content(user_msg)
        result = json.loads(response.text) # JSONデータとして読み込む

        print(f"AI解析結果: {result}") # ログ確認用

        # 2. 結果によって動きを変える
        msg_type = result.get("type")
        summary = result.get("summary")
        date_str = result.get("date")

        # 雑談(null)なら何もしない（既読スルー）
        if msg_type == "null":
            return

        # 3. タスクか予定なら Supabase に保存
        data_to_save = {
            "type": msg_type,
            "summary": summary,
            "date": date_str
        }
        # 'tasks'テーブルに追加
        supabase.table("tasks").insert(data_to_save).execute()

        # 4. 保存完了メッセージをLINEに送る（黒子なので簡潔に）
        reply_text = ""
        if msg_type == "task":
            reply_text = f"🛒 リストに追加: {summary}"
        elif msg_type == "event":
            reply_text = f"📅 予定をメモ: {summary} ({date_str})"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )

    except Exception as e:
        print(f"Error: {e}")
        # エラー時はユーザーには何も言わない（または「エラー」とだけ返す）

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)