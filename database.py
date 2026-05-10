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

# --- 认证与资料 ---
def sign_in(username, password):
    supabase = get_supabase()
    email = f"{username}@navigator.com" if "@" not in username else username
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return response, None
    except Exception as e:
        return None, str(e)

def sign_up_and_login(username, password, name, class_name):
    supabase = get_supabase()
    email = f"{username}@navigator.com" if "@" not in username else username
    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
        if response.user:
            supabase.table("profiles").insert({
                "id": response.user.id,
                "name": name,
                "class_name": class_name
            }).execute()
            return response.user, None
        return None, "注册失败"
    except Exception as e:
        return None, str(e)

def get_profile(uid):
    supabase = get_supabase()
    try:
        response = supabase.table("profiles").select("*").eq("id", uid).maybe_single().execute()
        return response.data
    except:
        return None

# --- 答题与分享 ---
def log_quiz_result(uid, category, question_text, student_answer, is_correct, time_spent, analysis=""):
    supabase = get_supabase()
    try:
        supabase.table("answer_logs").insert({
            "user_id": uid,
            "category": category,
            "question": question_text,
            "answer": student_answer,
            "is_correct": is_correct,
            "time_spent": time_spent,
            "analysis": analysis
        }).execute()
    except:
        pass

def share_to_community(q_data, category, uid):
    supabase = get_supabase()
    try:
        supabase.table("shared_questions").upsert({
            "category": category,
            "question": q_data["question"],
            "options": q_data["options"],
            "answer": q_data["answer"],
            "analysis": q_data["analysis"],
            "user_id": uid # 追踪贡献者
        }, on_conflict="question").execute()
        return True
    except:
        return False

# --- 排行榜核心逻辑 (v3.8) ---
def get_leaderboard_data():
    """获取所有用户的排行数据视图"""
    supabase = get_supabase()
    try:
        res = supabase.table("user_rankings").select("*").execute()
        return res.data if res.data else []
    except:
        return []

def get_community_selected(limit=15):
    supabase = get_supabase()
    try:
        res = supabase.table("shared_questions").select("*").order("likes_count", desc=True).limit(limit).execute()
        return res.data if res.data else []
    except:
        return []

def get_public_mistakes(limit=15):
    supabase = get_supabase()
    try:
        res = supabase.table("answer_logs").select("question, category, analysis").eq("is_correct", False).limit(limit).execute()
        return res.data if res.data else []
    except:
        return []

def get_random_shared_question():
    supabase = get_supabase()
    try:
        res = supabase.table("shared_questions").select("*").execute()
        if res.data: return random.choice(res.data)
        return None
    except: return None

def get_user_all_logs(uid):
    supabase = get_supabase()
    try:
        res = supabase.table("answer_logs").select("*").eq("user_id", uid).execute()
        return res.data if res.data else []
    except: return []
