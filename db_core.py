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
            payload = {
                "id": response.user.id, 
                "name": name, 
                "class_name": class_name, 
                "account_name": username.lower()
            }
            # 动态适应降级引擎：如果 profiles 表缺列，自动剔除
            for attempt in range(4):
                try:
                    supabase.table("profiles").insert(payload).execute()
                    return response.user, None
                except Exception as inner_e:
                    err_str = str(inner_e)
                    if 'PGRST204' in err_str:
                        import re
                        match = re.search(r"Could not find the '([^']+)' column", err_str)
                        if match:
                            bad_col = match.group(1)
                            if bad_col in payload:
                                del payload[bad_col]
                                continue
                    # 并非字段缺失引起的错误，直接抛出
                    return None, err_str
            return response.user, None
        return None, "注册失败：未返回用户信息"
    except Exception as e: return None, str(e)

def get_profile(uid):
    supabase = get_supabase()
    try:
        res = supabase.table("profiles").select("*").eq("id", uid).maybe_single().execute()
        return res.data
    except: return None

import threading

def log_quiz_result(uid, category, q_obj, student_answer, is_correct, time_spent):
    def _task():
        try:
            supabase = get_supabase()
            payload = {
                "user_id": uid, 
                "category": category, 
                "question": q_obj.get('question', q_obj.get('question_text', '')), 
                "options": q_obj.get('options', {}), 
                "answer": q_obj.get('answer', ''), 
                "analysis": q_obj.get('analysis', ''),
                "student_answer": student_answer,
                "is_correct": is_correct, 
                "time_spent": time_spent
            }
            
            for attempt in range(4):
                try:
                    supabase.table("answer_logs").insert(payload).execute()
                    return 
                except Exception as e:
                    err_str = str(e)
                    if 'PGRST204' in err_str:
                        import re
                        match = re.search(r"Could not find the '([^']+)' column", err_str)
                        if match:
                            bad_col = match.group(1)
                            if bad_col in payload:
                                del payload[bad_col]
                                continue
                    break
        except Exception as e:
            print(f"Async log error: {e}")
            
    # 后台异步执行入库，彻底解放主界面的渲染阻塞
    threading.Thread(target=_task, daemon=True).start()

def clear_user_mistakes(uid):
    supabase = get_supabase()
    try:
        supabase.table("answer_logs").delete().eq("user_id", uid).eq("is_correct", False).execute()
        return True
    except: return False

# --- 核心修复：排行榜强制关联 ---
def get_leaderboard_data():
    supabase = get_supabase()
    try:
        # 1. 获取基础排名
        res_rank = supabase.table("user_rankings").select("*").execute()
        # 2. 获取用户数据
        res_prof = supabase.table("profiles").select("*").execute()
        
        if not res_rank.data: return []
        
        prof_map = {p.get('id'): p for p in (res_prof.data or []) if p.get('id')}
        
        flat = []
        for r in res_rank.data:
            uid = r.get('user_id') or r.get('id')
            if not uid: continue
            
            p = prof_map.get(uid, {})
            # 融合数据，赋予默认值，杜绝空数据报错
            r['account_name'] = p.get('account_name', '')
            r['challenge_count'] = p.get('challenge_count', 0)
            r['challenge_success_count'] = p.get('challenge_success_count', 0)
            # 考虑到如果 user_rankings 没 name，用 profile 的
            if not r.get('name') and p.get('name'):
                r['name'] = p.get('name')
                
            flat.append(r)
        return flat
    except Exception as e:
        print(f"Leaderboard Error: {e}")
        return []

def normalize_text(text):
    if not text: return ""
    return re.sub(r'\s+', '', str(text).replace("<u>", "").replace("</u>", "").replace("*", ""))

# --- 核心修复：智能补全与释放同步限制 ---
def get_public_mistakes_with_kills(limit=100):
    supabase = get_supabase()
    try:
        # 1. 抓取答题日志
        res_logs = supabase.table("answer_logs").select("*").eq("is_correct", False).order('created_at', desc=True).limit(2000).execute()
        if not res_logs.data: return []
        
        # 2. 抓取精选题库，用于“智能补全”
        res_sh = supabase.table("shared_questions").select("*").execute()
        sh_map = {}
        if res_sh.data:
            sh_map = {normalize_text(s.get('question')): dict(s) for s in res_sh.data if s.get('question')}
        
        counts = {}
        processed_map = {}
        
        for r in res_logs.data:
            q_raw = r.get('question') or r.get('question_text')
            clean_str = normalize_text(q_raw)
            
            if not clean_str or len(clean_str) < 10: 
                continue
            
            # 核心修复：如果数据库因为缺列而丢弃了 options，我们从精选题库里把它“借”回来
            if clean_str in sh_map:
                std_q = sh_map[clean_str]
                if not r.get('options') or r.get('options') == {}:
                    r['options'] = std_q.get('options', {})
                if not r.get('answer'):
                    r['answer'] = std_q.get('answer', '')
                if not r.get('analysis'):
                    r['analysis'] = std_q.get('analysis', '')
                # 顺便把带富文本格式的完美题干借过来
                r['question'] = std_q.get('question', q_raw)
            
            if clean_str not in counts:
                counts[clean_str] = 1
                processed_map[clean_str] = r
            else:
                counts[clean_str] += 1
                
        final_list = []
        for clean_str, q_obj in processed_map.items():
            final_obj = dict(q_obj)
            final_obj['kill_count'] = counts[clean_str]
            final_list.append(final_obj)
            
        return sorted(final_list, key=lambda x: x['kill_count'], reverse=True)[:limit]
    except Exception as e:
        st.error(f"Mistakes Sync Error: {e}")
        return []

def share_to_community(q_data, category, uid, recommend_count=1):
    supabase = get_supabase()
    try:
        supabase.table("shared_questions").insert({
            "category": category, "question": q_data.get("question", ""), "options": q_data.get("options", {}),
            "answer": q_data.get("answer", ""), "analysis": q_data.get("analysis", ""), "user_id": uid, "recommend_count": recommend_count
        }).execute()
        return True
    except: return False

def get_community_selected(limit=1000):
    supabase = get_supabase()
    try:
        res = supabase.table("shared_questions").select("*").order("recommend_count", desc=True).order("id", desc=True).limit(limit).execute()
        # 过滤乱码，并严格排除处于 DRAFT_ 状态的待审核题目
        valid = [q for q in (res.data or []) if q.get('question') and len(q.get('question')) > 5 and not str(q.get('category')).startswith('DRAFT_')]
        return valid
    except: return []

def add_to_draft_pool(q_data):
    supabase = get_supabase()
    try:
        supabase.table("draft_pool").insert({
            "category": q_data.get("category"),
            "content": q_data,
            "logic_fingerprint": q_data.get("logic_fingerprint", ""),
            "knowledge_point": q_data.get("knowledge_point", "")
        }).execute()
        return True
    except: return False

def clean_draft_pool_data():
    supabase = get_supabase()
    try:
        res = supabase.table("draft_pool").select("*").execute()
        from ai_engine import get_clean_category
        for row in (res.data or []):
            content = row.get("content", {})
            full_text = content.get("question", "") + " " + content.get("analysis", "")
            raw_cat = row.get("category", "")
            
            clean = get_clean_category(raw_cat, full_text)
            if clean != raw_cat:
                content["category"] = clean
                supabase.table("draft_pool").update({
                    "category": clean,
                    "content": content
                }).eq("id", row["id"]).execute()
    except Exception as e:
        print(f"Hot wash error: {e}")

def get_draft_pool(category):
    supabase = get_supabase()
    try:
        res = supabase.table("draft_pool").select("*").eq("category", category).execute()
        if not res.data: return []
        ret = []
        for r in res.data:
            q = r.get('content', {})
            q['id'] = r.get('id')
            ret.append(q)
        return ret
    except: return []

def publish_draft(draft_id, category, admin_id):
    supabase = get_supabase()
    try:
        res = supabase.table("draft_pool").select("*").eq("id", draft_id).execute()
        if not res.data: return False
        q_data = res.data[0].get('content', {})
        
        try:
            supabase.table("shared_questions").insert({
                "category": category, 
                "question": q_data.get("question", ""), 
                "options": q_data.get("options", {}),
                "answer": q_data.get("answer", ""), 
                "analysis": q_data.get("analysis", ""), 
                "user_id": admin_id, 
                "recommend_count": 100
            }).execute()
        except Exception as e:
            if "duplicate key value violates unique constraint" in str(e) or "23505" in str(e):
                pass # It's a duplicate, safely ignore and proceed to delete the draft
            else:
                raise e # Re-raise if it's a different error
                
        res = supabase.table("draft_pool").delete().eq("id", draft_id).execute()
        return True, "Success"
    except Exception as e: 
        import traceback
        traceback.print_exc()
        return False, str(e)

def delete_draft(draft_id):
    supabase = get_supabase()
    try:
        supabase.table("draft_pool").delete().eq("id", draft_id).execute()
        return True
    except: return False

def get_admin_uuid():
    supabase = get_supabase()
    try:
        res = supabase.table("profiles").select("id").limit(1).execute()
        if res.data: return res.data[0]['id']
    except: pass
    return "00000000-0000-0000-0000-000000000000"

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

def delete_shared_question(q_id):
    supabase = get_supabase()
    try:
        supabase.table("shared_questions").delete().eq("id", q_id).execute()
        return True
    except: return False

def increment_challenge_stats(uid, success=False):
    supabase = get_supabase()
    try:
        res = supabase.table("profiles").select("challenge_count, challenge_success_count").eq("id", uid).execute()
        if res.data:
            c = res.data[0].get('challenge_count', 0) + 1
            cs = res.data[0].get('challenge_success_count', 0) + (1 if success else 0)
            supabase.table("profiles").update({"challenge_count": c, "challenge_success_count": cs}).eq("id", uid).execute()
    except Exception as e:
        print(f"Challenge update error: {e}")
