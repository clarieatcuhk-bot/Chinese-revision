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

# --- 数据操作 ---
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

# --- v8.7 究极容错查询 ---
def get_leaderboard_data():
    supabase = get_supabase()
    try:
        res_rank = supabase.table("user_rankings").select("*").execute()
        # 不再指定列名，直接选 * 避免报错
        res_prof = supabase.table("profiles").select("*").execute()
        
        if not res_rank.data: return []
        
        prof_map = {p['id']: p for p in (res_prof.data or [])}
        flat = []
        for r in res_rank.data:
            p = prof_map.get(r['user_id'], {})
            r['account_name'] = p.get('account_name', '') # 动态获取
            r['challenge_count'] = p.get('challenge_count', 0)
            r['challenge_success_count'] = p.get('challenge_success_count', 0)
            flat.append(r)
        return flat
    except Exception as e:
        st.error(f"排行榜抓取失败: {e}")
        return []

def get_public_mistakes_with_kills(limit=20):
    supabase = get_supabase()
    try:
        res = supabase.table("answer_logs").select("*").eq("is_correct", False).order('created_at', desc=True).limit(500).execute()
        if not res.data: return []
        counts = {}; processed = []; seen = set()
        for r in res.data:
            q_text = str(r['question']).strip()
            if q_text not in counts:
                counts[q_text] = 1; processed.append(r); seen.add(q_text)
            else: counts[q_text] += 1
        for p in processed: p['kill_count'] = counts[str(p['question']).strip()]
        return sorted(processed, key=lambda x: x['kill_count'], reverse=True)[:limit]
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

def delete_all_logs_of_question(q_text):
    supabase = get_supabase()
    try:
        supabase.table("answer_logs").delete().eq("question", q_text).execute()
        return True
    except: return False
