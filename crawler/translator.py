# 翻译为中文
import os
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI

def get_ai_translation(to_be_translated, api_key):
    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    messages = [
        {
            "role": "user",
            "content": to_be_translated
        }
    ]
    translation_options = {
        "source_lang": "English",
        "target_lang": "Chinese",
        "terms": [
        {
            "source": "good manufacturing practices",
            "target": "GMP"
        },
        {
            "source": "WHO",
            "target": "WHO"
        },
        {
            "source": "active pharmaceutical ingredients",
            "target": "原料药"
        }
    ]
    }

    completion = client.chat.completions.create(
        model="qwen-mt-turbo",
        messages=messages,
        extra_body={
            "translation_options": translation_options
        }
    )
    return completion.choices[0].message.content

if __name__ == "__main__":
    import os
    api_key = os.environ.get("TRANSLATOR_API_KEY")
    print(api_key)
    if not api_key:
        print("请先设置环境变量 TRANSLATOR_API_KEY")
    else:
        text = "Good Manufacturing Practice (GMP) is a system for ensuring that products are consistently produced and controlled according to quality standards."
        print("原文:", text)
        result = get_ai_translation(text, api_key)
        # result = json.loads(result)["choices"][0]["message"]["content"]
        print("翻译结果:", result)