import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import time
import random
import re
from database import (
    sign_in, sign_up_and_login, get_profile, log_quiz_result, 
    get_user_all_logs, share_to_community, get_community_selected, 
    get_public_mistakes_with_kills, get_leaderboard_data, 
    delete_all_logs_of_question, clear_user_mistakes
)
from ai_engine import generate_ai_question

# --- v9.7 王者回归·硬核修复版 ---
st.set_page_config(page_title="Zhongkao-Navigator Pro v9.7", page_icon="🏆", layout="wide")

# --- UI 样式 ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    .page-header { background: linear-gradient(90deg, #1e3a8a, #3b82f6); color: white; padding: 20px 30px; border-radius: 15px; margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    .gold-medal { color: #d4af37 !important; font-weight: bold; font-size: 1.2rem; }
    .admin-badge { background: #dc2626; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
    .kill-badge { background: #ef4444; color: white; padding: 2px 10px; border-radius: 12px; font-weight: bold; font-size: 0.85rem; }
    .mistake-card { border-left: 5px solid #ef4444; background: white; padding: 15px; border-radius: 8px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'active_tab' not in st.session_state: st.session_state.active_tab = "🌟 精选题库"
if 'challenge_q' not in st.session_state: st.session_state.challenge_q = None
if 'redo_q' not in st.session_state: st.session_state.redo_q = None

def format_html(text):
    if not text: return ""
    return text.replace("<u>", "<span style='text-decoration: underline; color: #2563eb;'>").replace("</u>", "</span>")

def main():
    if st.session_state.user is None: show_auth()
    else: app_shell()

def show_auth():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🏆 语文冲刺 Pro v9.7</h2>", unsafe_allow_html=True)
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
            rn = st.text_input("显示姓名")
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
        st.session_state.active_tab = st.radio("导航菜单", menu)
        st.divider()
        if st.button("退出系统"): st.session_state.user = None; st.rerun()

    # --- 渲染容器 ---
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
            st.markdown(f"### 【{q['category']}】 {format_html(q['question'])}", unsafe_allow_html=True)
            if st.button("立即挑战", key=f"sel_q_{q['id']}"):
                st.session_state.challenge_q = q; st.rerun()
            st.divider()

def render_mistake_stream():
    st.markdown("<div class='page-header'><h1>🚩 全站连斩错题流</h1><p>攻克高频难点</p></div>", unsafe_allow_html=True)
    mk = get_public_mistakes_with_kills()
    for m in mk:
        st.error(f"<span class='kill-badge'>⚔️ 连斩 {m['kill_count']} 人</span> {format_html(m['question'])}", icon="🔥")
        if st.button("终结此题", key=f"mk_v97_{m['question'][:20]}"):
            st.session_state.challenge_q = m; st.rerun()

def render_leaderboard():
    st.markdown("<div class='page-header'><h1>🏆 七维荣耀金榜</h1><p>全维度数据实时透视</p></div>", unsafe_allow_html=True)
    data = get_leaderboard_data()
    if not data: st.info("榜单同步中..."); return
    
    df = pd.DataFrame(data)
    # --- 强化管理员过滤逻辑 ---
    def filter_admin(row):
        an = str(row.get('account_name', '')).lower()
        dn = str(row.get('name', '')).lower()
        if an == "zhoumingen" or dn == "周铭恩": return True
        if an.startswith('hongyi') and an[6:].isdigit(): return True
        return False
    
    df_st = df[~df.apply(filter_admin, axis=1)] if not df.empty else df
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🔥 刷题榜")
        for i, r in df_st.sort_values('total_questions', ascending=False).head(5).reset_index().iterrows():
            st.write(f"{i+1}. {r['name']} - {r['total_questions']}题")
    with c2:
        st.subheader("⚔️ 战神榜")
        for i, r in df_st.sort_values('correct_questions', ascending=False).head(5).reset_index().iterrows():
            st.write(f"{i+1}. {r['name']} - {r['correct_questions']}对")
    with c3:
        st.subheader("💡 贡献榜")
        for i, r in df.sort_values('contributions', ascending=False).head(5).reset_index().iterrows():
            st.write(f"{i+1}. {r['name']} - {r['contributions']}次")
            
    st.divider()
    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    with r2c1:
        st.subheader("⚡ 速度榜")
        df_v = df_st[df_st['total_questions'] >= 5]
        if not df_v.empty:
            df_v['v'] = (df_v['total_time'] / df_v['total_questions']).round(1)
            for i, r in df_v.sort_values('v').head(3).reset_index().iterrows(): st.write(f"{i+1}. {r['name']} - {r['v']}s")
    with r2c2:
        st.subheader("⏳ 专注榜")
        for i, r in df_st.sort_values('total_time', ascending=False).head(3).reset_index().iterrows():
            st.write(f"{i+1}. {r['name']} - {(r['total_time']/60):.1f}m")
    with r2c3:
        st.subheader("🚩 质疑榜")
        for i, r in df_st.sort_values('challenge_count', ascending=False).head(3).reset_index().iterrows():
            st.write(f"{i+1}. {r['name']} - {r['challenge_count']}次")
    with r2c4:
        st.subheader("🏆 判官榜")
        for i, r in df_st.sort_values('challenge_success_count', ascending=False).head(3).reset_index().iterrows():
            st.write(f"{i+1}. {r['name']} - {r['challenge_success_count']}次")

def render_personal_dashboard():
    st.markdown("<div class='page-header'><h1>📊 个人能力全景画像</h1><p>全量记录，深度反馈</p></div>", unsafe_allow_html=True)
    logs = get_user_all_logs(st.session_state.user.id)
    df = pd.DataFrame(logs) if logs else pd.DataFrame(columns=['created_at', 'is_correct', 'category', 'question', 'options', 'answer', 'analysis', 'student_answer'])
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("⏱️ 状态波动图")
        if not df.empty:
            df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Shanghai')
            bin_stats = df.groupby(df['created_at'].dt.floor('10min'))['is_correct'].mean().reset_index()
            st.plotly_chart(px.line(bin_stats, x='created_at', y='is_correct', markers=True), use_container_width=True)
        else: st.info("做题后开启状态监控")
    with c2:
        st.subheader("🏹 五轴核心罗盘")
        axes = ["字音辨析", "成语运用", "病句诊断", "字形纠错", "3500字基础"]
        st_v = df.groupby('category')['is_correct'].mean().to_dict() if not df.empty else {}
        radar_values = [st_v.get(a, 0)*100 for a in axes]
        st.plotly_chart(go.Figure(data=go.Scatterpolar(r=radar_values, theta=axes, fill='toself')), use_container_width=True)

    st.divider()
    st.subheader("📖 智能错题涅槃集")
    wrongs = df[~df['is_correct']]
    if not wrongs.empty:
        latest = wrongs.sort_values('created_at', ascending=False).drop_duplicates('question')
        for cat in latest['category'].unique():
            with st.expander(f"📌 {cat} ({len(latest[latest['category']==cat])} 题)"):
                for _, m in latest[latest['category']==cat].iterrows():
                    st.markdown(f"<div class='mistake-card'><b>题干：</b>{format_html(m['question'])}<br>❌ 回答：{m['student_answer']} | ✅ 答案：{m['answer']}</div>", unsafe_allow_html=True)
                    if st.button("🔥 再练一次", key=f"redo_v97_{random.random()}"):
                        st.session_state.redo_q = m.to_dict(); st.rerun()
    else: st.success("暂无错题记录")

def render_admin_lab():
    st.markdown("<div class='page-header'><h1>📖 命题实验室</h1><p>Admin Only</p></div>", unsafe_allow_html=True)
    if st.button("✨ 生成字音精选题"):
        st.session_state.lab_q = generate_ai_question(None, "precise", "字音辨析")
    if 'lab_q' in st.session_state and st.session_state.lab_q:
        q = st.session_state.lab_q
        st.write(q['question'])
        if st.button("🚀 分享到全站"): share_to_community(q, q['category'], st.session_state.user.id); st.toast("已发布")

def render_challenge_mode():
    q = st.session_state.challenge_q
    st.markdown("<div class='page-header'><h1>🎯 挑战进行中</h1></div>", unsafe_allow_html=True)
    st.info(f"### {format_html(q['question'])}")
    opts = q.get('options', {})
    ans = st.radio("你的回答：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {opts.get(x, '...')}", key="act_v97", index=None)
    c1, c2 = st.columns(2)
    if ans and c1.button("确认提交"):
        log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q, ans, (ans == q['answer']), 5.0)
        if ans == q['answer']: st.success("正确！"); st.balloons()
        else: st.error(f"错误，答案：{q['answer']}")
    if c2.button("⬅️ 退出挑战"): st.session_state.challenge_q = None; st.rerun()

def render_redo_mode():
    q = st.session_state.redo_q
    st.markdown("<div class='page-header'><h1>🔥 错题涅槃练习</h1></div>", unsafe_allow_html=True)
    st.warning(f"### {format_html(q['question'])}")
    ans = st.radio("重选答案：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {q['options'].get(x, '...')}", key="redo_v97", index=None)
    c1, c2 = st.columns(2)
    if ans and c1.button("确认提交"):
        log_quiz_result(st.session_state.user.id, q['category'], q, ans, (ans == q['answer']), 5.0)
        if ans == q['answer']: st.success("涅槃成功！"); st.balloons()
    if c2.button("⬅️ 返回"): st.session_state.redo_q = None; st.rerun()

if __name__ == "__main__":
    main()
