import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import time
import random
import json
import re
from database import (
    sign_in, sign_up_and_login, get_profile, log_quiz_result, 
    get_user_all_logs, share_to_community, get_community_selected, 
    get_public_mistakes_with_kills, get_leaderboard_data, 
    clear_user_mistakes
)
from ai_engine import generate_ai_question

# --- v10.0 终极纯净版 ---
st.set_page_config(page_title="Zhongkao-Navigator Pro v10.0", page_icon="💎", layout="wide")

# --- UI 样式 ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    .page-header { background: linear-gradient(135deg, #0f172a, #3b82f6); color: white; padding: 25px; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
    .kill-badge { background: #ef4444; color: white; padding: 3px 12px; border-radius: 15px; font-weight: bold; font-size: 0.9rem; margin-right: 10px; }
    .gold-medal { color: #eab308; font-weight: bold; }
    .admin-badge { background: #dc2626; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 辅助工具 ---
def ensure_dict(data):
    if isinstance(data, dict): return data
    if isinstance(data, str):
        try: return json.loads(data)
        except:
            import ast
            try: return ast.literal_eval(data)
            except: return {}
    return {}

def format_html(text):
    if not text: return ""
    return str(text).replace("<u>", "<span style='text-decoration: underline; color: #2563eb; font-weight: bold;'>").replace("</u>", "</span>")

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'challenge_q' not in st.session_state: st.session_state.challenge_q = None
if 'redo_q' not in st.session_state: st.session_state.redo_q = None

def main():
    if st.session_state.user is None: show_auth()
    else: app_shell()

def show_auth():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>💎 语文导航 Pro v10.0</h2>", unsafe_allow_html=True)
        t = st.tabs(["🔑 登录", "📝 注册"])
        with t[0]:
            u = st.text_input("账号 ID")
            p = st.text_input("登录密码", type="password")
            if st.button("进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t[1]:
            ru = st.text_input("注册账号")
            rp = st.text_input("设置密码", type="password")
            rn = st.text_input("显示姓名")
            rc = st.text_input("班级")
            if st.button("立即加入", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_shell():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学"}
    acc = str(profile.get('account_name', user.email.split('@')[0])).lower()
    
    # 核心修复：更严格的管理员判定
    name_str = str(profile.get('name', '')).lower()
    is_admin = ('zhoumingen' in acc) or ('周铭恩' in name_str) or ('hongyi' in acc and any(c.isdigit() for c in acc))
    
    with st.sidebar:
        st.markdown(f"### 👋 {profile['name']} " + ("<span class='admin-badge'>ADMIN</span>" if is_admin else ""), unsafe_allow_html=True)
        menu = ["🌟 精选题库", "🚩 错题挑战", "🏆 荣耀金榜", "📊 个人画像"]
        if is_admin: menu.insert(0, "📖 命题实验室")
        
        # 核心修复：丝滑导航 (无 rerun)
        if st.session_state.challenge_q or st.session_state.redo_q:
            st.info("🎯 答题模式进行中")
            if st.button("⬅️ 强制退出"):
                st.session_state.challenge_q = None; st.session_state.redo_q = None; st.rerun()
            active_tab = None # 屏蔽主内容渲染
        else:
            active_tab = st.radio("系统频道", menu, key="nav_radio")
            
        st.divider()
        if st.button("退出系统"): st.session_state.user = None; st.rerun()

    # 逻辑路由
    if st.session_state.challenge_q: render_challenge_mode()
    elif st.session_state.redo_q: render_redo_mode()
    else:
        if active_tab == "🌟 精选题库": render_selected_questions()
        elif active_tab == "🚩 错题挑战": render_mistake_stream()
        elif active_tab == "🏆 荣耀金榜": render_leaderboard(is_admin)
        elif active_tab == "📊 个人画像": render_personal_dashboard()
        elif active_tab == "📖 命题实验室": render_admin_lab()

def render_selected_questions():
    st.markdown("<div class='page-header'><h1>🌟 老师精选题库</h1><p>已过滤无效数据的纯净版题库</p></div>", unsafe_allow_html=True)
    qs = get_community_selected()
    if not qs: st.info("目前没有精选题目")
    for q in qs:
        with st.container():
            st.markdown(f"### 【{q.get('category', '综合')}】 {format_html(q.get('question'))}", unsafe_allow_html=True)
            if st.button("立即挑战", key=f"sel_v10_{q['id']}"):
                st.session_state.challenge_q = q; st.rerun()
            st.divider()

def render_mistake_stream():
    st.markdown("<div class='page-header'><h1>🚩 全站连斩错题流</h1><p>全站师生共同攻克的易错难点</p></div>", unsafe_allow_html=True)
    mk = get_public_mistakes_with_kills()
    if not mk: st.success("目前全站没有精选错题。去精选题库试试身手吧！")
    for m in mk:
        # 核心修复：使用 unsafe_allow_html 渲染 HTML 标签，替代不支持的 st.error
        st.markdown(f"<div class='mistake-card'><span class='kill-badge'>⚔️ 连斩 {m.get('kill_count', 1)} 人</span> {format_html(m.get('question'))}</div>", unsafe_allow_html=True)
        if st.button("终结此题", key=f"mk_v10_{m.get('id', random.random())}"):
            st.session_state.challenge_q = m; st.rerun()
        st.write("") # 增加间距

def render_leaderboard(current_user_is_admin):
    st.markdown("<div class='page-header'><h1>🏆 七维荣耀金榜</h1><p>全面回归的7项竞技数据</p></div>", unsafe_allow_html=True)
    data = get_leaderboard_data()
    if not data: st.info("榜单数据加载中..."); return
    df = pd.DataFrame(data)
    
    # 核心修复：绝对的管理员屏蔽
    def is_adm(row):
        a = str(row.get('account_name', '')).lower()
        n = str(row.get('name', '')).lower()
        if 'zhoumingen' in a or '周铭恩' in n: return True
        if 'hongyi' in a and any(c.isdigit() for c in a): return True
        return False
        
    df_st = df[~df.apply(is_adm, axis=1)] if not df.empty else df
    
    # 强制渲染 7 个版块
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🔥 刷题榜")
        for i, r in df_st.sort_values('total_questions', ascending=False).head(5).reset_index().iterrows():
            st.write(f"{i+1}. {r['name']} - {r['total_questions']}题")
    with c2:
        st.subheader("⚔️ 战神榜")
        for i, r in df_st.sort_values('correct_questions', ascending=False).head(5).reset_index().iterrows():
            st.write(f"{i+1}. {r['name']} - {r['correct_questions']}对")
    with c3:
        st.subheader("💡 贡献榜 (含老师)")
        for i, r in df.sort_values('contributions', ascending=False).head(5).reset_index().iterrows():
            st.write(f"{i+1}. {r['name']} - {r['contributions']}次")
            
    st.divider()
    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    with r2c1:
        st.subheader("⚡ 速度榜")
        df_v = df_st[df_st['total_questions'] >= 5].copy()
        if not df_v.empty:
            df_v['v'] = (df_v['total_time'] / df_v['total_questions']).round(1)
            for i, r in df_v.sort_values('v').head(3).reset_index().iterrows(): st.write(f"{i+1}. {r['name']} - {r['v']}s")
    with r2c2:
        st.subheader("⏳ 专注榜")
        for i, r in df_st.sort_values('total_time', ascending=False).head(3).reset_index().iterrows():
            st.write(f"{i+1}. {r['name']} - {(r['total_time']/60):.1f}m")
    with r2c3:
        st.subheader("🚩 质疑榜")
        for i, r in df_st.sort_values('challenge_count', ascending=False).head(3).reset_index().iterrows():
            st.write(f"{i+1}. {r['name']} - {r['challenge_count']}次")
    with r2c4:
        st.subheader("🏆 判官榜")
        for i, r in df_st.sort_values('challenge_success_count', ascending=False).head(3).reset_index().iterrows():
            st.write(f"{i+1}. {r['name']} - {r['challenge_success_count']}次")

def render_personal_dashboard():
    st.markdown("<div class='page-header'><h1>📊 能力画像与涅槃中心</h1><p>图表修复，永不宕机</p></div>", unsafe_allow_html=True)
    logs = get_user_all_logs(st.session_state.user.id)
    df = pd.DataFrame(logs) if logs else pd.DataFrame(columns=['created_at', 'is_correct', 'category', 'question', 'options', 'answer', 'analysis', 'student_answer'])
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("⏱️ 状态波动图")
        # 核心修复：清洗失效的时间戳
        if not df.empty:
            df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
            df_clean = df.dropna(subset=['created_at']).copy()
            if not df_clean.empty:
                df_clean['created_at'] = df_clean['created_at'].dt.tz_convert('Asia/Shanghai')
                bin_stats = df_clean.groupby(df_clean['created_at'].dt.floor('10min'))['is_correct'].mean().reset_index()
                st.plotly_chart(px.line(bin_stats, x='created_at', y='is_correct', markers=True), use_container_width=True)
            else: st.info("需要更多近期答题数据")
        else: st.info("暂无做题记录，波动图将在你答题后生成。")
        
    with c2:
        st.subheader("🏹 五轴核心罗盘")
        axes = ["字音辨析", "成语运用", "病句诊断", "字形纠错", "3500字基础"]
        st_v = df.groupby('category')['is_correct'].mean().to_dict() if not df.empty else {}
        radar_values = [st_v.get(a, 0)*100 for a in axes]
        st.plotly_chart(go.Figure(data=go.Scatterpolar(r=radar_values, theta=axes, fill='toself')), use_container_width=True)

    st.divider()
    st.subheader("📖 智能错题涅槃集")
    if not df.empty:
        wrongs = df[~df['is_correct']]
        if not wrongs.empty:
            latest = wrongs.sort_values('created_at', ascending=False).drop_duplicates('question')
            for cat in latest['category'].unique():
                with st.expander(f"📌 {cat}"):
                    for _, m in latest[latest['category']==cat].iterrows():
                        st.markdown(f"**题干：** {format_html(m.get('question'))}", unsafe_allow_html=True)
                        if st.button("🔥 涅槃重练", key=f"redo_v10_{random.random()}"):
                            st.session_state.redo_q = m.to_dict(); st.rerun()
                        st.divider()
        else: st.success("干得漂亮！错题集目前是空的。")

def render_admin_lab():
    st.markdown("<div class='page-header'><h1>📖 命题实验室</h1><p>高质量出题机</p></div>", unsafe_allow_html=True)
    if st.button("✨ 生成字音精选题"):
        st.session_state.lab_q = generate_ai_question(None, "precise", "字音辨析")
    if 'lab_q' in st.session_state and st.session_state.lab_q:
        q = st.session_state.lab_q
        st.write(q['question'])
        if st.button("🚀 发布到全站"): share_to_community(q, q['category'], st.session_state.user.id); st.toast("发布成功")

def get_option_label(opts, key):
    val = opts.get(key) or opts.get(key.lower())
    return f"{key}. {val}" if val else key

def render_challenge_mode():
    q = st.session_state.challenge_q
    st.markdown("<div class='page-header'><h1>🎯 挑战正在进行</h1></div>", unsafe_allow_html=True)
    
    q_text = q.get('question') or q.get('question_text') or "数据异常"
    opts = ensure_dict(q.get('options', {}))
    
    # 核心修复：使用 markdown 渲染 HTML，替代不支持 HTML 的 st.info
    st.markdown(f"<div style='background-color:#eff6ff; padding: 15px; border-radius: 8px; border-left: 5px solid #3b82f6;'><h3>{format_html(q_text)}</h3></div>", unsafe_allow_html=True)
    st.write("")
    
    # 核心修复：适配 AI 把选项生成到题干里的情况
    ans = st.radio("请选择答案：", ["A", "B", "C", "D"], format_func=lambda x: get_option_label(opts, x), key="act_v10", index=None)
    
    c1, c2 = st.columns(2)
    if ans and c1.button("确认提交"):
        log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q, ans, (ans == q.get('answer')), 5.0)
        if ans == q.get('answer'): st.success("🎉 正确！挑战成功！"); st.balloons()
        else: st.error(f"❌ 错误。正确答案是：{q.get('answer')}")
        st.info(f"💡 解析：{q.get('analysis')}")
    
    if c2.button("⬅️ 退出挑战"):
        st.session_state.challenge_q = None; st.rerun()

def render_redo_mode():
    q = st.session_state.redo_q
    st.markdown("<div class='page-header'><h1>🔥 错题涅槃练习</h1></div>", unsafe_allow_html=True)
    
    q_text = q.get('question') or q.get('question_text') or "数据异常"
    opts = ensure_dict(q.get('options', {}))
    
    st.markdown(f"<div style='background-color:#fffbeb; padding: 15px; border-radius: 8px; border-left: 5px solid #f59e0b;'><h3>{format_html(q_text)}</h3></div>", unsafe_allow_html=True)
    st.write("")
    
    ans = st.radio("重选答案：", ["A", "B", "C", "D"], format_func=lambda x: get_option_label(opts, x), key="redo_v10", index=None)
    
    c1, c2 = st.columns(2)
    if ans and c1.button("确认提交"):
        log_quiz_result(st.session_state.user.id, q.get('category'), q, ans, (ans == q.get('answer')), 5.0)
        if ans == q.get('answer'): st.success("🎉 涅槃成功！新记录已同步"); st.balloons()
        else: st.error("仍然错误，请继续复习。")
    
    if c2.button("⬅️ 返回错题本"):
        st.session_state.redo_q = None; st.rerun()

if __name__ == "__main__":
    main()
