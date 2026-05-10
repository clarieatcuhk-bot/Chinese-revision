from supabase import create_client, Client
import streamlit as st
import random
import re

@st.cache_resource
def get_supabase() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Supabase 连接失败: {e}")
        return None

# --- 认证逻辑保持不变 ---
def sign_in(username, password):
    supabase = get_supabase()
    email = f"{username}@navigator.com" if "@" not in username else username
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return response, None
    except Exception as e: return None, str(e)

def sign_up_and_login(username, password, name, class_name):
    supabase = get_supabase()
    email = f"{username}@navigator.com" if "@" not in username else username
    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
        if response.user:
            acc_name = username.lower()
            supabase.table("profiles").insert({"id": response.user.id, "name": name, "class_name": class_name, "account_name": acc_name}).execute()
            return response.user, None
        return None, "注册失败"
    except Exception as e: return None, str(e)

def get_profile(uid):
    supabase = get_supabase()
    try:
        res = supabase.table("profiles").select("*").eq("id", uid).maybe_single().execute()
        return res.data
    except: return None

# --- 数据记录 ---
def log_quiz_result(uid, category, q_obj, student_answer, is_correct, time_spent):
    supabase = get_supabase()
    try:
        supabase.table("answer_logs").insert({
            "user_id": uid, "category": category, 
            "question": q_obj['question'], "options": q_obj['options'], 
            "answer": q_obj['answer'], "analysis": q_obj['analysis'],
            "is_correct": is_correct, "time_spent": time_spent
        }).execute()
    except: pass

# --- 核心修复：更强大的错题嗅探引擎 ---
def clean_q_text(text):
    """深度清洗题目文本，去除所有干扰匹配的符号"""
    if not text: return ""
    # 去除 Markdown 加粗、下划线、空格、换行
    t = str(text).replace("**", "").replace("__", "").replace("<u>", "").replace("</u>", "")
    return re.sub(r'\s+', '', t)

def get_public_mistakes_with_kills(limit=20):
    supabase = get_supabase()
    try:
        # v8.1 修复 1：按时间倒序排列，并扩大抓取范围到 2000 条记录
        res_logs = supabase.table("answer_logs")\
            .select("question, options, answer, analysis, category, created_at")\
            .eq("is_correct", False)\
            .order('created_at', desc=True)\
            .limit(2000)\
            .execute()
            
        if not res_logs.data: return []
        
        # 获取精选题库，同步进行深度清洗
        res_sh = supabase.table("shared_questions").select("question").execute()
        shared_clean_map = {clean_q_text(s['question']): s['question'] for s in res_sh.data}
        
        counts = {}; processed = []; seen_clean = set()
        
        for r in res_logs.data:
            raw_text = r['question']
            clean_text = clean_q_text(raw_text)
            
            # 如果这道错题的“纯文字骨架”存在于精选题库中
            if clean_text in shared_clean_map:
                std_text = shared_clean_map[clean_text] # 使用精选题库里的标准文本展示
                if std_text not in seen_clean:
                    counts[std_text] = 1
                    # 修正显示用的题目为标准精选文本
                    r['question'] = std_text
                    processed.append(r)
                    seen_clean.add(std_text)
                else:
                    counts[std_text] += 1
        
        for p in processed:
            p['kill_count'] = counts.get(p['question'], 1)
            
        return sorted(processed, key=lambda x: x['kill_count'], reverse=True)[:limit]
    except Exception as e:
        print(f"Mistake Sync Error: {e}")
        return []

# --- 其他函数保持稳定 ---
def get_leaderboard_data():
    supabase = get_supabase()
    try:
        res = supabase.table("user_rankings").select("*, profiles(account_name, challenge_count, challenge_success_count)").execute()
        if not res.data: return []
        flat = []
        for r in res.data:
            p = r.get('profiles') or {}
            r['account_name'] = p.get('account_name', '')
            r['challenge_count'] = p.get('challenge_count', 0)
            r['challenge_success_count'] = p.get('challenge_success_count', 0)
            flat.append(r)
        return flat
    except: return []

def share_to_community(q_data, category, uid):
    supabase = get_supabase()
    try:
        supabase.table("shared_questions").insert({
            "category": category, "question": q_data["question"], "options": q_data["options"],
            "answer": q_data["answer"], "analysis": q_data["analysis"], "user_id": uid, "recommend_count": 1
        }).execute()
        return True
    except: return False

def get_community_selected(limit=100):
    supabase = get_supabase()
    try:
        res = supabase.table("shared_questions").select("*").order("recommend_count", desc=True).limit(limit).execute()
        return res.data if res.data else []
    except: return []

def get_user_all_logs(uid):
    supabase = get_supabase()
    try:
        res = supabase.table("answer_logs").select("*").eq("user_id", uid).execute()
        return res.data if res.data else []
    except: return []

def get_random_shared_question():
    supabase = get_supabase()
    try:
        res = supabase.table("shared_questions").select("*").execute()
        return random.choice(res.data) if res.data else None
    except: return None

def delete_shared_question_by_id(q_id):
    supabase = get_supabase()
    try:
        supabase.table("shared_questions").delete().eq("id", q_id).execute()
        return True
    except: return False

def delete_all_logs_of_question(q_text):
    supabase = get_supabase()
    try:
        supabase.table("answer_logs").delete().eq("question", q_text).execute()
        return True
    except: return False
