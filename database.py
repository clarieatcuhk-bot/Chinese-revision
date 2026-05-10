from supabase import create_client, Client
import streamlit as st
import random

@st.cache_resource
def get_supabase() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Supabase 连接失败: {e}")
        return None

# --- 认证 ---
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

# --- 数据操作 v7.5 ---
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

def record_challenge(uid, is_success=False):
    supabase = get_supabase()
    try:
        # v7.5 增强：如果列不存在，操作会静默失败而不会导致 app 崩溃
        p = get_profile(uid)
        if not p: return
        new_count = (p.get('challenge_count') or 0) + 1
        new_success = (p.get('challenge_success_count') or 0) + (1 if is_success else 0)
        supabase.table("profiles").update({
            "challenge_count": new_count, "challenge_success_count": new_success
        }).eq("id", uid).execute()
    except: pass

def get_leaderboard_data():
    supabase = get_supabase()
    try:
        # v7.5 鲁棒查询：先尝试连表获取 account_name 和质疑战绩
        try:
            res = supabase.table("user_rankings").select("*, profiles(account_name, challenge_count, challenge_success_count)").execute()
            if res.data:
                flat = []
                for r in res.data:
                    p = r.get('profiles') or {}
                    r['account_name'] = p.get('account_name', '')
                    r['challenge_count'] = p.get('challenge_count', 0)
                    r['challenge_success_count'] = p.get('challenge_success_count', 0)
                    flat.append(r)
                return flat
        except:
            # 彻底降级：只拿基础排名
            res = supabase.table("user_rankings").select("*").execute()
            if res.data:
                for r in res.data:
                    r['account_name'] = ""; r['challenge_count'] = 0; r['challenge_success_count'] = 0
                return res.data
        return []
    except: return []

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

def share_to_community(q_data, category, uid):
    supabase = get_supabase()
    try:
        supabase.table("shared_questions").insert({
            "category": category, "question": q_data["question"], "options": q_data["options"],
            "answer": q_data["answer"], "analysis": q_data["analysis"], "user_id": uid, "recommend_count": 1
        }).execute()
        return True
    except: return False

def get_community_selected(limit=50):
    supabase = get_supabase()
    try:
        res = supabase.table("shared_questions").select("*").order("recommend_count", desc=True).limit(limit).execute()
        return res.data if res.data else []
    except: return []

def get_public_mistakes_with_kills(limit=20):
    supabase = get_supabase()
    try:
        res = supabase.table("answer_logs").select("question, options, answer, analysis, category").eq("is_correct", False).execute()
        if not res.data: return []
        counts = {}; processed = []
        for r in res.data:
            q = r['question']
            if q not in counts: counts[q] = 1; processed.append(r)
            else: counts[q] += 1
        for p in processed: p['kill_count'] = counts[p['question']]
        return sorted(processed, key=lambda x: x['kill_count'], reverse=True)[:limit]
    except: return []

def get_random_shared_question():
    supabase = get_supabase()
    try:
        res = supabase.table("shared_questions").select("*").execute()
        return random.choice(res.data) if res.data else None
    except: return None

def get_user_all_logs(uid):
    supabase = get_supabase()
    try:
        res = supabase.table("answer_logs").select("*").eq("user_id", uid).execute()
        return res.data if res.data else []
    except: return []
