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
    """
    v4.0 终极清洗：确保所有关键字段存在且格式正确
    """
    if not isinstance(q, dict): return {"error": "JSON 格式非字典"}
    
    # 1. 核心键名规范化
    key_map = {
        "question": ["Question", "q", "content", "题干"],
        "answer": ["Answer", "ans", "答案"],
        "analysis": ["Analysis", "解析", "原因"],
        "options": ["Options", "opts", "选项"],
        "category": ["Category", "cat", "分类"]
    }
    for std, aliases in key_map.items():
        if std not in q:
            for alias in aliases:
                if alias in q: q[std] = q[alias]; break
    
    # 2. 补全缺失的关键键
    if "question" not in q: q["question"] = "题目内容加载失败"
    if "answer" not in q: q["answer"] = "A"
    if "analysis" not in q: q["analysis"] = "暂无详细解析"
    if "category" not in q: q["category"] = default_cat
    
    # 3. Options 字典化与补齐
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
    
    # 根据模式和目标定制 Prompt
    context = "中考语文核心考点"
    if items:
        if isinstance(items, list): context = "; ".join([it.get('word', '') for it in items if isinstance(it, dict)])
        else: context = str(items)

    prompt = f"""
    请作为中考语文命题专家，针对【{context}】命制一道选择题。
    考查类型需求：{target_hint or '全随机'}
    
    要求：
    1. 标注方式：考查字词必须用（ ）包裹，例如：下面词语中（确凿）的读音...
    2. 输出格式：必须输出 JSON，包含以下字段：
       - question: 题干
       - options: 字典 {{"A": "...", "B": "...", "C": "...", "D": "..."}}
       - answer: 正确选项字母
       - analysis: 深度解析（含逻辑分析）
       - category: 必须分类为【字音、成语、病句、字词扩展、字形】中的一个。
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个只输出 JSON 的教育专家。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        raw = extract_json_robustly(response.choices[0].message.content)
        return sanitize_question(raw, default_cat=target_hint or "综合")
    except Exception as e:
        return {"error": str(e)}
