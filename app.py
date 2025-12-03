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

# --- AIへの指示書（担当者特定を強化） ---
SYSTEM_PROMPT = """
あなたは家族の会話を分析するシステムです。
入力されたメッセージが「タスク」や「予定」である場合のみJSONで出力してください。
雑談は type: "null" にしてください。

【重要な指示：担当者の特定】
会話の文脈から「誰がやるべきか（担当者）」を推測して assignee に入れてください。
その際、以下のルールを優先してください。

1. 「私」「俺」「僕」など発言者自身を指す言葉の場合
   → 出力は必ず "発言者本人" としてください。（後でシステムが本名に置き換えます）

2. 第三者を指す場合（パパ、ママなど）
   → 文脈に合わせて「お父さん」「お母さん」などに統一してください。

【JSONフォーマット】
{
    "type": "task" または "event" または "null",
    "summary": "内容（短く）",
    "date": "日付（あれば）",
    "assignee": "担当者の名前"
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

# タスク完了API
@app.route("/complete_task", methods=['POST'])
def complete_task():
    data = request.json
    task_id = data.get('id')
    summary = data.get('summary')
    source_id = data.get('source_id')

    if not task_id:
        return jsonify({"status": "error"}), 400

    try:
        supabase.table("tasks").delete().eq("id", task_id).execute()

        if source_id:
            try:
                line_bot_api.push_message(
                    source_id,
                    TextSendMessage(text=f"✅ 完了: {summary}\nお疲れ様でした！")
                )
            except LineBotApiError:
                pass # 送れなくてもOK

        return jsonify({"status": "success"})
    except Exception as e:
        print(f"削除エラー: {e}")
        return jsonify({"status": "error"}), 500

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
    user_id = event.source.user_id
    # グループIDがあればそっちを、なければユーザーIDを送信元とする
    source_id = event.source.group_id if event.source.type == 'group' else user_id

    # ★Lv.2追加：LINEのプロフィール名を取得する
    sender_name = "不明なユーザー"
    try:
        if event.source.type == 'group':
            profile = line_bot_api.get_group_member_profile(event.source.group_id, user_id)
        else:
            profile = line_bot_api.get_profile(user_id)
        sender_name = profile.display_name
    except Exception as e:
        print(f"名前取得エラー: {e}")

    try:
        # AIに「誰が発言したか」もプロンプトに含めて渡す
        full_prompt = f"発言者: {sender_name}\nメッセージ: {user_msg}"
        
        response = model.generate_content(full_prompt)
        result = json.loads(response.text)

        msg_type = result.get("type")
        summary = result.get("summary")
        date_str = result.get("date")
        assignee = result.get("assignee")

        # 「発言者本人」なら、LINEの表示名に置き換える
        if assignee == "発言者本人":
            assignee = sender_name

        if msg_type == "null":
            return

        # Supabaseに保存
        data_to_save = {
            "type": msg_type,
            "summary": summary,
            "date": date_str,
            "assignee": assignee,
            "source_id": source_id 
        }
        supabase.table("tasks").insert(data_to_save).execute()

        reply_text = ""
        if msg_type == "task":
            reply_text = f"🛒 リストに追加: {summary}\n(担当: {assignee})"
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