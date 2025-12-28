import os
import sys
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv

# モジュールの読み込み
# assign_latest_task と get_active_topics があることを確認してください
from modules.database import add_task, save_message, get_recent_messages, assign_latest_task, get_active_topics
from modules.extractor import analyze_message
from modules.ginza_logic import analyze_with_ginza

load_dotenv()

CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

app = FastAPI()

@app.get("/")
def root():
    return {"message": "FamilyFlow Bot is running!"}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_decode = body.decode("utf-8")
    try:
        handler.handle(body_decode, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text
    user_id = event.source.user_id
    group_id = getattr(event.source, "group_id", user_id)

    print(f"📩 受信: {user_msg}")

    # 1. 履歴取得 & 保存
    history = get_recent_messages(group_id, limit=5)
    save_message(group_id, user_id, user_msg, role="user")
    
    # ★DBから現在進行中のプロジェクト名リストを取得（カンニングペーパー）
    current_topics = get_active_topics(group_id)
    print(f"📂 現在のプロジェクト: {current_topics}")

    # 2. 解析 (GiNZA -> Gemini)
    ginza_result = analyze_with_ginza(user_msg)
    
    if ginza_result:
        print("⚡️ GiNZA判定")
        category = ginza_result.get("category")
        summary = ginza_result.get("summary")
        source_type = "ginza"
        llm_result = {}
    else:
        print("🤔 Gemini判定")
        # ★ここで current_topics を渡して表記ゆれを防ぐ
        llm_result = analyze_message(user_msg, history=history, existing_topics=current_topics)
        category = llm_result.get("category")
        summary = llm_result.get("summary")
        source_type = "llm"

    # 3. 処理分岐
    if category == "task":
        # 新規タスクは「担当者なし」で登録
        topic = llm_result.get("topic", "一般") if source_type == "llm" else "一般"
        add_task(group_id, summary, task_type="task", topic=topic, assignee=None)
        
        # 修正1：説明文を削除し、登録報告だけにする
        reply_text = f"✅ 登録: {summary}\n(案件: {topic})"
        
    elif category == "idea":
        topic = llm_result.get("topic", "アイデア") if source_type == "llm" else "アイデア"
        add_task(group_id, summary, task_type="idea", topic=topic)
        reply_text = f"💡 メモ: {summary} (案件: {topic})"
        
    elif category == "accept":
        # 立候補ロジック
        user_name = "私" 
        
        # 直近のタスクを更新しに行く
        task_content, assigned_name = assign_latest_task(group_id, user_name)
        
        if task_content:
            # 成功した場合（日常タスク）のみ返信する
            reply_text = f"🙆‍♀️ {assigned_name}さんにアサインしました！\n担当: {task_content}"
        
        elif assigned_name == "project_locked":
            # 修正2：プロジェクト案件の場合は、何も言わずに終了する（return）
            print("プロジェクト案件のためアサインスキップ（返信なし）")
            return
            
        else:
            print("割り当て対象なし")
            return

    else:
        print("雑談/その他 スルー")
        return

    # 4. 返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )