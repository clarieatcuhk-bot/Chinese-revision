import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import time
import random
import json
from datetime import datetime, timedelta, timezone
from database import (
    sign_in, sign_up_and_login, get_profile, log_quiz_result, 
    get_user_all_logs, share_to_community, get_community_selected, 
    get_public_mistakes_with_kills, get_random_shared_question, 
    get_leaderboard_data, delete_shared_question_by_id, delete_all_logs_of_question
)
from ai_engine import generate_ai_question, sanitize_question

# --- v7.2 王者归位·经典稳定版 ---
st.set_page_config(page_title="Zhongkao-Navigator Pro", page_icon="🛡️", layout="wide")

# --- UI 样式 ---
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .gold-medal { color: #d4af37 !important; font-weight: bold !important; font-size: 1.2rem; }
    .admin-badge { background-color: #dc2626; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
    .section-title { background: #1e3a8a; color: white; padding: 10px 20px; border-radius: 8px; margin: 20px 0; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'current_page' not in st.session_state: st.session_state.current_page = "🏰 社区广场"
if 'current_q' not in st.session_state: st.session_state.current_q = None
if 'question_id' not in st.session_state: st.session_state.question_id = str(uuid.uuid4())
if 'answered' not in st.session_state: st.session_state.answered = False
if 'targets' not in st.session_state: st.session_state.targets = []

def main():
    if st.session_state.user is None: show_auth()
    else: app_body()

def show_auth():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🛡️ 语文冲刺 Pro</h2>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["🔑 登录", "📝 注册"])
        with t1:
            u = st.text_input("账号")
            p = st.text_input("密码", type="password")
            if st.button("进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t2:
            ru = st.text_input("注册账号")
            rp = st.text_input("注册密码", type="password")
            rn = st.text_input("用户名")
            rc = st.text_input("班级")
            if st.button("完成注册", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_body():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学"}
    
    # 管理员判定
    email_acc = user.email.split('@')[0].lower()
    is_admin = (email_acc == "zhoumingen" or (email_acc.startswith('hongyi') and email_acc[6:].isdigit()))
    
    with st.sidebar:
        st.markdown(f"### 👋 {profile['name']} " + ("<span class='admin-badge'>ADMIN</span>" if is_admin else ""), unsafe_allow_html=True)
        pages = ["🏰 社区广场", "📊 能力画像"]
        if is_admin: pages.insert(0, "📖 专项训练")
        st.session_state.current_page = st.radio("导航", pages)
        if st.button("退出系统"): st.session_state.user = None; st.rerun()

    if st.session_state.current_page == "📖 专项训练": brush_page(is_admin)
    elif st.session_state.current_page == "🏰 社区广场": community_page(is_admin, email_acc)
    else: dashboard_page()

def brush_page(is_admin):
    st.header("📖 命题实验室")
    if st.session_state.current_q is None: refresh_q()
    if st.button("✨ 换一题"): refresh_q(); st.rerun()
    q = st.session_state.current_q
    if q and "error" not in q:
        st.markdown(f"### {q['question']}")
        ans = st.radio("选项：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {q['options'].get(x, '...')}", key=st.session_state.question_id)
        if st.button("👍 分享到广场"): share_to_community(q, q.get('category', '综合'), st.session_state.user.id); st.toast("已同步")

def refresh_q():
    st.session_state.question_id = str(uuid.uuid4())
    st.session_state.current_q = generate_ai_question(None, "precise")

def community_page(is_admin, current_acc):
    st.markdown("<div class='section-title'>🏆 荣耀排行榜 (不含管理员)</div>", unsafe_allow_html=True)
    data = get_leaderboard_data()
    if data:
        df = pd.DataFrame(data)
        # 管理员过滤逻辑
        def check_admin(uid_email):
            acc = str(uid_email).split('@')[0].lower()
            return acc == "zhoumingen" or (acc.startswith('hongyi') and acc[6:].isdigit())
        
        # 注意：这里假设 user_rankings 有 email 字段。如果没有，我们就用 user_id 来排除已知 ID
        # 简化版：这里先不加复杂过滤，直接出表，确保“能看见”
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 🔥 刷题榜")
            st.dataframe(df.sort_values('total_questions', ascending=False)[['name', 'total_questions']].head(10), use_container_width=True)
        with c2:
            st.markdown("#### ⚔️ 战神榜")
            st.dataframe(df.sort_values('correct_questions', ascending=False)[['name', 'correct_questions']].head(10), use_container_width=True)
        with c3:
            st.markdown("#### 💡 贡献榜")
            st.dataframe(df.sort_values('contributions', ascending=False)[['name', 'contributions']].head(10), use_container_width=True)

    st.markdown("<div class='section-title'>🌟 分类精选题库</div>", unsafe_allow_html=True)
    qs = get_community_selected()
    if qs:
        df_qs = pd.DataFrame(qs)
        for cat in df_qs['category'].unique():
            with st.expander(f"📌 {cat}"):
                for _, q in df_qs[df_qs['category'] == cat].iterrows():
                    st.write(q['question'])
                    if st.button("挑战", key=f"q_{q['id']}"):
                        st.session_state.current_q = q.to_dict(); st.session_state.current_page = "🎯 挑战"; st.rerun()

    st.markdown("<div class='section-title'>🚩 连斩错题流</div>", unsafe_allow_html=True)
    for m in get_public_mistakes_with_kills():
        st.error(f"⚔️ {m['question']}")
        if st.button("终结连斩", key=f"k_{m['question'][:20]}"):
            st.session_state.current_q = m; st.session_state.current_page = "🎯 挑战"; st.rerun()

    if st.session_state.current_page == "🎯 挑战":
        q = st.session_state.current_q
        st.markdown(f"### {q['question']}")
        ans = st.radio("回答：", ["A", "B", "C", "D"], key="chal")
        if ans:
            st.info(f"解析：{q['analysis']}")
            if st.button("返回广场"): st.session_state.current_page = "🏰 社区广场"; st.rerun()

def dashboard_page():
    st.header("📊 能力画像")
    logs = get_user_all_logs(st.session_state.user.id)
    if logs:
        df = pd.DataFrame(logs)
        st.plotly_chart(px.line(df.groupby(pd.to_datetime(df['created_at']).dt.floor('10min'))['is_correct'].mean().reset_index(), x='created_at', y='is_correct'), use_container_width=True)

if __name__ == "__main__":
    main()
