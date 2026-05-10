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
    # 强制去除题目中的 HTML 标签
    if "question" in q:
        q["question"] = re.sub(r'<.*?>', '', q["question"]).replace('一蹴而就', '（一蹴而就）')
    
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
    if not client: return {"error": "AI 未配置"}
    
    prompt = f"""
    针对【{target_hint or '中考语文考点'}】命制一道选择题。
    ⚠️ 禁止使用任何 HTML 标签（如 <span>, <u> 等）。
    ⚠️ 考察词语时，请用（ ）或 [ ] 标注。
    
    输出 JSON {{question, options, answer, analysis, category}}。
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[{"role": "system", "content": "你是一个严谨的中考专家，禁止使用 HTML 标签。"}, {"role": "user", "content": prompt}],
            temperature=0.3
        )
        raw = extract_json_robustly(response.choices[0].message.content)
        return sanitize_question(raw, default_cat=target_hint or "综合")
    except Exception as e:
        return {"error": str(e)}

def evaluate_challenge(q, reason):
    client = get_ai_client()
    if not client: return False, "AI 服务未配置"
    
    prompt = f"""
    你是一位资深的中考语文教研员。有一位学生对以下题目发起了严厉的质疑。
    【原题干】：{q.get('question')}
    【官方答案】：{q.get('answer')}
    【官方解析】：{q.get('analysis')}
    【学生的质疑理由】：{reason}
    
    请你作为最高判官，重新审视这道题。
    你的任务：
    1. 客观评判学生的质疑是否合理。
    2. 如果学生的质疑一针见血（题目确实有错、超纲、或者存在歧义），请判定成功 (success: true)。
    3. 如果题目本身是完美的，是学生知识点掌握不牢固导致理解偏差，请驳回质疑 (success: false)。
    4. 给出具有指导意义的回复 (reply)。
    
    输出必须是严格的 JSON 格式：
    {{"success": true/false, "reply": "你的判决回复内容..."}}
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[{"role": "system", "content": "你是公正严明的中考语文教研专家判官。输出必须是JSON。"}, {"role": "user", "content": prompt}],
            temperature=0.2
        )
        raw = extract_json_robustly(response.choices[0].message.content)
        if raw and 'success' in raw and 'reply' in raw:
            return bool(raw['success']), str(raw['reply'])
        return False, "AI 判官给出了一堆乱码，驳回质疑。"
    except Exception as e:
        return False, f"调用异常，驳回：{str(e)}"
