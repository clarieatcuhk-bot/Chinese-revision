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
    if not client: return {"error": "AI 配置缺失"}
    
    context = "中考语文核心考点"
    if items:
        if isinstance(items, list): context = "; ".join([it.get('word', '') for it in items if isinstance(it, dict)])
        else: context = str(items)

    # --- v5.0 DeepSeek V4 适配与严谨 Prompt ---
    prompt = f"""
    你现在是 DeepSeek V4 支持下的中考专家组，针对【{context}】命制一道选择题。
    考查类型需求：{target_hint or '全随机'}
    
    ⚠️ 命题准则：
    1. 真实性：严禁发明错误的语法。
    2. 严谨性：答案唯一，解析透彻。
    3. 标注：考查字词用（ ）包裹。
    
    输出格式：JSON {{question, options, answer, analysis, category}}。
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-v4", # 适配 V4 模型
            messages=[
                {"role": "system", "content": "你是一个只输出 JSON 的 V4 教育专家。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        raw = extract_json_robustly(response.choices[0].message.content)
        return sanitize_question(raw, default_cat=target_hint or "综合")
    except Exception as e:
        # 降级处理：如果 V4 模型不存在，切换到 deepseek-chat
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": "只输出 JSON"}, {"role": "user", "content": prompt}],
                temperature=0.5
            )
            raw = extract_json_robustly(response.choices[0].message.content)
            return sanitize_question(raw, default_cat=target_hint or "综合")
        except:
            return {"error": str(e)}
