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
    get_public_mistakes, get_random_shared_question
)
from ai_engine import generate_ai_question, sanitize_question

# --- v3.5 精准选课与多维分析版 ---
st.set_page_config(page_title="Zhongkao-Navigator Pro v3.5", page_icon="🎯", layout="wide")

# --- UI 样式 ---
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .stMetric { background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
    .quadrant-mastered { background-color: #dcfce7; padding: 10px; border-radius: 5px; text-align: center; }
    .quadrant-blind { background-color: #fee2e2; padding: 10px; border-radius: 5px; text-align: center; }
    .badge { background-color: #1e3a8a; color: white; padding: 3px 10px; border-radius: 50px; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# --- 知识点映射表 ---
KNOWLEDGE_POINTS = {
    "字音辨析": "字音",
    "字形纠错": "字形",
    "成语运用": "成语",
    "病句诊断": "病句",
    "3500字基础": "字库-基础",
    "3500字进阶": "字库-挑战"
}

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'current_q' not in st.session_state: st.session_state.current_q = None
if 'question_id' not in st.session_state: st.session_state.question_id = str(uuid.uuid4())
if 'answered' not in st.session_state: st.session_state.answered = False

# --- 素材加载 ---
@st.cache_data
def load_all_assets():
    try:
        with open("chinese_assets.json", "r", encoding="utf-8") as f: assets = json.load(f)
        with open("chars_3500.json", "r", encoding="utf-8") as f: chars = json.load(f)
        return assets, chars
    except: return {"content": []}, {"chars": []}

assets_db, chars_lib = load_all_assets()

def main():
    if st.session_state.user is None:
        show_auth()
    else:
        app_body()

def show_auth():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align: center;'>🎯 中考语文导航 v3.5</h2>", unsafe_allow_html=True)
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
            if st.button("立即开通", use_container_width=True):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if err: st.error(err)
                else:
                    st.session_state.user = user
                    st.rerun()

def app_body():
    user = st.session_state.user
    profile = get_profile(user.id)
    if not profile: profile = {"name": "新同学", "class_name": "待完善"}
    
    with st.sidebar:
        st.markdown(f"### 👤 {profile.get('name')}")
        st.caption(f"班级：{profile.get('class_name')}")
        st.divider()
        page = st.radio("导航", ["📖 精准刷题", "🏰 社区广场", "📊 深度画像"])
        if st.button("退出登录"):
            st.session_state.user = None
            st.rerun()

    if page == "📖 精准刷题":
        brush_page()
    elif page == "🏰 社区广场":
        community_page()
    else:
        dashboard_v3_page()

# --- 1. 题目选择器与刷题逻辑 ---
def brush_page():
    st.header("精准选课挑战")
    
    # 知识点多选器
    targets = st.multiselect(
        "🎯 锁定考点范围：",
        options=list(KNOWLEDGE_POINTS.keys()),
        default=[],
        placeholder="选择你想攻克的板块（留空则全随机）"
    )
    
    c1, c2 = st.columns([4, 1])
    with c2:
        if st.button("✨ 生成题目", use_container_width=True) or st.session_state.current_q is None:
            refresh_q(targets)
            st.rerun()

    q = st.session_state.current_q
    if q and "error" not in q:
        # 显示所属分类
        cat_display = q.get('category', '综合')
        st.markdown(f"<span class='badge'>{cat_display}</span>", unsafe_allow_html=True)
        
        st.markdown(f"### {q['question']}", unsafe_allow_html=True)
        
        ans = st.radio(
            "选择答案：", ["A", "B", "C", "D"],
            format_func=lambda x: f"{x}. {q['options'].get(x, '数据加载中')}",
            key=st.session_state.question_id, index=None, disabled=st.session_state.answered
        )

        if ans and not st.session_state.answered:
            st.session_state.answered = True
            st.session_state.end_time = time.time()
            time_spent = st.session_state.end_time - st.session_state.start_time
            is_correct = (ans == q['answer'])
            
            # 入库时使用 AI 返回的具体 category，而不是模式名称
            log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q['question'], ans, is_correct, time_spent, q['analysis'])
            
            if is_correct: st.success(f"✅ 正确！耗时：{time_spent:.1f}s"); st.balloons()
            else: st.error(f"❌ 错误！正确答案：{q['answer']}")

        if st.session_state.answered:
            st.markdown("---")
            st.info(f"💡 **解析**：{q['analysis']}")
            if st.button("点赞并分享", help="分享至社区广场") and not q.get('from_community'):
                share_to_community(q, q.get('category', '综合'))
                st.toast("已同步至广场！")
            if st.button("继续刷题 ➡️"):
                refresh_q(targets)
                st.rerun()

def refresh_q(targets):
    st.session_state.answered = False
    st.session_state.question_id = str(uuid.uuid4())
    
    # 确定生成的重点
    target_focus = random.choice(targets) if targets else None
    
    with st.spinner("AI 教练正在命题..."):
        # 优先检测共享库是否有匹配
        if random.random() < 0.2:
            shared_q = get_random_shared_question()
            if shared_q:
                shared_q["from_community"] = True
                st.session_state.current_q = shared_q
                st.session_state.start_time = time.time()
                return

        # AI 动态命题
        if target_focus == "病句诊断":
            res = generate_ai_question(None, "grammar")
        elif target_focus in ["3500字基础", "3500字进阶"]:
            chars = chars_lib.get('chars', [])
            # 基础取前 1500，进阶取后 2000
            char_pool = chars[:1500] if "基础" in target_focus else chars[1500:]
            res = generate_ai_question(random.choice(char_pool), "discovery")
        else:
            # 课内板块精准抽取
            pool = assets_db.get('content', [])
            # 这里的 items 只是素材，由 AI 根据 target_focus 决定出什么题
            items = random.sample(pool, min(len(pool), 3))
            res = generate_ai_question(items, "precise")
        
        st.session_state.current_q = res
        st.session_state.start_time = time.time()

# --- 2. 深度画像 3.0：四轴对齐与象限背景 ---
def dashboard_v3_page():
    st.header("📊 深度能力画像 3.0")
    logs = get_user_all_logs(st.session_state.user.id)
    if not logs: st.info("数据分析中..."); return
    
    df = pd.DataFrame(logs)
    
    # --- 指标卡 ---
    acc = (df['is_correct'].sum() / len(df)) * 100
    avg_t = df['time_spent'].mean()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("累计刷题", f"{len(df)}")
    c2.metric("综合正确率", f"{acc:.1f}%")
    c3.metric("平均用时", f"{avg_t:.1f}s")
    c4.metric("今日热度", f"{len(df[pd.to_datetime(df['created_at']).dt.date == datetime.now().date()])}")

    st.divider()

    # --- 能力罗盘：强制 4 个轴对齐 ---
    r_c1, r_c2 = st.columns(2)
    with r_c1:
        # 定义固定轴：字音、成语、病句、字形
        fixed_cats = ["字音", "成语", "病句", "字形"]
        cat_stats = df.groupby('category')['is_correct'].mean().to_dict()
        radar_values = [cat_stats.get(cat, 0) * 100 for cat in fixed_cats]
        
        fig_radar = go.Figure(data=go.Scatterpolar(
            r=radar_values, theta=fixed_cats, fill='toself', line_color='#1e3a8a'
        ))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), title="🏹 四轴闭环能力地图")
        st.plotly_chart(fig_radar, use_container_width=True)

    with r_c2:
        # 象限分析：带辅助线
        sc_df = df.groupby('category').agg({'is_correct': 'mean', 'time_spent': 'mean'}).reset_index()
        fig_scatter = px.scatter(sc_df, x='time_spent', y='is_correct', text='category', size_max=40, title="⚡ 表现与效率分布")
        fig_scatter.add_vline(x=avg_t, line_dash="dash", line_color="gray")
        fig_scatter.add_hline(y=acc/100, line_dash="dash", line_color="gray")
        st.plotly_chart(fig_scatter, use_container_width=True)

    # --- 3. 智能导出建议 ---
    st.subheader("📓 导出个性化复习建议")
    # 生成建议文本
    advice = "### 🛡️ 智能提分建议\n"
    for cat in fixed_cats:
        score = cat_stats.get(cat, 0) * 100
        if score < 60:
            advice += f"- **{cat}专项**：当前正确率仅 {score:.1f}%，处于盲区。建议回归课本，重点梳理该板块基础逻辑。\n"
        elif score > 85:
            advice += f"- **{cat}优势**：表现优异（{score:.1f}%），请继续保持！\n"
    
    st.info(advice)
    if st.button("📥 下载完整复习建议文档"):
        st.download_button("确认下载", advice, file_name="Zhongkao_Advice.md")

# --- 社区广场逻辑保持 ---
def community_page():
    st.header("🏰 社区共享广场")
    t1, t2 = st.tabs(["精选题库", "全站错题"])
    with t1:
        for q in get_community_selected():
            with st.container():
                st.markdown(f"**[{q['category']}]** {q['question']}")
                if st.button(f"挑战此题", key=f"c_{q['id']}"):
                    q["from_community"] = True
                    st.session_state.current_q = q; st.rerun()

if __name__ == "__main__":
    main()
