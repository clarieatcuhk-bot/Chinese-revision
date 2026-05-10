import streamlit as st
import pandas as pd
import plotly.express as px
import uuid
import time
import random
import json
from database import sign_in, sign_up_and_login, get_profile, log_quiz_result, get_user_logs
from ai_engine import generate_ai_question, sanitize_question

# --- v2.6 稳定版配置 ---
st.set_page_config(
    page_title="Zhongkao-Navigator v2.6",
    page_icon="🛡️",
    layout="centered"
)

# --- 渲染样式 ---
st.markdown("""
<style>
    .main { background-color: #f7f9f7; }
    u {
        text-decoration: none;
        border-bottom: 2px dotted #2e7d32; 
        font-weight: bold;
    }
    .stMetric { background-color: white; padding: 15px; border-radius: 12px; border: 1px solid #e1e8e1; }
    .warning-card { background-color: #fffbe6; border: 1px solid #ffe58f; padding: 1rem; border-radius: 8px; color: #856404; margin-bottom: 1rem; }
    /* 隐藏登录状态下的某些多余元素 */
</style>
""", unsafe_allow_html=True)

# --- Session State 核心管理 ---
if 'user' not in st.session_state: st.session_state.user = None
if 'user_profile' not in st.session_state: st.session_state.user_profile = None
if 'current_q' not in st.session_state: st.session_state.current_q = None
if 'question_id' not in st.session_state: st.session_state.question_id = str(uuid.uuid4())
if 'answered' not in st.session_state: st.session_state.answered = False
if 'start_time' not in st.session_state: st.session_state.start_time = 0

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

# --- 认证界面渲染 ---
def show_auth_page():
    st.title("🛡️ 中考语文导航")
    st.markdown("### 欢迎使用提分神器")
    
    t1, t2 = st.tabs(["🔑 账号登录", "📝 快速注册"])
    
    with t1:
        u = st.text_input("用户名 (邮箱)", key="l_u")
        p = st.text_input("密码", type="password", key="l_p")
        if st.button("立即登录", use_container_width=True):
            with st.spinner("验证中..."):
                res, err = sign_in(u, p)
                if err: 
                    st.error(f"登录失败: {err}")
                elif res and res.user:
                    st.session_state.user = res.user
                    st.session_state.user_profile = get_profile(res.user.id)
                    st.success("登录成功！跳转中...")
                    time.sleep(0.5)
                    st.rerun()
                
    with t2:
        ru = st.text_input("新用户名", key="r_u")
        rp = st.text_input("设置密码", type="password", key="r_p")
        rn = st.text_input("真实姓名", key="r_n")
        rc = st.text_input("班级", key="r_c")
        if st.button("确认注册并进入", use_container_width=True):
            with st.spinner("创建账户中..."):
                user, err = sign_up_and_login(ru, rp, rn, rc)
                if err: 
                    st.error(f"注册失败: {err}")
                else:
                    st.session_state.user = user
                    st.session_state.user_profile = get_profile(user.id)
                    st.success("注册成功！")
                    time.sleep(0.5)
                    st.rerun()

# --- 主程序渲染 ---
def show_app_page():
    user = st.session_state.user
    profile = st.session_state.user_profile
    
    # 如果 profile 丢失，重新获取一次
    if profile is None:
        st.session_state.user_profile = get_profile(user.id)
        profile = st.session_state.user_profile

    # 侧边栏
    with st.sidebar:
        st.title("🛡️ 导航控制台")
        st.write(f"👤 **{profile.get('name', '同学') if profile else '同学'}**")
        st.caption(f"📍 {profile.get('class_name', '基础班') if profile else '中考冲刺'}")
        st.divider()
        page = st.radio("功能模块", ["📖 专项刷题", "📊 错题看板"])
        if st.button("安全退出", use_container_width=True):
            st.session_state.user = None
            st.session_state.user_profile = None
            st.rerun()

    if page == "📖 专项刷题":
        brush_ui()
    else:
        dashboard_ui()

def brush_ui():
    st.header("智能提分专项")
    
    c1, c2 = st.columns([3, 1])
    with c1:
        mode = st.radio("请选择训练模式：", ["课内精准", "全量字库", "病句专项"], horizontal=True)
    with c2:
        if st.button("✨ 换一题", use_container_width=True) or st.session_state.current_q is None:
            refresh_question(mode)
            st.rerun()

    q = st.session_state.current_q
    if q:
        if "error" in q:
            st.error(f"⚠️ {q['error']}")
            if st.button("重新生成"):
                refresh_question(mode)
                st.rerun()
            return

        # 渲染题干
        st.markdown(f"### {q['question']}", unsafe_allow_html=True)
        
        # 计时器逻辑 (45s 警告)
        if st.session_state.answered and not st.session_state.is_correct:
            elapsed = st.session_state.end_time - st.session_state.start_time
            if elapsed > 45:
                st.markdown("<div class='warning-card'>🚨 效率预警：该题耗时过长且回答错误，说明此考点存在逻辑盲区。</div>", unsafe_allow_html=True)

        # 渲染选项
        opts = q['options']
        ans = st.radio(
            "选择答案：",
            ["A", "B", "C", "D"],
            format_func=lambda x: f"{x}. {opts.get(x, '加载中...')}",
            key=st.session_state.question_id,
            index=None,
            disabled=st.session_state.answered
        )

        if ans and not st.session_state.answered:
            st.session_state.answered = True
            st.session_state.end_time = time.time()
            is_correct = (ans == q['answer'])
            st.session_state.is_correct = is_correct
            
            # 入库
            log_quiz_result(
                st.session_state.user.id,
                mode,
                q['question'],
                ans,
                is_correct,
                st.session_state.end_time - st.session_state.start_time,
                q.get('analysis', '')
            )
            
            if is_correct:
                st.success("✅ 回答正确！")
                st.balloons()
            else:
                st.error(f"❌ 回答错误。正确答案是：{q['answer']}")

        if st.session_state.answered:
            st.markdown("---")
            st.markdown("#### 💡 深度解析")
            st.info(q['analysis'])
            if st.button("继续下一题 ➡️", use_container_width=True):
                st.session_state.current_q = None
                st.rerun()

def refresh_question(mode):
    st.session_state.answered = False
    st.session_state.question_id = str(uuid.uuid4())
    
    with st.spinner("AI 命题中..."):
        if mode == "课内精准":
            pool = assets_db.get('content', [])
            items = random.sample(pool, min(len(pool), 2))
            res = generate_ai_question(items, "precise")
        elif mode == "全量字库":
            char = random.choice(chars_lib.get('chars', ["确", "凿"]))
            res = generate_ai_question(char, "discovery")
        else:
            res = generate_ai_question(None, "grammar")
            
        st.session_state.current_q = res
        st.session_state.start_time = time.time()

def dashboard_ui():
    st.header("📊 学习画像分析")
    logs = get_user_logs(st.session_state.user.id)
    if not logs:
        st.info("尚无数据，快去刷题吧！")
        return

    df = pd.DataFrame(logs)
    c1, c2 = st.columns(2)
    with c1:
        if 'category' in df.columns:
            err_df = df[~df['is_correct']].groupby('category').size().reset_index(name='count')
            if not err_df.empty:
                fig = px.pie(err_df, values='count', names='category', title="薄弱知识点分布", hole=0.3)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("⚠️ 错题分布图需要更新数据库字段。")
            
    with c2:
        if 'time_spent' in df.columns and 'category' in df.columns:
            time_df = df.groupby('category')['time_spent'].mean().reset_index()
            fig_time = px.bar(time_df, x='category', y='time_spent', title="平均思考时长 (s)")
            st.plotly_chart(fig_time, use_container_width=True)
        else:
            st.warning("⚠️ 耗时统计图需要更新数据库字段。")

    st.divider()
    wrongs = df[~df['is_correct']].sort_values('created_at', ascending=False)
    if not wrongs.empty:
        md = "# 🛡️ 错题避雷手册\n\n"
        for _, row in wrongs.iterrows():
            q_clean = row['question'].replace("<u>", "**").replace("</u>", "**")
            md += f"### 【{row['category']}】 {q_clean}\n"
            md += f"- **正确答案**: {row['answer']}\n"
            md += f"- **逻辑解析**: {row.get('analysis', '')}\n\n---\n"
        st.download_button("📥 导出避雷手册 (Markdown)", data=md, file_name="Mistakes.md", use_container_width=True)

# --- 入口 ---
if __name__ == "__main__":
    if st.session_state.user is None:
        show_auth_page()
    else:
        show_app_page()
