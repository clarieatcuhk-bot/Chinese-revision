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
    get_public_mistakes_with_kills, get_leaderboard_data, 
    delete_all_logs_of_question
)
from ai_engine import generate_ai_question

# --- v8.5 重火力·全量回归版 ---
st.set_page_config(page_title="Zhongkao-Navigator Pro v8.5", page_icon="🏆", layout="wide")

# --- UI 样式 ---
st.markdown("""
<style>
    .gold-medal { color: #d4af37 !important; font-weight: bold !important; font-size: 1.2rem; }
    .admin-badge { background-color: #dc2626; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
    .section-title { background: #1e3a8a; color: white; padding: 10px 20px; border-radius: 8px; margin: 20px 0; font-size: 1.2rem; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'current_page' not in st.session_state: st.session_state.current_page = "🏰 社区广场"
if 'current_q' not in st.session_state: st.session_state.current_q = None

def main():
    if st.session_state.user is None: show_auth()
    else: app_body()

def show_auth():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🏆 语文冲刺 Pro v8.5</h2>", unsafe_allow_html=True)
        t = st.tabs(["🔑 登录", "📝 注册"])
        with t[0]:
            u = st.text_input("账号")
            p = st.text_input("密码", type="password")
            if st.button("进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t[1]:
            ru = st.text_input("注册 ID")
            rp = st.text_input("注册密码", type="password")
            rn = st.text_input("用户名")
            rc = st.text_input("班级")
            if st.button("完成注册", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_body():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学"}
    acc = profile.get('account_name', user.email.split('@')[0]).lower()
    is_admin = (acc == "zhoumingen" or (acc.startswith('hongyi') and acc[6:].isdigit()))
    
    with st.sidebar:
        st.markdown(f"### 👋 {profile['name']} " + ("<span class='admin-badge'>ADMIN</span>" if is_admin else ""), unsafe_allow_html=True)
        pages = ["🏰 社区广场", "📊 能力画像"]
        if is_admin: pages.insert(0, "📖 专项训练")
        st.session_state.current_page = st.radio("系统导航", pages, index=pages.index(st.session_state.current_page) if st.session_state.current_page in pages else 0)
        if st.button("登出"): st.session_state.user = None; st.rerun()

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
        st.markdown(f"### {q['question']}")
        ans = st.radio("选项预览：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {q['options'].get(x, '...')}", key="q_prev", index=None)
        if ans:
            log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q, ans, (ans == q['answer']), 5.0)
            if st.button("👍 分享到广场"): share_to_community(q, q.get('category', '综合'), st.session_state.user.id); st.toast("分享成功")

def refresh_q():
    st.session_state.current_q = generate_ai_question(None, "precise", "字音辨析")

def community_page(is_admin, current_acc):
    st.markdown("<div class='section-title'>🏆 七维荣耀金榜</div>", unsafe_allow_html=True)
    data = get_leaderboard_data()
    if data:
        df = pd.DataFrame(data); is_adm = lambda a: a == "zhoumingen" or (str(a).startswith('hongyi') and str(a)[6:].isdigit())
        df_students = df[~df['account_name'].apply(is_adm)]
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 🔥 刷题榜")
            for i, r in df_students.sort_values('total_questions', ascending=False).head(5).reset_index().iterrows():
                st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['total_questions']}题", unsafe_allow_html=True)
        with c2:
            st.markdown("#### ⚔️ 战神榜")
            for i, r in df_students.sort_values('correct_questions', ascending=False).head(5).reset_index().iterrows():
                st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['correct_questions']}对", unsafe_allow_html=True)
        with c3:
            st.markdown("#### 💡 贡献榜")
            for i, r in df.sort_values('contributions', ascending=False).head(5).reset_index().iterrows():
                st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['contributions']}次", unsafe_allow_html=True)
        
        st.divider()
        r2c1, r2c2, r2c3, r2c4 = st.columns(4)
        with r2c1:
            st.markdown("#### ⚡ 速度王")
            df_st_speed = df_students[df_students['total_questions'] >= 5]
            if not df_st_speed.empty:
                df_st_speed['speed'] = (df_st_speed['total_time'] / df_st_speed['total_questions']).round(1)
                for i, r in df_st_speed.sort_values('speed').head(3).reset_index().iterrows():
                    st.markdown(f"{i+1}. {r['name']} - {r['speed']}s")
        with r2c2:
            st.markdown("#### ⏳ 专注王")
            for i, r in df_students.sort_values('total_time', ascending=False).head(3).reset_index().iterrows():
                st.markdown(f"{i+1}. {r['name']} - {(r['total_time']/60):.1f}min")
        with r2c3:
            st.markdown("#### 🚩 质疑王")
            for i, r in df_students.sort_values('challenge_count', ascending=False).head(3).reset_index().iterrows():
                st.markdown(f"{i+1}. {r['name']} - {r['challenge_count']}次")
        with r2c4:
            st.markdown("#### 🏆 判官王")
            for i, r in df_students.sort_values('challenge_success_count', ascending=False).head(3).reset_index().iterrows():
                st.markdown(f"{i+1}. {r['name']} - {r['challenge_success_count']}次")

    st.markdown("<div class='section-title'>🌟 老师精选题库</div>", unsafe_allow_html=True)
    qs = get_community_selected()
    if qs:
        for q in qs:
            with st.expander(f"📌 【{q['category']}】 {q['question'][:40]}..."):
                st.write(q['question'])
                if st.button("立即挑战", key=f"sq_{q['id']}"):
                    st.session_state.current_q = q; st.session_state.current_page = "🎯 挑战模式"; st.rerun()

    st.markdown("<div class='section-title'>🚩 全站连斩错题流 (暴力实时)</div>", unsafe_allow_html=True)
    mistakes = get_public_mistakes_with_kills()
    for m in mistakes:
        st.error(f"⚔️ 连斩 {m['kill_count']} 人 | {m['question']}")
        if st.button("终结连斩", key=f"k_{m['question'][:20]}_{random.random()}"):
            st.session_state.current_q = m; st.session_state.current_page = "🎯 挑战模式"; st.rerun()

def challenge_mode(is_admin):
    st.header("🎯 正在挑战")
    q = st.session_state.current_q
    if q:
        st.markdown(f"### {q['question']}")
        ans = st.radio("你的回答：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {q.get('options', {}).get(x, '...')}", key="chal")
        if ans:
            log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q, ans, (ans == q['answer']), 5.0)
            st.info(f"解析：{q['analysis']}")
            if st.button("返回广场"): st.session_state.current_page = "🏰 社区广场"; st.rerun()

def dashboard_page():
    st.header("📊 能力画像")
    logs = get_user_all_logs(st.session_state.user.id)
    df = pd.DataFrame(logs) if logs else pd.DataFrame(columns=['created_at', 'is_correct', 'category'])
    
    st.subheader("⏱️ 10 分钟波动图")
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Shanghai')
        bin_stats = df.groupby(df['created_at'].dt.floor('10min'))['is_correct'].mean().reset_index()
        st.plotly_chart(px.line(bin_stats, x='created_at', y='is_correct', markers=True), use_container_width=True)
    else: st.plotly_chart(px.line(title="暂无数据"), use_container_width=True)

    st.subheader("🏹 五轴能力罗盘")
    fixed_axes = ["字音辨析", "成语运用", "病句诊断", "字形纠错", "3500字基础"]
    stats = df.groupby('category')['is_correct'].mean().to_dict() if not df.empty else {}
    radar_values = [stats.get(ax, 0) * 100 for ax in fixed_axes]
    st.plotly_chart(go.Figure(data=go.Scatterpolar(r=radar_values, theta=fixed_axes, fill='toself')), use_container_width=True)

if __name__ == "__main__":
    main()
