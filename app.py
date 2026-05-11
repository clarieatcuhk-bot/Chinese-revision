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
    clear_user_mistakes, delete_all_logs_of_question, delete_shared_question,
    increment_challenge_stats, normalize_text, get_draft_pool, publish_draft
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
    return str(text).replace("<u>", "<span style='text-decoration: underline; color: #2563eb; font-weight: bold;'>").replace("</u>", "</span>")

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
        
        if st.session_state.challenge_q or st.session_state.redo_q:
            st.info("🎯 答题模式进行中")
            if st.button("⬅️ 强制退出"):
                st.session_state.challenge_q = None; st.session_state.redo_q = None
                st.session_state.show_challenge_box = False
                st.rerun()
            active_tab = None 
        else:
            active_tab = st.radio("系统频道", menu, key="nav_radio")
            
        st.divider()
        if st.button("退出系统"): st.session_state.user = None; st.rerun()

    if st.session_state.challenge_q: render_challenge_mode()
    elif st.session_state.redo_q: render_redo_mode()
    else:
        if active_tab == "🌟 精选题库": render_selected_questions(is_admin)
        elif active_tab == "🚩 错题挑战": render_mistake_stream(is_admin)
        elif active_tab == "⚡ 极速特训": render_fast_training()
        elif active_tab == "🏆 荣耀金榜": render_leaderboard(is_admin)
        elif active_tab == "📊 个人画像": render_personal_dashboard()
        elif active_tab == "📖 命题实验室": render_admin_lab()

def render_selected_questions(is_admin):
    st.markdown("<div class='page-header'><h1>🌟 老师精选题库</h1><p>分门别类，高效攻克</p></div>", unsafe_allow_html=True)
    qs = get_community_selected()
    if not qs: 
        st.info("目前没有精选题目")
        return
        
    user_logs = get_user_all_logs(st.session_state.user.id)
    done_texts = {normalize_text(log.get('question', '')) for log in user_logs if log.get('question')}
        
    cats = sorted(list(set([q.get('category', '综合') for q in qs])))
    
    # 移动端终极优化：将 Tabs 替换为 Selectbox，避免同时渲染大量 DOM 节点导致手机卡顿
    selected_cat = st.selectbox("📚 选择考点大类：", cats)
    
    cat_qs = [q for q in qs if q.get('category', '综合') == selected_cat]
    
    # 限制单页显示数量，极速提升手机端渲染效率
    max_display = 20 
    for q in cat_qs[:max_display]:
        q_norm = normalize_text(q.get('question', ''))
        is_done = q_norm in done_texts
        status_badge = "<span class='status-badge-done'>✅ 已做</span>" if is_done else "<span class='status-badge-new'>🆕 未做</span>"
        
        with st.container():
            st.markdown(f"<h4>{status_badge}{format_html(q.get('question'))}</h4>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            if c1.button("立即挑战" if not is_done else "再次挑战", key=f"sel_v10_{q['id']}"):
                st.session_state.challenge_q = q; st.rerun()
                
            if is_admin:
                if c2.button("🗑️ 强力清除", key=f"del_sel_{q['id']}"):
                    delete_shared_question(q['id'])
                    st.toast("✅ 已从精选题库永久删除")
                    time.sleep(0.5); st.rerun()
            st.divider()
            
    if len(cat_qs) > max_display:
        st.info(f"👆 已为您展示最新的 {max_display} 道题，请先完成挑战。")

def render_mistake_stream(is_admin):
    st.markdown("<div class='page-header'><h1>🚩 全站连斩错题流</h1><p>全站高频易错点集结</p></div>", unsafe_allow_html=True)
    mk = get_public_mistakes_with_kills()
    if not mk: 
        st.success("目前全站没有精选错题。去精选题库试试身手吧！")
        return
        
    cats = sorted(list(set([m.get('category', '综合') for m in mk])))
    
    # 移动端优化：Selectbox 替代 Tabs
    selected_cat = st.selectbox("📚 选择薄弱考点：", cats)
    
    cat_mk = [m for m in mk if m.get('category', '综合') == selected_cat]
    
    max_display = 20
    for m in cat_mk[:max_display]:
        st.markdown(f"<div class='mistake-card'><span class='kill-badge'>⚔️ 连斩 {m.get('kill_count', 1)} 人</span> <span style='font-weight:500;'>{format_html(m.get('question'))}</span></div>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        if c1.button("终结此题", key=f"mk_v10_{m.get('id', random.random())}"):
            st.session_state.challenge_q = m; st.rerun()
            
        if is_admin:
            if c2.button("🗑️ 拔除错题", key=f"del_mk_{m.get('id', random.random())}"):
                delete_all_logs_of_question(m.get('question'))
                st.toast("✅ 该错题已从全站记录中抹除")
                time.sleep(0.5); st.rerun()
        st.write("") 
        
    if len(cat_mk) > max_display:
        st.info(f"👆 错题较多，当前仅展示最具挑战性的 {max_display} 题。")

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
    axes = ["字音辨析", "成语运用", "病句诊断", "字形纠错", "3500字基础"]
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
                if st.button("🔥 涅槃重练", key=f"redo_v10_{random.random()}"):
                    st.session_state.redo_q = m.to_dict(); st.rerun()
        else: st.success("干得漂亮！错题集目前是空的。")

def render_admin_lab():
    st.markdown("<div class='page-header'><h1>📖 命题实验室</h1><p>工业级自动化刷题审核流水线</p></div>", unsafe_allow_html=True)
    
    cats = ["字音辨析", "成语运用", "病句诊断", "字形纠错", "3500字基础", "文学常识与传统文化"]
    sel_cat = st.selectbox("🎯 选择审核流水线考点：", cats)
    
    # 动态补货算法 (Dynamic Refill)
    if 'refill_lock' not in st.session_state: st.session_state.refill_lock = False
    
    drafts = get_draft_pool(sel_cat)
    draft_count = len(drafts)
    
    c1, c2 = st.columns([3, 1])
    c1.markdown(f"**当前【{sel_cat}】缓冲池余量: `{draft_count}` 题**")
    if c2.button("🔄 刷新池子", use_container_width=True): st.rerun()
    
    if draft_count < 10 and not st.session_state.refill_lock:
        st.session_state.refill_lock = True
        needed = 3 * (10 - draft_count)
        fetch_count = min(needed, 5) # 每次最多批量 5 题防超时
        st.toast(f"🚨 池子告急！AI 正在后台静默补货 {fetch_count} 题...")
        
        def _refill(category, count):
            try:
                new_qs = generate_ai_question_batch(category, count)
                for q in new_qs:
                    share_to_community(q, f"DRAFT_{category}", "admin_system")
            except: pass
            finally:
                st.session_state.refill_lock = False
                
        import threading
        t = threading.Thread(target=_refill, args=(sel_cat, fetch_count), daemon=True)
        try:
            from streamlit.runtime.scriptrunner import add_script_run_ctx
            add_script_run_ctx(t)
        except: pass
        t.start()
        
    st.divider()
    
    # 老师审核流水线 (Audit UI)
    if drafts:
        q = drafts[0]
        q_text = q.get('question', '')
        opts = ensure_dict(q.get('options', {}))
        
        st.markdown(f"<div style='background-color:#f0fdf4; padding: 15px; border-radius: 8px; border-left: 5px solid #22c55e; margin-bottom: 15px;'><h3>{format_html(q_text)}</h3></div>", unsafe_allow_html=True)
        
        for k in ["A", "B", "C", "D"]:
            v = opts.get(k) or opts.get(k.lower())
            if v: st.write(f"**{k}.** {v}")
                
        st.success(f"✅ 正确答案：{q.get('answer')}")
        st.info(f"💡 解析：{q.get('analysis')}")
            
        col1, col2 = st.columns(2)
        if col1.button("✅ 完美无瑕，通过并入库！", use_container_width=True): 
            publish_draft(q['id'], sel_cat)
            st.toast("入库成功！下一题已自动加载。")
            time.sleep(0.3)
            st.rerun()
            
        if col2.button("🗑️ 逻辑不通，直接报废", use_container_width=True):
            delete_shared_question(q['id'])
            st.toast("已物理删除，下一题已加载。")
            time.sleep(0.3)
            st.rerun()
    else:
        st.info("🕒 当前分类的缓冲池已空，AI 正在后台紧急加班出题中... 请稍候刷新！")

def render_fast_training():
    st.markdown("<div class='page-header'><h1>⚡ 极速特训</h1><p>智能出题引擎，零延迟连刷体验</p></div>", unsafe_allow_html=True)
    
    cats = ["字音辨析", "成语运用", "病句诊断", "字形纠错", "3500字基础", "文学常识与传统文化"]
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

def get_option_label(opts, key):
    val = opts.get(key) or opts.get(key.lower())
    return f"{key}. {val}" if val else key

def render_challenge_mode():
    q = st.session_state.challenge_q
    st.markdown("<div class='page-header'><h1>🎯 挑战正在进行</h1></div>", unsafe_allow_html=True)
    
    q_text = q.get('question') or q.get('question_text') or "数据异常"
    opts = ensure_dict(q.get('options', {}))
    
    st.markdown(f"<div style='background-color:#eff6ff; padding: 15px; border-radius: 8px; border-left: 5px solid #3b82f6; margin-bottom: 20px;'><h4 style='line-height:1.5;'>{format_html(q_text)}</h4></div>", unsafe_allow_html=True)
    
    ans = st.radio("请选择答案：", ["A", "B", "C", "D"], format_func=lambda x: get_option_label(opts, x), key="act_v10", index=None)
    st.write("")
    
    c1, c2 = st.columns(2)
    if ans and c1.button("确认提交"):
        log_quiz_result(st.session_state.user.id, q.get('category', '综合'), q, ans, (ans == q.get('answer')), 5.0)
        if ans == q.get('answer'): st.success("🎉 正确！"); st.balloons()
        else: st.error(f"❌ 错误。正确答案是：{q.get('answer')}")
        st.info(f"💡 解析：{q.get('analysis')}")
    
    if c2.button("⬅️ 退出挑战"):
        st.session_state.challenge_q = None
        st.session_state.show_challenge_box = False
        st.rerun()
        
    st.write("")
    if st.button("🚨 质疑 AI"):
        st.session_state.show_challenge_box = True
        
    if st.session_state.get('show_challenge_box'):
        st.divider()
        st.markdown("### 🚨 发起质疑")
        reason = st.text_area("告诉AI错在哪里（答案错、超纲、解析离谱）：")
        if st.button("提交给最高评判网络"):
            with st.spinner("🧠 判官模型重新推演中..."):
                try:
                    success, reply = evaluate_challenge(q, reason)
                except Exception as e:
                    success, reply = False, f"调用异常：{e}"
                    
                increment_challenge_stats(st.session_state.user.id, success)
                
                if success:
                    st.success(f"🎉 判官大人英明！已记录在榜！AI回复：{reply}")
                else:
                    st.error(f"❌ 证据不足，驳回！AI回复：{reply}")

def render_redo_mode():
    q = st.session_state.redo_q
    st.markdown("<div class='page-header'><h1>🔥 错题涅槃练习</h1></div>", unsafe_allow_html=True)
    
    q_text = q.get('question') or q.get('question_text') or "数据异常"
    opts = ensure_dict(q.get('options', {}))
    
    st.markdown(f"<div style='background-color:#fffbeb; padding: 15px; border-radius: 8px; border-left: 5px solid #f59e0b; margin-bottom: 20px;'><h4 style='line-height:1.5;'>{format_html(q_text)}</h4></div>", unsafe_allow_html=True)
    
    ans = st.radio("重选答案：", ["A", "B", "C", "D"], format_func=lambda x: get_option_label(opts, x), key="redo_v10", index=None)
    st.write("")
    
    c1, c2 = st.columns(2)
    if ans and c1.button("确认提交"):
        log_quiz_result(st.session_state.user.id, q.get('category'), q, ans, (ans == q.get('answer')), 5.0)
        if ans == q.get('answer'): st.success("🎉 涅槃成功！新记录已同步"); st.balloons()
        else: st.error("仍然错误，请继续复习。")
    
    if c2.button("⬅️ 返回错题本"):
        st.session_state.redo_q = None
        st.session_state.show_challenge_box = False
        st.rerun()

if __name__ == "__main__":
    main()
# Force redeploy
