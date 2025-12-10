import spacy
import json

# GiNZAの準備
print("GiNZAモデルを読み込んでいます...（数秒かかります）")
nlp = spacy.load('ja_ginza')

def analyze_with_ginza(text):
    doc = nlp(text)
    
    task_type = "null"
    summary = ""
    assignee = "不明"
    
    # --- ルール1: タスクっぽいキーワードがあるか探す ---
    # ここに「反応させたい言葉」を人力で登録する必要があります（これが大変！）
    task_keywords = ["買う", "買っ", "お願い", "頼む", "掃除", "洗濯", "予約"]
    event_keywords = ["集合", "行く", "ランチ", "旅行", "出張"]
    
    # 文中の動詞や名詞をチェック
    is_task = False
    is_event = False
    target_word = "" # 「牛乳」などを入れる変数

    for token in doc:
        # 動詞の基本形（lemma_）でチェック
        if token.lemma_ in task_keywords:
            is_task = True
        elif token.lemma_ in event_keywords:
            is_event = True
            
        # 「何を」にあたる言葉（目的語 obj）を探す
        if token.dep_ == "obj": 
            target_word = token.text

    # --- ルール2: 判定結果を作る ---
    if is_task:
        task_type = "task"
        # 目的語があればそれを使う、なければ文全体を使う
        if target_word:
            summary = f"{target_word}をする/買う"
        else:
            summary = text # 諦めて全文出す
            
    elif is_event:
        task_type = "event"
        summary = text
        
    # --- ルール3: 担当者を探す（主語 nsubj を探す） ---
    for token in doc:
        if token.dep_ == "nsubj": # 主語
            assignee = token.text

    return {
        "input": text,
        "type": task_type,
        "summary": summary,
        "assignee": assignee
    }

# --- 実験コーナー ---
# ここにテストしたい文章を入れてみよう！
test_sentences = [
    "牛乳を買ってきて",           # 1. 簡単な命令
    "パパが明日、洗剤を買う",      # 2. 主語あり
    "来週の日曜に駅前集合ね",      # 3. 予定
    "洗剤がないよ",               # 4. 文脈理解が必要（難問）
    "昨日のテレビ面白かったね"      # 5. 雑談
]

print("-" * 50)
print("【GiNZAによる解析結果】")
print("-" * 50)

for text in test_sentences:
    result = analyze_with_ginza(text)
    # JSONっぽく表示
    print(json.dumps(result, ensure_ascii=False))

print("-" * 50)