import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import time
import random
import json
from datetime import datetime
from database import (
    sign_in, sign_up_and_login, get_profile, log_quiz_result, 
    get_user_all_logs, share_to_community, get_community_selected, 
    get_public_mistakes_with_kills, get_random_shared_question, get_leaderboard_data
)
from ai_engine import generate_ai_question, sanitize_question

# --- v5.0 DeepSeek V4 & 五维之王荣耀版 ---
st.set_page_config(page_title="Zhongkao Navigator v5.0", page_icon="💎", layout="wide")

# --- UI 样式 (高贵紫+金) ---
st.markdown("""
<style>
    .main { background-color: #fcfaff; }
    .gold-medal { color: #d4af37; font-weight: bold; font-size: 1.25rem; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); }
    .standard-name { color: #4b5563; font-weight: 500; }
    .king-card { background: linear-gradient(135deg, #6d28d9 0%, #4c1d95 100%); color: white; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .badge { background-color: #6d28d9; color: white; padding: 3px 12px; border-radius: 50px; font-size: 0.85rem; }
    .kill-streak { color: #dc2626; font-weight: bold; background: #fee2e2; padding: 2px 8px; border-radius: 4px; }
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
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>💎 语文冲刺 v5.0</h2>", unsafe_allow_html=True)
        st.caption("<p style='text-align:center;'>DeepSeek V4 超强算力支持</p>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["🔑 登录", "📝 注册"])
        with t1:
            u = st.text_input("账号", key="l_u") # 改为账号
            p = st.text_input("密码", type="password", key="l_p")
            if st.button("立即进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t2:
            ru = st.text_input("账号 (用于登录)", key="r_u") # 改为账号
            rp = st.text_input("设置密码", type="password", key="r_p")
            rn = st.text_input("用户名 (展示姓名)", key="r_n") # 改为用户名
            rc = st.text_input("所在班级", key="r_c")
            if st.button("完成账号注册", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_body():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新用户", "class_name": "备考中"}
    
    with st.sidebar:
        st.markdown(f"### 🛡️ {profile['name']}")
        st.caption(f"班级：{profile['class_name']}")
        st.divider()
        pages = ["📖 专项训练", "🏰 社区广场", "📊 能力画像"]
        idx = pages.index(st.session_state.current_page) if st.session_state.current_page in pages else 0
        st.session_state.current_page = st.radio("系统导航", pages, index=idx)
        st.divider()
        st.markdown("🎯 **锁定考点：**")
        st.session_state.targets = st.multiselect("多选：", ["字音辨析", "成语运用", "病句诊断", "3500字基础", "3500字进阶"], default=st.session_state.targets)
        if st.button("退出注销"): st.session_state.user = None; st.rerun()

    if st.session_state.current_page == "📖 专项训练": brush_page()
    elif st.session_state.current_page == "🏰 社区广场": community_page()
    else: dashboard_page()

def brush_page():
    st.header("DeepSeek V4 精准命题")
    c1, c2 = st.columns([5, 1])
    with c2:
        if st.button("✨ 下一题", use_container_width=True) or st.session_state.current_q is None:
            refresh_q(st.session_state.targets)
            st.rerun()

    q = st.session_state.current_q
    if q and "error" not in q:
        st.markdown(f"<span class='badge'>{q.get('category', '综合')}</span>", unsafe_allow_html=True)
        st.markdown(f"### {format_text(q['question'])}", unsafe_allow_html=True)
        ans = st.radio("选择你的答案：", ["A", "B", "C", "D"], 
                       format_func=lambda x: f"{x}. {q['options'].get(x, '...')}", 
                       key=st.session_state.question_id, index=None, disabled=st.session_state.answered)
        
        if ans and not st.session_state.answered:
            st.session_state.answered = True
            time_spent = time.time() - st.session_state.start_time
            is_correct = (ans == q['answer'])
            log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q['question'], ans, is_correct, time_spent, q['analysis'])
            if is_correct: st.success("🎉 正确！"); st.balloons()
            else: st.error(f"❌ 错误。答案是：{q['answer']}")

        if st.session_state.answered:
            st.info(f"💡 **V4 解析**：{q['analysis']}")
            if st.button("👍 分享到社区广场"):
                share_to_community(q, q.get('category', '综合'), st.session_state.user.id)
                st.toast("贡献成功！")
            if st.button("继续刷题 ➡️"):
                refresh_q(st.session_state.targets)
                st.rerun()

def refresh_q(targets):
    st.session_state.answered = False
    st.session_state.question_id = str(uuid.uuid4())
    st.session_state.start_time = time.time()
    target_focus = random.choice(targets) if targets else None
    with st.spinner("DeepSeek V4 正在为你命题..."):
        if random.random() < 0.2:
            res = get_random_shared_question()
            if res: res["from_community"] = True; st.session_state.current_q = res; return
        if target_focus == "病句诊断": res = generate_ai_question(None, "grammar", "病句")
        elif target_focus and "3500字" in target_focus:
            pool = chars_lib.get('chars', [])
            res = generate_ai_question(random.choice(pool), "discovery", "字词扩展")
        else:
            pool = assets_db.get('content', [])
            res = generate_ai_question(random.sample(pool, 2) if pool else None, "precise", target_focus)
        st.session_state.current_q = res

# --- 🏰 社区广场 & 🏆 五维之王排行榜 ---
def community_page():
    st.header("🏰 荣耀社区广场")
    t1, t2, t3 = st.tabs(["🏆 荣耀五维榜", "🌟 精选题库", "🚩 连斩错题流"])
    
    with t1:
        data = get_leaderboard_data()
        if data:
            df = pd.DataFrame(data)
            df['accuracy'] = (df['correct_questions'] / df['total_questions'].replace(0, 1) * 100).round(1)
            df['time_mins'] = (df['total_time'] / 60).round(1)
            
            st.markdown("### 🏆 荣耀之王展示墙")
            c1, c2, c3, c4, c5 = st.columns(5)
            # 勤奋王
            with c1:
                top = df.sort_values('total_questions', ascending=False).iloc[0]
                st.markdown(f"<div class='king-card'>🔥 勤奋之王<br><b>{top['name']}</b><br>{top['total_questions']}题</div>", unsafe_allow_html=True)
            # 准确率王 (过滤题量过低的用户)
            with c2:
                qualified = df[df['total_questions'] >= 10]
                if not qualified.empty:
                    top = qualified.sort_values('accuracy', ascending=False).iloc[0]
                    st.markdown(f"<div class='king-card'>🏅 准确率王<br><b>{top['name']}</b><br>{top['accuracy']}%</div>", unsafe_allow_html=True)
                else: st.markdown("<div class='king-card'>🏅 准确率王<br>虚位以待</div>", unsafe_allow_html=True)
            # 时长王
            with c3:
                top = df.sort_values('total_time', ascending=False).iloc[0]
                st.markdown(f"<div class='king-card'>⏳ 专注之王<br><b>{top['name']}</b><br>{top['time_mins']}min</div>", unsafe_allow_html=True)
            # 战神王
            with c4:
                top = df.sort_values('correct_questions', ascending=False).iloc[0]
                st.markdown(f"<div class='king-card'>⚔️ 战神之王<br><b>{top['name']}</b><br>{top['correct_questions']}对</div>", unsafe_allow_html=True)
            # 贡献王
            with c5:
                top = df.sort_values('contributions', ascending=False).iloc[0]
                st.markdown(f"<div class='king-card'>💡 共享之王<br><b>{top['name']}</b><br>{top['contributions']}贡献</div>", unsafe_allow_html=True)

            st.divider()
            st.markdown("#### 📜 全站精英榜")
            # 综合展示榜单
            for i, row in df.sort_values('correct_questions', ascending=False).head(10).reset_index().iterrows():
                name_style = "gold-medal" if i == 0 else "standard-name"
                st.markdown(f"{i+1}. <span class='{name_style}'>{row['name']}</span> ({row['class_name']}) - 累计正确 {row['correct_questions']} 题", unsafe_allow_html=True)

    with t2:
        for q in get_community_selected():
            with st.expander(f"【{q['category']}】 {q['question'][:30]}..."):
                count = q.get('recommend_count', 1)
                st.markdown(f"⭐ {count} 人诚心推荐")
                st.markdown(format_text(q['question']))
                if st.button("立即挑战", key=f"sq_{q['id']}"):
                    st.session_state.current_q = q; st.session_state.current_page = "📖 专项练习"; st.rerun()

    with t3:
        for m in get_public_mistakes_with_kills():
            with st.container():
                kills = m.get('kill_count', 1)
                st.markdown(f"<span class='kill-streak'>⚔️ 连斩 {kills} 人</span>", unsafe_allow_html=True)
                st.error(f"**[{m['category']}]** {format_text(m['question'])}")

def dashboard_page():
    st.header("📊 深度能力画像")
    logs = get_user_all_logs(st.session_state.user.id)
    if logs:
        df = pd.DataFrame(logs)
        df['created_at'] = pd.to_datetime(df['created_at'])
        df['date'] = df['created_at'].dt.date
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df.groupby('category')['is_correct'].mean().reset_index(), x='category', y='is_correct', title="各板块正确率"), use_container_width=True)
        with c2: st.plotly_chart(px.line(df.groupby('date')['is_correct'].mean().reset_index(), x='date', y='is_correct', title="每日进度"), use_container_width=True)
    else: st.info("暂无数据")

if __name__ == "__main__":
    main()
