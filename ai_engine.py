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
    if not isinstance(q, dict): return {"error": "JSON 格式异常"}
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
        if k not in new_opts: new_opts[k] = "数据加载失败"
    q["options"] = new_opts
    return q

def generate_ai_question(items, mode, target_hint=None):
    client = get_ai_client()
    if not client: return {"error": "AI API Key 未配置"}
    
    context = "中考语文核心考点"
    if items:
        if isinstance(items, list): context = "; ".join([it.get('word', '') for it in items if isinstance(it, dict)])
        else: context = str(items)

    # --- v6.6 DeepSeek V4 Pro 严谨版 ---
    prompt = f"""
    针对【{context}】命制一道选择题。考查类型：{target_hint or '全随机'}。
    
    ⚠️ 核心规范：
    1. 题干必须包含“最恰当的一项”。
    2. 错误项必须有“硬伤”（搭配不当、成分残缺等），严禁主观评价。
    3. 自检环节：确保答案唯一且逻辑严密。
    
    输出格式：JSON {{question, options, answer, analysis, category}}。
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro", # 升级为 Pro 版
            messages=[
                {"role": "system", "content": "你是一个极其保守、严谨的中考专家，仅输出 JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        raw = extract_json_robustly(response.choices[0].message.content)
        return sanitize_question(raw, default_cat=target_hint or "综合")
    except Exception as e:
        # 如果 Pro 版调用失败，尝试退回到通用 chat
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": "只输出 JSON"}, {"role": "user", "content": prompt}],
                temperature=0.3
            )
            raw = extract_json_robustly(response.choices[0].message.content)
            return sanitize_question(raw, default_cat=target_hint or "综合")
        except:
            return {"error": str(e)}

def re_verify_question(q):
    """
    质疑功能：使用 Pro 版进行深度复核
    """
    client = get_ai_client()
    if not client: return "AI 暂不可用"
    
    prompt = f"""
    有用户质疑此题存在错误：
    题干：{q['question']}
    答案：{q['answer']}
    解析：{q['analysis']}
    
    请用批判性思维深度复核。若确认出错，请以“【AI 已认错】”开头；若无误，请给出更强的辩护逻辑。
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro", # 质疑复核同样使用 Pro
            messages=[{"role": "system", "content": "你是纠错专家。"}, {"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content
    except:
        return "质疑通道异常"
