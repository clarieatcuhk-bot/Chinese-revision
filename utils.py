import json
import random
import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

@st.cache_data
def load_data(file_path):
    """
    加载并缓存 JSON 数据
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"加载数据失败: {e}")
        return None

def get_ai_client(api_key):
    """
    获取 DeepSeek API 客户端 (OpenAI 兼容模式)
    """
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

def generate_question_ai(client, items, mode):
    """
    调用 AI 生成题目
    """
    # 提取素材信息
    material_desc = ""
    for item in items:
        if item['type'] == 'word_pronunciation':
            material_desc += f"- 词语: {item['word']}, 读音: {item.get('pinyin', '未知')}, 课文: {item.get('lesson', '未知')}\n"
        elif item['type'] == 'idiom_meaning':
            material_desc += f"- 成语: {item['word']}, 含义: {item.get('meaning', '未知')}\n"

    # 根据模式定制 Prompt
    mode_hint = {
        "字音挑战": "重点考查字音（读音是否正确），干扰项应包含常见的误读点。",
        "成语辨析": "重点考查成语在具体语境中的运用是否恰当，或成语含义的理解。",
        "随机乱斗": "综合考查字音、字形或词义，风格参照中考语文第一大题。"
    }.get(mode, "综合考查基础知识。")

    prompt = f"""
    你是一位资深中考语文命题专家。请基于以下提供的素材，编写一道符合“中考语文基础知识”风格的四选一单选题。

    【素材内容】
    {material_desc}

    【出题要求】
    1. 目标模式：{mode}。内容要求：{mode_hint}
    2. 风格：严谨、专业，模仿全国各地中考真题（如北京、上海、江苏等）的第一大题。
    3. 选项：四个选项（A, B, C, D），只有一个正确答案。
    4. 深度解析：使用“逻辑关联记忆法”，不仅解释正确项，也要指出错误项的错误点及其记忆窍门，帮助学生举一反三。

    【输出格式】
    必须严格返回 JSON 格式，严禁包含任何 Markdown 格式块或解释性文字。
    JSON 结构示例：
    {{
        "question": "下列词语中加点字注音全部正确的一项是...",
        "options": {{
            "A": "选项A...",
            "B": "选项B...",
            "C": "选项C...",
            "D": "选项D..."
        }},
        "answer": "A",
        "analysis": "【逻辑关联记忆】..."
    }}
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个专业的中考语文命题助手。你只输出合法的 JSON 数据。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        return {"error": f"AI 生成失败: {str(e)}"}
