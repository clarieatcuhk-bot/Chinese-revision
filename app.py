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
    get_public_mistakes_with_kills, get_random_shared_question, get_leaderboard_data
)
from ai_engine import generate_ai_question, sanitize_question

# --- v5.6 北京时间校准版 ---
st.set_page_config(page_title="Zhongkao-Navigator v5.6", page_icon="🕒", layout="wide")

# 定义北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))

def get_now_bj():
    return datetime.now(BEIJING_TZ)

# --- UI 样式 ---
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .source-tag { background-color: #f1f5f9; color: #475569; padding: 2px 10px; border-radius: 4px; font-size: 0.8rem; border: 1px solid #e2e8f0; }
    .label-tag { background-color: #e0f2fe; color: #0369a1; padding: 2px 10px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'current_page' not in st.session_state: st.session_state.current_page = "📖 专项训练"
if 'current_q' not in st.session_state: st.session_state.current_q = None
if 'question_id' not in st.session_state: st.session_state.question_id = str(uuid.uuid4())
if 'answered' not in st.session_state: st.session_state.answered = False
if 'targets' not in st.session_state: st.session_state.targets = []

# --- 数据加载 ---
@st.cache_data
def load_data():
    try:
        with open("chinese_assets.json", "r", encoding="utf-8") as f: a = json.load(f)
        with open("chars_3500.json", "r", encoding="utf-8") as f: c = json.load(f)
        return a, c
    except: return {"content": []}, {"chars": []}

assets_db, chars_lib = load_data()

def format_text(text):
    if not text: return ""
    return text.replace("<u>", " **【").replace("</u>", "】** ").replace("（", " **（").replace("）", "）** ")

def main():
    if st.session_state.user is None: show_auth()
    else: app_body()

def show_auth():
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🕒 语文冲刺 v5.6</h2>", unsafe_allow_html=True)
        st.caption("<p style='text-align:center;'>全站时间已校准至北京时间 (CST)</p>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["🔑 登录", "📝 注册"])
        with t1:
            u = st.text_input("账号", key="l_u")
            p = st.text_input("密码", type="password", key="l_p")
            if st.button("进入系统"):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t2:
            ru = st.text_input("账号", key="r_u")
            rp = st.text_input("密码", type="password", key="r_p")
            rn = st.text_input("用户名", key="r_n")
            rc = st.text_input("班级", key="r_c")
            if st.button("注册账号"):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_body():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学", "class_name": "备考中"}
    with st.sidebar:
        st.markdown(f"### 👋 {profile['name']}")
        st.divider()
        pages = ["📖 专项训练", "🏰 社区广场", "📊 能力画像"]
        idx = pages.index(st.session_state.current_page) if st.session_state.current_page in pages else 0
        st.session_state.current_page = st.radio("导航", pages, index=idx)
        st.divider()
        st.session_state.targets = st.multiselect("锁定考点：", ["字音辨析", "字形纠错", "成语运用", "病句诊断", "3500字基础", "3500字进阶"], default=st.session_state.targets)
        if st.button("注销"): st.session_state.user = None; st.rerun()

    if st.session_state.current_page == "📖 专项训练": brush_page()
    elif st.session_state.current_page == "🏰 社区广场": community_page()
    else: dashboard_page()

def brush_page():
    st.header("精准考点冲刺")
    c1, c2 = st.columns([5, 1])
    with c2:
        if st.button("✨ 下一题", use_container_width=True) or st.session_state.current_q is None:
            refresh_q(st.session_state.targets)
            st.rerun()

    q = st.session_state.current_q
    if q and "error" not in q:
        st.markdown(f"<span class='source-tag'>来源：{q.get('source', '🤖 AI')}</span> <span class='label-tag'>标签：{q.get('category', '综合')}</span>", unsafe_allow_html=True)
        st.markdown(f"### {format_text(q['question'])}", unsafe_allow_html=True)
        ans = st.radio("选择：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {q['options'].get(x, '...')}", key=st.session_state.question_id, index=None, disabled=st.session_state.answered)
        
        if ans and not st.session_state.answered:
            st.session_state.answered = True
            time_spent = time.time() - st.session_state.start_time
            is_correct = (ans == q['answer'])
            log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q['question'], ans, is_correct, time_spent, q['analysis'])
            if is_correct: st.success("🎉 正确！"); st.balloons()
            else: st.error(f"❌ 错误。正确答案：{q['answer']}")

        if st.session_state.answered:
            st.info(f"💡 解析：{q['analysis']}")
            if st.button("👍 分享广场"):
                share_to_community(q, q.get('category', '综合'), st.session_state.user.id)
                st.toast("已同步")
            if st.button("挑战下一题 ➡️"): refresh_q(st.session_state.targets); st.rerun()

def refresh_q(targets):
    st.session_state.answered = False
    st.session_state.question_id = str(uuid.uuid4())
    st.session_state.start_time = time.time()
    target_focus = random.choice(targets) if targets else None
    with st.spinner("AI 出题中..."):
        if random.random() < 0.2:
            res = get_random_shared_question()
            if res: res["source"] = "🌟 社区精选"; st.session_state.current_q = res; return
        res = generate_ai_question(None, "precise", target_focus)
        res["source"] = "🤖 AI 命题"; st.session_state.current_q = res

def community_page():
    st.header("🏰 荣耀社区广场")
    t1, t2, t3 = st.tabs(["🏆 荣耀排行", "🌟 精选题库", "🚩 连斩错题"])
    with t1:
        data = get_leaderboard_data()
        if data:
            st.dataframe(pd.DataFrame(data).sort_values('correct_questions', ascending=False), use_container_width=True)
    with t2:
        for q in get_community_selected():
            with st.expander(f"【{q['category']}】 {q['question'][:30]}..."):
                st.markdown(f"⭐ {q.get('recommend_count', 1)} 人推荐")
                st.markdown(format_text(q['question']))
                if st.button("立即挑战", key=f"sq_{q['id']}"):
                    st.session_state.current_q = q; st.session_state.current_q["source"] = "🌟 社区精选"; st.session_state.current_page = "📖 专项训练"; st.rerun()
    with t3:
        for m in get_public_mistakes_with_kills():
            with st.container():
                kills = m.get('kill_count', 1)
                st.markdown(f"<span style='color:red; font-weight:bold;'>⚔️ 连斩 {kills} 人</span>", unsafe_allow_html=True)
                st.error(format_text(m['question']))
                if st.button("终结连斩", key=f"kill_{kills}_{random.random()}"):
                    st.session_state.current_q = m; st.session_state.current_q["source"] = "🚩 错题终结"; st.session_state.current_page = "📖 专项练习"; st.rerun()

def dashboard_page():
    st.header("📊 深度画像 v5.6")
    logs = get_user_all_logs(st.session_state.user.id)
    if not logs: st.info("暂无数据"); return
    
    df = pd.DataFrame(logs)
    # --- 核心：时区转换 ---
    df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Shanghai')
    df['date'] = df['created_at'].dt.date
    
    st.subheader("⏱️ 状态波动 (北京时间)")
    df['time_bin'] = df['created_at'].dt.floor('10min')
    bin_stats = df.groupby('time_bin')['is_correct'].mean().reset_index()
    bin_stats['is_correct'] *= 100
    st.plotly_chart(px.line(bin_stats, x='time_bin', y='is_correct', markers=True, title="10分钟颗粒度波动线 (CST)"), use_container_width=True)

    st.subheader("📅 每日复习时长 (北京时间)")
    usage_df = df.groupby('date')['time_spent'].sum().reset_index()
    usage_df['time_spent'] = (usage_df['time_spent'] / 60).round(1)
    st.table(usage_df.sort_values('date', ascending=False))

    st.divider()
    radar_df = df.groupby('category')['is_correct'].mean().reset_index()
    st.plotly_chart(px.line_polar(radar_df, r='is_correct', theta='category', line_close=True, title="综合能力罗盘"), use_container_width=True)

if __name__ == "__main__":
    main()
