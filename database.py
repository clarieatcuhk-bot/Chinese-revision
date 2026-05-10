from supabase import create_client, Client
import streamlit as st

@st.cache_resource
def get_supabase() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Supabase 配置失败: {e}")
        return None

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

def log_quiz_result(uid, category, question_text, student_answer, is_correct, time_spent, analysis=""):
    """
    v2.9 字段自修复向导：针对 'Could not find column' 报错提供精确补救。
    """
    supabase = get_supabase()
    full_data = {
        "user_id": uid,
        "category": category,
        "question": question_text,
        "answer": student_answer,
        "is_correct": is_correct,
        "time_spent": time_spent,
        "analysis": analysis
    }
    
    try:
        supabase.table("answer_logs").insert(full_data).execute()
    except Exception as e:
        show_db_error_wizard_v29(e)

def show_db_error_wizard_v29(e):
    """
    v2.9 版诊断：提供“一键修补”脚本
    """
    st.error(f"❌ 数据库入库失败: {str(e)}")
    
    with st.expander("🛠️ 数据库结构一键修补指南", expanded=True):
        st.markdown("""
        **报错原因**：你的 `answer_logs` 表缺少必要的列（如 `answer` 或 `question`）。
        这是因为在版本升级过程中，我们引入了更多的分析维度。
        
        **修复方法**：请复制以下脚本，在 Supabase **SQL Editor** 中运行：
        """)
        
        st.code("""
-- 1. 补齐所有可能缺失的列
ALTER TABLE public.answer_logs ADD COLUMN IF NOT EXISTS question text;
ALTER TABLE public.answer_logs ADD COLUMN IF NOT EXISTS answer text;
ALTER TABLE public.answer_logs ADD COLUMN IF NOT EXISTS is_correct boolean;
ALTER TABLE public.answer_logs ADD COLUMN IF NOT EXISTS category text;
ALTER TABLE public.answer_logs ADD COLUMN IF NOT EXISTS time_spent float;
ALTER TABLE public.answer_logs ADD COLUMN IF NOT EXISTS analysis text;

-- 2. 确保权限关闭（防止 RLS 拦截）
ALTER TABLE public.answer_logs DISABLE ROW LEVEL SECURITY;
        """, language="sql")
        
        st.info("💡 运行完上述脚本后，请刷新页面重新答题即可。")

def get_profile(uid):
    supabase = get_supabase()
    try:
        response = supabase.table("profiles").select("*").eq("id", uid).maybe_single().execute()
        return response.data
    except:
        return None

def get_user_logs(uid):
    supabase = get_supabase()
    try:
        response = supabase.table("answer_logs").select("*").eq("user_id", uid).execute()
        return response.data if response.data else []
    except:
        return []
