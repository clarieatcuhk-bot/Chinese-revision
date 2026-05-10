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

# --- v4.0 旗舰版配置 ---
st.set_page_config(page_title="Zhongkao-Navigator v4.0", page_icon="🏆", layout="wide")

# --- UI 样式 ---
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .stMetric { background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); border-top: 4px solid #1e3a8a; }
    .badge { background-color: #1e3a8a; color: white; padding: 3px 12px; border-radius: 50px; font-size: 0.85rem; font-weight: 500; }
    .quadrant-label { font-size: 0.9rem; font-weight: bold; color: #64748b; }
</style>
""", unsafe_allow_html=True)

# --- 知识点映射 ---
CAT_OPTIONS = ["字音辨析", "成语运用", "病句诊断", "3500字基础", "3500字进阶"]

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'current_page' not in st.session_state: st.session_state.current_page = "📖 专项训练"
if 'current_q' not in st.session_state: st.session_state.current_q = None
if 'question_id' not in st.session_state: st.session_state.question_id = str(uuid.uuid4())
if 'answered' not in st.session_state: st.session_state.answered = False

# --- 素材加载 ---
@st.cache_data
def load_all_data():
    try:
        with open("chinese_assets.json", "r", encoding="utf-8") as f: a = json.load(f)
        with open("chars_3500.json", "r", encoding="utf-8") as f: c = json.load(f)
        return a, c
    except: return {"content": []}, {"chars": []}

assets_db, chars_lib = load_all_data()

def format_display_text(text):
    if not text: return ""
    text = text.replace("<u>", " **（").replace("</u>", "）** ")
    text = text.replace("（", " **（").replace("）", "）** ")
    return text

def main():
    if st.session_state.user is None: show_auth()
    else: app_body()

def show_auth():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center; color:#1e3a8a;'>🎯 中考语文导航 v4.0</h2>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["🔑 登录", "📝 注册"])
        with t1:
            u = st.text_input("用户名", key="l_u")
            p = st.text_input("密码", type="password", key="l_p")
            if st.button("进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if not err: st.session_state.user = res.user; st.rerun()
        with t2:
            ru = st.text_input("设置用户名", key="r_u")
            rp = st.text_input("设置密码", type="password", key="r_p")
            rn = st.text_input("姓名", key="r_n")
            rc = st.text_input("班级", key="r_c")
            if st.button("立即注册", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if not err: st.session_state.user = user; st.rerun()

def app_body():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学", "class_name": "备考中"}
    
    with st.sidebar:
        st.markdown(f"### 👤 {profile['name']}")
        st.caption(f"班级：{profile['class_name']}")
        st.divider()
        
        # --- 页面选择 ---
        pages = ["📖 专项训练", "🏰 社区广场", "📊 深度画像"]
        idx = pages.index(st.session_state.current_page) if st.session_state.current_page in pages else 0
        st.session_state.current_page = st.radio("导航", pages, index=idx)
        
        st.divider()
        # --- 知识点多选器 (Selector v4.0) ---
        st.markdown("🎯 **锁定考点：**")
        st.session_state.targets = st.multiselect("可多选：", CAT_OPTIONS, default=[], label_visibility="collapsed")
        
        st.divider()
        if st.button("退出系统"): st.session_state.user = None; st.rerun()

    if st.session_state.current_page == "📖 专项训练": brush_page()
    elif st.session_state.current_page == "🏰 社区广场": community_page()
    else: dashboard_v4_page()

def brush_page():
    st.header("考点精准突击")
    c1, c2 = st.columns([5, 1])
    with c2:
        if st.button("✨ 下一题", use_container_width=True) or st.session_state.current_q is None:
            refresh_q(st.session_state.targets)
            st.rerun()

    q = st.session_state.current_q
    if q and "error" not in q:
        if 'question' not in q:
            st.warning("题目加载异常，请点击下一题。")
            return
            
        st.markdown(f"<span class='badge'>{q.get('category', '综合')}</span>", unsafe_allow_html=True)
        st.markdown(f"### {format_display_text(q['question'])}", unsafe_allow_html=True)
        
        ans = st.radio("你的答案：", ["A", "B", "C", "D"], 
                       format_func=lambda x: f"{x}. {q['options'].get(x, '...')}", 
                       key=st.session_state.question_id, index=None, disabled=st.session_state.answered)
        
        if ans and not st.session_state.answered:
            st.session_state.answered = True
            time_spent = time.time() - st.session_state.start_time
            is_correct = (ans == q['answer'])
            # 自动分类存储
            log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q['question'], ans, is_correct, time_spent, q['analysis'])
            if is_correct: st.success("🎉 正确！"); st.balloons()
            else: st.error(f"❌ 错误。正确答案是：{q['answer']}")

        if st.session_state.answered:
            st.info(f"💡 **解析**：{q['analysis']}")
            if st.button("👍 分享至社区"):
                share_to_community(q, q.get('category', '综合'), st.session_state.user.id)
                st.toast("已同步！")
            if st.button("挑战下一题 ➡️"):
                refresh_q(st.session_state.targets)
                st.rerun()

def refresh_q(targets):
    st.session_state.answered = False
    st.session_state.question_id = str(uuid.uuid4())
    st.session_state.start_time = time.time()
    
    target_focus = random.choice(targets) if targets else None
    
    with st.spinner("AI 教练正在为你命题..."):
        if random.random() < 0.2:
            res = get_random_shared_question()
            if res: res["from_community"] = True; st.session_state.current_q = res; return
        
        if target_focus == "病句诊断":
            res = generate_ai_question(None, "grammar", "病句")
        elif target_focus and "3500字" in target_focus:
            chars = chars_lib.get('chars', [])
            pool = chars[:1500] if "基础" in target_focus else chars[1500:]
            res = generate_ai_question(random.choice(pool), "discovery", "字词扩展")
        else:
            pool = assets_db.get('content', [])
            items = random.sample(pool, 2) if pool else None
            res = generate_ai_question(items, "precise", target_focus)
            
        st.session_state.current_q = res

# --- 3. 深度画像 4.0：五轴雷达与象限逻辑 ---
def dashboard_v4_page():
    st.header("📊 深度能力全景画像 v4.0")
    logs = get_user_all_logs(st.session_state.user.id)
    if not logs: st.info("尚未收集到练习数据，去刷几题吧！"); return
    
    df = pd.DataFrame(logs)
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    # 指标卡
    acc = (df['is_correct'].sum() / len(df)) * 100
    avg_t = df['time_spent'].mean()
    m1, m2, m3 = st.columns(3)
    m1.metric("累计刷题", f"{len(df)}")
    m2.metric("综合正确率", f"{acc:.1f}%")
    m3.metric("平均耗时", f"{avg_t:.1f}s")

    st.divider()
    
    # --- 能力罗盘 2.0 (5轴对齐) ---
    c1, c2 = st.columns(2)
    with c1:
        # 五个固定轴
        fixed_axes = ["字音", "成语", "病句", "字形", "字词扩展"]
        # 计算各维度正确率
        stats = df.groupby('category')['is_correct'].mean().to_dict()
        radar_values = [stats.get(ax, 0) * 100 for ax in fixed_axes]
        
        fig_radar = go.Figure(data=go.Scatterpolar(
            r=radar_values, theta=fixed_axes, fill='toself', line_color='#1e3a8a'
        ))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), title="🏹 五轴核心能力地图")
        st.plotly_chart(fig_radar, use_container_width=True)

    with c2:
        # 象限分析优化
        sc_df = df.groupby('category').agg({'is_correct': 'mean', 'time_spent': 'mean'}).reset_index()
        fig_scatter = px.scatter(sc_df, x='time_spent', y='is_correct', text='category', size_max=40, title="⚡ 表现与效率分布")
        # 背景中线
        fig_scatter.add_vline(x=avg_t, line_dash="dash", line_color="gray")
        fig_scatter.add_hline(y=acc/100, line_dash="dash", line_color="gray")
        
        # 语义标注
        st.plotly_chart(fig_scatter, use_container_width=True)
        st.markdown("""
        <div style='display: flex; justify-content: space-around;'>
            <div class='quadrant-mastered'>💪 肌肉记忆区<br>(快且准)</div>
            <div class='quadrant-blind'>⚠️ 逻辑重灾区<br>(慢且错)</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    # 智能复习建议导出逻辑保持...
    bad_cats = [cat for cat in fixed_axes if stats.get(cat, 0) < 0.6]
    if bad_cats:
        st.warning(f"🚨 **重点突破建议**：你在【{', '.join(bad_cats)}】板块表现欠佳，建议在侧边栏锁定这些考点进行专项突击！")

# --- 社区广场逻辑 ---
def community_page():
    st.header("🏰 社区共享广场")
    t1, t2, t3 = st.tabs(["📊 荣誉排行榜", "🌟 精选题库", "🚩 全站错题"])
    with t1:
        data = get_leaderboard_data()
        if data:
            ldf = pd.DataFrame(data).sort_values('correct_questions', ascending=False)
            st.table(ldf[['name', 'class_name', 'correct_questions', 'total_questions', 'contributions']].head(10))
    with t2:
        for q in get_community_selected():
            with st.expander(f"【{q['category']}】 {q['question'][:30]}..."):
                st.markdown(format_display_text(q['question']))
                if st.button("挑战此题", key=f"q_{q['id']}"):
                    st.session_state.current_q = q
                    st.session_state.current_page = "📖 专项训练"
                    st.rerun()
    with t3:
        for m in get_public_mistakes():
            st.error(f"**[{m['category']}]** {format_display_text(m['question'])}")

if __name__ == "__main__":
    main()
