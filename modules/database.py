import os
from supabase import create_client, Client
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

# Supabaseに接続する準備
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

# キーがない場合の安全策
if not url or not key:
    print("Warning: SupabaseのURLまたはKEYが設定されていません")
    supabase = None
else:
    supabase: Client = create_client(url, key)

# modules/database.py の add_task を修正

def add_task(family_id, content, task_type="task", topic="雑多なタスク", assignee=None):
    """
    タスクを追加する（assignee引数を受け取り、DBのassignee_id列に入れる）
    """
    if not supabase:
        return None

    data = {
        "family_group_id": family_id,
        "content": content,
        "type": task_type,
        "topic": topic,
        "assignee_id": assignee, # ← ここ！DBの列名(assignee_id)に合わせます
        "status": "pending"
    }
    
    try:
        response = supabase.table("tasks").insert(data).execute()
        return response
    except Exception as e:
        print(f"Supabase Error: {e}")
        return None
    
# --- modules/database.py の既存コードの下に追加 ---

def save_message(group_id, user_id, content, role="user"):
    """
    LINEのメッセージをログとして保存する
    """
    if not supabase:
        return None
    
    data = {
        "group_id": group_id,
        "user_id": user_id,
        "content": content,
        "role": role
    }
    try:
        supabase.table("messages").insert(data).execute()
    except Exception as e:
        print(f"Save Message Error: {e}")

def get_recent_messages(group_id, limit=5):
    """
    直近の会話ログを取得する（コンテキスト用）
    """
    if not supabase:
        return []
    
    try:
        # 最新のものから順に取得
        response = supabase.table("messages")\
            .select("content, role, created_at")\
            .eq("group_id", group_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        # 古い順（時系列）に並べ直して返す
        return sorted(response.data, key=lambda x: x['created_at'])
    except Exception as e:
        print(f"Get History Error: {e}")
        return []
    
def assign_latest_task(group_id, assignee_name):
    """
    そのグループの直近の未割り当てタスクを探し、
    【日常系のトピックの場合のみ】担当者を設定する
    """
    if not supabase:
        return None, None

    # アサインを許可するトピック（これ以外はプロジェクトとみなしてアサインしない）
    ASSIGNABLE_TOPICS = ["一般", "買い物", "家事", "雑多なタスク", "未分類"]

    try:
        # 1. 直近の未完了タスクを取得
        response = supabase.table("tasks")\
            .select("id, content, topic")\
            .eq("family_group_id", group_id)\
            .eq("status", "pending")\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        
        tasks = response.data
        
        if not tasks:
            return None, None # タスクがない

        target_task = tasks[0]
        topic = target_task.get('topic', '一般')

        # ★ここが重要！
        # トピックが「日常系」に含まれていないなら、アサインせずに終了
        if topic not in ASSIGNABLE_TOPICS:
            print(f"Skipped assignment for project topic: {topic}")
            return None, "project_locked" # プロジェクト案件なのでアサインしない

        # 2. 担当者を更新
        supabase.table("tasks")\
            .update({"assignee_id": assignee_name})\
            .eq("id", target_task['id'])\
            .execute()
            
        return target_task['content'], assignee_name

    except Exception as e:
        print(f"Assign Error: {e}")
        return None, None
    
    
def get_active_topics(group_id):
    """
    現在進行中のプロジェクト（トピック）名のリストを取得する
    """
    if not supabase:
        return []
    
    try:
        # pending（未完了）のタスクから topic を取得
        response = supabase.table("tasks")\
            .select("topic")\
            .eq("family_group_id", group_id)\
            .eq("status", "pending")\
            .execute()
        
        # 重複を排除してリスト化（空文字やNoneは除外）
        topics = list(set([row['topic'] for row in response.data if row.get('topic')]))
        return topics
    except Exception as e:
        print(f"Get Topics Error: {e}")
        return []