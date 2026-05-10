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
    if not isinstance(q, dict): return q
    opts = q.get("options", {})
    new_opts = {}
    if isinstance(opts, list):
        keys = ["A", "B", "C", "D"]
        for i, val in enumerate(opts):
            if i < 4: new_opts[keys[i]] = val
    elif isinstance(opts, dict):
        for k, v in opts.items(): new_opts[str(k).upper()] = v
    for k in ["A", "B", "C", "D"]:
        if k not in new_opts: new_opts[k] = "数据缺失"
    q["options"] = new_opts
    return q

def generate_ai_question(items, mode):
    client = get_ai_client()
    if not client: return {"error": "AI 配置缺失"}

    # --- 鲁棒性修复：处理 items 为 None 的情况 ---
    context = "中考常用词语"
    if items:
        if isinstance(items, list):
            context = "; ".join([it.get('word', '') for it in items if isinstance(it, dict)])
        elif isinstance(items, str):
            context = items

    if mode == "discovery":
        prompt = f"针对‘{context}’命题。格式：JSON {{question, options:{{A,B,C,D}}, answer, analysis}}。标注用括号。"
    elif mode == "grammar":
        prompt = "命制中考病句题。标注用括号。格式：JSON。"
    else:
        prompt = f"基于‘{context}’命题。标注用括号。格式：JSON。"

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个中考专家，只输出 JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        data = extract_json_robustly(response.choices[0].message.content)
        return sanitize_question(data) if data else {"error": "JSON 提取失败"}
    except Exception as e:
        return {"error": str(e)}
