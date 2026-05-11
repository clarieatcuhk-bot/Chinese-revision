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
    if not client: return {"error": "AI 未配置"}
    
    prompt = f"""
    【目标考点】：{target_hint or '综合基础'}
    
    Role: 顶级中考语文命题专家，拥有 20 年一线教学与阅卷经验。
    Task: 生成高质量的中考语文练习题，严禁出现题干、选项、答案与解析互相冲突的情况。
    
    1. 逻辑生成规程 (Strict Execution Order):
    Step 1 - 考点提取: 锁定目标字符（参考 3500 字表）或常见课内考点。
    Step 2 - 逻辑预设: 明确本题的“正确逻辑路径”。例如：本题考查“成分残缺”，正确选项必须主谓宾完整，错误选项必须缺失主语。
    Step 3 - 选项隔离: 编写干扰项时，必须确保每个干扰项的错误类型是唯一的，且与正确答案有明显的边界。
    Step 4 - 交叉校验: 生成解析后，必须自我检查：解析是否直接支持了正确答案？解析是否逐一驳回了错误选项？
    
    2. 题目格式约束 (Strict JSON Schema):
    请直接输出合法的 JSON 格式：
    {{
      "hidden_logic": "(必须) 在输出题目内容前，先简述本题的逻辑架构，确保 AI 自身大脑清醒",
      "question": "(必须) 题干，加点字或重点词语必须使用 <u></u> 标注",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "answer": "(必须) 只能是 'A', 'B', 'C', 'D' 之一",
      "analysis": "(必须) 包含“手术刀紧缩法”解析，必须与答案严格对应",
      "category": "{target_hint or '综合基础'}"
    }}
    
    3. 考点锁定 (Domain Specific):
    - 病句类: 严格限定在六类语病（语序不当、搭配不当、成分残缺、结构混乱、表意不明、不合逻辑）。
    - 字音字形: 必须参考 3500 字表的标准读音，严禁生造读音。
    
    4. 幻觉屏蔽原则:
    - 严禁在解析中出现“虽然...但是...”等模棱两可的废话。
    - 严禁出现“以上选项均不正确”等无效干扰。
    - 双重确认: 你的答案字母必须与解析内容 100% 匹配。
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[{"role": "system", "content": "你是顶级中考语文命题专家，请严格遵循规程并输出合法的 JSON。"}, {"role": "user", "content": prompt}],
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
