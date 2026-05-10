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
    get_public_mistakes, get_random_shared_question, get_leaderboard_data
)
from ai_engine import generate_ai_question, sanitize_question

# --- v3.8 荣耀社区版配置 ---
st.set_page_config(page_title="Zhongkao-Navigator Hall of Fame", page_icon="🏆", layout="wide")

# --- 样式设计 ---
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .leaderboard-table { background-color: white; border-radius: 12px; padding: 10px; }
    .metric-card { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); border-top: 3px solid #1e3a8a; }
    .badge-gold { color: #f59e0b; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'current_q' not in st.session_state: st.session_state.current_q = None
if 'question_id' not in st.session_state: st.session_state.question_id = str(uuid.uuid4())
if 'answered' not in st.session_state: st.session_state.answered = False

# --- 加载资产 ---
@st.cache_data
def load_assets():
    try:
        with open("chinese_assets.json", "r", encoding="utf-8") as f: assets = json.load(f)
        with open("chars_3500.json", "r", encoding="utf-8") as f: chars = json.load(f)
        return assets, chars
    except: return {"content": []}, {"chars": []}

assets_db, chars_lib = load_assets()

def main():
    if st.session_state.user is None: show_auth()
    else: app_body()

def show_auth():
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🛡️ 语文冲刺·荣耀版</h2>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["🔑 登录", "📝 注册"])
        with t1:
            u = st.text_input("用户名", key="l_u")
            p = st.text_input("密码", type="password", key="l_p")
            if st.button("立即进入"):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t2:
            ru = st.text_input("用户名", key="r_u")
            rp = st.text_input("密码", type="password", key="r_p")
            rn = st.text_input("姓名", key="r_n")
            rc = st.text_input("班级", key="r_c")
            if st.button("完成注册"):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_body():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学", "class_name": "备考中"}
    
    with st.sidebar:
        st.title(f"👋 {profile['name']}")
        st.caption(f"班级：{profile['class_name']}")
        st.divider()
        page = st.radio("导航菜单", ["📖 专项练习", "🏰 社区广场", "📊 深度画像"])
        if st.button("退出系统"): st.session_state.user = None; st.rerun()

    if page == "📖 专项练习": brush_page()
    elif page == "🏰 社区广场": community_page()
    else: dashboard_page()

def brush_page():
    st.header("精准考点冲刺")
    targets = st.multiselect("🎯 锁定考点：", ["字音辨析", "字形纠错", "成语运用", "病句诊断", "3500字基础", "3500字进阶"])
    c1, c2 = st.columns([4, 1])
    with c2:
        if st.button("✨ 生成新题", use_container_width=True) or st.session_state.current_q is None:
            refresh_q(targets)
            st.rerun()

    q = st.session_state.current_q
    if q and "error" not in q:
        st.markdown(f"### {q['question']}", unsafe_allow_html=True)
        ans = st.radio("你的选择：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {q['options'].get(x, '...')}", key=st.session_state.question_id, index=None, disabled=st.session_state.answered)
        
        if ans and not st.session_state.answered:
            st.session_state.answered = True
            time_spent = time.time() - st.session_state.start_time
            is_correct = (ans == q['answer'])
            log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q['question'], ans, is_correct, time_spent, q['analysis'])
            if is_correct: st.success("🎉 正确！"); st.balloons()
            else: st.error(f"❌ 错误。正确答案：{q['answer']}")

        if st.session_state.answered:
            st.info(f"💡 解析：{q['analysis']}")
            if st.button("👍 分享给他人 (贡献+1)"):
                if share_to_community(q, q.get('category', '综合'), st.session_state.user.id):
                    st.toast("贡献成功！可在排行榜查看。")
            if st.button("继续刷题 ➡️"): refresh_q(targets); st.rerun()

def refresh_q(targets):
    st.session_state.answered = False
    st.session_state.question_id = str(uuid.uuid4())
    st.session_state.start_time = time.time()
    with st.spinner("AI 正在命题..."):
        # 混合抽题逻辑
        if random.random() < 0.2:
            res = get_random_shared_question()
            if res: res["from_community"] = True; st.session_state.current_q = res; return
        # AI 命题逻辑 (简化示例)
        target = random.choice(targets) if targets else "综合"
        res = generate_ai_question(random.sample(assets_db.get('content', []), 2), "precise")
        st.session_state.current_q = res

def community_page():
    st.header("🏰 社区广场 & 🏆 荣耀榜")
    t1, t2, t3 = st.tabs(["📊 荣耀排行榜", "🌟 精选题库", "🚩 全站错题流"])
    
    with t1:
        data = get_leaderboard_data()
        if not data:
            st.info("排行榜正在计算中，快去刷题抢占席位吧！")
        else:
            ldf = pd.DataFrame(data)
            # 计算正确率
            ldf['accuracy'] = (ldf['correct_questions'] / ldf['total_questions'].replace(0, 1) * 100).round(1)
            # 转换时间为分钟
            ldf['time_mins'] = (ldf['total_time'] / 60).round(1)
            
            sub_t1, sub_t2, sub_t3, sub_t4 = st.tabs(["🎯 准确率榜", "🔥 勤奋榜", "💡 贡献榜", "⏳ 时长榜"])
            with sub_t1:
                st.dataframe(ldf[['name', 'class_name', 'accuracy', 'correct_questions']].sort_values('accuracy', ascending=False).head(10), use_container_width=True)
            with sub_t2:
                st.dataframe(ldf[['name', 'class_name', 'total_questions']].sort_values('total_questions', ascending=False).head(10), use_container_width=True)
            with sub_t3:
                st.dataframe(ldf[['name', 'class_name', 'contributions']].sort_values('contributions', ascending=False).head(10), use_container_width=True)
            with sub_t4:
                st.dataframe(ldf[['name', 'class_name', 'time_mins']].sort_values('time_mins', ascending=False).head(10), use_container_width=True)

    with t2:
        for q in get_community_selected():
            st.markdown(f"**[{q['category']}]** {q['question']} (赞:{q['likes_count']})")
    with t3:
        for m in get_public_mistakes():
            st.error(f"**[{m['category']}]** {m['question']}")

def dashboard_page():
    st.header("📊 深度能力画像")
    logs = get_user_all_logs(st.session_state.user.id)
    if logs:
        df = pd.DataFrame(logs)
        st.plotly_chart(px.line_polar(df.groupby('category')['is_correct'].mean().reset_index(), r='is_correct', theta='category', line_close=True))
    else: st.info("暂无数据")

if __name__ == "__main__":
    main()
