import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import time
import random
import json
import re
from db_core import (
    sign_in, sign_up_and_login, get_profile, log_quiz_result, 
    get_user_all_logs, share_to_community, get_community_selected, 
    get_public_mistakes_with_kills, get_leaderboard_data, 
    clear_user_mistakes, delete_all_logs_of_question, delete_shared_question,
    increment_challenge_stats, normalize_text, get_draft_pool, publish_draft, get_admin_uuid,
    add_to_draft_pool, delete_draft, clean_draft_pool_data
)
from ai_engine import generate_ai_question, evaluate_challenge, generate_ai_question_batch

# --- v10.12 极致移动端优化版 ---
st.set_page_config(page_title="Zhongkao-Navigator Pro v10.12", page_icon="💎", layout="wide")

# --- UI 样式 (专门针对移动端优化间距和按钮宽度) ---
st.markdown("""
<style>
    .page-header { background: linear-gradient(135deg, #0f172a, #3b82f6); color: white; padding: 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    .page-header h1 { font-size: 1.8rem; margin-bottom: 5px; }
    .kill-badge { background: #ef4444; color: white; padding: 3px 10px; border-radius: 12px; font-weight: bold; font-size: 0.8rem; margin-right: 8px; white-space: nowrap; }
    .admin-badge { background: #dc2626; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; }
    .mistake-card { background: var(--secondary-background-color); padding: 12px; border-radius: 8px; margin-bottom: 12px; border: 1px solid var(--border-color); }
    .status-badge-done { background:#10b981; color:white; padding:2px 8px; border-radius:12px; font-size:0.8rem; vertical-align:middle; margin-right:8px; white-space: nowrap; }
    .status-badge-new { background:#f59e0b; color:white; padding:2px 8px; border-radius:12px; font-size:0.8rem; vertical-align:middle; margin-right:8px; white-space: nowrap; }
    /* 移动端优化：减少按钮边距，增强点击区 */
    div.stButton > button { width: 100%; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

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
    text = str(text)
    import re
    # 截断题干中可能混入的 "A. xxx B. xxx" 选项文本
    match = re.search(r'(\n|<br>)?\s*A[．、.]\s', text)
    if match:
        text = text[:match.start()].strip()
    return text.replace("<u>", "<span style='text-decoration: underline; color: #2563eb; font-weight: bold;'>").replace("</u>", "</span>")

def format_analysis(text):
    if not text: return ""
    text = str(text)
    import re
    match = re.search(r'<!-- KP: (.*?) -->', text)
    if match:
        kp = match.group(1)
        text = text.replace(match.group(0), f"\n\n**🏷️ 核心知识点**：`{kp}`")
    return text

def ensure_dict(obj):
    return obj if isinstance(obj, dict) else {}

@st.cache_resource
def start_global_daemon():
    class WorkerInfo:
        def __init__(self):
            self.status = "初始化"
            self.last_run = "未运行"
            self.total_generated = 0
            self.total_discarded = 0
            self.hit_rate = 0.0
            self.inventory = {}
            
    info = WorkerInfo()
    import threading
    import time
    from db_core import get_admin_uuid, get_draft_pool, add_to_draft_pool
    from ai_engine import generate_ai_question_batch
    import re
    
    def _daemon():
        admin_id = get_admin_uuid()
        cats = ["字音", "字形", "病句", "成语"]
        
        info.status = "执行启动期数据库热洗 (Hot Wash)..."
        clean_draft_pool_data()
        
        while True:
            info.status = "扫描全站题库..."
            for cat in cats:
                drafts = get_draft_pool(cat)
                x = len(drafts)
                info.inventory[cat] = x
                if x < 10:
                    info.status = f"正在为【{cat}】智能补货..."
                    needed = 3 * (10 - x)
                    fetch_count = min(needed, 2)
                    
                    recent_kps = []
                    for d in drafts[:10]:
                        match = re.search(r'<!-- KP: (.*?) -->', d.get('analysis', ''))
                        if match: recent_kps.append(match.group(1))
                    
                    try:
                        new_qs = generate_ai_question_batch(cat, fetch_count, recent_kps)
                        for q in new_qs:
                            info.total_generated += 1
                            kp = q.get('knowledge_point', '')
                            if kp and kp in recent_kps:
                                info.total_discarded += 1
                                continue
                            if add_to_draft_pool(q):
                                info.inventory[cat] = info.inventory.get(cat, 0) + 1
                    except Exception as e:
                        print(f"Daemon error: {e}")
            
            if info.total_generated > 0:
                info.hit_rate = (info.total_discarded / info.total_generated) * 100
                
            info.status = "休眠中 (等待下一轮扫描)"
            import datetime
            bj_tz = datetime.timezone(datetime.timedelta(hours=8))
            info.last_run = datetime.datetime.now(bj_tz).strftime("%H:%M:%S")
            time.sleep(300)
            
    t = threading.Thread(target=_daemon, daemon=True)
    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx
        add_script_run_ctx(t)
    except: pass
    t.start()
    return info

worker_info = start_global_daemon()

# --- Session State ---
if 'user' not in st.session_state: st.session_state.user = None
if 'challenge_q' not in st.session_state: st.session_state.challenge_q = None
if 'redo_q' not in st.session_state: st.session_state.redo_q = None
if 'show_challenge_box' not in st.session_state: st.session_state.show_challenge_box = False

def main():
    if st.session_state.user is None: show_auth()
    else: app_shell()

def show_auth():
    st.markdown("<h2 style='text-align:center;'>💎 语文导航 Pro</h2>", unsafe_allow_html=True)
    t = st.tabs(["🔑 登录", "📝 注册"])
    with t[0]:
        u = st.text_input("账号 ID")
        p = st.text_input("登录密码", type="password")
        if st.button("进入系统", use_container_width=True):
            res, err = sign_in(u.strip(), p)
            if not err: st.session_state.user = res.user; st.rerun()
            else: st.error(f"登录失败: {err}")
    with t[1]:
        ru = st.text_input("注册账号")
        rp = st.text_input("设置密码", type="password")
        rn = st.text_input("显示姓名")
        rc = st.text_input("班级")
        if st.button("立即加入", use_container_width=True):
            user, err = sign_up_and_login(ru.strip(), rp, rn.strip(), rc.strip())
            if not err: st.session_state.user = user; st.rerun()
            else: st.error(f"注册失败: {err}")

def app_shell():
    user = st.session_state.user
    profile = get_profile(user.id) or {"name": "新同学"}
    acc = str(profile.get('account_name', user.email.split('@')[0])).lower()
    
    name_str = str(profile.get('name', '')).lower()
    is_admin = ('zhoumingen' in acc) or ('周铭恩' in name_str) or ('hongyi' in acc and any(c.isdigit() for c in acc))
    
    with st.sidebar:
        st.markdown(f"### 👋 {profile['name']} " + ("<span class='admin-badge'>ADMIN</span>" if is_admin else ""), unsafe_allow_html=True)
        menu = ["🌟 精选题库", "🚩 错题挑战", "⚡ 极速特训", "🏆 荣耀金榜", "📊 个人画像"]
        if is_admin: menu.insert(0, "📖 命题实验室")
        
        active_tab = st.radio("系统频道", menu, key="nav_radio")
        
        st.divider()
        if st.button("退出系统"): st.session_state.user = None; st.rerun()

    if active_tab == "🌟 精选题库": render_selected_questions(is_admin)
    elif active_tab == "🚩 错题挑战": render_mistake_stream(is_admin)
    elif active_tab == "⚡ 极速特训": render_fast_training()
    elif active_tab == "🏆 荣耀金榜": render_leaderboard(is_admin)
    elif active_tab == "📊 个人画像": render_personal_dashboard()
    elif active_tab == "📖 命题实验室": render_admin_lab()

def get_option_label(opts, key):
    val = opts.get(key) or opts.get(key.lower())
    if not val: return key
    import re
    # Streamlit radio 不支持原生 HTML 标签，因此将 <u> 转换为 Markdown 加粗
    val = re.sub(r'<\/?u[^>]*>', '**', str(val), flags=re.IGNORECASE)
    return f"{key}. {val}"

def render_selected_questions(is_admin):
    st.markdown("<div class='page-header'><h1>🌟 老师精选题库</h1><p>全自动答题流水线，攻克未做题目</p></div>", unsafe_allow_html=True)
    qs = get_community_selected()
    if not qs: 
        st.info("目前没有精选题目")
        return
        
    user_logs = get_user_all_logs(st.session_state.user.id)
    done_texts = {normalize_text(log.get('question', '')) for log in user_logs if log.get('question')}
    
    cats = ["字音", "字形", "病句", "成语"]
    c1, c2 = st.columns([3, 1])
    with c1:
        selected_cat = st.selectbox("📚 选择考点大类：", cats)
    with c2:
        st.write("")
        st.write("")
        if st.button("🔄 同步最新题库", use_container_width=True):
            st.session_state.unattempted_queue = [q for q in qs if q.get('category', '综合') == selected_cat and normalize_text(q.get('question', '')) not in done_texts]
            st.rerun()
            
    cat_qs = [q for q in qs if q.get('category', '综合') == selected_cat]
    total_count = len(cat_qs)
    done_list = [q for q in cat_qs if normalize_text(q.get('question', '')) in done_texts]
    done_count = len(done_list)
    
    st.progress(done_count / total_count if total_count > 0 else 0.0)
    st.caption(f"🎯 当前模块进度：已掌握 {done_count} 题 / 共 {total_count} 题")
    
    with st.expander("👀 查看已完成题目总览"):
        if not done_list:
            st.info("暂无已完成的题目")
        else:
            for idx, dq in enumerate(done_list):
                st.markdown(f"**{idx+1}.** {format_html(dq.get('question'))}", unsafe_allow_html=True)
    st.divider()
    
    # 构建 unattempted_list
    if 'unattempted_queue' not in st.session_state or st.session_state.get('last_sel_cat') != selected_cat:
        st.session_state.unattempted_queue = [q for q in cat_qs if normalize_text(q.get('question', '')) not in done_texts]
        st.session_state.last_sel_cat = selected_cat
        st.session_state.last_question_review = None
        
    queue = st.session_state.unattempted_queue
    
    if not queue:
        st.session_state.last_question_review = None
        st.success("🎉 恭喜！当前模块已通关，请前往【个人画像】查看今日能力报告。")
        return
        
    q = queue[0]
    q_text = q.get('question', '')
    opts = ensure_dict(q.get('options', {}))
    
    state_key = f"sel_submitted_{q['id']}"
    if state_key not in st.session_state:
        st.session_state[state_key] = False
    st.markdown(f"<div style='background-color:#eff6ff; padding: 15px; border-radius: 8px; border-left: 5px solid #3b82f6; margin-bottom: 20px;'><h4 style='line-height:1.5;'>{format_html(q_text)}</h4></div>", unsafe_allow_html=True)
    
    ph_ans = st.empty()
    ans = ph_ans.radio("请选择答案：", ["A", "B", "C", "D"], format_func=lambda x: get_option_label(opts, x), key=f"sel_rad_{q['id']}", disabled=st.session_state[state_key], index=None)
    st.write("")
    
    ph_btn = st.empty()
    
    if not st.session_state[state_key]:
        def on_submit():
            if ans:
                st.session_state[state_key] = True
                is_correct = (ans == q.get('answer'))
                st.session_state[f"sel_correct_{q['id']}"] = is_correct
                log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q, ans, is_correct, 5.0)
                
        ph_btn.button("提交答案 🎯", on_click=on_submit, use_container_width=True, disabled=(not ans))
    else:
        is_correct = st.session_state.get(f"sel_correct_{q['id']}")
        if is_correct:
            st.success("🎉 **回答正确！**")
        else:
            st.error(f"❌ **回答错误**。正确答案是 **{q.get('answer')}**。")
        st.info(f"💡 解析：\n{format_analysis(q.get('analysis'))}")
        
        def on_next():
            st.session_state.unattempted_queue.pop(0)
            if not st.session_state.unattempted_queue:
                st.session_state.nav_radio = "📊 个人画像"
                
        ph_btn.button("确认并进入下一题 ⏭️", on_click=on_next, use_container_width=True, type="primary")
        
    if is_admin:
        st.divider()
        if st.button("🗑️ 强力清除此题 (管理员)", key=f"del_sel_{q['id']}"):
            delete_shared_question(q['id'])
            st.session_state.unattempted_queue.pop(0)
            st.toast("✅ 已从精选题库永久删除")
            time.sleep(0.5); st.rerun()

def render_mistake_stream(is_admin):
    st.markdown("<div class='page-header'><h1>🚩 错题重练</h1><p>直击软肋，查漏补缺</p></div>", unsafe_allow_html=True)
    
    user_logs = get_user_all_logs(st.session_state.user.id)
    # 筛选曾经错过的题目
    mistakes = [log for log in user_logs if log.get('is_correct') is False]
    
    if not mistakes: 
        st.success("🎉 目前没有错题记录，太棒了！去精选题库挑战一下吧！")
        return
        
    # 去重并提取分类
    sh_qs = get_community_selected(limit=2000)
    sh_map = {normalize_text(q.get('question', '')): q for q in sh_qs}
    
    seen = set()
    uniq_mistakes = []
    for m in reversed(mistakes): # 按时间倒序或正序，此处倒序保证最近的先练
        q_text_raw = str(m.get('question', ''))
        q_text = normalize_text(q_text_raw)
        if q_text and q_text not in seen:
            seen.add(q_text)
            
            opts = ensure_dict(m.get('options', {}))
            ans = m.get('answer')
            analysis = m.get('analysis')
            
            # 容错降级：如果 user_logs 丢失了选项（因为部分用户旧表没这列），从全站题库里“借”回来
            if q_text in sh_map:
                std_q = sh_map[q_text]
                if not opts: opts = ensure_dict(std_q.get('options', {}))
                if not ans: ans = std_q.get('answer')
                if not analysis: analysis = std_q.get('analysis')
                q_text_raw = std_q.get('question', q_text_raw) # 顺便借用可能带有富文本的完美题干
            
            q_data = {
                "id": m.get('id'),
                "question": q_text_raw,
                "options": opts,
                "answer": ans,
                "analysis": analysis
            }
            uniq_mistakes.append((m.get('category', '综合'), q_data, m.get('id')))
            
    cats = ["字音", "字形", "病句", "成语"]
    selected_cat = st.selectbox("📚 选择薄弱考点：", cats)
    
    if 'review_queue' not in st.session_state or st.session_state.get('last_mis_cat') != selected_cat:
        st.session_state.review_queue = [q for cat, q, _ in uniq_mistakes if cat == selected_cat]
        st.session_state.last_mis_cat = selected_cat
        st.session_state.last_question_review = None
        
    queue = st.session_state.review_queue
    
    if not queue:
        st.session_state.last_question_review = None
        st.success("🎉 恭喜！当前考点错题已清空，请前往【个人画像】查看今日能力报告。")
        return
        
    q = queue[0]
    q_text = q.get('question', '')
    opts = ensure_dict(q.get('options', {}))
    
    state_key = f"mis_submitted_{q['id']}"
    if state_key not in st.session_state:
        st.session_state[state_key] = False
        
    ph_ans = st.empty()
    ans = ph_ans.radio("重选答案：", ["A", "B", "C", "D"], format_func=lambda x: get_option_label(opts, x), key=f"redo_rad_{q['id']}", disabled=st.session_state[state_key], index=None)
    st.write("")
    
    ph_btn = st.empty()
    
    if not st.session_state[state_key]:
        def on_submit_mistake():
            if ans:
                st.session_state[state_key] = True
                is_correct = (ans == q.get('answer'))
                st.session_state[f"mis_correct_{q['id']}"] = is_correct
                log_quiz_result(st.session_state.user.id, selected_cat, q, ans, is_correct, 5.0)
                
        ph_btn.button("提交答案 🎯", on_click=on_submit_mistake, use_container_width=True, disabled=(not ans))
    else:
        is_correct = st.session_state.get(f"mis_correct_{q['id']}")
        if is_correct:
            st.success("🎉 **涅槃成功！新记录已同步。**")
        else:
            st.error(f"❌ **仍然错误**。正确答案是 **{q.get('answer')}**。")
        st.info(f"💡 解析：\n{format_analysis(q.get('analysis'))}")
        
        def on_next_mistake():
            st.session_state.review_queue.pop(0)
            if not st.session_state.review_queue:
                st.session_state.nav_radio = "📊 个人画像"
                
        ph_btn.button("确认并进入下一题 ⏭️", on_click=on_next_mistake, use_container_width=True, type="primary")

def render_leaderboard(current_user_is_admin):
    st.markdown("<div class='page-header'><h1>🏆 七维荣耀金榜</h1><p>全景竞技数据</p></div>", unsafe_allow_html=True)
    data = get_leaderboard_data()
    if not data: st.info("榜单数据加载中..."); return
    df = pd.DataFrame(data)
    
    def is_adm(row):
        a = str(row.get('account_name', '')).lower()
        n = str(row.get('name', '')).lower()
        if 'zhoumingen' in a or '周铭恩' in n: return True
        if 'hongyi' in a and any(c.isdigit() for c in a): return True
        return False
        
    df_st = df[~df.apply(is_adm, axis=1)] if not df.empty else df
    
    # 移动端优化：对于手机端，将栏目变成2列，而不是挤成3列4列
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🔥 刷题榜")
        for i, r in df_st.sort_values('total_questions', ascending=False).head(5).reset_index().iterrows():
            st.markdown(f"**{i+1}.** {r['name']} ({r['total_questions']}题)")
    with c2:
        st.markdown("### ⚔️ 战神榜")
        for i, r in df_st.sort_values('correct_questions', ascending=False).head(5).reset_index().iterrows():
            st.markdown(f"**{i+1}.** {r['name']} ({r['correct_questions']}对)")
            
    st.divider()
    
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.markdown("### 💡 贡献榜(师)")
        for i, r in df.sort_values('contributions', ascending=False).head(3).reset_index().iterrows():
            st.markdown(f"**{i+1}.** {r['name']} ({r['contributions']}次)")
    with r2c2:
        st.markdown("### ⚡ 速度榜")
        df_v = df_st[df_st['total_questions'] >= 5].copy()
        if not df_v.empty:
            df_v['v'] = (df_v['total_time'] / df_v['total_questions']).round(1)
            for i, r in df_v.sort_values('v').head(3).reset_index().iterrows(): 
                st.markdown(f"**{i+1}.** {r['name']} ({r['v']}s)")
                
    st.divider()
    
    r3c1, r3c2 = st.columns(2)
    with r3c1:
        st.markdown("### 🚩 质疑榜")
        for i, r in df_st.sort_values('challenge_count', ascending=False).head(3).reset_index().iterrows():
            st.markdown(f"**{i+1}.** {r['name']} ({r['challenge_count']}次)")
    with r3c2:
        st.markdown("### 🏆 判官榜")
        for i, r in df_st.sort_values('challenge_success_count', ascending=False).head(3).reset_index().iterrows():
            st.markdown(f"**{i+1}.** {r['name']} ({r['challenge_success_count']}次)")

def render_personal_dashboard():
    st.markdown("<div class='page-header'><h1>📊 能力画像与错题本</h1><p>AI驱动的数据中心</p></div>", unsafe_allow_html=True)
    logs = get_user_all_logs(st.session_state.user.id)
    df = pd.DataFrame(logs) if logs else pd.DataFrame(columns=['created_at', 'is_correct', 'category', 'question', 'options', 'answer', 'analysis', 'student_answer'])
    
    # 移动端优化：取消强制分栏，让图表上下排列填满屏幕
    st.markdown("### ⏱️ 状态波动图")
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
        df_clean = df.dropna(subset=['created_at']).copy()
        if not df_clean.empty:
            df_clean['created_at'] = df_clean['created_at'].dt.tz_convert('Asia/Shanghai')
            bin_stats = df_clean.groupby(df_clean['created_at'].dt.floor('10min'))['is_correct'].mean().reset_index()
            # 禁用 ModeBar 提高渲染性能
            fig_line = px.line(bin_stats, x='created_at', y='is_correct', markers=True)
            st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': False})
        else: st.info("需要更多近期答题数据")
    else: st.info("暂无做题记录，波动图将在你答题后生成。")
        
    st.markdown("### 🏹 核心罗盘")
    axes = ["字音", "字形", "病句", "成语"]
    st_v = df.groupby('category')['is_correct'].mean().to_dict() if not df.empty else {}
    radar_values = [st_v.get(a, 0)*100 for a in axes]
    fig_radar = go.Figure(data=go.Scatterpolar(r=radar_values, theta=axes, fill='toself'))
    st.plotly_chart(fig_radar, use_container_width=True, config={'displayModeBar': False})

    st.divider()
    st.markdown("### 📖 智能错题涅槃集")
    if not df.empty:
        wrongs = df[~df['is_correct']]
        if not wrongs.empty:
            latest = wrongs.sort_values('created_at', ascending=False).drop_duplicates('question')
            cats = latest['category'].unique()
            selected_wrong_cat = st.selectbox("📚 选择复习科目：", cats)
            
            # 移动端优化：仅展示选中科目的前20条错题
            for _, m in latest[latest['category'] == selected_wrong_cat].head(20).iterrows():
                st.markdown(f"<div class='mistake-card'><span style='font-weight:500;'>{format_html(m.get('question'))}</span><br><br><span style='color:#ef4444;'>❌ 回答：{m.get('student_answer', '无')}</span> | <span style='color:#10b981;'>✅ 答案：{m.get('answer')}</span></div>", unsafe_allow_html=True)
        else: st.success("干得漂亮！错题集目前是空的。")

def render_admin_lab():
    st.markdown("<div class='page-header'><h1>📖 命题实验室</h1><p>全自动去重命题流水线</p></div>", unsafe_allow_html=True)
    
    # --- 后台流水线监控面板 ---
    st.markdown("### ⚙️ 后台流水线监控面板")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("守护线程状态", worker_info.status)
    c2.metric("上次扫描", worker_info.last_run)
    c3.metric("去重命中率", f"{worker_info.hit_rate:.1f}%")
    c4.metric("生成/报废", f"{worker_info.total_generated} / {worker_info.total_discarded}")
    
    with st.expander("📦 各分类实时库存情况"):
        for k, v in worker_info.inventory.items():
            st.write(f"- **{k}**: {v} 题")
            
    st.divider()
    
    cats = ["字音", "字形", "病句", "成语"]
    sel_cat = st.selectbox("🎯 选择审核流水线考点：", cats)
    
    drafts = get_draft_pool(sel_cat)
    draft_count = len(drafts)
    
    c1, c2 = st.columns([3, 1])
    c1.markdown(f"**当前【{sel_cat}】缓冲池余量: `{draft_count}` 题**")
    if c2.button("🔄 刷新界面", use_container_width=True): st.rerun()
        
    st.divider()
    
    # 老师审核流水线 (Audit UI)
    if drafts:
        q = drafts[0]
        q_text = q.get('question', '')
        opts = ensure_dict(q.get('options', {}))
        
        st.markdown(f"<div style='background-color:#f0fdf4; padding: 15px; border-radius: 8px; border-left: 5px solid #22c55e; margin-bottom: 15px;'><h3>{format_html(q_text)}</h3></div>", unsafe_allow_html=True)
        
        for k in ["A", "B", "C", "D"]:
            if opts.get(k) or opts.get(k.lower()):
                st.markdown(get_option_label(opts, k))
                
        st.success(f"✅ 正确答案：{q.get('answer')}")
        st.info(f"💡 解析：\n{format_analysis(q.get('analysis'))}")
            
        col1, col2 = st.columns(2)
        if col1.button("✅ 完美无瑕，通过并入库！", use_container_width=True): 
            success, msg = publish_draft(q['id'], sel_cat, st.session_state.user.id)
            if success:
                if msg == "Duplicate":
                    st.toast("⚠️ 触发去重机制：该题库已存在完全相同的题目，已为您自动报废！", icon="♻️")
                    time.sleep(1.5)
                else:
                    st.toast("🎉 入库成功！下一题已自动加载。", icon="✅")
                    time.sleep(0.3)
                st.rerun()
            else:
                st.error(f"入库失败: {msg}")
            
        if col2.button("🗑️ 逻辑不通，直接报废", use_container_width=True):
            delete_draft(q['id'])
            st.toast("已物理删除，下一题已加载。")
            time.sleep(0.3)
            st.rerun()
    else:
        st.info("🕒 当前分类的缓冲池已空，守护线程将自动为您后台补货，请稍候刷新！")

def render_fast_training():
    st.markdown("<div class='page-header'><h1>⚡ 极速特训</h1><p>智能出题引擎，零延迟连刷体验</p></div>", unsafe_allow_html=True)
    
    cats = ["字音", "字形", "病句", "成语"]
    sel_cat = st.selectbox("🎯 选择特训考点：", cats)
    
    if 'fast_queue' not in st.session_state: st.session_state.fast_queue = []
    if 'is_fetching' not in st.session_state: st.session_state.is_fetching = False
    if 'fast_q_cat' not in st.session_state: st.session_state.fast_q_cat = sel_cat
    if 'current_fast_q' not in st.session_state: st.session_state.current_fast_q = None
    
    # 切换科目时清空缓冲池
    if st.session_state.fast_q_cat != sel_cat:
        st.session_state.fast_queue = []
        st.session_state.fast_q_cat = sel_cat
        st.session_state.current_fast_q = None
        
    # 后台智能预充 (保持至少 2 题在缓存池)
    if len(st.session_state.fast_queue) < 2 and not st.session_state.is_fetching:
        st.session_state.is_fetching = True
        
        def bg_fetch_ai(category):
            try:
                q = generate_ai_question(None, "precise", category)
                if q and "error" not in q:
                    st.session_state.fast_queue.append(q)
            except: pass
            finally:
                st.session_state.is_fetching = False

        import threading
        t = threading.Thread(target=bg_fetch_ai, args=(sel_cat,), daemon=True)
        try:
            from streamlit.runtime.scriptrunner import add_script_run_ctx
            add_script_run_ctx(t)
        except: pass
        t.start()
        
    if not st.session_state.current_fast_q:
        if st.button("🚀 立即开始特训", use_container_width=True):
            if st.session_state.fast_queue:
                st.session_state.current_fast_q = st.session_state.fast_queue.pop(0)
                st.rerun()
            else:
                # 混合动力降级：如果 AI 还没出来，直接秒拉精选题库
                qs = get_community_selected()
                cat_qs = [q for q in (qs or []) if q.get('category') == sel_cat]
                if cat_qs:
                    st.session_state.current_fast_q = random.choice(cat_qs)
                    st.rerun()
                else:
                    st.warning("⚡ 引擎正在预热中，请稍等 1-2 秒后再点击...")
    else:
        q = st.session_state.current_fast_q
        q_text = q.get('question') or q.get('question_text') or "数据异常"
        opts = ensure_dict(q.get('options', {}))
        
        st.markdown(f"<div style='background-color:#eff6ff; padding: 15px; border-radius: 8px; border-left: 5px solid #3b82f6; margin-bottom: 20px;'><h4 style='line-height:1.5;'>{format_html(q_text)}</h4></div>", unsafe_allow_html=True)
        ans = st.radio("请选择答案：", ["A", "B", "C", "D"], format_func=lambda x: get_option_label(opts, x), key="fast_radio", index=None)
        
        if 'fast_ans_submitted' not in st.session_state: st.session_state.fast_ans_submitted = False
        
        if not st.session_state.fast_ans_submitted:
            if ans and st.button("确认提交", use_container_width=True):
                st.session_state.fast_ans_submitted = True
                st.session_state.fast_ans_correct = (ans == q.get('answer'))
                # 日志记录已经在后台异步执行，绝不卡顿
                log_quiz_result(st.session_state.user.id, q.get('category', sel_cat), q, ans, st.session_state.fast_ans_correct, 5.0)
                st.rerun()
        else:
            if st.session_state.fast_ans_correct: st.success("🎉 漂亮，回答正确！")
            else: st.error(f"❌ 错误。正确答案是：{q.get('answer')}")
            st.info(f"💡 解析：{q.get('analysis')}")
            
            c1, c2 = st.columns(2)
            if c1.button("下一题 ⏭️", use_container_width=True):
                st.session_state.fast_ans_submitted = False
                if st.session_state.fast_queue:
                    st.session_state.current_fast_q = st.session_state.fast_queue.pop(0)
                else:
                    qs = get_community_selected()
                    cat_qs = [q for q in (qs or []) if q.get('category') == sel_cat]
                    st.session_state.current_fast_q = random.choice(cat_qs) if cat_qs else None
                st.rerun()
            if c2.button("结束特训 🛑", use_container_width=True):
                st.session_state.fast_ans_submitted = False
                st.session_state.current_fast_q = None
                st.rerun()

if __name__ == "__main__":
    main()
