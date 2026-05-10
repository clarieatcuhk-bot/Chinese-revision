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
    get_leaderboard_data, delete_shared_question_by_id, record_challenge
)
from ai_engine import generate_ai_question, sanitize_question, re_verify_question

# --- v6.5 全能战线·终极版 ---
st.set_page_config(page_title="Zhongkao-Navigator Pro v6.5", page_icon="🧬", layout="wide")

BEIJING_TZ = timezone(timedelta(hours=8))

# --- UI 样式 (高规格) ---
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .gold-medal { color: #d4af37; font-weight: bold; font-size: 1.15rem; }
    .admin-badge { background-color: #dc2626; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }
    .disclaimer { font-size: 0.8rem; color: #64748b; text-align: center; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; background: white; margin-bottom: 20px; }
    .king-wall-card { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 15px; margin-bottom: 10px; border-top: 4px solid #1e3a8a; }
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
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🚀 语文冲刺 Pro v6.5</h2>", unsafe_allow_html=True)
        st.markdown("<div class='disclaimer'>AI 可能存在错误，请大胆质疑！</div>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["🔑 登录", "📝 注册"])
        with t1:
            u = st.text_input("账号", key="l_u")
            p = st.text_input("密码", type="password", key="l_p")
            if st.button("进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t2:
            ru = st.text_input("设置账号 (不可更改)", key="r_u")
            rp = st.text_input("设置密码", type="password", key="r_p")
            rn = st.text_input("用户名 (展示姓名)", key="r_n")
            rc = st.text_input("班级", key="r_c")
            if st.button("完成注册", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_body():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学", "class_name": "备考中"}
    # --- 管理员检测逻辑 (看账号 ZhouMingen) ---
    is_admin = (user.email == "ZhouMingen@navigator.com")
    
    with st.sidebar:
        st.markdown(f"### 👋 {profile['name']} " + ("<span class='admin-badge'>ADMIN</span>" if is_admin else ""), unsafe_allow_html=True)
        st.caption(f"账号：{user.email.split('@')[0]}")
        st.divider()
        pages = ["📖 专项训练", "🏰 社区广场", "📊 能力画像"]
        idx = pages.index(st.session_state.current_page) if st.session_state.current_page in pages else 0
        st.session_state.current_page = st.radio("系统导航", pages, index=idx)
        st.divider()
        st.session_state.targets = st.multiselect("考点多选：", ["字音辨析", "字形纠错", "成语运用", "病句诊断", "3500字基础", "3500字进阶"], default=st.session_state.targets)
        if st.button("退出系统"): st.session_state.user = None; st.rerun()

    if st.session_state.current_page == "📖 专项训练": brush_page()
    elif st.session_state.current_page == "🏰 社区广场": community_page(is_admin)
    else: dashboard_page()

def brush_page():
    st.header("考点突击练习")
    c1, c2 = st.columns([5, 1])
    with c2:
        if st.button("✨ 换一题", use_container_width=True) or st.session_state.current_q is None:
            refresh_q(st.session_state.targets)
            st.rerun()
    q = st.session_state.current_q
    if q and "error" not in q:
        st.markdown(f"**知识点**：{q.get('category', '综合')}")
        st.markdown(f"### {format_text(q['question'])}", unsafe_allow_html=True)
        ans = st.radio("你的选择：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {q['options'].get(x, '...')}", key=st.session_state.question_id, index=None, disabled=st.session_state.answered)
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
                    with st.spinner("AI 重新复核中..."):
                        review = re_verify_question(q)
                        st.warning(review)
                        is_success = ("【AI 已认错】" in review)
                        record_challenge(st.session_state.user.id, is_success)
                        if is_success and 'id' in q: delete_shared_question_by_id(q['id'])
            with c3:
                if st.button("刷下一题 ➡️", use_container_width=True): refresh_q(st.session_state.targets); st.rerun()

def refresh_q(targets):
    st.session_state.answered = False
    st.session_state.question_id = str(uuid.uuid4())
    st.session_state.start_time = time.time()
    with st.spinner("AI 命题中..."):
        if random.random() < 0.2:
            q = get_random_shared_question()
            if q and q.get('id') not in st.session_state.seen_q_ids:
                st.session_state.seen_q_ids.add(q.get('id')); st.session_state.current_q = q; return
        target_focus = random.choice(targets) if targets else None
        st.session_state.current_q = generate_ai_question(None, "precise", target_focus)

# --- 🏆 七维荣耀排行榜 ---
def community_page(is_admin):
    st.header("🏰 社区荣耀广场")
    t1, t2, t3 = st.tabs(["🏆 七维荣耀榜", "🌟 精选题库", "🚩 连斩错题"])
    with t1:
        data = get_leaderboard_data()
        if data:
            df = pd.DataFrame(data)
            df['accuracy'] = (df['correct_questions'] / df['total_questions'].replace(0, 1) * 100).round(1)
            df['avg_speed'] = (df['total_time'] / df['total_questions'].replace(0, 1)).round(1)
            
            # 布局 3+4
            r1c1, r1c2, r1c3 = st.columns(3)
            with r1c1:
                st.markdown("#### 🔥 刷题最多 (勤奋王)")
                top = df.sort_values('total_questions', ascending=False).head(5).reset_index()
                for i, r in top.iterrows():
                    st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['total_questions']}题", unsafe_allow_html=True)
            with r1c2:
                st.markdown("#### ⚔️ 正确最多 (战神)")
                top = df.sort_values('correct_questions', ascending=False).head(5).reset_index()
                for i, r in top.iterrows():
                    st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['correct_questions']}对", unsafe_allow_html=True)
            with r1c3:
                st.markdown("#### ⏳ 时间最长 (专注)")
                top = df.sort_values('total_time', ascending=False).head(5).reset_index()
                for i, r in top.iterrows():
                    st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {(r['total_time']/60):.1f}min", unsafe_allow_html=True)
            
            st.divider()
            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            with r2c1:
                st.markdown("#### 💡 贡献最大")
                top = df.sort_values('contributions', ascending=False).head(5).reset_index()
                for i, r in top.iterrows():
                    st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['contributions']}次", unsafe_allow_html=True)
            with r2c2:
                st.markdown("#### ⚡ 速度最快")
                # 过滤题量过低的用户
                top = df[df['total_questions'] >= 10].sort_values('avg_speed', ascending=True).head(5).reset_index()
                for i, r in top.iterrows():
                    st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['avg_speed']}s/题", unsafe_allow_html=True)
            with r2c3:
                st.markdown("#### 🚩 质疑之王")
                top = df.sort_values('challenge_count', ascending=False).head(5).reset_index()
                for i, r in top.iterrows():
                    st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['challenge_count']}次", unsafe_allow_html=True)
            with r2c4:
                st.markdown("#### 🏆 判官之王")
                top = df.sort_values('challenge_success_count', ascending=False).head(5).reset_index()
                for i, r in top.iterrows():
                    st.markdown(f"{i+1}. <span class=\"{'gold-medal' if i==0 else ''}\">{r['name']}</span> - {r['challenge_success_count']}次", unsafe_allow_html=True)

    with t2:
        for q in get_community_selected():
            with st.expander(f"【{q['category']}】 {q['question'][:30]}..."):
                st.markdown(f"⭐ {q.get('recommend_count', 1)} 人推荐")
                st.markdown(format_text(q['question']))
                c1, c2, c3 = st.columns([1, 1, 4])
                if c1.button("挑战", key=f"sq_{q['id']}"):
                    st.session_state.current_q = q; st.session_state.current_page = "📖 专项训练"; st.rerun()
                if is_admin:
                    if c2.button("🗑️ 删除", key=f"del_sq_{q['id']}"):
                        if delete_shared_question_by_id(q['id']): st.toast("已删除"); st.rerun()

    with t3:
        for m in get_public_mistakes_with_kills():
            kills = m.get('kill_count', 1)
            st.error(f"⚔️ 连斩 {kills} 人 | {format_text(m['question'])}")
            if st.button("挑战终结", key=f"kill_{kills}_{random.random()}"):
                st.session_state.current_q = m; st.session_state.current_page = "📖 专项训练"; st.rerun()

def dashboard_page():
    st.header("📊 深度能力全景画像")
    logs = get_user_all_logs(st.session_state.user.id)
    if not logs: st.info("尚未收集到数据"); return
    
    df = pd.DataFrame(logs)
    df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Shanghai')
    
    # --- 五轴能力罗盘 ---
    st.subheader("🏹 五轴核心能力分布")
    fixed_axes = ["字音辨析", "成语运用", "病句诊断", "字形纠错", "字词扩展"]
    stats = df.groupby('category')['is_correct'].mean().to_dict()
    radar_values = [stats.get(ax, 0) * 100 for ax in fixed_axes]
    fig_radar = go.Figure(data=go.Scatterpolar(r=radar_values, theta=fixed_axes, fill='toself', line_color='#1e3a8a'))
    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])))
    st.plotly_chart(fig_radar, use_container_width=True)

    # --- 10分钟状态波动 ---
    st.subheader("⏱️ 10分钟颗粒度状态波动")
    df['time_bin'] = df['created_at'].dt.floor('10min')
    bin_stats = df.groupby('time_bin')['is_correct'].mean().reset_index()
    bin_stats['is_correct'] *= 100
    st.plotly_chart(px.line(bin_stats, x='time_bin', y='is_correct', markers=True), use_container_width=True)

    # --- 导出功能 ---
    st.divider()
    if st.button("📥 导出 Markdown 错题手册", use_container_width=True):
        md = "# 🛡️ 中考语文避雷手册\n\n"
        for cat in df['category'].unique():
            wrongs = df[(df['category'] == cat) & (~df['is_correct'])]
            if not wrongs.empty:
                md += f"## 【{cat}板块】\n"
                for _, row in wrongs.iterrows():
                    md += f"### {row['question']}\n- ❌ 错误答案: {row['answer']}\n- 💡 深度解析: {row['analysis']}\n\n"
        st.download_button("点击下载", md, file_name="Zhongkao_Pro_Mistakes.md")

if __name__ == "__main__":
    main()
