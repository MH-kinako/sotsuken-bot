import spacy

# 日本語モデルの読み込み
try:
    nlp = spacy.load("ja_ginza")
except Exception:
    import ja_ginza
    nlp = ja_ginza.load()

def analyze_with_ginza(text):
    """
    GiNZAを使って構文解析を行う（強化版）。
    1. 「名詞＋を/に＋動詞」の正式な形
    2. 「名詞＋動詞」の省略形（例：卵買って、温泉行く）
    の両方を検出する。
    """
    doc = nlp(text)
    
    # ターゲット動詞リスト（「頼む」「お願い」なども追加）
    target_verbs = ["買う", "購入", "行く", "予約", "申込む", "調べる", "払う", "頼む", "お願い"]
    
    for token in doc:
        # デバッグ用：どんな単語・品詞・基本形で認識されたか確認したいときに有効
        # print(f"{token.text} -> pos:{token.pos_} lemma:{token.lemma_} dep:{token.dep_}")

        # 動詞の基本形(lemma)がターゲットに含まれているかチェック
        if token.lemma_ in target_verbs:
            
            objective = ""
            
            # --- 戦略1：ちゃんとした文法（依存関係）で探す ---
            for child in token.children:
                # obj: 目的語（〜を）
                # obl: 斜格（〜に、〜へ） ※「温泉に行く」などはoblになることが多い
                # nmod: 修飾語（たまに誤解析でここに来ることもある）
                if child.dep_ in ["obj", "obl", "nmod"] and child.pos_ in ["NOUN", "PROPN"]:
                    objective = child.text
                    break
            
            # --- 戦略2：口語対応（助詞省略パターン） ---
            # 戦略1で見つからず、かつ動詞の「ひとつ前」が名詞なら、それを対象とみなす
            # 例：「卵(NOUN) 買って(VERB)」
            if not objective and token.i > 0:
                prev_token = doc[token.i - 1]
                if prev_token.pos_ in ["NOUN", "PROPN"]:
                    objective = prev_token.text

            # 対象が見つかったらタスクとして返す
            if objective:
                # 文末が「？」の場合は、タスクではなく「相談(Idea)」の可能性が高いので除外する工夫
                # 例：「明日カラオケ行く？」→ タスクにしてしまうとウザがられる
                if doc[-1].text == "?" or doc[-1].text == "？":
                    return None

                return {
                    "category": "task",
                    "summary": f"{objective}を{token.lemma_}", # 基本形で保存（例：卵を買う）
                    "due_date": None,
                    "assignee": None
                }
                
    return None

# --- テスト用 ---
if __name__ == "__main__":
    tests = [
        "卵を買う",          # 基本
        "卵買って",          # 助詞省略・依頼
        "明日、温泉行く",     # 助詞省略・移動
        "洗剤をお願い",       # 依頼
        "カラオケ行く？"      # 疑問形（除外すべき）
    ]
    
    for t in tests:
        print(f"解析中: {t}")
        print(analyze_with_ginza(t))
        print("---")