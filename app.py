import os
import json
from flask import Flask, request, abort, render_template, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
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

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
genai.configure(api_key=GEMINI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SYSTEM_PROMPT = """
あなたは家族の会話を分析するシステムです。
入力されたメッセージが「タスク」や「予定」である場合のみJSONで出力してください。
雑談は type: "null" にしてください。
{
    "type": "task" または "event" または "null",
    "summary": "内容（短く）",
    "date": "日付（あれば）"
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

@app.route("/list")
def show_list():
    return render_template("index.html")

# ▼▼▼ 新機能：タスク完了API ▼▼▼
@app.route("/complete_task", methods=['POST'])
def complete_task():
    data = request.json
    task_id = data.get('id')
    summary = data.get('summary')
    source_id = data.get('source_id') # LINEの送信先ID

    if not task_id:
        return jsonify({"status": "error"}), 400

    try:
        # 1. Supabaseから削除
        supabase.table("tasks").delete().eq("id", task_id).execute()

        # 2. LINEに通知（source_idがある場合のみ）
        if source_id:
            try:
                line_bot_api.push_message(
                    source_id,
                    TextSendMessage(text=f"✅ 完了: {summary}\nお疲れ様でした！")
                )
            except LineBotApiError as e:
                print(f"LINE送信エラー: {e}")
                # ブロックされている等の理由で送れなくても、削除は成功とする

        return jsonify({"status": "success"})
    except Exception as e:
        print(f"削除エラー: {e}")
        return jsonify({"status": "error"}), 500
# ▲▲▲ ここまで ▲▲▲

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
    
    # 送信元のIDを取得（グループID または ユーザーID）
    source_id = event.source.group_id if event.source.type == 'group' else event.source.user_id

    try:
        response = model.generate_content(user_msg)
        result = json.loads(response.text)

        msg_type = result.get("type")
        summary = result.get("summary")
        date_str = result.get("date")

        if msg_type == "null":
            return

        # Supabaseに保存（source_idを追加！）
        data_to_save = {
            "type": msg_type,
            "summary": summary,
            "date": date_str,
            "source_id": source_id 
        }
        supabase.table("tasks").insert(data_to_save).execute()

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)