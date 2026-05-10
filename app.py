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

# --- v9.6 错题涅槃·智能管理系统 ---
st.set_page_config(page_title="Zhongkao-Navigator Pro v9.6", page_icon="🛡️", layout="wide")

# --- UI 样式 ---
st.markdown("""
<style>
    .stApp { background-color: #f1f5f9; }
    .page-title { background: linear-gradient(135deg, #0f172a, #1e40af); color: white; padding: 20px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
    .mistake-card { border-left: 6px solid #ef4444; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); margin-bottom: 15px; }
    .wrong-ans { color: #dc2626; font-weight: bold; background: #fef2f2; padding: 2px 6px; border-radius: 4px; }
    .right-ans { color: #16a34a; font-weight: bold; background: #f0fdf4; padding: 2px 6px; border-radius: 4px; }
    .analysis-box { background: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 6px; margin-top: 10px; font-size: 0.95rem; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'active_tab' not in st.session_state: st.session_state.active_tab = "🌟 精选题库"
if 'challenge_q' not in st.session_state: st.session_state.challenge_q = None
if 'redo_q' not in st.session_state: st.session_state.redo_q = None

def format_html(text):
    if not text: return ""
    return text.replace("<u>", "<span style='text-decoration: underline; font-weight: bold; color: #1e40af;'>").replace("</u>", "</span>")

def main():
    if st.session_state.user is None: show_auth()
    else: app_shell()

def show_auth():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🛡️ 语文导航 Pro v9.6</h2>", unsafe_allow_html=True)
        t = st.tabs(["🔑 登录", "📝 注册"])
        with t[0]:
            u = st.text_input("账号 ID")
            p = st.text_input("登录密码", type="password")
            if st.button("进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t[1]:
            ru = st.text_input("注册 ID")
            rp = st.text_input("设置密码", type="password")
            rn = st.text_input("真实姓名")
            rc = st.text_input("所属班级")
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
        st.session_state.active_tab = st.radio("系统导航", menu)
        st.divider()
        if st.button("退出登录"): st.session_state.user = None; st.rerun()

    # 逻辑覆盖层
    if st.session_state.challenge_q: render_challenge_mode()
    elif st.session_state.redo_q: render_redo_mode()
    else:
        if st.session_state.active_tab == "🌟 精选题库": render_selected_questions()
        elif st.session_state.active_tab == "🚩 错题挑战": render_mistake_stream()
        elif st.session_state.active_tab == "🏆 荣耀金榜": render_leaderboard()
        elif st.session_state.active_tab == "📊 个人画像": render_personal_dashboard()
        elif st.session_state.active_tab == "📖 命题实验室": render_admin_lab()

# --- 1. 精选题库 ---
def render_selected_questions():
    st.markdown("<div class='page-title'><h1>🌟 老师精选题库</h1><p>全站高质量教学资源实时同步</p></div>", unsafe_allow_html=True)
    qs = get_community_selected()
    for q in qs:
        with st.container():
            st.markdown(f"### 【{q['category']}】 {format_html(q['question'])}", unsafe_allow_html=True)
            if st.button("立即挑战", key=f"sel_{q['id']}"):
                st.session_state.challenge_q = q; st.rerun()
            st.divider()

# --- 2. 错题挑战 ---
def render_mistake_stream():
    st.markdown("<div class='page-title'><h1>🚩 全站连斩错题流</h1><p>攻克那些难倒了全站同学的题目</p></div>", unsafe_allow_html=True)
    mk = get_public_mistakes_with_kills()
    for m in mk:
        st.error(f"⚔️ 连斩 {m['kill_count']} 人 | {format_html(m['question'])}")
        if st.button("终结此题", key=f"mk_{random.random()}"):
            st.session_state.challenge_q = m; st.rerun()

# --- 3. 荣耀榜单 ---
def render_leaderboard():
    st.markdown("<div class='page-title'><h1>🏆 七维荣耀金榜</h1><p>全维度数据透视排名</p></div>", unsafe_allow_html=True)
    data = get_leaderboard_data()
    if not data: return
    df = pd.DataFrame(data); is_adm = lambda a: a == "zhoumingen" or (str(a).startswith('hongyi') and str(a)[6:].isdigit())
    df_st = df[~df['account_name'].apply(is_adm)] if 'account_name' in df.columns else df
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🔥 刷题王")
        for i, r in df_st.sort_values('total_questions', ascending=False).head(5).reset_index().iterrows(): st.write(f"{i+1}. {r['name']} - {r['total_questions']}题")
    with c2:
        st.subheader("⚔️ 战神榜")
        for i, r in df_st.sort_values('correct_questions', ascending=False).head(5).reset_index().iterrows(): st.write(f"{i+1}. {r['name']} - {r['correct_questions']}对")
    with c3:
        st.subheader("💡 贡献榜")
        for i, r in df.sort_values('contributions', ascending=False).head(5).reset_index().iterrows(): st.write(f"{i+1}. {r['name']} - {r['contributions']}次")

# --- 4. 个人画像 & 错题涅槃系统 ---
def render_personal_dashboard():
    st.markdown("<div class='page-title'><h1>📊 个人能力全景画像</h1><p>错题自动归类，消灭弱点，延伸罗盘</p></div>", unsafe_allow_html=True)
    logs = get_user_all_logs(st.session_state.user.id)
    df = pd.DataFrame(logs) if logs else pd.DataFrame(columns=['created_at', 'is_correct', 'category', 'question', 'options', 'answer', 'analysis', 'student_answer'])
    
    # 罗盘展示
    c1, c2 = st.columns([2, 1])
    with c1:
        if not df.empty:
            df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Shanghai')
            st.plotly_chart(px.line(df.groupby(df['created_at'].dt.floor('10min'))['is_correct'].mean().reset_index(), x='created_at', y='is_correct', markers=True, title="实时状态起伏"), use_container_width=True)
    with c2:
        ax = ["字音辨析", "成语运用", "病句诊断", "字形纠错", "3500字基础"]
        st_v = df.groupby('category')['is_correct'].mean().to_dict() if not df.empty else {}
        st.plotly_chart(go.Figure(data=go.Scatterpolar(r=[st_v.get(a, 0)*100 for a in ax], theta=ax, fill='toself')), use_container_width=True)

    st.divider()
    st.header("📖 智能错题涅槃中心")
    
    # 1. 资产管理
    col_cl, col_ex = st.columns([1, 1])
    if col_cl.button("🔥 清空错题记录", use_container_width=True):
        if clear_user_mistakes(st.session_state.user.id): st.toast("错题已归零！"); st.rerun()

    # 2. 分组展示逻辑
    wrongs = df[~df['is_correct']]
    if wrongs.empty:
        st.success("🎉 你的错题集目前是空的，能力罗盘已推向极致！")
    else:
        # 去重聚合
        counts = wrongs.groupby('question').size().to_dict()
        latest_wrongs = wrongs.sort_values('created_at', ascending=False).drop_duplicates('question')
        
        # 按分类分组
        for cat in latest_wrongs['category'].unique():
            with st.expander(f"📌 分类：{cat} ({len(latest_wrongs[latest_wrongs['category']==cat])} 题)"):
                for _, m in latest_wrongs[latest_wrongs['category']==cat].iterrows():
                    st.markdown(f"**题干：** {format_html(m['question'])}", unsafe_allow_html=True)
                    st.markdown(f"❌ 错误次数: **{counts.get(m['question'], 1)}** | 你的回答: <span class='wrong-ans'>{m['student_answer']}</span> | 正确答案: <span class='right-ans'>{m['answer']}</span>", unsafe_allow_html=True)
                    
                    c_btn, c_ana = st.columns([1, 4])
                    if c_btn.button("🔥 再练一次", key=f"redo_{random.random()}"):
                        st.session_state.redo_q = m.to_dict(); st.rerun()
                    
                    st.markdown(f"<div class='analysis-box'><b>🔍 逻辑拆解：</b><br>{m['analysis']}</div>", unsafe_allow_html=True)
                    st.divider()

        # 3. 物理导出
        md = "# 🛡️ 深度诊疗手册\n\n"
        all_text = " ".join(latest_wrongs['question'].tolist())
        md += f"### ⚠️ 高频避雷词：{', '.join(re.findall(r'[\u4e00-\u9fa5]{2,4}', all_text)[:10])}\n\n"
        for _, r in latest_wrongs.iterrows():
            md += f"## [{r['category']}] {r['question']}\n- ❌ 累计出错: {counts.get(r['question'], 1)} 次\n- 💡 诊疗建议: {r['analysis']}\n\n"
        col_ex.download_button("📥 导出 Markdown 复习版", md, file_name="Review.md", use_container_width=True)

# --- 5. 管理员实验室 ---
def render_admin_lab():
    st.markdown("<div class='page-title'><h1>📖 命题实验室</h1><p>Admin Only</p></div>", unsafe_allow_html=True)
    if st.button("✨ 随机生成字音精选题"):
        st.session_state.lab_q = generate_ai_question(None, "precise", "字音辨析")
    if 'lab_q' in st.session_state and st.session_state.lab_q:
        q = st.session_state.lab_q
        st.markdown(f"### {format_html(q['question'])}", unsafe_allow_html=True)
        if st.button("🚀 分享到全站"):
            share_to_community(q, q['category'], st.session_state.user.id); st.toast("已发布")

# --- 🎯 挑战模式覆盖层 ---
def render_challenge_mode():
    q = st.session_state.challenge_q
    st.markdown("<div class='page-title'><h1>🎯 社区挑战模式</h1></div>", unsafe_allow_html=True)
    st.info(f"### {format_html(q['question'])}")
    ans = st.radio("选择回答：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {q['options'].get(x, '...')}", key="act_q", index=None)
    c1, c2 = st.columns(2)
    if ans and c1.button("提交"):
        log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q, ans, (ans == q['answer']), 5.0)
        if ans == q['answer']: st.success("正确！"); st.balloons()
        else: st.error(f"错误，答案：{q['answer']}")
    if c2.button("⬅️ 退出"): st.session_state.challenge_q = None; st.rerun()

# --- 🎯 再练一次覆盖层 ---
def render_redo_mode():
    q = st.session_state.redo_q
    st.markdown("<div class='page-title'><h1>🔥 错题涅槃练习</h1></div>", unsafe_allow_html=True)
    st.warning(f"### {format_html(q['question'])}")
    ans = st.radio("重选答案：", ["A", "B", "C", "D"], format_func=lambda x: f"{x}. {q['options'].get(x, '...')}", key="redo_act", index=None)
    c1, c2 = st.columns(2)
    if ans and c1.button("提交"):
        log_quiz_result(st.session_state.user.id, q['category'], q, ans, (ans == q['answer']), 5.0)
        if ans == q['answer']: st.success("涅槃成功！该正确记录已同步至画像。"); st.balloons()
        else: st.error("仍然错误，请继续研读解析。")
    if c2.button("⬅️ 返回错题本"): st.session_state.redo_q = None; st.rerun()

if __name__ == "__main__":
    main()
