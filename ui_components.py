# ui_components.py
import json
import streamlit as st
import streamlit.components.v1 as components
from api_client import fetch_openai_models
from config_manager import save_config, record_model_usage, PROFILE_SCHEMA_VERSION
from prompts import DEFAULT_PROFILE_NAME

def inject_custom_css():
    st.markdown("""
    <style>
        .block-container { max-width: 96% !important; padding-top: 1.5rem !important; padding-left: 1.5rem !important; padding-right: 1.5rem !important; padding-bottom: 0 !important; }
        ::-webkit-scrollbar { display: none !important; }
        * { -ms-overflow-style: none !important; scrollbar-width: none !important; }
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) { flex-direction: row-reverse; text-align: right; }
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stMarkdownContainer"] { background-color: #e8f0fe; color: #1a73e8; padding: 12px 16px; border-radius: 16px 4px 16px 16px; display: inline-block; text-align: left; }
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stMarkdownContainer"] { background-color: #f1f3f4; color: #202124; padding: 12px 16px; border-radius: 4px 16px 16px 16px; display: inline-block; }
        .st-emotion-cache-1wivap2 { padding: 0 !important; } 
        .step-card-content { padding: 1rem; overflow-y: auto; height: 100%; }
        .sticky-header { position: sticky; top: 0; background-color: white; z-index: 10; border-bottom: 1px solid #e0e0e0; padding-bottom: 8px; margin-bottom: 12px; }
        .sticky-header p { margin: 0 !important; font-size: 0.9rem; color: #5f6368; }
        .sticky-header strong { color: #202124; font-size: 1.05rem; }
        div[data-testid="stChatInput"] { padding-top: 0 !important; padding-bottom: 4rem !important; }
        .gemini-scroll-down { position: fixed; bottom: 120px; left: 50%; transform: translateX(-50%); width: 34px; height: 34px; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 2px 6px rgba(0,0,0,0.1); z-index: 99999; text-decoration: none !important; color: #5f6368 !important; transition: all 0.2s; }
        .gemini-scroll-down:hover { background-color: #f8f9fa; box-shadow: 0 4px 10px rgba(0,0,0,0.15); color: #1a73e8 !important; }
        .gemini-scroll-down svg { width: 20px; height: 20px; fill: currentColor; }
        [data-testid="stAppViewBlockContainer"] > div:first-child { display: none !important; }
    </style>
    <a href="#bottom-anchor" class="gemini-scroll-down" title="滚动到底部">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M16.59 8.59L12 13.17 7.41 8.59 6 10l6 6 6-6z"/></svg>
    </a>
    """, unsafe_allow_html=True)

def render_action_icons(text_to_copy: str, msg_idx: int, is_user: bool = True):
    safe_text = json.dumps(text_to_copy)
    copy_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>'
    edit_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>'
    rewind_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/></svg>'
    
    html_content = f"""
    <style>
        body {{ margin: 0; padding: 0; background: transparent; overflow: hidden; display: flex; align-items: center; justify-content: flex-start; gap: 4px; }}
        button {{ background: transparent; border: none; cursor: pointer; color: #9aa0a6; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; transition: background-color 0.2s, color 0.2s; padding: 0; }}
        button:hover {{ background-color: #f1f3f4; color: #1a73e8; }}
        svg {{ width: 16px; height: 16px; fill: currentColor; }}
    </style>
    <button id="btn_copy" title="复制" onclick='navigator.clipboard.writeText({safe_text}); const b = document.getElementById("btn_copy"); b.innerHTML = "<span style=\\"font-size:14px;color:#1a73e8;\\">✓</span>"; setTimeout(() => {{ b.innerHTML = `{copy_svg}`; }}, 1200);'>{copy_svg}</button>
    """
    
    if is_user:
        html_content += f"""
        <button id="btn_edit" title="编辑原文" onclick='triggerQueryAction("edit", {msg_idx})'>{edit_svg}</button>
        <button id="btn_rewind" title="回溯重译" onclick='triggerQueryAction("rewind", {msg_idx})'>{rewind_svg}</button>
        <script>
            function triggerQueryAction(action, idx) {{
                const url = new URL(window.parent.location);
                url.searchParams.set('action', action);
                url.searchParams.set('msg_idx', idx);
                window.parent.history.pushState({{}}, '', url);
                window.parent.dispatchEvent(new Event('popstate'));
            }}
        </script>
        """
    components.html(html_content, height=30, width=120 if is_user else 40)

@st.dialog("⚙️ 系统与配置", width="large")
def show_settings_dialog():
    st.markdown("#### 1. API 接口与凭据管理")
    env_names = list(st.session_state.api_envs.keys())
    current_env_idx = env_names.index(st.session_state.active_env) if st.session_state.active_env in env_names else 0
    
    col_env1, col_env2 = st.columns([1, 1])
    with col_env1: sel_env = st.selectbox("选择或切换接口环境", options=env_names, index=current_env_idx)
    with col_env2: st.markdown("<br>", unsafe_allow_html=True); new_env_name = st.text_input("➕ 另存为新接口", label_visibility="collapsed")
        
    edit_target = new_env_name.strip() if new_env_name.strip() else sel_env
    is_default = (edit_target == "Gemini 原生接口 (默认)")
    
    curr_url = "https://generativelanguage.googleapis.com/v1beta/openai/" if is_default else st.session_state.api_envs.get(edit_target, {}).get("url", "")
    curr_key = st.session_state.api_envs.get(edit_target, {}).get("key", "")
    
    url_input = st.text_input("接口地址 (Base URL)", value=curr_url, disabled=is_default)
    key_input = st.text_input("API 凭据 / 密码", value=curr_key, type="password")
    
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🧪 测试连接并获取模型列表"):
            if not key_input.strip() or not url_input.strip(): st.warning("请填写完整的地址和凭据")
            else:
                with st.spinner("正在连通接口..."):
                    success, result = fetch_openai_models(key_input.strip(), url_input.strip())
                    if success: st.session_state.available_models = result; st.success(f"获取到 {len(result)} 个可用模型。")
                    else: st.error(f"拉取失败: {result}")
    with col_btn2:
        current_idx = 0
        if st.session_state.selected_model in st.session_state.available_models: current_idx = st.session_state.available_models.index(st.session_state.selected_model)
        selected = st.selectbox("从拉取列表中选择模型", options=st.session_state.available_models, index=current_idx)
        manual_model = st.text_input("或手动输入指定模型名称", value="")
        final_model = manual_model.strip() if manual_model.strip() else selected

    st.markdown("---")
    st.markdown("#### 2. Agent 3-Step Prompts 管理")
    
    st.caption("每个模板的内容是“附加规则”，会追加在该步骤 system 消息的角色句之后；任务说明与输入材料的模板固定使用参考项目的原文。“参考原版（默认）”没有附加规则，且不可编辑；想基于它或其他模板修改，请在下方“另存为新模板”。")
    tab_t, tab_r, tab_i = st.tabs(["🗣️ Step 1: 初译", "🕵️‍♂️ Step 2: 审校", "✨ Step 3: 定稿"])
    with tab_t:
        t_names = list(st.session_state.translator_profiles.keys())
        sel_t = st.selectbox("选择初译模板", options=t_names, index=t_names.index(st.session_state.active_t) if st.session_state.active_t in t_names else 0)
        t_text = st.text_area("编辑初译附加规则", value=st.session_state.translator_profiles[sel_t], height=180, disabled=(sel_t == DEFAULT_PROFILE_NAME))
        new_t_name = st.text_input("另存为新初译模板 (选填)")
    with tab_r:
        r_names = list(st.session_state.reviewer_profiles.keys())
        sel_r = st.selectbox("选择审校模板", options=r_names, index=r_names.index(st.session_state.active_r) if st.session_state.active_r in r_names else 0)
        r_text = st.text_area("编辑审校附加规则", value=st.session_state.reviewer_profiles[sel_r], height=180, disabled=(sel_r == DEFAULT_PROFILE_NAME))
        new_r_name = st.text_input("另存为新审校模板 (选填)")
    with tab_i:
        i_names = list(st.session_state.improver_profiles.keys())
        sel_i = st.selectbox("选择定稿模板", options=i_names, index=i_names.index(st.session_state.active_i) if st.session_state.active_i in i_names else 0)
        i_text = st.text_area("编辑定稿附加规则", value=st.session_state.improver_profiles[sel_i], height=180, disabled=(sel_i == DEFAULT_PROFILE_NAME))
        new_i_name = st.text_input("另存为新定稿模板 (选填)")

    if st.button("✅ 保存全部配置并生效", type="primary"):
        st.session_state.api_envs[edit_target] = {"url": url_input.strip(), "key": key_input.strip()}
        st.session_state.active_env = edit_target
        record_model_usage(final_model)
        
        st.session_state.active_t = new_t_name.strip() if new_t_name.strip() else sel_t
        st.session_state.translator_profiles[st.session_state.active_t] = t_text
        st.session_state.active_r = new_r_name.strip() if new_r_name.strip() else sel_r
        st.session_state.reviewer_profiles[st.session_state.active_r] = r_text
        st.session_state.active_i = new_i_name.strip() if new_i_name.strip() else sel_i
        st.session_state.improver_profiles[st.session_state.active_i] = i_text
            
        save_config({"api_config": {"active_env": st.session_state.active_env, "envs": st.session_state.api_envs, "current_model": st.session_state.selected_model}, "skills": {"translator_profiles": st.session_state.translator_profiles, "active_translator": st.session_state.active_t, "reviewer_profiles": st.session_state.reviewer_profiles, "active_reviewer": st.session_state.active_r, "improver_profiles": st.session_state.improver_profiles, "active_improver": st.session_state.active_i, "profile_schema": PROFILE_SCHEMA_VERSION, "skills_legacy": st.session_state.skills_legacy}})
        st.success("配置已保存并生效！")
        st.rerun()
