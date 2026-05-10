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

def sanitize_question(q, default_cat="综合"):
    if not isinstance(q, dict): return {"error": "Invalid format"}
    key_map = {
        "question": ["Question", "q", "题干"],
        "answer": ["Answer", "ans", "答案"],
        "analysis": ["Analysis", "解析"],
        "options": ["Options", "opts", "选项"],
        "category": ["Category", "cat"]
    }
    for std, aliases in key_map.items():
        if std not in q:
            for alias in aliases:
                if alias in q: q[std] = q[alias]; break
    if "category" not in q: q["category"] = default_cat
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

def generate_ai_question(items, mode, target_hint=None):
    client = get_ai_client()
    if not client: return {"error": "AI 未配置"}
    
    context = "中考语文核心考点"
    if items:
        if isinstance(items, list): context = "; ".join([it.get('word', '') for it in items if isinstance(it, dict)])
        else: context = str(items)

    # --- v6.0 强制自检 Prompt ---
    prompt = f"""
    针对【{context}】命制一道选择题。考查类型：{target_hint or '全随机'}。
    
    ⚠️ 强制性自我核查 (必须在输出前完成)：
    1. 核实题干描述是否严谨，是否存在“灰色地带”。
    2. 确保干扰项必须有明确语法/逻辑错误，禁止“生硬”等主观错误。
    3. 检查答案与解析是否 100% 对应。
    
    输出 JSON {{question, options, answer, analysis, category}}。标注用（ ）。
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-v4",
            messages=[
                {"role": "system", "content": "你是一个极度保守、具备自我批判精神的中考专家。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        raw = extract_json_robustly(response.choices[0].message.content)
        return sanitize_question(raw, default_cat=target_hint or "综合")
    except Exception as e:
        return {"error": str(e)}

def re_verify_question(q):
    """
    质疑题目功能：AI 重新审视自己是否出错
    """
    client = get_ai_client()
    if not client: return "AI 暂不可用"
    
    prompt = f"""
    有用户质疑以下题目可能存在错误：
    题干：{q['question']}
    答案：{q['answer']}
    解析：{q['analysis']}
    
    请你重新、深度、批判性地审视这道题。
    如果你发现之前的答案或题目确实存在逻辑错误，请在回复开头明确说明“【AI 已认错】”，并说明理由。
    如果你认为题目无误，请给出更深入的理由说明。
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": "你是一个严谨的学术纠错专家。"}, {"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content
    except: return "质疑请求失败"
