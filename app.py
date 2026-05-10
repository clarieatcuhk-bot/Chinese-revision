import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import time
import random
import json
from datetime import datetime, timedelta
from database import (
    sign_in, sign_up_and_login, get_profile, log_quiz_result, 
    get_user_all_logs, share_to_community, get_community_selected, 
    get_public_mistakes, get_random_shared_question
)
from ai_engine import generate_ai_question, sanitize_question

# --- Dashboard 2.0 全能专业版配置 ---
st.set_page_config(
    page_title="Zhongkao-Navigator Dashboard 2.0",
    page_icon="🎯",
    layout="wide"
)

# --- 专业莫兰迪/深空蓝配色样式 ---
st.markdown("""
<style>
    .main { background-color: #f0f2f6; }
    u { text-decoration: none; border-bottom: 2px dotted #1e3a8a; font-weight: bold; }
    
    /* 指标卡美化 */
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center;
        border-top: 4px solid #1e3a8a;
    }
    
    .community-card { 
        background-color: white; padding: 1.5rem; border-radius: 12px; 
        border-left: 5px solid #1e3a8a; margin-bottom: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .badge { background-color: #e0e7ff; color: #1e3a8a; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'current_q' not in st.session_state: st.session_state.current_q = None
if 'question_id' not in st.session_state: st.session_state.question_id = str(uuid.uuid4())
if 'answered' not in st.session_state: st.session_state.answered = False
if 'is_shared' not in st.session_state: st.session_state.is_shared = False

# --- 素材加载 ---
@st.cache_data
def load_all_assets():
    try:
        with open("chinese_assets.json", "r", encoding="utf-8") as f:
            assets = json.load(f)
        with open("chars_3500.json", "r", encoding="utf-8") as f:
            chars = json.load(f)
        return assets, chars
    except:
        return {"content": []}, {"chars": []}

assets_db, chars_lib = load_all_assets()

def main():
    if st.session_state.user is None:
        show_auth()
    else:
        app_body()

def show_auth():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<h1 style='text-align: center; color: #1e3a8a;'>🎯 中考语文导航 v3.0</h1>", unsafe_allow_html=True)
        st.caption("CUHK 实验室级数据分析 + 社区共享题库")
        t1, t2 = st.tabs(["🔑 登录", "📝 注册"])
        with t1:
            u = st.text_input("用户名", key="l_u")
            p = st.text_input("密码", type="password", key="l_p")
            if st.button("进入系统", use_container_width=True):
                res, err = sign_in(u, p)
                if err: st.error("登录失败")
                else:
                    st.session_state.user = res.user
                    st.rerun()
        with t2:
            ru = st.text_input("用户名", key="r_u")
            rp = st.text_input("密码", type="password", key="r_p")
            rn = st.text_input("姓名", key="r_n")
            rc = st.text_input("班级", key="r_c")
            if st.button("完成注册", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if err: st.error(err)
                else:
                    st.session_state.user = user
                    st.rerun()

def app_body():
    user = st.session_state.user
    profile = get_profile(user.id)
    
    with st.sidebar:
        st.markdown(f"### 👤 {profile.get('name', '同学')}")
        st.caption(f"📍 {profile.get('class_name', '基础班')}")
        st.divider()
        page = st.radio("功能模块", ["📖 专项刷题", "🏰 社区广场", "📊 学习画像 2.0"])
        if st.button("安全注销", use_container_width=True):
            st.session_state.user = None
            st.rerun()

    if page == "📖 专项刷题":
        brush_page()
    elif page == "🏰 社区广场":
        community_page()
    else:
        dashboard_v2_page()

# --- 刷题页面逻辑 ---
def brush_page():
    st.header("智能提分挑战")
    c1, c2 = st.columns([4, 1])
    with c1:
        mode = st.radio("模式：", ["精准课内", "字库发现", "病句专项"], horizontal=True)
    with c2:
        if st.button("✨ 换一题", use_container_width=True) or st.session_state.current_q is None:
            refresh_q(mode)
            st.rerun()

    q = st.session_state.current_q
    if q and "error" not in q:
        if q.get("from_community"):
            st.markdown("<span class='badge'>🌟 社区精选 (免 Token)</span>", unsafe_allow_html=True)
            
        st.markdown(f"### {q['question']}", unsafe_allow_html=True)
        
        ans = st.radio(
            "你的答案：", ["A", "B", "C", "D"],
            format_func=lambda x: f"{x}. {q['options'].get(x, '加载失败')}",
            key=st.session_state.question_id, index=None, disabled=st.session_state.answered
        )

        if ans and not st.session_state.answered:
            st.session_state.answered = True
            st.session_state.end_time = time.time()
            time_spent = st.session_state.end_time - st.session_state.start_time
            is_correct = (ans == q['answer'])
            log_quiz_result(st.session_state.user.id, mode, q['question'], ans, is_correct, time_spent, q['analysis'])
            
            if is_correct:
                st.success(f"✅ 正确！耗时：{time_spent:.1f}s")
                st.balloons()
            else:
                st.error(f"❌ 错误！正确答案：{q['answer']}")

        if st.session_state.answered:
            st.markdown("---")
            st.markdown("#### 💡 AI 深度解析")
            st.info(q['analysis'])
            
            c1, c2, c3 = st.columns([2, 2, 4])
            with c1:
                if st.button("👍 值得分享", disabled=st.session_state.is_shared):
                    if share_to_community(q, mode):
                        st.session_state.is_shared = True
                        st.toast("已同步到社区广场！")
            with c2:
                if st.button("👎 题目有误"): st.toast("已反馈给实验室")
            with c3:
                if st.button("继续刷下一题 ➡️", use_container_width=True):
                    refresh_q(mode)
                    st.rerun()

def refresh_q(mode):
    st.session_state.answered = False
    st.session_state.is_shared = False
    st.session_state.question_id = str(uuid.uuid4())
    with st.spinner("AI 实验室正在命题..."):
        if random.random() < 0.2:
            shared_q = get_random_shared_question()
            if shared_q:
                shared_q["from_community"] = True
                st.session_state.current_q = shared_q
                st.session_state.start_time = time.time()
                return
        if "精准" in mode:
            pool = assets_db.get('content', [])
            items = random.sample(pool, min(len(pool), 2))
            res = generate_ai_question(items, "precise")
        elif "字库" in mode:
            char = random.choice(chars_lib.get('chars', ["确", "凿"]))
            res = generate_ai_question(char, "discovery")
        else:
            res = generate_ai_question(None, "grammar")
        st.session_state.current_q = res
        st.session_state.start_time = time.time()

# --- 社区广场逻辑 ---
def community_page():
    st.header("🏰 社区共享广场")
    t1, t2 = st.tabs(["🌟 精选题库", "🚩 全站错题避雷"])
    with t1:
        selected = get_community_selected()
        for q in selected:
            with st.container():
                st.markdown(f"""
                <div class='community-card'>
                    <span class='badge'>{q['category']}</span>
                    <p style='margin-top:10px; font-weight: 500;'>{q['question']}</p>
                    <details>
                        <summary style='color: #1e3a8a; cursor: pointer;'>显示解析</summary>
                        <div style='background:#f8f9fa; padding:15px; border-radius:8px; margin-top:10px;'>
                            <b style='color: #2e7d32;'>答案：{q['answer']}</b><br>{q['analysis']}
                        </div>
                    </details>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"立即挑战该题", key=f"sq_{q['id']}"):
                    q["from_community"] = True
                    st.session_state.current_q = q
                    st.session_state.answered = False
                    st.rerun()
    with t2:
        mistakes = get_public_mistakes()
        for m in mistakes:
            st.markdown(f"""
            <div class='community-card' style='border-left-color: #ef4444;'>
                <span class='badge' style='background:#fef2f2; color:#ef4444;'>高频错题</span>
                <p style='margin-top:10px;'>{m['question']}</p>
                <p style='font-size:0.9rem; color:#6b7280;'>避雷建议：{m['analysis'][:100]}...</p>
            </div>
            """, unsafe_allow_html=True)

# --- 核心看板 2.0 逻辑 (Pandas & Plotly) ---
def dashboard_v2_page():
    st.header("📊 学习画像分析 2.0")
    logs = get_user_all_logs(st.session_state.user.id)
    if not logs:
        st.info("尚无练习数据，请先开始刷题！")
        return

    # --- 数据处理 ---
    df = pd.DataFrame(logs)
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['date'] = df['created_at'].dt.date
    
    # --- 1. 核心指标卡 ---
    total = len(df)
    acc = (df['is_correct'].sum() / total) * 100
    avg_t = df['time_spent'].mean()
    today = len(df[df['date'] == datetime.now().date()])
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f"<div class='metric-card'><small>累计刷题</small><h2>{total}</h2></div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='metric-card'><small>平均正确率</small><h2 style='color: #2e7d32;'>{acc:.1f}%</h2></div>", unsafe_allow_html=True)
    with c3: st.markdown(f"<div class='metric-card'><small>平均耗时</small><h2>{avg_t:.1f}s</h2></div>", unsafe_allow_html=True)
    with c4: st.markdown(f"<div class='metric-card'><small>今日完成</small><h2 style='color: #1e3a8a;'>{today}</h2></div>", unsafe_allow_html=True)

    st.divider()

    # --- 2. 能力罗盘与象限分析 ---
    row1_c1, row1_c2 = st.columns(2)
    
    with row1_c1:
        # 雷达图
        radar_data = df.groupby('category')['is_correct'].mean().reset_index()
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=radar_data['is_correct']*100, theta=radar_data['category'],
            fill='toself', line_color='#1e3a8a'
        ))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), title="🎯 个人能力罗盘", showlegend=False)
        st.plotly_chart(fig_radar, use_container_width=True)

    with row1_c2:
        # 象限图
        scatter_data = df.groupby('category').agg({'is_correct': 'mean', 'time_spent': 'mean'}).reset_index()
        fig_scatter = px.scatter(
            scatter_data, x='time_spent', y='is_correct', text='category',
            title="⚡ 效率-表现象限分析", labels={'time_spent': '耗时 (s)', 'is_correct': '准确率'},
            size_max=40
        )
        fig_scatter.add_vline(x=avg_t, line_dash="dash", line_color="gray")
        fig_scatter.add_hline(y=acc/100, line_dash="dash", line_color="gray")
        st.plotly_chart(fig_scatter, use_container_width=True)

    # --- 3. 趋势与雷点 ---
    row2_c1, row2_c2 = st.columns([2, 1])
    
    with row2_c1:
        # 趋势图
        trend_df = df.groupby('date').size().reset_index(name='count')
        fig_trend = px.area(trend_df, x='date', y='count', title="📈 七日复习热度趋势", color_discrete_sequence=['#1e3a8a'])
        st.plotly_chart(fig_trend, use_container_width=True)
        
    with row2_c2:
        st.markdown("#### 🚩 高频“雷点” Top 5")
        bad_cats = df[~df['is_correct']].groupby('category').size().sort_values(ascending=False).head(5)
        for cat, count in bad_cats.items():
            st.error(f"**{cat}**: 累计错误 {count} 次")
        
        # 错题导出
        wrongs = df[~df['is_correct']].sort_values('created_at', ascending=False)
        md = "# 🛡️ 错题避雷手册\n\n"
        for _, row in wrongs.iterrows():
            md += f"### {row['question']}\n- 答案: {row['answer']}\n- 耗时: {row['time_spent']:.1f}s\n- 解析: {row['analysis']}\n\n"
        st.download_button("📥 导出 Markdown 错题本", data=md, file_name="Zhongkao_Mistakes.md", use_container_width=True)

if __name__ == "__main__":
    main()
