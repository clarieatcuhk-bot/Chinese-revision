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
        brace_match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
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
    if not client: return {"error": "AI 未配置"}
    
    prompt = f"""
    【目标考点】：{target_hint or '综合基础'}
    
    Role: 国家级中考语文命题专家，擅长构建高逻辑一致性、零幻觉的大规模标准化题库。
    Task: 在“命题实验室”架构下，通过“逻辑前置”模式，生成 1 道待审核的高质量题目。
    
    1. 逻辑生成规程 (The Iron Logic):
    - 逻辑指纹 (logic_fingerprint): 在生成每道题前，必须先在内部确定逻辑支点（如：本题考查“成分残缺”中的“介词掩盖主语”）。
    - 自检闭环: 强制要求生成的 analysis（解析）必须能反向推导出唯一的 answer。若解析逻辑模糊，该题视为不合格。
    - 注点规范: 题干中考察的加点字或重难点词必须使用 <u></u> 标签包裹。
    
    2. 混合动力源:
    - 你的知识库应融合全国主流《中考语文考点大纲》与《初中生3500字表》。
    
    3. 容错与防幻觉指令:
    - 严禁自相矛盾: 题干背景（如“研学活动”、“传统节日”）必须与语病或字词逻辑完美匹配。
    - 严禁 Key 缺失: options 必须完整包含 A, B, C, D 键位。
    
    4. 题目格式约束 (Strict JSON Schema):
    请直接输出单一合法的 JSON 对象（严禁输出为列表，严禁附加其他文本）：
    {{
      "category": "{target_hint or '综合基础'}",
      "logic_fingerprint": "(必须) 简述本题的逻辑支点与考点",
      "question": "(必须) 题干，含 <u></u>",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "answer": "(必须) 只能是 'A', 'B', 'C', 'D' 之一",
      "analysis": "(必须) 手术刀紧缩法解析，必须与答案严格对应，自检闭环"
    }}
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[{"role": "system", "content": "你是国家级中考语文命题专家，请严格遵循逻辑闭环并输出合法的单一 JSON 对象。"}, {"role": "user", "content": prompt}],
            temperature=0.25
        )
        raw = extract_json_robustly(response.choices[0].message.content)
        # 兼容处理如果是列表的情况
        if isinstance(raw, list) and len(raw) > 0: raw = raw[0]
        return sanitize_question(raw, default_cat=target_hint or "综合")
    except Exception as e:
        return {"error": str(e)}

def generate_ai_question_batch(category, count=1):
    client = get_ai_client()
    if not client: return []
    
    prompt = f"""
    Role: 国家级中考语文命题专家，拥有 20 年逻辑校验经验。
    
    Task: 批量生产 {count} 道【{category}】题目，存入“全站预生成池”。
    
    1. 逻辑锁定协议 (Crucial!):
    前置校验: 在生成每道题的内容前，必须先在内部生成 logic_anchor（逻辑锚点）。
    一致性检查: 强制检查：解析内容必须能唯一指向答案字母。若出现“答案为 A 但解析在讲 B”的情况，该题自动作废。
    解析风格: 使用“手术刀紧缩法”，直击语病或字音的核心矛盾。
    
    2. 格式与素材约束:
    HTML 支持: 考察字必须使用 <u></u> 标注。
    数据源: 严格对应 chinese_assets.json（课内）或 chars_3500.json（全量）。
    JSON 结构: 必须返回标准的 JSON 数组，数组中每个对象包含：
    "category": "{category}", "question", "options" (A,B,C,D字典格式), "answer", "analysis", "logic_fingerprint"
    
    3. 幻觉屏蔽:
    严禁出现模糊不清的干扰项。
    干扰项的设置必须符合中考常考误区（如：介词掩盖主语、多音字误读）。
    
    请直接输出 JSON 数组，例如 [{{...}}, {{...}}]
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[{"role": "system", "content": "必须返回合法的 JSON 数组格式。"}, {"role": "user", "content": prompt}],
            temperature=0.3
        )
        raw = extract_json_robustly(response.choices[0].message.content)
        res = []
        if isinstance(raw, list):
            for item in raw:
                q = sanitize_question(item, default_cat=category)
                if q and "error" not in q: res.append(q)
        elif isinstance(raw, dict):
            q = sanitize_question(raw, default_cat=category)
            if q and "error" not in q: res.append(q)
        return res
    except Exception as e:
        print(f"Batch generation error: {e}")
        return []

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
