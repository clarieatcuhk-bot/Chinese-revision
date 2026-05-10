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

    # --- v5.1 保守命题补丁 (严禁玄学) ---
    prompt = f"""
    你现在是中考命题委员会的资深研究员，针对【{context}】命制一道选择题。
    
    ⚠️ 核心禁令 (核心错误准则)：
    1. 【严禁玄学】：错误选项必须有“硬伤”（如：主谓搭配不当、成分残缺、褒贬误用、逻辑截然相反等）。
    2. 【严禁主观】：严禁以“语气生硬”、“表达不地道”等模糊理由作为错误标准。错误项必须能用一句话说清它违反了哪条语法或逻辑规则。
    3. 【保守风格】：题目风格应效仿人教版正式考试题，正确项必须无可挑剔。
    
    输出格式：JSON {{question, options, answer, analysis, category}}。标注用（ ）。
    """

    try:
        # 尝试 V4
        response = client.chat.completions.create(
            model="deepseek-v4",
            messages=[
                {"role": "system", "content": "你是一个极其保守、严谨的中考专家，只输出 JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3 # 进一步降低随机性
        )
        raw = extract_json_robustly(response.choices[0].message.content)
        return sanitize_question(raw, default_cat=target_hint or "综合")
    except:
        # 回退到稳定版
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": "严禁玄学，只输出 JSON"}, {"role": "user", "content": prompt}],
                temperature=0.3
            )
            raw = extract_json_robustly(response.choices[0].message.content)
            return sanitize_question(raw, default_cat=target_hint or "综合")
        except Exception as e:
            return {"error": str(e)}
