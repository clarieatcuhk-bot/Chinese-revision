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
            supabase.table("profiles").insert({"id": response.user.id, "name": name, "class_name": class_name}).execute()
            return response.user, None
        return None, "注册失败"
    except Exception as e: return None, str(e)

def get_profile(uid):
    supabase = get_supabase()
    try:
        res = supabase.table("profiles").select("*").eq("id", uid).maybe_single().execute()
        return res.data
    except: return None

# --- 数据操作 v6.0 ---
def log_quiz_result(uid, category, question_text, student_answer, is_correct, time_spent, analysis=""):
    supabase = get_supabase()
    try:
        supabase.table("answer_logs").insert({
            "user_id": uid, "category": category, "question": question_text,
            "answer": student_answer, "is_correct": is_correct, "time_spent": time_spent, "analysis": analysis
        }).execute()
    except: pass

def delete_shared_question_by_id(q_id):
    """管理员专用：物理删除题目"""
    supabase = get_supabase()
    try:
        supabase.table("shared_questions").delete().eq("id", q_id).execute()
        return True
    except: return False

def share_to_community(q_data, category, uid):
    supabase = get_supabase()
    try:
        exist = supabase.table("shared_questions").select("id, recommend_count").eq("question", q_data["question"]).maybe_single().execute()
        if exist.data:
            new_count = (exist.data.get("recommend_count") or 1) + 1
            supabase.table("shared_questions").update({"recommend_count": new_count}).eq("id", exist.data["id"]).execute()
        else:
            supabase.table("shared_questions").insert({
                "category": category, "question": q_data["question"], "options": q_data["options"],
                "answer": q_data["answer"], "analysis": q_data["analysis"], "user_id": uid, "recommend_count": 1
            }).execute()
        return True
    except: return False

def get_leaderboard_data():
    supabase = get_supabase()
    try:
        res = supabase.table("user_rankings").select("*").execute()
        return res.data if res.data else []
    except: return []

def get_community_selected(limit=20):
    supabase = get_supabase()
    try:
        res = supabase.table("shared_questions").select("*").order("recommend_count", desc=True).limit(limit).execute()
        return res.data if res.data else []
    except: return []

def get_public_mistakes_with_kills(limit=20):
    supabase = get_supabase()
    try:
        res = supabase.table("answer_logs").select("question, category, analysis").eq("is_correct", False).execute()
        if not res.data: return []
        counts = {}
        processed = []
        for r in res.data:
            q = r['question']
            if q not in counts:
                counts[q] = 1; processed.append(r)
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
