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
    get_leaderboard_data, delete_shared_question_by_id
)
from ai_engine import generate_ai_question, sanitize_question, re_verify_question

# --- v6.0.1 修复版 ---
st.set_page_config(page_title="Zhongkao-Navigator v6.0.1", page_icon="🛡️", layout="wide")

BEIJING_TZ = timezone(timedelta(hours=8))

# --- UI 样式 ---
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .gold-medal { color: #d4af37; font-weight: bold; font-size: 1.25rem; }
    .admin-badge { background-color: #dc2626; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; }
    .disclaimer { font-size: 0.8rem; color: #64748b; text-align: center; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; background: white; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'current_page' not in st.session_state: st.session_state.current_page = "📖 专项训练"
if 'current_q' not in st.session_state: st.session_state.current_q = None
if 'question_id' not in st.session_state: st.session_state.question_id = str(uuid.uuid4())
if 'answered' not in st.session_state: st.session_state.answered = False
if 'targets' not in st.session_state: st.session_state.targets = []
if 'seen_q_ids' not in st.session_state: st.session_state.seen_q_ids = set()

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
        st.markdown("<h2 style='text-align:center;'>🛡️ 语文冲刺 v6.0</h2>", unsafe_allow_html=True)
        st.markdown("<div class='disclaimer'>⚠️ AI 可能存在错误，请大胆质疑！</div>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["🔑 登录", "📝 注册"])
        with t1:
            u = st.text_input("账号", key="l_u")
            p = st.text_input("密码", type="password", key="l_p")
            if st.button("进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t2:
            ru = st.text_input("设置账号", key="r_u")
            rp = st.text_input("设置密码", type="password", key="r_p")
            rn = st.text_input("用户名 (展示姓名)", key="r_n")
            rc = st.text_input("所在班级", key="r_c")
            if st.button("完成注册", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_body():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学", "class_name": "备考中"}
    is_admin = (profile['name'] == "ZhouMingen")
    
    with st.sidebar:
        st.markdown(f"### 👋 {profile['name']} " + ("<span class='admin-badge'>ADMIN</span>" if is_admin else ""), unsafe_allow_html=True)
        st.divider()
        pages = ["📖 专项训练", "🏰 社区广场", "📊 能力画像"]
        idx = pages.index(st.session_state.current_page) if st.session_state.current_page in pages else 0
        st.session_state.current_page = st.radio("导航", pages, index=idx)
        st.divider()
        st.session_state.targets = st.multiselect("锁定考点：", ["字音辨析", "字形纠错", "成语运用", "病句诊断", "3500字基础", "3500字进阶"], default=st.session_state.targets)
        if st.button("注销退出"): st.session_state.user = None; st.rerun()

    if st.session_state.current_page == "📖 专项训练": brush_page()
    elif st.session_state.current_page == "🏰 社区广场": community_page(is_admin)
    else: dashboard_page()

def brush_page():
    st.header("真理战线·专项练习")
    st.markdown("<div class='disclaimer'>AI 可能存在错误，请大胆质疑。</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([5, 1])
    with c2:
        if st.button("✨ 换一题", use_container_width=True) or st.session_state.current_q is None:
            refresh_q(st.session_state.targets)
            st.rerun()
    q = st.session_state.current_q
    if q and "error" not in q:
        st.markdown(f"**分类**：{q.get('category', '综合')}")
        st.markdown(f"### {format_text(q['question'])}", unsafe_allow_html=True)
        ans = st.radio("你的回答：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {q['options'].get(x, '...')}", key=st.session_state.question_id, index=None, disabled=st.session_state.answered)
        if ans and not st.session_state.answered:
            st.session_state.answered = True
            is_correct = (ans == q['answer'])
            log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q['question'], ans, is_correct, time.time() - st.session_state.start_time, q['analysis'])
            if is_correct: st.success("🎉 正确！"); st.balloons()
            else: st.error(f"❌ 错误。答案：{q['answer']}")
        if st.session_state.answered:
            st.info(f"💡 AI 解析：{q['analysis']}")
            c1, c2, c3 = st.columns([2, 2, 4])
            with c1:
                if st.button("👍 分享好题"): share_to_community(q, q.get('category', '综合'), st.session_state.user.id); st.toast("已同步")
            with c2:
                if st.button("🚩 质疑题目"):
                    with st.spinner("自查中..."):
                        review = re_verify_question(q)
                        st.warning(review)
                        if "【AI 已认错】" in review and 'id' in q: delete_shared_question_by_id(q['id'])
            with c3:
                if st.button("下一题 ➡️", use_container_width=True): refresh_q(st.session_state.targets); st.rerun()

def refresh_q(targets):
    st.session_state.answered = False
    st.session_state.question_id = str(uuid.uuid4())
    st.session_state.start_time = time.time()
    with st.spinner("出题中..."):
        if random.random() < 0.2:
            q = get_random_shared_question()
            if q and q.get('id') not in st.session_state.seen_q_ids:
                st.session_state.seen_q_ids.add(q.get('id')); st.session_state.current_q = q; return
        target_focus = random.choice(targets) if targets else None
        st.session_state.current_q = generate_ai_question(None, "precise", target_focus)

def community_page(is_admin):
    st.header("🏰 荣耀社区广场")
    t1, t2, t3 = st.tabs(["🏆 荣耀金榜", "🌟 精选题库", "🚩 连斩错题"])
    with t1:
        data = get_leaderboard_data()
        if data:
            df = pd.DataFrame(data)
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("#### 🔥 勤奋榜")
                top = df.sort_values('total_questions', ascending=False).head(10).reset_index()
                for i, r in top.iterrows():
                    st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['total_questions']}题", unsafe_allow_html=True)
            with c2:
                st.markdown("#### ⚔️ 战神榜")
                top = df.sort_values('correct_questions', ascending=False).head(10).reset_index()
                for i, r in top.iterrows():
                    st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['correct_questions']}对", unsafe_allow_html=True)
            with c3:
                st.markdown("#### 💡 贡献榜")
                top = df.sort_values('contributions', ascending=False).head(10).reset_index()
                for i, r in top.iterrows():
                    st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['contributions']}次", unsafe_allow_html=True)
    with t2:
        for q in get_community_selected():
            with st.expander(f"【{q['category']}】 {q['question'][:30]}..."):
                st.markdown(f"⭐ {q.get('recommend_count', 1)} 人推荐")
                cols = st.columns([1, 1, 4])
                if cols[0].button("挑战", key=f"sq_{q['id']}"):
                    st.session_state.current_q = q; st.session_state.current_page = "📖 专项训练"; st.rerun()
                if is_admin:
                    if cols[1].button("🗑️ 删除", key=f"del_sq_{q['id']}"):
                        if delete_shared_question_by_id(q['id']): st.toast("已删除"); st.rerun()
    with t3:
        for m in get_public_mistakes_with_kills():
            kills = m.get('kill_count', 1)
            st.error(f"⚔️ 连斩 {kills} 人 | {format_text(m['question'])}")
            if st.button("终结连斩", key=f"kill_{kills}_{random.random()}"):
                st.session_state.current_q = m; st.session_state.current_page = "📖 专项训练"; st.rerun()

def dashboard_page():
    st.header("📊 能力画像")
    logs = get_user_all_logs(st.session_state.user.id)
    if logs:
        df = pd.DataFrame(logs)
        df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Shanghai')
        st.plotly_chart(px.line(df.groupby(df['created_at'].dt.floor('10min'))['is_correct'].mean().reset_index(), x='created_at', y='is_correct', title="状态波动图"), use_container_width=True)
    else: st.info("暂无数据")

if __name__ == "__main__":
    main()
