# ui_components.py
import json
import streamlit as st
import streamlit.components.v1 as components
from api_client import fetch_openai_models
from config_manager import save_config, record_model_usage, secret_api_key, PROFILE_SCHEMA_VERSION
from prompts import DEFAULT_PROFILE_NAME

def inject_custom_css():
    st.markdown("""
    <style>
        .block-container { max-width: 96% !important; padding-top: 4rem !important; padding-left: 1.5rem !important; padding-right: 1.5rem !important; padding-bottom: 9rem !important; }
        ::-webkit-scrollbar { width: 10px; height: 10px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(128, 128, 128, 0.45); border-radius: 6px; border: 2px solid transparent; background-clip: content-box; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(128, 128, 128, 0.7); background-clip: content-box; }
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

ALIGN_CHAT_SCRIPT = """
(function () {
  var D = window.parent.document;
  if (D.getElementById('align-chat-input')) return;  // 只安装一次
  var s = D.createElement('script');
  s.id = 'align-chat-input';
  s.textContent = '(' + function () {
    function align() {
      var a = document.getElementById('bottom-anchor');
      var bc = document.querySelector('[data-testid="stBottomBlockContainer"]');
      if (!a || !bc) return;
      var col = a.closest('[data-testid="stColumn"]');
      if (!col) return;
      var r = col.getBoundingClientRect();
      var w = bc.parentElement.getBoundingClientRect().width;
      if (w - r.right < 0 || r.left < 0) return;
      bc.style.setProperty('padding-left', Math.round(r.left) + 'px', 'important');
      bc.style.setProperty('padding-right', Math.round(w - r.right) + 'px', 'important');
    }
    setInterval(align, 300);
    align();
  }.toString() + ')()';
  D.head.appendChild(s);
})();
"""


def align_chat_input():
    """让底部输入框的左右边缘与右侧对话区对齐（位于左侧步骤面板的右边框之外）。
    Streamlit 没有提供这个布局的设置，所以用一小段脚本读取右侧栏的位置；脚本失效时输入框保持默认的全宽。"""
    components.html(f"<script>{ALIGN_CHAT_SCRIPT}</script>", height=0)


def render_action_icons(text_to_copy: str, msg_idx: int, is_user: bool = True):
    # 译文通过 <script> 里的 JSON 字面量传给按钮，不再拼进 HTML 属性（含撇号、引号、< > & 的文本会破坏属性）。
    # 把 < > & 以及 U+2028/2029 转成 \u 转义，避免 "</script>" 或 "<!--" 提前结束脚本块。
    safe_text = (
        json.dumps(text_to_copy)
        .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    )
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
    <button id="btn_copy" title="复制" type="button">{copy_svg}</button>
    <script>
        (function() {{
            const TEXT = {safe_text};
            const btn = document.getElementById("btn_copy");
            const ICON = btn.innerHTML;
            function fallbackCopy(t) {{
                const ta = document.createElement("textarea");
                ta.value = t;
                ta.style.position = "fixed";
                ta.style.opacity = "0";
                document.body.appendChild(ta);
                ta.select();
                let ok = false;
                try {{ ok = document.execCommand("copy"); }} catch (e) {{}}
                document.body.removeChild(ta);
                return ok;
            }}
            function flash(ok) {{
                btn.textContent = ok ? "\\u2713" : "\\u2717";
                btn.style.color = ok ? "#1a73e8" : "#d93025";
                btn.style.fontSize = "14px";
                setTimeout(function() {{ btn.innerHTML = ICON; btn.style.color = ""; btn.style.fontSize = ""; }}, 1200);
            }}
            btn.addEventListener("click", function() {{
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    navigator.clipboard.writeText(TEXT).then(function() {{ flash(true); }}, function() {{ flash(fallbackCopy(TEXT)); }});
                }} else {{
                    flash(fallbackCopy(TEXT));
                }}
            }});
        }})();
    </script>
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
    key_input = st.text_input("API 凭据 / 密码", value=curr_key, type="password",
                              help="仅在当前浏览器会话中保留，不会写入 config.json，刷新页面后需要重新输入。长期使用请在 Streamlit 的 Secrets 中配置。")
    if secret_api_key(edit_target):
        st.caption("✅ 已在 Secrets 中配置了该接口的密钥，这里留空即可。")
    effective_key = key_input.strip() or secret_api_key(edit_target)

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🧪 测试连接并获取模型列表"):
            if not effective_key or not url_input.strip(): st.warning("请填写完整的地址和凭据")
            else:
                with st.spinner("正在连通接口..."):
                    success, result = fetch_openai_models(effective_key, url_input.strip())
                    if success: st.session_state.available_models = result; st.success(f"获取到 {len(result)} 个可用模型。")
                    else: st.error(f"拉取失败: {result}")
    with col_btn2:
        current_idx = 0
        if st.session_state.selected_model in st.session_state.available_models: current_idx = st.session_state.available_models.index(st.session_state.selected_model)
        selected = st.selectbox("从拉取列表中选择模型", options=st.session_state.available_models, index=current_idx)
        manual_model = st.text_input("或手动输入指定模型名称", value="")
        final_model = manual_model.strip() if manual_model.strip() else selected

    st.markdown("---")
    st.markdown("#### 2. 方案管理（Step 1 初译 + Step 3 定稿）")
    st.caption("一个方案包含初译与定稿两份“附加规则”，会追加在对应步骤 system 消息的角色句之后；任务说明与输入材料的模板固定使用参考项目的原文。Step 2（审校）固定使用参考原文，不可编辑。页面顶部的“方案”下拉框可以一键同时切换两步。“参考原版（默认）”没有附加规则，且不可编辑；想基于它或其他方案修改，请在下方“另存为新方案”。")
    scheme_names = list(st.session_state.schemes.keys())
    sel_scheme = st.selectbox("选择方案", options=scheme_names, index=scheme_names.index(st.session_state.active_scheme) if st.session_state.active_scheme in scheme_names else 0)
    is_default_scheme = (sel_scheme == DEFAULT_PROFILE_NAME)
    tab_t, tab_i = st.tabs(["🗣️ Step 1: 初译", "✨ Step 3: 定稿"])
    with tab_t:
        t_text = st.text_area("编辑初译附加规则", value=st.session_state.schemes[sel_scheme]["translator"], height=180, disabled=is_default_scheme)
    with tab_i:
        i_text = st.text_area("编辑定稿附加规则", value=st.session_state.schemes[sel_scheme]["improver"], height=180, disabled=is_default_scheme)
    new_scheme_name = st.text_input("另存为新方案 (选填)")

    if st.button("✅ 保存全部配置并生效", type="primary"):
        st.session_state.api_envs[edit_target] = {"url": url_input.strip(), "key": key_input.strip()}
        st.session_state.active_env = edit_target
        record_model_usage(final_model)

        target_scheme = new_scheme_name.strip() if new_scheme_name.strip() else sel_scheme
        if target_scheme != DEFAULT_PROFILE_NAME:  # 默认方案固定为参考原版，不写入
            st.session_state.schemes[target_scheme] = {"translator": t_text, "improver": i_text}
        st.session_state.active_scheme = target_scheme

        save_config({"api_config": {"active_env": st.session_state.active_env, "envs": st.session_state.api_envs, "current_model": st.session_state.selected_model}, "skills": {"schemes": st.session_state.schemes, "active_scheme": st.session_state.active_scheme, "profile_schema": PROFILE_SCHEMA_VERSION, "skills_legacy": st.session_state.skills_legacy}})
        st.session_state.plaintext_key_warning = False  # 文件中的明文密钥已在保存时清除
        st.success("配置已保存并生效！密钥不会写入文件，仅在本次会话中有效。")
        st.rerun()
