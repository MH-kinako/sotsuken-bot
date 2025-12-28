import os
from google import genai
from dotenv import load_dotenv

# .envを読み込む
load_dotenv()

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("APIキーが読み込めません。.envを確認してください")
else:
    print(f"APIキーを確認しました: {api_key[:5]}...")

    try:
        client = genai.Client(api_key=api_key)
        print("\n--- 使用可能なモデル一覧 ---")
        
        # モデル一覧を取得して表示
        # ※ generateContentメソッドをサポートしているモデルだけを表示します
        for m in client.models.list():
            if "generateContent" in m.supported_actions:
                print(f"- {m.name}")
                
        print("--------------------------")
        
    except Exception as e:
        print(f"\nエラーが発生しました:\n{e}")