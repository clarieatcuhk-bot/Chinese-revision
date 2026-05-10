import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import time
import random
import json
import re
from database import (
    sign_in, sign_up_and_login, get_profile, log_quiz_result, 
    get_user_all_logs, share_to_community, get_community_selected, 
    get_public_mistakes_with_kills, get_leaderboard_data, 
    delete_all_logs_of_question, clear_user_mistakes
)
from ai_engine import generate_ai_question

# --- v9.8 全数据校验·深度修复版 ---
st.set_page_config(page_title="Zhongkao-Navigator Pro v9.8", page_icon="🧬", layout="wide")

# --- UI 样式 ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    .page-header { background: linear-gradient(90deg, #1e3a8a, #3b82f6); color: white; padding: 20px 30px; border-radius: 15px; margin-bottom: 30px; }
    .kill-badge { background: #ef4444; color: white; padding: 2px 10px; border-radius: 12px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 辅助工具：确保数据格式正确 ---
def ensure_dict(data):
    if isinstance(data, dict): return data
    if isinstance(data, str):
        try: return json.loads(data)
        except: return {}
    return {}

def format_html(text):
    if not text: return "题目加载中..."
    return text.replace("<u>", "<span style='text-decoration: underline; color: #2563eb; font-weight: bold;'>").replace("</u>", "</span>")

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'active_tab' not in st.session_state: st.session_state.active_tab = "🌟 精选题库"
if 'challenge_q' not in st.session_state: st.session_state.challenge_q = None
if 'redo_q' not in st.session_state: st.session_state.redo_q = None

def main():
    if st.session_state.user is None: show_auth()
    else: app_shell()

def show_auth():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🧬 语文导航 Pro v9.8</h2>", unsafe_allow_html=True)
        t = st.tabs(["🔑 登录", "📝 注册"])
        with t[0]:
            u = st.text_input("账号 ID")
            p = st.text_input("登录密码", type="password")
            if st.button("进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t[1]:
            ru = st.text_input("注册账号")
            rp = st.text_input("设置密码", type="password")
            rn = st.text_input("姓名")
            rc = st.text_input("班级")
            if st.button("立即加入", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_shell():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学"}
    acc = profile.get('account_name', user.email.split('@')[0]).lower()
    is_admin = (acc == "zhoumingen" or (acc.startswith('hongyi') and acc[6:].isdigit()))
    
    with st.sidebar:
        st.markdown(f"### 👋 {profile['name']} " + ("<span class='admin-badge'>ADMIN</span>" if is_admin else ""), unsafe_allow_html=True)
        menu = ["🌟 精选题库", "🚩 错题挑战", "🏆 荣耀金榜", "📊 个人画像"]
        if is_admin: menu.insert(0, "📖 命题实验室")
        
        # 强制同步导航
        if st.session_state.challenge_q or st.session_state.redo_q:
            st.info("🎯 挑战进行中...")
            if st.button("⬅️ 退出挑战模式"):
                st.session_state.challenge_q = None; st.session_state.redo_q = None; st.rerun()
        else:
            idx = menu.index(st.session_state.active_tab) if st.session_state.active_tab in menu else 0
            st.session_state.active_tab = st.radio("导航菜单", menu, index=idx)
        
        st.divider()
        if st.button("登出系统"): st.session_state.user = None; st.rerun()

    # 逻辑路由
    if st.session_state.challenge_q: render_challenge_mode()
    elif st.session_state.redo_q: render_redo_mode()
    else:
        if st.session_state.active_tab == "🌟 精选题库": render_selected_questions()
        elif st.session_state.active_tab == "🚩 错题挑战": render_mistake_stream()
        elif st.session_state.active_tab == "🏆 荣耀金榜": render_leaderboard()
        elif st.session_state.active_tab == "📊 个人画像": render_personal_dashboard()
        elif st.session_state.active_tab == "📖 命题实验室": render_admin_lab()

def render_selected_questions():
    st.markdown("<div class='page-header'><h1>🌟 老师精选题库</h1><p>全站高质量教学资源</p></div>", unsafe_allow_html=True)
    qs = get_community_selected()
    for q in qs:
        with st.container():
            st.markdown(f"### 【{q.get('category', '综合')}】 {format_html(q.get('question'))}", unsafe_allow_html=True)
            if st.button("立即挑战", key=f"sel_q_{q['id']}"):
                st.session_state.challenge_q = q; st.rerun()
            st.divider()

def render_mistake_stream():
    st.markdown("<div class='page-header'><h1>🚩 全站连斩错题流</h1><p>攻克全站高频难点</p></div>", unsafe_allow_html=True)
    mk = get_public_mistakes_with_kills()
    for m in mk:
        st.error(f"<span class='kill-badge'>⚔️ 连斩 {m['kill_count']} 人</span> {format_html(m.get('question'))}", icon="🔥")
        if st.button("终结此题", key=f"mk_v98_{m.get('id', random.random())}"):
            st.session_state.challenge_q = m; st.rerun()

def render_leaderboard():
    st.markdown("<div class='page-header'><h1>🏆 七维荣耀金榜</h1><p>实时数据透视</p></div>", unsafe_allow_html=True)
    data = get_leaderboard_data()
    if not data: st.info("榜单加载中..."); return
    df = pd.DataFrame(data); is_adm = lambda a: a == "zhoumingen" or (str(a).startswith('hongyi') and str(a)[6:].isdigit())
    df_st = df[~df['account_name'].apply(is_adm)] if 'account_name' in df.columns else df
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🔥 刷题榜")
        for i, r in df_st.sort_values('total_questions', ascending=False).head(5).reset_index().iterrows(): st.write(f"{i+1}. {r['name']} - {r['total_questions']}题")
    with c2:
        st.subheader("⚔️ 战神榜")
        for i, r in df_st.sort_values('correct_questions', ascending=False).head(5).reset_index().iterrows(): st.write(f"{i+1}. {r['name']} - {r['correct_questions']}对")
    with c3:
        st.subheader("💡 贡献榜")
        for i, r in df.sort_values('contributions', ascending=False).head(5).reset_index().iterrows(): st.write(f"{i+1}. {r['name']} - {r['contributions']}次")

def render_personal_dashboard():
    st.markdown("<div class='page-header'><h1>📊 个人能力全景画像</h1><p>全量数据监控</p></div>", unsafe_allow_html=True)
    logs = get_user_all_logs(st.session_state.user.id)
    df = pd.DataFrame(logs) if logs else pd.DataFrame(columns=['created_at', 'is_correct', 'category', 'question', 'options', 'answer', 'analysis', 'student_answer'])
    
    c1, c2 = st.columns([2, 1])
    with c1:
        if not df.empty:
            df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Shanghai')
            st.plotly_chart(px.line(df.groupby(df['created_at'].dt.floor('10min'))['is_correct'].mean().reset_index(), x='created_at', y='is_correct', markers=True), use_container_width=True)
    with c2:
        axes = ["字音辨析", "成语运用", "病句诊断", "字形纠错", "3500字基础"]
        st_v = df.groupby('category')['is_correct'].mean().to_dict() if not df.empty else {}
        st.plotly_chart(go.Figure(data=go.Scatterpolar(r=[st_v.get(a, 0)*100 for a in axes], theta=axes, fill='toself')), use_container_width=True)

    st.divider()
    st.subheader("📖 我的错题本")
    wrongs = df[~df['is_correct']]
    if not wrongs.empty:
        latest = wrongs.sort_values('created_at', ascending=False).drop_duplicates('question')
        for cat in latest['category'].unique():
            with st.expander(f"📌 {cat}"):
                for _, m in latest[latest['category']==cat].iterrows():
                    st.markdown(f"**题干：** {format_html(m.get('question'))}", unsafe_allow_html=True)
                    if st.button("🔥 涅槃重练", key=f"redo_v98_{random.random()}"):
                        st.session_state.redo_q = m.to_dict(); st.rerun()
    else: st.success("暂无错题记录")

def render_admin_lab():
    st.markdown("<div class='page-header'><h1>📖 命题实验室</h1></div>", unsafe_allow_html=True)
    if st.button("✨ 生成新精选题"):
        st.session_state.lab_q = generate_ai_question(None, "precise", "字音辨析")
    if 'lab_q' in st.session_state and st.session_state.lab_q:
        q = st.session_state.lab_q
        st.write(q['question'])
        if st.button("🚀 分享到全站"): share_to_community(q, q['category'], st.session_state.user.id); st.toast("已发布")

def render_challenge_mode():
    q = st.session_state.challenge_q
    st.markdown("<div class='page-header'><h1>🎯 挑战正在进行</h1></div>", unsafe_allow_html=True)
    
    # --- 核心修复：强制字典化并检测字段 ---
    q_text = q.get('question') or q.get('question_text') or "数据异常，请退出重试"
    opts = ensure_dict(q.get('options', {}))
    
    st.info(f"### {format_html(q_text)}")
    ans = st.radio("请选择答案：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {opts.get(x, '...')}", key="act_v98", index=None)
    
    c1, c2 = st.columns(2)
    if ans and c1.button("确认提交"):
        log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q, ans, (ans == q.get('answer')), 5.0)
        if ans == q.get('answer'): st.success("🎉 正确！挑战成功！"); st.balloons()
        else: st.error(f"❌ 错误。正确答案是：{q.get('answer')}")
        st.info(f"💡 解析：{q.get('analysis')}")
    
    if c2.button("⬅️ 退出挑战"):
        st.session_state.challenge_q = None; st.rerun()

def render_redo_mode():
    q = st.session_state.redo_q
    st.markdown("<div class='page-header'><h1>🔥 错题涅槃练习</h1></div>", unsafe_allow_html=True)
    
    q_text = q.get('question') or q.get('question_text') or "数据异常"
    opts = ensure_dict(q.get('options', {}))
    
    st.warning(f"### {format_html(q_text)}")
    ans = st.radio("重选答案：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {opts.get(x, '...')}", key="redo_v98", index=None)
    
    c1, c2 = st.columns(2)
    if ans and c1.button("确认提交"):
        log_quiz_result(st.session_state.user.id, q.get('category'), q, ans, (ans == q.get('answer')), 5.0)
        if ans == q.get('answer'): st.success("🎉 涅槃成功！"); st.balloons()
    
    if c2.button("⬅️ 返回画像"):
        st.session_state.redo_q = None; st.rerun()

if __name__ == "__main__":
    main()
