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
    get_leaderboard_data, delete_shared_question_by_id, delete_all_logs_of_question, record_challenge
)
from ai_engine import generate_ai_question, re_verify_question

# --- v7.7 纯净荣耀版 ---
st.set_page_config(page_title="Zhongkao-Navigator Pro v7.7", page_icon="🛡️", layout="wide")

BEIJING_TZ = timezone(timedelta(hours=8))

# --- UI 样式 ---
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .gold-medal { color: #d4af37 !important; font-weight: bold !important; font-size: 1.15rem; }
    .admin-badge { background-color: #dc2626; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
    .section-title { background: #1e3a8a; color: white; padding: 10px 20px; border-radius: 8px; margin: 20px 0; font-size: 1.2rem; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'current_page' not in st.session_state: st.session_state.current_page = "🏰 社区广场"
if 'current_q' not in st.session_state: st.session_state.current_q = None
if 'question_id' not in st.session_state: st.session_state.question_id = str(uuid.uuid4())
if 'answered' not in st.session_state: st.session_state.answered = False
if 'targets' not in st.session_state: st.session_state.targets = []

def format_text(text):
    if not text: return ""
    return text.replace("<u>", " **【").replace("</u>", "】** ").replace("（", " **（").replace("）", "）** ")

def main():
    if st.session_state.user is None: show_auth()
    else: app_body()

def show_auth():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🛡️ 语文冲刺 Pro v7.7</h2>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["🔑 登录", "📝 注册"])
        with t1:
            u = st.text_input("账号", key="l_u")
            p = st.text_input("密码", type="password", key="l_p")
            if st.button("进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t2:
            ru = st.text_input("账号 ID", key="r_u")
            rp = st.text_input("密码", type="password", key="r_p")
            rn = st.text_input("显示姓名", key="r_n")
            rc = st.text_input("班级", key="r_c")
            if st.button("完成注册", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_body():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学"}
    acc = profile.get('account_name', user.email.split('@')[0]).lower()
    is_admin = (acc == "zhoumingen" or (acc.startswith('hongyi') and acc[6:].isdigit() and 1 <= int(acc[6:]) <= 100))
    
    with st.sidebar:
        st.markdown(f"### 👋 {profile['name']} " + ("<span class='admin-badge'>ADMIN</span>" if is_admin else ""), unsafe_allow_html=True)
        # --- 修复：导航白名单包含挑战模式 ---
        base_pages = ["🏰 社区广场", "📊 能力画像"]
        if is_admin: base_pages.insert(0, "📖 专项训练")
        
        # 允许“挑战模式”作为隐藏页面存在
        all_allowed = base_pages + ["🎯 挑战模式"]
        
        # 导航控制
        if st.session_state.current_page not in all_allowed:
            st.session_state.current_page = "🏰 社区广场"
            
        # 只有基础页面显示在 radio 中
        display_page = st.session_state.current_page if st.session_state.current_page in base_pages else "🏰 社区广场"
        nav_res = st.radio("系统导航", base_pages, index=base_pages.index(display_page))
        
        # 只有当用户主动点击 radio 时才切换（避免覆盖挑战模式）
        if nav_res != display_page:
            st.session_state.current_page = nav_res
            st.rerun()
            
        st.divider()
        if is_admin:
            st.session_state.targets = st.multiselect("考点锁定(Admin)：", ["字音辨析", "字形纠错", "成语运用", "病句诊断", "3500字基础"], default=st.session_state.targets)
        if st.button("注销退出"): st.session_state.user = None; st.rerun()

    # 页面路由
    if st.session_state.current_page == "📖 专项训练": brush_page(is_admin)
    elif st.session_state.current_page == "🏰 社区广场": community_page(is_admin, acc)
    elif st.session_state.current_page == "🎯 挑战模式": challenge_mode(is_admin)
    else: dashboard_page()

def brush_page(is_admin):
    st.header("📖 命题实验室")
    if st.session_state.current_q is None: refresh_q()
    if st.button("✨ 换一题"): refresh_q(); st.rerun()
    q = st.session_state.current_q
    if q and "error" not in q:
        st.markdown(f"### {format_text(q['question'])}", unsafe_allow_html=True)
        opts = q.get('options', {})
        ans = st.radio("答题预览：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {opts.get(x, '...')}", key=st.session_state.question_id, index=None)
        if ans:
            log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q, ans, (ans == q['answer']), 5.0)
            if ans == q['answer']: st.success("正确！")
            else: st.error(f"错误，答案是 {q['answer']}")
            st.info(f"解析：{q['analysis']}")
            if st.button("👍 分享到广场并贡献"): share_to_community(q, q.get('category', '综合'), st.session_state.user.id); st.toast("贡献成功")

def refresh_q():
    st.session_state.answered = False
    st.session_state.question_id = str(uuid.uuid4())
    st.session_state.start_time = time.time()
    st.session_state.current_q = generate_ai_question(None, "precise", random.choice(st.session_state.targets) if st.session_state.targets else None)

def community_page(is_admin, current_acc):
    st.markdown("<div class='section-title'>🏰 社区荣耀广场</div>", unsafe_allow_html=True)
    data = get_leaderboard_data()
    if data:
        df = pd.DataFrame(data)
        # --- 增强型管理员过滤逻辑 ---
        def is_really_admin(row):
            acc_name = str(row.get('account_name', '')).lower()
            disp_name = str(row.get('name', '')).lower()
            # 匹配 zhoumingen 或 hongyi1-100
            if acc_name == "zhoumingen" or disp_name == "周铭恩": return True
            if acc_name.startswith('hongyi') and acc_name[6:].isdigit(): return True
            return False

        df_students = df[~df.apply(is_really_admin, axis=1)]
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 🔥 刷题榜 (学生)")
            for i, r in df_students.sort_values('total_questions', ascending=False).head(5).reset_index().iterrows():
                st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['total_questions']}题", unsafe_allow_html=True)
        with c2:
            st.markdown("#### ⚔️ 战神榜 (学生)")
            for i, r in df_students.sort_values('correct_questions', ascending=False).head(5).reset_index().iterrows():
                st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['correct_questions']}对", unsafe_allow_html=True)
        with c3:
            st.markdown("#### 💡 贡献榜 (全站)")
            for i, r in df.sort_values('contributions', ascending=False).head(5).reset_index().iterrows():
                st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['contributions']}次", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>🌟 知识点精选题库 (分类)</div>", unsafe_allow_html=True)
    qs = get_community_selected()
    if qs:
        df_qs = pd.DataFrame(qs)
        for cat in df_qs['category'].unique():
            with st.expander(f"📌 {cat} ({len(df_qs[df_qs['category']==cat])}题)"):
                for _, q in df_qs[df_qs['category']==cat].iterrows():
                    st.write(f"**{q['question']}**")
                    if st.button("挑战", key=f"sq_{q['id']}"):
                        st.session_state.current_q = q.to_dict(); st.session_state.current_page = "🎯 挑战模式"; st.rerun()
                    if is_admin:
                        if st.button("🗑️ 删除", key=f"del_{q['id']}"):
                            if delete_shared_question_by_id(q['id']): st.toast("已下架"); st.rerun()

    st.markdown("<div class='section-title'>🚩 全站连斩错题流</div>", unsafe_allow_html=True)
    for m in get_public_mistakes_with_kills():
        kills = m.get('kill_count', 1)
        st.error(f"⚔️ 连斩 {kills} 人 | {format_text(m['question'])}")
        if st.button("挑战终结", key=f"k_{kills}_{random.random()}"):
            st.session_state.current_q = m; st.session_state.current_page = "🎯 挑战模式"; st.rerun()
        if is_admin:
            if st.button("🗑️ 强制清除", key=f"fdel_{kills}_{random.random()}"):
                if delete_all_logs_of_question(m['question']): st.toast("已清除"); st.rerun()

def challenge_mode(is_admin):
    st.header("🎯 社区挑战模式")
    q = st.session_state.current_q
    if q:
        st.markdown(f"### {format_text(q['question'])}", unsafe_allow_html=True)
        opts = q.get('options', {})
        ans = st.radio("回答：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {opts.get(x, '...')}", key="chal_q", index=None)
        if ans:
            is_correct = (ans == q['answer'])
            log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q, ans, is_correct, 5.0)
            if is_correct: st.success("🎉 正确！挑战成功！"); st.balloons()
            else: st.error(f"❌ 错误。答案：{q['answer']}")
            st.info(f"💡 解析：{q['analysis']}")
            if st.button("返回广场"): 
                st.session_state.current_page = "🏰 社区广场"
                st.rerun()

def dashboard_page():
    st.header("📊 深度能力画像")
    logs = get_user_all_logs(st.session_state.user.id)
    if logs:
        df = pd.DataFrame(logs)
        st.plotly_chart(px.line(df.groupby(pd.to_datetime(df['created_at']).dt.floor('10min'))['is_correct'].mean().reset_index(), x='created_at', y='is_correct', title="状态波动"), use_container_width=True)
    else: st.info("暂无数据")

if __name__ == "__main__":
    main()
