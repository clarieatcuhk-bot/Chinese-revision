import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import time
import random
from database import (
    sign_in, sign_up_and_login, get_profile, log_quiz_result, 
    get_user_all_logs, share_to_community, get_community_selected, 
    get_public_mistakes_with_kills, get_leaderboard_data, 
    delete_all_logs_of_question
)
from ai_engine import generate_ai_question

# --- v9.0 模块化·隔离重构版 ---
st.set_page_config(page_title="Zhongkao-Navigator Pro v9.0", page_icon="🧩", layout="wide")

# --- UI 样式 ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    .gold-medal { color: #d4af37 !important; font-weight: bold; font-size: 1.2rem; }
    .admin-badge { background-color: #dc2626; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
    .page-title { background: linear-gradient(90deg, #1e3a8a, #3b82f6); color: white; padding: 15px 25px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
    .kill-badge { display: inline-block; background: #ef4444; color: white; padding: 2px 10px; border-radius: 15px; font-weight: bold; font-size: 0.85rem; margin-right: 10px; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'active_tab' not in st.session_state: st.session_state.active_tab = "🌟 精选题库"
if 'challenge_q' not in st.session_state: st.session_state.challenge_q = None

def main():
    if st.session_state.user is None: show_auth()
    else: app_shell()

def show_auth():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🧩 语文冲刺 Pro v9.0</h2>", unsafe_allow_html=True)
        t = st.tabs(["🔑 登录", "📝 注册"])
        with t[0]:
            u = st.text_input("账号")
            p = st.text_input("密码", type="password")
            if st.button("进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t[1]:
            ru = st.text_input("注册 ID")
            rp = st.text_input("设置密码", type="password")
            rn = st.text_input("学生姓名")
            rc = st.text_input("班级名称")
            if st.button("立即加入", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_shell():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学"}
    acc = profile.get('account_name', user.email.split('@')[0]).lower()
    is_admin = (acc == "zhoumingen" or (acc.startswith('hongyi') and acc[6:].isdigit()))
    
    # --- 侧边栏导航 (物理隔离) ---
    with st.sidebar:
        st.markdown(f"### 👋 {profile['name']} " + ("<span class='admin-badge'>ADMIN</span>" if is_admin else ""), unsafe_allow_html=True)
        menu_items = ["🌟 精选题库", "🚩 错题挑战", "🏆 荣耀金榜", "📊 个人画像"]
        if is_admin: menu_items.insert(0, "📖 命题实验室")
        
        # 强制更新当前选择
        st.session_state.active_tab = st.radio("导航菜单", menu_items)
        st.divider()
        if st.button("退出系统"): st.session_state.user = None; st.rerun()

    # --- 渲染逻辑 (模块化隔离) ---
    if st.session_state.challenge_q:
        render_challenge_mode()
    else:
        if st.session_state.active_tab == "🌟 精选题库": render_selected_questions(is_admin)
        elif st.session_state.active_tab == "🚩 错题挑战": render_mistake_stream(is_admin)
        elif st.session_state.active_tab == "🏆 荣耀金榜": render_leaderboard()
        elif st.session_state.active_tab == "📊 个人画像": render_personal_dashboard()
        elif st.session_state.active_tab == "📖 命题实验室": render_admin_lab(is_admin)

# --- 1. 精选题库页面 ---
def render_selected_questions(is_admin):
    st.markdown("<div class='page-title'><h1>🌟 老师精选题库</h1><p>全站高质量题目汇聚地</p></div>", unsafe_allow_html=True)
    qs = get_community_selected()
    if not qs: st.info("库中暂无题目，等待老师发布。")
    for q in qs:
        with st.container():
            st.markdown(f"### 【{q['category']}】 {q['question']}")
            if st.button("立即挑战", key=f"sel_{q['id']}"):
                st.session_state.challenge_q = q; st.rerun()
            st.divider()

# --- 2. 错题挑战页面 ---
def render_mistake_stream(is_admin):
    st.markdown("<div class='page-title'><h1>🚩 全站连斩错题流</h1><p>围剿那些终结了大家的难题</p></div>", unsafe_allow_html=True)
    mistakes = get_public_mistakes_with_kills()
    if not mistakes: st.info("全站目前没有待挑战的错题。")
    for m in mistakes:
        st.error(f"<span class='kill-badge'>⚔️ 连斩 {m['kill_count']} 人</span> {m['question']}", icon="🔥")
        if st.button("终结此题", key=f"mk_{random.random()}"):
            st.session_state.challenge_q = m; st.rerun()
        st.divider()

# --- 3. 荣耀榜单页面 ---
def render_leaderboard():
    st.markdown("<div class='page-title'><h1>🏆 七维荣耀金榜</h1><p>数据见证成长，排名彰显实力</p></div>", unsafe_allow_html=True)
    data = get_leaderboard_data()
    if not data: st.warning("暂无榜单数据，快去答题吧！"); return
    
    df = pd.DataFrame(data); is_adm = lambda a: a == "zhoumingen" or (str(a).startswith('hongyi') and str(a)[6:].isdigit())
    df_st = df[~df['account_name'].apply(is_adm)] if 'account_name' in df.columns else df
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🔥 刷题王")
        for i, r in df_st.sort_values('total_questions', ascending=False).head(5).reset_index().iterrows():
            st.markdown(f"{i+1}. {r['name']} - {r['total_questions']}题")
    with c2:
        st.subheader("⚔️ 战神榜")
        for i, r in df_st.sort_values('correct_questions', ascending=False).head(5).reset_index().iterrows():
            st.markdown(f"{i+1}. {r['name']} - {r['correct_questions']}对")
    with c3:
        st.subheader("💡 贡献榜")
        for i, r in df.sort_values('contributions', ascending=False).head(5).reset_index().iterrows():
            st.markdown(f"{i+1}. {r['name']} - {r['contributions']}次")
    
    st.divider()
    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    with r2c1:
        st.subheader("⚡ 速度王")
        df_v = df_st[df_st['total_questions'] >= 5]
        if not df_v.empty:
            df_v['v'] = (df_v['total_time'] / df_v['total_questions']).round(1)
            for i, r in df_v.sort_values('v').head(3).reset_index().iterrows(): st.markdown(f"{i+1}. {r['name']} - {r['v']}s")
    with r2c2:
        st.subheader("⏳ 专注王")
        for i, r in df_st.sort_values('total_time', ascending=False).head(3).reset_index().iterrows(): st.markdown(f"{i+1}. {r['name']} - {(r['total_time']/60):.1f}m")
    with r2c3:
        st.subheader("🚩 质疑王")
        for i, r in df_st.sort_values('challenge_count', ascending=False).head(3).reset_index().iterrows(): st.markdown(f"{i+1}. {r['name']} - {r['challenge_count']}次")
    with r2c4:
        st.subheader("🏆 判官王")
        for i, r in df_st.sort_values('challenge_success_count', ascending=False).head(3).reset_index().iterrows(): st.markdown(f"{i+1}. {r['name']} - {r['challenge_success_count']}次")

# --- 4. 个人画像页面 ---
def render_personal_dashboard():
    st.markdown("<div class='page-title'><h1>📊 个人能力全景画像</h1><p>深度洞察你的每一个知识盲区</p></div>", unsafe_allow_html=True)
    logs = get_user_all_logs(st.session_state.user.id)
    df = pd.DataFrame(logs) if logs else pd.DataFrame(columns=['created_at', 'is_correct', 'category', 'question', 'answer', 'analysis'])
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("⏱️ 状态波动图")
        if not df.empty:
            df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Shanghai')
            bin_stats = df.groupby(df['created_at'].dt.floor('10min'))['is_correct'].mean().reset_index()
            st.plotly_chart(px.line(bin_stats, x='created_at', y='is_correct', markers=True), use_container_width=True)
    with col2:
        st.subheader("🏹 五轴能力分布")
        ax = ["字音辨析", "成语运用", "病句诊断", "字形纠错", "3500字基础"]
        st_data = df.groupby('category')['is_correct'].mean().to_dict() if not df.empty else {}
        radar_values = [st_data.get(a, 0)*100 for a in ax]
        st.plotly_chart(go.Figure(data=go.Scatterpolar(r=radar_values, theta=ax, fill='toself')), use_container_width=True)

    st.divider()
    st.subheader("📥 错题诊疗手册")
    wrongs = df[~df['is_correct']]
    if not wrongs.empty:
        md = "# 🛡️ 错题诊疗手册\n\n"
        for _, r in wrongs.iterrows(): md += f"### {r['question']}\n- ❌ 错误: {r['answer']}\n- 💡 解析: {r.get('analysis', '无')}\n\n"
        st.download_button("导出 PDF/Markdown 离线版", md, file_name="My_Mistakes.md", use_container_width=True)
    else: st.success("目前没有错题记录，继续保持！")

# --- 5. 管理员实验室 ---
def render_admin_lab(is_admin):
    st.markdown("<div class='page-title'><h1>📖 命题实验室</h1><p>管理员专属调试与发布中心</p></div>", unsafe_allow_html=True)
    if st.button("✨ 立即生成新题目"):
        st.session_state.lab_q = generate_ai_question(None, "precise", "综合")
    
    if 'lab_q' in st.session_state and st.session_state.lab_q:
        q = st.session_state.lab_q
        st.markdown(f"### {q['question']}")
        for k, v in q['options'].items(): st.write(f"{k}. {v}")
        st.info(f"正确答案：{q['answer']} | 解析：{q['analysis']}")
        if st.button("🚀 分享到全站精选题库"):
            share_to_community(q, q.get('category', '综合'), st.session_state.user.id)
            st.toast("已成功推送到全站精选题库！")

# --- 🎯 挑战模式覆盖层 (Overlay) ---
def render_challenge_mode():
    q = st.session_state.challenge_q
    st.markdown(f"<div class='page-title'><h1>🎯 正在进行挑战</h1><p>当前题目：{q.get('category', '挑战题')}</p></div>", unsafe_allow_html=True)
    
    st.info(f"### {q['question']}")
    opts = q.get('options', {})
    ans = st.radio("你的选择：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {opts.get(x, '...')}", key="active_chal", index=None)
    
    c1, c2 = st.columns(2)
    if ans:
        if c1.button("确认提交"):
            is_correct = (ans == q['answer'])
            log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q, ans, is_correct, 5.0)
            if is_correct: st.success("🎉 正确！挑战成功！"); st.balloons()
            else: st.error(f"❌ 错误。正确答案是：{q['answer']}")
            st.info(f"💡 解析：{q['analysis']}")
    
    if c2.button("⬅️ 退出挑战"):
        st.session_state.challenge_q = None
        st.rerun()

if __name__ == "__main__":
    main()
