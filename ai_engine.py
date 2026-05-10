import json
import re
import streamlit as st
from openai import OpenAI

def get_ai_client():
    try:
        # 兼容两种常用的密钥命名
        api_key = st.secrets.get("DEEPSEEK_API_KEY") or st.secrets.get("OPENAI_API_KEY")
        base_url = st.secrets.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        
        if not api_key:
            st.error("🔑 Secrets 中未找到 API_KEY (DEEPSEEK_API_KEY 或 OPENAI_API_KEY)")
            return None
            
        return OpenAI(api_key=api_key, base_url=base_url)
    except Exception as e:
        st.error(f"AI 客户端初始化失败: {e}")
        return None

def extract_json_robustly(text):
    """
    更强大的 JSON 提取逻辑：支持 Markdown 代码块和裸 JSON
    """
    # 1. 尝试匹配 Markdown JSON 块
    json_block = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if json_block:
        content = json_block.group(1)
    else:
        # 2. 尝试匹配大括号块
        brace_match = re.search(r'(\{.*\})', text, re.DOTALL)
        content = brace_match.group(1) if brace_match else text
    
    try:
        # 去除可能的干扰字符
        content = content.strip()
        return json.loads(content)
    except Exception as e:
        st.sidebar.error(f"JSON 解析失败内容: {text[:100]}...") # 辅助调试
        return None

def sanitize_question(q):
    if not isinstance(q, dict): return q
    
    # 统一转换 options 为字典
    options = q.get("options", {})
    new_options = {}
    
    if isinstance(options, list):
        keys = ["A", "B", "C", "D"]
        for i, val in enumerate(options):
            if i < 4: new_options[keys[i]] = val
    elif isinstance(options, dict):
        for k, v in options.items():
            new_options[str(k).upper()] = v
            
    for k in ["A", "B", "C", "D"]:
        if k not in new_options:
            new_options[k] = "数据缺失"
            
    q["options"] = new_options
    return q

def generate_ai_question(items, mode):
    client = get_ai_client()
    if not client: return {"error": "AI 客户端未就绪"}

    # 强化 Prompt：明确结构，减少废话
    if mode == "discovery":
        prompt = f"""
        请作为中考语文专家，针对汉字“{items}”命制一道四选一单选题。
        考查范围：读音、字形、成语或语境辨析。
        
        要求：
        1. 题干中需要学生关注的汉字用 <u></u> 标签包裹。
        2. 解析中包含该字的“形旁溯源”或“记忆窍门”。
        3. 必须输出如下格式的 JSON 字符串：
        {{
            "question": "题干内容...",
            "options": {{"A": "选项1", "B": "选项2", "C": "选项3", "D": "选项4"}},
            "answer": "A/B/C/D",
            "analysis": "深度解析内容..."
        }}
        """
    elif mode == "grammar":
        prompt = """
        请命制一道中考风格的“病句辨析”单选题。
        场景：革命英雄事迹、文化遗产保护或校园生活。
        
        要求：
        1. 题干中关键句用 <u></u> 包裹。
        2. 选项包含 3 个语病项和 1 个正确项。
        3. 解析使用“紧缩法”分析句子成分。
        4. 必须输出如下格式的 JSON 字符串：
        {{
            "question": "题干内容...",
            "options": {{"A": "选项1", "B": "选项2", "C": "选项3", "D": "选项4"}},
            "answer": "A/B/C/D",
            "analysis": "解析内容..."
        }}
        """
    else:
        # 精准模式
        context = "; ".join([it['word'] for it in items])
        prompt = f"""
        请基于以下词语素材，命制一道中考语文基础题：{context}
        要求：
        1. 考查字用 <u></u> 标签包裹。
        2. 解析需展示逻辑关联。
        3. 必须输出如下格式的 JSON 字符串：
        {{
            "question": "题干内容...",
            "options": {{"A": "选项1", "B": "选项2", "C": "选项3", "D": "选项4"}},
            "answer": "A/B/C/D",
            "analysis": "解析内容..."
        }}
        """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个严谨的中考语文专家。请直接输出 JSON，不要包含任何前导词或后记。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        content = response.choices[0].message.content
        
        # 1. 鲁棒提取
        data = extract_json_robustly(content)
        if not data or "question" not in data:
            # 二次尝试：如果不包含 key，可能是格式偏移
            raise ValueError("AI 返回的 JSON 结构不完整")
            
        # 2. 清洗
        return sanitize_question(data)
    except Exception as e:
        return {"error": f"命题引擎故障: {str(e)}"}
