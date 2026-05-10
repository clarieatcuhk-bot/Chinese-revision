import json
import re
import streamlit as st
from openai import OpenAI

def get_ai_client():
    try:
        api_key = st.secrets.get("DEEPSEEK_API_KEY") or st.secrets.get("OPENAI_API_KEY")
        base_url = st.secrets.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        if not api_key: return None
        return OpenAI(api_key=api_key, base_url=base_url)
    except: return None

def extract_json_robustly(text):
    json_block = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if json_block: content = json_block.group(1)
    else:
        brace_match = re.search(r'(\{.*\})', text, re.DOTALL)
        content = brace_match.group(1) if brace_match else text
    try: return json.loads(content.strip())
    except: return None

def sanitize_question(q):
    """
    v3.9.2 终极纠偏：处理 AI 随机生成的各种键名
    """
    if not isinstance(q, dict): return q
    
    # 1. 核心键名纠偏 (处理大小写或缩写)
    key_map = {
        "question": ["Question", "question_text", "q", "content"],
        "answer": ["Answer", "ans", "right_answer"],
        "analysis": ["Analysis", "解析", "explain", "reason"],
        "options": ["Options", "opts", "choices"]
    }
    
    for std_key, aliases in key_map.items():
        if std_key not in q:
            for alias in aliases:
                if alias in q:
                    q[std_key] = q[alias]
                    break
    
    # 2. Options 格式纠偏
    opts = q.get("options", {})
    new_opts = {}
    if isinstance(opts, list):
        keys = ["A", "B", "C", "D"]
        for i, val in enumerate(opts):
            if i < 4: new_opts[keys[i]] = val
    elif isinstance(opts, dict):
        for k, v in opts.items(): new_opts[str(k).upper()] = v
    
    for k in ["A", "B", "C", "D"]:
        if k not in new_opts: new_opts[k] = "选项加载异常"
        
    q["options"] = new_opts
    return q

def generate_ai_question(items, mode):
    client = get_ai_client()
    if not client: return {"error": "AI 配置缺失"}
    
    context = "中考常用词语"
    if items:
        if isinstance(items, list): context = "; ".join([it.get('word', '') for it in items if isinstance(it, dict)])
        elif isinstance(items, str): context = items

    prompt = f"针对‘{context}’命制一道中考语文选择题。要求：标注用括号，输出 JSON {{question, options, answer, analysis}}。"

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个中考专家，只输出 JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        raw_data = extract_json_robustly(response.choices[0].message.content)
        if raw_data:
            return sanitize_question(raw_data)
        return {"error": "JSON 提取失败"}
    except Exception as e:
        return {"error": str(e)}
