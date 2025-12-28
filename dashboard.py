import streamlit as st
import pandas as pd
from modules.database import supabase

# --- ページ設定 ---
st.set_page_config(page_title="FamilyFlow Board", layout="wide")

# --- CSS (最小限・シンプル設定) ---
# ボタンを透明にする設定だけ残します。位置調整のCSSは全部捨てました。
st.markdown("""
<style>
    /* ボタンの枠線と背景を消してアイコン風にする */
    .stButton > button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #555 !important; /* アイコンの色 */
        font-size: 1.5rem !important;
        padding: 0 !important;
    }
    
    /* ホバー時に少し濃くする（色はつけない） */
    .stButton > button:hover {
        color: #000 !important;
        background: rgba(0,0,0,0.05) !important; /* うっすらグレー */
    }

    /* テキストの見た目 */
    .my-task { font-weight: bold; font-size: 1.1rem; color: #333; }
    .other-task { color: #AAA; font-size: 1.1rem; }
    .meta { font-size: 0.8rem; color: #CCC; margin-left: 10px; }
    
    /* 履歴の打ち消し線 */
    .done-text { text-decoration: line-through; color: #CCC; }
    
    /* 区切り線 */
    hr { margin: 10px 0; border-color: #EEE; }
</style>
""", unsafe_allow_html=True)

if not supabase:
    st.error("Supabase設定エラー")
    st.stop()

# --- DB操作関数 ---
def update_status(task_id, new_status):
    supabase.table("tasks").update({"status": new_status}).eq("id", task_id).execute()

def hard_delete_task(task_id):
    supabase.table("tasks").delete().eq("id", task_id).execute()

def assign_task(task_id, user_name):
    supabase.table("tasks").update({"assignee_id": user_name}).eq("id", task_id).execute()

def release_task(task_id):
    supabase.table("tasks").update({"assignee_id": None}).eq("id", task_id).execute()

# --- サイドバー ---
st.sidebar.title("ユーザー選択")
family_members = ["私", "母", "父", "妹"]
current_user = st.sidebar.selectbox("あなたは誰ですか？", family_members)
st.sidebar.markdown("---")
if st.sidebar.button('再読み込み'):
    st.rerun()

# --- データ取得 ---
response = supabase.table("tasks").select("*").order("created_at", desc=True).limit(100).execute()
if not response.data:
    st.info("データがありません")
    st.stop()
df = pd.DataFrame(response.data)

if 'topic' not in df.columns:
    df['topic'] = "一般"
df['topic'] = df['topic'].fillna("一般")

st.title(f"FamilyFlow Board")

ROUTINE_TOPICS = ["一般", "買い物", "家事", "雑多なタスク", "未分類", "アイデア"]
df_routine = df[df['topic'].isin(ROUTINE_TOPICS)]
df_project = df[~df['topic'].isin(ROUTINE_TOPICS)]

# --- レイアウト比率 ---
LAYOUT = [1, 10, 1]

# --- 共通：行を表示する関数 ---
def render_task_row(row, is_history=False):
    # ★ここが魔法の修正点！ vertical_alignment="center" で強制的に中央揃えにする
    c_icon, c_text, c_action = st.columns(LAYOUT, vertical_alignment="center")
    
    assignee = row.get('assignee_id')
    
    # --- 1. 左アイコン ---
    if is_history:
        # 履歴モード: 戻すボタン
        if c_icon.button(":material/undo:", key=f"rev_{row['id']}"):
            update_status(row['id'], "pending")
            st.rerun()
    else:
        # 通常モード
        if assignee is None or assignee == current_user:
            # 完了ボタン (○)
            if c_icon.button(":material/radio_button_unchecked:", key=f"check_{row['id']}"):
                update_status(row['id'], "done")
                st.rerun()
        else:
            # 他人のタスク (Lock)
            # ★ポイント: Markdownではなく「無効化されたボタン」として表示することで、サイズ・位置が完全に一致します
            c_icon.button(":material/lock:", key=f"lock_{row['id']}", disabled=True)

    # --- 2. テキスト ---
    doer = row.get('assignee_id', 'ー')
    date = row['created_at'][5:10].replace('-', '/')
    
    if is_history:
        style = "done-text"
        c_text.markdown(f"<span class='{style}'>{row['content']}</span> <span class='meta'>{doer} ({date})</span>", unsafe_allow_html=True)
    else:
        if assignee == current_user:
            c_text.markdown(f"<span class='my-task'>{row['content']}</span>", unsafe_allow_html=True)
        elif assignee:
            c_text.markdown(f"<span class='other-task'>{row['content']} ({assignee})</span>", unsafe_allow_html=True)
        else:
            c_text.write(f"{row['content']}")

    # --- 3. 右アイコン ---
    if is_history:
        # 履歴モード: 抹消ボタン
        if c_action.button(":material/close:", key=f"hard_{row['id']}"):
            hard_delete_task(row['id'])
            st.rerun()
    else:
        # 通常モード
        if assignee == current_user:
            if c_action.button(":material/remove_circle_outline:", key=f"drop_{row['id']}"):
                release_task(row['id'])
                st.rerun()
        elif assignee:
            c_action.write("") 
        else:
            if c_action.button(":material/person_add:", key=f"pick_{row['id']}"):
                assign_task(row['id'], current_user)
                st.rerun()

# --- メインエリア ---
col_task, col_idea = st.columns([1, 1])

# ==========================================
# 左側：日常リスト
# ==========================================
with col_task:
    st.subheader("日常リスト")
    with st.container(border=True):
        active_routine = df_routine[df_routine['status'] == 'pending']
        if len(active_routine) == 0:
            st.caption("タスクなし")
        else:
            for _, row in active_routine.iterrows():
                render_task_row(row, is_history=False)
                st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True) # 少し余白

    st.markdown("---")
    with st.expander("完了履歴"):
        for _, row in df_routine[df_routine['status'] == 'done'].iterrows():
            render_task_row(row, is_history=True)
    with st.expander("ゴミ箱"):
        for _, row in df_routine[df_routine['status'] == 'deleted'].iterrows():
            render_task_row(row, is_history=True)

# ==========================================
# 右側：プロジェクト
# ==========================================
with col_idea:
    st.subheader("プロジェクト")
    active_projects = df_project[df_project['status'] == 'pending']
    
    if len(active_projects) == 0:
        st.info("プロジェクトなし")
    else:
        topics = active_projects['topic'].unique()
        for topic in topics:
            topic_df = active_projects[active_projects['topic'] == topic]
            with st.expander(f"{topic} ({len(topic_df)})", expanded=True):
                for _, row in topic_df.iterrows():
                    # プロジェクトも同じ関数を使う（ただしアサイン機能はボタンを表示しないだけ）
                    # ここではシンプルにするため直接書きますが、vertical_alignmentを使います
                    c_icon, c_text, c_del = st.columns(LAYOUT, vertical_alignment="center")
                    
                    if c_icon.button(":material/radio_button_unchecked:", key=f"chk_proj_{row['id']}"):
                        update_status(row['id'], "done")
                        st.rerun()
                    
                    c_text.write(f"{row['content']}")
                    
                    if c_del.button(":material/delete:", key=f"del_proj_{row['id']}"):
                        update_status(row['id'], "deleted")
                        st.rerun()

    st.markdown("---")
    with st.expander("完了履歴"):
        for _, row in df_project[df_project['status'] == 'done'].iterrows():
            render_task_row(row, is_history=True)
    with st.expander("ゴミ箱"):
        for _, row in df_project[df_project['status'] == 'deleted'].iterrows():
            render_task_row(row, is_history=True)