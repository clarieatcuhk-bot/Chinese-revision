import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import time
import random
import json
import re
from datetime import datetime
from database import (
    sign_in, sign_up_and_login, get_profile, log_quiz_result, 
    get_user_all_logs, share_to_community, get_community_selected, 
    get_public_mistakes, get_random_shared_question, get_leaderboard_data
)
from ai_engine import generate_ai_question, sanitize_question

# --- v3.9.1 稳定性补丁版 ---
st.set_page_config(page_title="Zhongkao-Navigator v3.9.1", page_icon="🎯", layout="wide")

# --- 素材加载 (全局变量) ---
@st.cache_data
def load_all_data():
    try:
        with open("chinese_assets.json", "r", encoding="utf-8") as f: a = json.load(f)
        with open("chars_3500.json", "r", encoding="utf-8") as f: c = json.load(f)
        return a, c
    except:
        return {"content": []}, {"chars": []}

# 明确初始化全局变量
assets_db, chars_lib = load_all_data()

# --- 增强渲染逻辑 ---
def format_display_text(text):
    if not text: return ""
    text = text.replace("<u>", " **【").replace("</u>", "】** ")
    text = text.replace("（", " **（").replace("）", "）** ")
    return text

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'current_page' not in st.session_state: st.session_state.current_page = "📖 专项练习"
if 'current_q' not in st.session_state: st.session_state.current_q = None
if 'question_id' not in st.session_state: st.session_state.question_id = str(uuid.uuid4())
if 'answered' not in st.session_state: st.session_state.answered = False

def main():
    if st.session_state.user is None: show_auth()
    else: app_body()

def show_auth():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🛡️ 语文冲刺·荣耀版</h2>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["🔑 登录", "📝 注册"])
        with t1:
            u = st.text_input("用户名", key="l_u")
            p = st.text_input("密码", type="password", key="l_p")
            if st.button("进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t2:
            ru = st.text_input("用户名", key="r_u")
            rp = st.text_input("密码", type="password", key="r_p")
            rn = st.text_input("姓名", key="r_n")
            rc = st.text_input("班级", key="r_c")
            if st.button("立即开通", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_body():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学", "class_name": "备考中"}
    
    with st.sidebar:
        st.title(f"👋 {profile['name']}")
        st.divider()
        pages = ["📖 专项练习", "🏰 社区广场", "📊 深度画像"]
        idx = pages.index(st.session_state.current_page) if st.session_state.current_page in pages else 0
        page = st.radio("功能导航", pages, index=idx)
        st.session_state.current_page = page
        if st.button("注销退出"): st.session_state.user = None; st.rerun()

    if st.session_state.current_page == "📖 专项练习": brush_page()
    elif st.session_state.current_page == "🏰 社区广场": community_page()
    else: dashboard_page()

def brush_page():
    st.header("考点精准挑战")
    targets = st.multiselect("🎯 锁定范围：", ["字音辨析", "字形纠错", "成语运用", "病句诊断", "3500字基础", "3500字进阶"])
    c1, c2 = st.columns([4, 1])
    with c2:
        if st.button("✨ 换一题", use_container_width=True) or st.session_state.current_q is None:
            refresh_q(targets)
            st.rerun()

    q = st.session_state.current_q
    if q and "error" not in q:
        # --- 修复：防御性检查核心字段 ---
        if 'question' not in q:
            st.warning("⚠️ 题目加载异常（字段缺失），请尝试重新生成。")
            if st.button("🔄 重新命题"):
                refresh_q([])
                st.rerun()
            return
            
        q_text = format_display_text(q['question'])
        st.markdown(f"### {q_text}", unsafe_allow_html=True)
        ans = st.radio("你的答案：", ["A", "B", "C", "D"], 
                       format_func=lambda x: f"{x}. {q['options'].get(x, '...')}", 
                       key=st.session_state.question_id, index=None, disabled=st.session_state.answered)
        
        if ans and not st.session_state.answered:
            st.session_state.answered = True
            is_correct = (ans == q['answer'])
            log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q['question'], ans, is_correct, 0, q['analysis'])
            if is_correct: st.success("🎉 正确！"); st.balloons()
            else: st.error(f"❌ 错误。答案是：{q['answer']}")

        if st.session_state.answered:
            st.info(f"💡 解析：{q['analysis']}")
            if st.button("👍 分享到广场"):
                share_to_community(q, q.get('category', '综合'), st.session_state.user.id)
                st.toast("分享成功！")
            if st.button("继续刷题 ➡️"): refresh_q(targets); st.rerun()

def refresh_q(targets):
    st.session_state.answered = False
    st.session_state.question_id = str(uuid.uuid4())
    st.session_state.start_time = time.time()
    with st.spinner("AI 出题中..."):
        if random.random() < 0.2:
            res = get_random_shared_question()
            if res: res["from_community"] = True; st.session_state.current_q = res; return
        
        # 使用全局变量 assets_db
        pool = assets_db.get('content', [])
        items = random.sample(pool, 2) if pool else None
        res = generate_ai_question(items, "precise")
        st.session_state.current_q = res

def community_page():
    st.header("🏰 社区共享广场")
    t1, t2, t3 = st.tabs(["📊 荣誉排行榜", "🌟 精选题库", "🚩 全站错题流"])
    with t1:
        data = get_leaderboard_data()
        if data:
            ldf = pd.DataFrame(data).sort_values('correct_questions', ascending=False)
            st.dataframe(ldf[['name', 'class_name', 'correct_questions', 'total_questions', 'contributions']], use_container_width=True)
    with t2:
        for q in get_community_selected():
            with st.expander(f"【{q['category']}】 {q['question'][:30]}..."):
                st.markdown(format_display_text(q['question']))
                if st.button(f"立即挑战", key=f"q_{q['id']}"):
                    st.session_state.current_q = q
                    st.session_state.answered = False
                    st.session_state.current_page = "📖 专项练习"
                    st.rerun()
    with t3:
        for m in get_public_mistakes():
            st.error(f"**[{m['category']}]** {format_display_text(m['question'])}")

def dashboard_page():
    st.header("📊 深度能力画像")
    logs = get_user_all_logs(st.session_state.user.id)
    if logs:
        df = pd.DataFrame(logs)
        radar_df = df.groupby('category')['is_correct'].mean().reset_index()
        fig = px.line_polar(radar_df, r='is_correct', theta='category', line_close=True)
        st.plotly_chart(fig, use_container_width=True)
    else: st.info("暂无数据")

if __name__ == "__main__":
    main()
