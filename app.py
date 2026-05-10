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
    get_leaderboard_data, delete_shared_question_by_id, record_challenge,
    delete_all_logs_of_question
)
from ai_engine import generate_ai_question, sanitize_question, re_verify_question

# --- v7.0 权限锁死与广场分类版 ---
st.set_page_config(page_title="Zhongkao-Navigator Pro v7.0", page_icon="🛡️", layout="wide")

BEIJING_TZ = timezone(timedelta(hours=8))

# --- UI 样式 ---
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .gold-medal { color: #d4af37 !important; font-weight: bold !important; font-size: 1.2rem; }
    .admin-badge { background-color: #dc2626; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
    .cat-header { background: #e2e8f0; padding: 5px 15px; border-radius: 5px; margin-top: 20px; font-weight: bold; color: #1e3a8a; }
    .kill-streak { color: #ef4444; font-weight: bold; background: #fef2f2; padding: 5px 12px; border-radius: 6px; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'current_page' not in st.session_state: st.session_state.current_page = "🏰 社区广场" # 默认改为广场
if 'current_q' not in st.session_state: st.session_state.current_q = None
if 'question_id' not in st.session_state: st.session_state.question_id = str(uuid.uuid4())
if 'answered' not in st.session_state: st.session_state.answered = False
if 'targets' not in st.session_state: st.session_state.targets = []
if 'seen_q_ids' not in st.session_state: st.session_state.seen_q_ids = set()

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
        st.markdown("<h2 style='text-align:center;'>🛡️ 语文冲刺 Pro v7.0</h2>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["🔑 登录", "📝 注册"])
        with t1:
            u = st.text_input("账号", key="l_u")
            p = st.text_input("密码", type="password", key="l_p")
            if st.button("进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t2:
            ru = st.text_input("设置账号", key="r_u")
            rp = st.text_input("密码", type="password", key="r_p")
            rn = st.text_input("用户名", key="r_n")
            rc = st.text_input("班级", key="r_c")
            if st.button("完成注册", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_body():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学", "class_name": "备考中"}
    
    # --- v7.0 管理员判定 (ZhouMingen + hongyi1-100) ---
    account = user.email.split('@')[0].lower()
    is_hongyi = account.startswith('hongyi') and account[6:].isdigit() and 1 <= int(account[6:]) <= 100
    is_admin = (account == "zhoumingen" or is_hongyi)
    
    with st.sidebar:
        st.markdown(f"### 👋 {profile['name']} " + ("<span class='admin-badge'>ADMIN</span>" if is_admin else ""), unsafe_allow_html=True)
        st.caption(f"账号：{account}")
        st.divider()
        
        # 权限过滤：非管理员不能进入专项训练
        if is_admin:
            pages = ["📖 专项训练", "🏰 社区广场", "📊 能力画像"]
        else:
            pages = ["🏰 社区广场", "📊 能力画像"]
            if st.session_state.current_page == "📖 专项训练": st.session_state.current_page = "🏰 社区广场"
            
        st.session_state.current_page = st.radio("导航控制", pages)
        st.divider()
        if is_admin:
            st.session_state.targets = st.multiselect("锁定考点(管理员)：", ["字音辨析", "字形纠错", "成语运用", "病句诊断", "3500字基础", "3500字进阶"], default=st.session_state.targets)
        if st.button("退出系统"): st.session_state.user = None; st.rerun()

    if st.session_state.current_page == "📖 专项训练": brush_page(is_admin)
    elif st.session_state.current_page == "🏰 社区广场": community_page(is_admin)
    else: dashboard_page()

def brush_page(is_admin):
    st.header("管理员命题实验室")
    if st.session_state.current_q is None: refresh_q(st.session_state.targets)
    c1, c2 = st.columns([5, 1])
    with c2:
        if st.button("✨ 换一题", use_container_width=True): refresh_q(st.session_state.targets); st.rerun()
    q = st.session_state.current_q
    if q and "error" not in q:
        st.markdown(f"**考点**：{q.get('category', '综合')}")
        st.markdown(f"### {format_text(q['question'])}", unsafe_allow_html=True)
        opts = q.get('options', {})
        ans = st.radio("选择：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {opts.get(x, '...')}", key=st.session_state.question_id, index=None, disabled=st.session_state.answered)
        if ans and not st.session_state.answered:
            st.session_state.answered = True
            is_correct = (ans == q['answer'])
            log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q, ans, is_correct, time.time() - st.session_state.start_time)
            if is_correct: st.success("🎉 正确！"); st.balloons()
            else: st.error(f"❌ 错误。答案：{q['answer']}")
        if st.session_state.answered:
            st.info(f"💡 AI 解析：{q['analysis']}")
            c1, c2 = st.columns(2)
            if c1.button("👍 分享到广场"): share_to_community(q, q.get('category', '综合'), st.session_state.user.id); st.toast("已同步")
            if c2.button("下一题 ➡️"): refresh_q(st.session_state.targets); st.rerun()

def refresh_q(targets):
    st.session_state.answered = False
    st.session_state.question_id = str(uuid.uuid4())
    st.session_state.start_time = time.time()
    st.session_state.current_q = generate_ai_question(None, "precise", random.choice(targets) if targets else None)

def community_page(is_admin):
    st.header("🏰 社区荣耀广场")
    t1, t2, t3 = st.tabs(["🏆 七维荣耀金榜", "🌟 知识点精选题库", "🚩 全站连斩错题流"])
    
    with t1:
        data = get_leaderboard_data()
        if data:
            df = pd.DataFrame(data)
            df['avg_speed'] = (df['total_time'] / df['total_questions'].replace(0, 1)).round(1)
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("#### 🔥 刷题王者")
                top = df.sort_values('total_questions', ascending=False).head(5).reset_index()
                for i, r in top.iterrows(): st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['total_questions']}题", unsafe_allow_html=True)
            with c2:
                st.markdown("#### ⚔️ 战神榜")
                top = df.sort_values('correct_questions', ascending=False).head(5).reset_index()
                for i, r in top.iterrows(): st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['correct_questions']}对", unsafe_allow_html=True)
            with c3:
                st.markdown("#### ⏳ 专注榜")
                top = df.sort_values('total_time', ascending=False).head(5).reset_index()
                for i, r in top.iterrows(): st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {(r['total_time']/60):.1f}min", unsafe_allow_html=True)
            st.divider()
            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            with r2c1:
                st.markdown("#### ⚡ 闪电王")
                top = df[df['total_questions'] >= 10].sort_values('avg_speed', ascending=True).head(5).reset_index()
                for i, r in top.iterrows(): st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['avg_speed']}s", unsafe_allow_html=True)
            with r2c2:
                st.markdown("#### 💡 贡献王")
                top = df.sort_values('contributions', ascending=False).head(5).reset_index()
                for i, r in top.iterrows(): st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['contributions']}次", unsafe_allow_html=True)
            with r2c3:
                st.markdown("#### 🚩 质疑王")
                top = df.sort_values('challenge_count', ascending=False).head(5).reset_index()
                for i, r in top.iterrows(): st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['challenge_count']}次", unsafe_allow_html=True)
            with r2c4:
                st.markdown("#### 🏆 判官王")
                top = df.sort_values('challenge_success_count', ascending=False).head(5).reset_index()
                for i, r in top.iterrows(): st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['challenge_success_count']}次", unsafe_allow_html=True)

    with t2:
        qs = get_community_selected()
        if qs:
            # --- v7.0 广场分类展示 ---
            categories = ["字音辨析", "字形纠错", "成语运用", "病句诊断", "3500字基础", "3500字进阶", "综合"]
            for cat in categories:
                cat_qs = [q for q in qs if q['category'] == cat or (cat == "综合" and q['category'] not in categories)]
                if cat_qs:
                    st.markdown(f"<div class='cat-header'>📌 {cat}</div>", unsafe_allow_html=True)
                    for q in cat_qs:
                        with st.expander(f"⭐ {q.get('recommend_count', 1)}人推荐 | {q['question'][:40]}..."):
                            st.markdown(format_text(q['question']))
                            c1, c2 = st.columns([1, 4])
                            if c1.button("挑战", key=f"sq_{q['id']}"):
                                st.session_state.current_q = q; st.session_state.current_page = "🏰 社区广场练习"; st.rerun() # 特殊处理，下文补充
                            if is_admin:
                                if st.button("🗑️ 删除", key=f"del_sq_{q['id']}"):
                                    if delete_shared_question_by_id(q['id']): st.toast("已下架"); st.rerun()
        else: st.info("题库虚位以待")

    with t3:
        for m in get_public_mistakes_with_kills():
            kills = m.get('kill_count', 1)
            with st.container():
                st.markdown(f"<span class='kill-streak'>⚔️ 已连斩 {kills} 人</span>", unsafe_allow_html=True)
                st.error(f"{format_text(m['question'])}")
                c1, c2 = st.columns([2, 5])
                if c1.button("挑战终结", key=f"km_{kills}_{random.random()}"):
                    st.session_state.current_q = m; st.session_state.current_page = "🏰 社区广场练习"; st.rerun()
                if is_admin:
                    if st.button("🗑️ 强制清除", key=f"del_km_{kills}_{random.random()}"):
                        if delete_all_logs_of_question(m['question']): st.toast("已下架"); st.rerun()

    # 处理从广场发起的挑战 UI
    if st.session_state.current_page == "🏰 社区广场练习":
        st.divider()
        st.subheader("🎯 正在挑战社区题目")
        q = st.session_state.current_q
        if q:
            st.markdown(f"### {format_text(q['question'])}", unsafe_allow_html=True)
            ans = st.radio("你的回答：", ["A", "B", "C", "D"], key="comm_q", index=None)
            if ans:
                is_correct = (ans == q['answer'])
                log_quiz_result(st.session_state.user.id, q['category'], q, ans, is_correct, 5.0)
                if is_correct: st.success("🎉 正确！"); st.balloons()
                else: st.error(f"❌ 错误。答案：{q['answer']}")
                st.info(f"💡 解析：{q['analysis']}")
                if st.button("返回广场"): st.session_state.current_page = "🏰 社区广场"; st.rerun()

def dashboard_page():
    st.header("📊 深度能力全景画像")
    logs = get_user_all_logs(st.session_state.user.id)
    if not logs: st.info("暂无数据"); return
    df = pd.DataFrame(logs)
    df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Shanghai')
    
    st.subheader("⏱️ 10 分钟状态波动图")
    df['time_bin'] = df['created_at'].dt.floor('10min')
    bin_stats = df.groupby('time_bin')['is_correct'].mean().reset_index()
    bin_stats['is_correct'] *= 100
    st.plotly_chart(px.line(bin_stats, x='time_bin', y='is_correct', markers=True), use_container_width=True)

    st.subheader("🏹 五轴核心能力罗盘")
    fixed_axes = ["字音辨析", "成语运用", "病句诊断", "字形纠错", "3500字基础"]
    stats = df.groupby('category')['is_correct'].mean().to_dict()
    radar_values = [stats.get(ax, 0) * 100 for ax in fixed_axes]
    st.plotly_chart(go.Figure(data=go.Scatterpolar(r=radar_values, theta=fixed_axes, fill='toself')), use_container_width=True)
    
    if st.button("📥 导出错题诊断手册"):
        md = "# 🛡️ 错题手册\n\n"
        for _, r in df[~df['is_correct']].iterrows():
            md += f"### {r['question']}\n- ❌ 错误: {r['answer']}\n- 💡 解析: {r['analysis']}\n\n"
        st.download_button("点击下载", md, file_name="Mistakes.md")

if __name__ == "__main__":
    main()
