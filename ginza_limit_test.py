import spacy
from spacy import displacy

print("GiNZAモデルを読み込み中...")
nlp = spacy.load('ja_ginza')

def analyze_fridge_memo(text):
    doc = nlp(text)
    
    memo_type = "null"
    content = ""
    amount = ""
    
    # 1. 固有表現抽出（NER）で「お金」や「日付」を引っこ抜く！
    # GiNZAは自動で "Money" や "Date" というラベルを貼ってくれます。
    entities = {ent.label_: ent.text for ent in doc.ents}
    
    # 金額があれば取得
    if "Money" in entities:
        amount = entities["Money"]

    # 2. 文の「メインの動詞」と「時制（過去/命令）」を解析
    main_verb = None
    is_past = False   # 過去形か？（〜した）
    is_order = False  # 命令形か？（〜して、〜頼む）
    
    for token in doc:
        # 動詞、かつ文の根っこ（root）を探す
        if token.pos_ == "VERB" and token.dep_ == "ROOT":
            main_verb = token.lemma_ # 基本形
            
            # 助動詞(aux)をチェックして時制を見る
            for child in token.children:
                if child.dep_ == "aux":
                    if child.lemma_ in ["た", "だ"]: # 過去形
                        is_past = True
                    if child.lemma_ in ["て", "てください", "くれ"]: # 命令形っぽい
                        is_order = True
    
    # 3. ルールによる分類（ここが腕の見せ所）
    
    # パターンA：【お金メモ】（金額がある ＋ 貸し借り系の動詞）
    money_verbs = ["払う", "貸す", "借りる", "立て替える"]
    if amount and main_verb in money_verbs:
        memo_type = "money"
        content = f"{amount}を{main_verb}"

    # パターンB：【在庫メモ】（モノがある ＋ 過去形/完了形）
    # 「買った」「届いた」「ある」
    stock_verbs = ["買う", "購入", "届く", "もらう"]
    if is_past and main_verb in stock_verbs:
        memo_type = "stock"
        # 目的語(obj)を探す
        target = "何か"
        for token in doc:
            if token.dep_ == "obj":
                target = token.text
        content = f"{target}が家にある（{main_verb}）"

    # パターンC：【タスク】（命令形 or 未然形）
    elif is_order or (not is_past and main_verb in ["買う", "行く"]):
        memo_type = "task"
        # 目的語を探す
        target = "何か"
        for token in doc:
            if token.dep_ == "obj":
                target = token.text
        content = f"{target}を{main_verb}"

    return {
        "text": text,
        "type": memo_type,
        "content": content,
        "debug_verb": f"{main_verb}(過去:{is_past}/命令:{is_order})"
    }

# --- テスト ---
sentences = [
    "牛乳を買ってきて",           # タスク
    "ランチ代1000円払ったよ",     # 金額メモ
    "実家からお米が届いた",       # 在庫メモ
    "プリン買ったよ",            # 在庫メモ
    "明日集合ね"                 # その他
]

print("-" * 50)
for s in sentences:
    res = analyze_fridge_memo(s)
    print(f"入力: {res['text']}")
    print(f"判定: [{res['type']}] {res['content']}")
    print(f"分析: {res['debug_verb']}")
    print("-" * 50)