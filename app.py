import streamlit as st

# 从拆分模块中导入功能
from config_manager import init_session_state, record_model_usage
from ui_components import inject_custom_css, show_settings_dialog, render_action_icons
from agent_core import run_agentic_translation

# ==================== 1. 页面初始化与 CSS 注入 ====================
st.set_page_config(
    page_title="3-Step Regulatory Translation Agent",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed"
)
inject_custom_css()
init_session_state()

# ==================== 2. 后端处理 URL 传来的操作指令 ====================
if "action" in st.query_params and "msg_idx" in st.query_params:
    action_type = st.query_params["action"]
    msg_idx = int(st.query_params["msg_idx"])
    st.query_params.clear()
    
    if action_type == "edit":
        st.session_state.editing_idx = msg_idx
        st.rerun()
    elif action_type == "rewind":
        st.session_state.pending_rewind_idx = msg_idx
        st.rerun()

# ==================== 3. 页面头部导航 ====================
header_col1, header_col2, header_col3 = st.columns([6, 3, 1])
with header_col1:
    st.title("🧬 3-Step Regulatory Translation Agent")
    curr_active_key = st.session_state.api_envs.get(st.session_state.active_env, {}).get("key", "")
    st.caption(f"{'🟢' if curr_active_key else '🔴'} 接口: `{st.session_state.active_env}`")

with header_col2:
    st.write("")
    hist_ids = [m["id"] for m in st.session_state.model_history]
    combined_models = list(dict.fromkeys(hist_ids + st.session_state.available_models))
    current_idx = combined_models.index(st.session_state.selected_model) if st.session_state.selected_model in combined_models else 0
    sel_model = st.selectbox("当前选择模型", options=combined_models, index=current_idx, label_visibility="collapsed")
    if sel_model != st.session_state.selected_model:
        record_model_usage(sel_model)
        st.rerun()

with header_col3:
    st.write("")
    if st.button("⚙️ 设置"):
        show_settings_dialog()

# ==================== 4. 侧置“品”字形主布局 ====================
left_col, right_col = st.columns([3, 7], gap="medium")
active_turn = st.session_state.messages[-1] if len(st.session_state.messages) > 0 else None

# ----------------- 左侧：Step 1 与 Step 2 面板 -----------------
with left_col:
    with st.container(height=350, border=True):
        st.markdown(f'''
        <div class="step-card-content">
            <div class="sticky-header">
                <strong>Step 1 · 初步翻译</strong>
                <p>🔵 规则：{st.session_state.active_t}</p>
            </div>
            <div class="step-body">
                {"<br>".join(active_turn["step1"].split(chr(10))) if active_turn else "<span style='color:gray;font-size:14px;'>暂无内容，发送文本后在此展示第一步初译。</span>"}
            </div>
        </div>
        ''', unsafe_allow_html=True)

    with st.container(height=350, border=True):
        st.markdown(f'''
        <div class="step-card-content">
            <div class="sticky-header">
                <strong>Step 2 · 严格审校与修订建议</strong>
                <p>🔵 规则：{st.session_state.active_r}</p>
            </div>
            <div class="step-body">
                {"<br>".join(active_turn["step2"].split(chr(10))) if active_turn else "<span style='color:gray;font-size:14px;'>暂无内容，发送文本后在此展示第二步审校结果。</span>"}
            </div>
        </div>
        ''', unsafe_allow_html=True)

# ----------------- 右侧：主页面对话流 -----------------
with right_col:
    chat_container = st.container(height=640, border=False) 
    with chat_container:
        for i, msg in enumerate(st.session_state.messages):
            # 用户气泡
            with st.chat_message("user"):
                if st.session_state.editing_idx == i:
                    edited_val = st.text_area("编辑原文", value=msg["user"], key=f"edit_area_{i}", label_visibility="collapsed")
                    ec1, ec2, _ = st.columns([1, 1, 10])
                    with ec1:
                        if st.button("✔️ 保存修改", key=f"save_edit_{i}"):
                            active_env_data = st.session_state.api_envs.get(st.session_state.active_env, {})
                            with st.spinner(f"⏳ 正在调用 {st.session_state.selected_model} 执行 3-Step 法规翻译..."):
                                s1, s2, s3, direction = run_agentic_translation(edited_val, st.session_state.selected_model, active_env_data.get("key", ""), active_env_data.get("url", ""), st.session_state.translator_profiles[st.session_state.active_t], st.session_state.reviewer_profiles[st.session_state.active_r], st.session_state.improver_profiles[st.session_state.active_i])
                                st.session_state.messages[i] = {"user": edited_val, "step1": s1, "step2": s2, "step3": s3, "model": st.session_state.selected_model, "direction": direction}
                                st.session_state.messages = st.session_state.messages[:i + 1]
                                st.session_state.editing_idx = None
                                st.rerun()
                    with ec2:
                        if st.button("✖️ 取消", key=f"cancel_edit_{i}"):
                            st.session_state.editing_idx = None
                            st.rerun()
                else:
                    st.markdown(msg["user"])
                    render_action_icons(msg["user"], i, is_user=True)

            # Agent 回复气泡
            with st.chat_message("assistant"):
                direction_note = f" | 方向: {msg['direction']}" if msg.get("direction") else ""
                st.caption(f"Model: `{msg.get('model', st.session_state.selected_model)}` | 规则: `{st.session_state.active_i}`{direction_note} · Turn #{i + 1}")
                st.markdown(msg["step3"])
                render_action_icons(msg["step3"], i, is_user=False)

        # 处理等待执行的回溯 (Rewind) 任务
        if "pending_rewind_idx" in st.session_state:
            rewind_idx = st.session_state.pending_rewind_idx
            del st.session_state["pending_rewind_idx"]
            active_env_data = st.session_state.api_envs.get(st.session_state.active_env, {})
            with st.spinner(f"⏳ 正在调用 {st.session_state.selected_model} 执行 3-Step 法规翻译..."):
                target_text = st.session_state.messages[rewind_idx]["user"]
                s1, s2, s3, direction = run_agentic_translation(target_text, st.session_state.selected_model, active_env_data.get("key", ""), active_env_data.get("url", ""), st.session_state.translator_profiles[st.session_state.active_t], st.session_state.reviewer_profiles[st.session_state.active_r], st.session_state.improver_profiles[st.session_state.active_i])
                st.session_state.messages = st.session_state.messages[:rewind_idx]
                st.session_state.messages.append({"user": target_text, "step1": s1, "step2": s2, "step3": s3, "model": st.session_state.selected_model, "direction": direction})
                st.rerun()

        st.markdown('<div id="bottom-anchor"></div>', unsafe_allow_html=True)

# ----------------- 5. 底部输入流处理 -----------------
prompt = st.chat_input("输入需要翻译的临床/法规文本...")
if prompt:
    active_env_data = st.session_state.api_envs.get(st.session_state.active_env, {})
    exec_key = active_env_data.get("key", "")
    if not exec_key:
        st.error("❌ 当前选中的接口尚未配置凭据，请点击右上角【⚙️ 设置】。")
    else:
        record_model_usage(st.session_state.selected_model)
        st.session_state.pending_new_prompt = prompt
        st.rerun()

if "pending_new_prompt" in st.session_state:
    pending_prompt = st.session_state.pending_new_prompt
    del st.session_state["pending_new_prompt"]
    
    active_env_data = st.session_state.api_envs.get(st.session_state.active_env, {})
    with chat_container:
        with st.chat_message("user"):
            st.markdown(pending_prompt)
        with st.chat_message("assistant"):
            with st.spinner(f"⏳ 正在调用 {st.session_state.selected_model} 执行 3-Step 法规翻译..."):
                s1, s2, s3, direction = run_agentic_translation(pending_prompt, st.session_state.selected_model, active_env_data.get("key", ""), active_env_data.get("url", ""), st.session_state.translator_profiles[st.session_state.active_t], st.session_state.reviewer_profiles[st.session_state.active_r], st.session_state.improver_profiles[st.session_state.active_i])
                st.session_state.messages.append({"user": pending_prompt, "step1": s1, "step2": s2, "step3": s3, "model": st.session_state.selected_model, "direction": direction})
                st.rerun()
