import os
import json
import re
import requests
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

# 引入独立文件中的 3 个 Prompt 预设
from prompts import DEFAULT_TRANSLATOR, DEFAULT_REVIEWER, DEFAULT_IMPROVER

# ==================== 1. 页面基础配置 ====================
st.set_page_config(
    page_title="医药法规智能翻译 Agent",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================== 界面样式优化注入 (彻底重构) ====================
st.markdown("""
<style>
    /* 1. 整体页面上移，减少顶部空白 */
    .block-container { padding-top: 2rem !important; }
    
    /* 2. 全局隐藏浏览器原生滚动条，保持页面极简清爽 */
    ::-webkit-scrollbar { display: none !important; }
    * { -ms-overflow-style: none !important; scrollbar-width: none !important; }
    
    /* 3. 气泡聊天样式微调 */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) { flex-direction: row-reverse; text-align: right; }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stMarkdownContainer"] {
        background-color: #e8f0fe; color: #1a73e8; padding: 12px 16px; border-radius: 16px 4px 16px 16px; display: inline-block; text-align: left;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stMarkdownContainer"] {
        background-color: #f1f3f4; color: #202124; padding: 12px 16px; border-radius: 4px 16px 16px 16px; display: inline-block;
    }

    /* 4. 彻底重置对话框下方的 Streamlit Button 样式，实现极简透明纯图标 */
    div[data-testid="stChatMessage"] div[data-testid="stButton"] > button {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #5f6368 !important;
        padding: 0 !important;
        margin: 0 !important;
        min-height: 0 !important;
        height: 32px !important;
        width: 32px !important;
        border-radius: 50% !important;
        line-height: 1 !important;
        font-size: 1.1rem !important;
        transition: background-color 0.2s, color 0.2s !important;
    }
    div[data-testid="stChatMessage"] div[data-testid="stButton"] > button:hover {
        background-color: #f1f3f4 !important;
        color: #1a73e8 !important;
    }

    /* 5. Gemini 风格输入框正上方居中悬浮向下箭头 */
    .gemini-scroll-down {
        position: fixed;
        bottom: 95px; /* 精确悬浮在底部 Chat Input 正上方 */
        left: 50%;
        transform: translateX(-50%);
        width: 36px;
        height: 36px;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        z-index: 99999;
        text-decoration: none !important;
        color: #5f6368 !important;
        transition: all 0.2s;
    }
    .gemini-scroll-down:hover {
        background-color: #f8f9fa;
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        color: #1a73e8 !important;
    }
    .gemini-scroll-down svg { width: 20px; height: 20px; fill: currentColor; }
</style>

<!-- 向下箭头 HTML -->
<a href="#bottom-anchor" class="gemini-scroll-down" title="滚动到底部">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M16.59 8.59L12 13.17 7.41 8.59 6 10l6 6 6-6z"/></svg>
</a>
""", unsafe_allow_html=True)


# ==================== 配置与状态管理 ====================
def load_config():
    default_cfg = {
        "api_config": {
            "active_env": "Gemini 原生接口 (默认)",
            "envs": {"Gemini 原生接口 (默认)": {"url": "https://generativelanguage.googleapis.com/v1beta/openai/", "key": ""}},
            "current_model": "gemini-2.5-flash"
        },
        "skills": {}
    }
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_cfg

def save_config(config_data):
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)

config = load_config()

# === 状态初始化 ===
api_cfg = config.get("api_config", {})
if "api_envs" not in st.session_state: st.session_state.api_envs = api_cfg.get("envs", {})
if "active_env" not in st.session_state: st.session_state.active_env = api_cfg.get("active_env", "Gemini 原生接口 (默认)")
if "selected_model" not in st.session_state: st.session_state.selected_model = api_cfg.get("current_model", "gemini-2.5-flash")
if "available_models" not in st.session_state: st.session_state.available_models = [st.session_state.selected_model]
if "model_history" not in st.session_state: st.session_state.model_history = [{"id": st.session_state.selected_model, "count": 1}]

skills_cfg = config.get("skills", {})
st.session_state.translator_profiles = skills_cfg.get("translator_profiles", {"标准初译 (默认)": DEFAULT_TRANSLATOR})
st.session_state.reviewer_profiles = skills_cfg.get("reviewer_profiles", {"严格审校 (默认)": DEFAULT_REVIEWER})
st.session_state.improver_profiles = skills_cfg.get("improver_profiles", {"规则定稿 (默认)": DEFAULT_IMPROVER})

st.session_state.active_t = skills_cfg.get("active_translator", "标准初译 (默认)")
st.session_state.active_r = skills_cfg.get("active_reviewer", "严格审校 (默认)")
st.session_state.active_i = skills_cfg.get("active_improver", "规则定稿 (默认)")

if "messages" not in st.session_state: st.session_state.messages = []
if "editing_idx" not in st.session_state: st.session_state.editing_idx = None


# ==================== 工具函数 ====================
def record_model_usage(model_name: str):
    model_name = model_name.strip()
    if not model_name: return
    new_list = [item for item in st.session_state.model_history if item["id"] != model_name]
    existing = next((item for item in st.session_state.model_history if item["id"] == model_name), {"count": 0})
    new_list.insert(0, {"id": model_name, "count": existing["count"] + 1})
    st.session_state.model_history = new_list
    st.session_state.selected_model = model_name

def render_copy_icon_button(text_to_copy: str, key: str):
    """完美对齐的无缝 iframe 复制按钮"""
    safe_text = json.dumps(text_to_copy)
    svg_icon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>'
    components.html(
        f"""
        <style>
            body {{ margin: 0; padding: 0; background: transparent; overflow: hidden; display: flex; align-items: center; justify-content: center; }}
            button {{
                background: transparent; border: none; cursor: pointer; color: #5f6368; 
                width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
                transition: background-color 0.2s, color 0.2s;
            }}
            button:hover {{ background-color: #f1f3f4; color: #1a73e8; }}
            svg {{ width: 18px; height: 18px; fill: currentColor; }}
        </style>
        <button id="btn_{key}" title="复制文本" onclick='
            navigator.clipboard.writeText({safe_text});
            const b = document.getElementById("btn_{key}");
            b.innerHTML = "<span style=\\"font-size:14px;color:#1a73e8;\\">✓</span>";
            setTimeout(() => {{ b.innerHTML = `{svg_icon}`; }}, 1500);
        '>{svg_icon}</button>
        """,
        height=32, width=32,
    )

def fetch_openai_models(api_key, base_url):
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        models_page = client.models.list()
        models = [m.id.replace("models/", "") for m in models_page.data if not any(kw in m.id.lower() for kw in ["embedding", "tts", "whisper", "dall-e", "image", "vision", "audio", "aqa", "realtime", "moderation", "instruct", "babbage", "davinci", "curie", "ada", "search", "similarity", "text-", "rerank", "question"])]
        models = sorted(list(set(models)), reverse=True)
        return True, models if models else ["未获取到文本模型，请手动输入"]
    except Exception as e:
        return False, str(e)


# ==================== 设置与大模型调用逻辑 ====================
def auto_detect_language(text):
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    if chinese_chars > 2 or (len(text.strip()) > 0 and chinese_chars / len(text.strip()) > 0.05):
        return "Chinese", "English", "United States"
    return "English", "Chinese", "China"

def call_llm(client, model, system_prompt, user_prompt):
    response = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], temperature=0.3)
    return response.choices[0].message.content

def run_agentic_translation(source_text, model_name, api_key, base_url, trans_skill, rev_skill, imp_skill):
    client = OpenAI(api_key=api_key, base_url=base_url)
    source_lang, target_lang, country = auto_detect_language(source_text)
    
    init_prompt = f"Translate the following {source_lang} text into {target_lang} for {country}:\n\n{source_text}"
    init_translation = call_llm(client, model_name, trans_skill, init_prompt)
    
    review_prompt = f"Source Text ({source_lang}):\n{source_text}\n\nInitial Translation ({target_lang}):\n{init_translation}\n\nCritique this translation strictly against regulatory requirements, terminology consistency, and accuracy."
    critique = call_llm(client, model_name, rev_skill, review_prompt)
    
    improve_prompt = f"Source Text ({source_lang}):\n{source_text}\n\nInitial Translation:\n{init_translation}\n\nReviewer Critique:\n{critique}\n\nProvide the final, polished translation incorporating the critique above. Output ONLY the final translation without conversational text."
    final_translation = call_llm(client, model_name, imp_skill, improve_prompt)
    
    return f"**【Step 1 忠实初译 ({source_lang} ➡️ {target_lang})】**\n\n{init_translation}", f"**【Step 2 审校与法规规则核对】**\n\n{critique}", final_translation


@st.dialog("⚙️ 系统与配置", width="large")
def show_settings_dialog():
    st.markdown("#### 1. API 接口与凭据管理")
    env_names = list(st.session_state.api_envs.keys())
    current_env_idx = env_names.index(st.session_state.active_env) if st.session_state.active_env in env_names else 0
    
    col_env1, col_env2 = st.columns([1, 1])
    with col_env1:
        sel_env = st.selectbox("选择或切换接口环境", options=env_names, index=current_env_idx)
    with col_env2:
        st.markdown("<br>", unsafe_allow_html=True)
        new_env_name = st.text_input("➕ 另存为新接口 (选填)", placeholder="例如：公司内网代理", label_visibility="collapsed")
        
    edit_target = new_env_name.strip() if new_env_name.strip() else sel_env
    is_default = (edit_target == "Gemini 原生接口 (默认)")
    
    curr_url = "https://generativelanguage.googleapis.com/v1beta/openai/" if is_default else st.session_state.api_envs.get(edit_target, {}).get("url", "")
    curr_key = st.session_state.api_envs.get(edit_target, {}).get("key", "")
    
    url_input = st.text_input("接口地址 (Base URL)", value=curr_url, disabled=is_default)
    key_input = st.text_input("API 凭据 / 密码", value=curr_key, type="password")
    
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🧪 测试连接并获取模型列表"):
            if not key_input.strip() or not url_input.strip():
                st.warning("请填写完整的地址和凭据")
            else:
                with st.spinner("正在连通接口..."):
                    success, result = fetch_openai_models(key_input.strip(), url_input.strip())
                    if success:
                        st.session_state.available_models = result
                        st.success(f"✅ 验证成功！获取到 {len(result)} 个可用模型。")
                    else:
                        st.error(f"❌ 拉取失败: {result}")
    with col_btn2:
        current_idx = 0
        if st.session_state.selected_model in st.session_state.available_models:
            current_idx = st.session_state.available_models.index(st.session_state.selected_model)
        selected = st.selectbox("从拉取列表中选择模型", options=st.session_state.available_models, index=current_idx)
        manual_model = st.text_input("或手动输入指定模型名称", value="", placeholder="例如: gpt-4o")
        final_model = manual_model.strip() if manual_model.strip() else selected

    st.markdown("---")
    st.markdown("#### 2. Agent 3-Step Prompts 管理 (吴恩达 Translation-Agent 标准)")
    
    tab_t, tab_r, tab_i = st.tabs(["🗣️ Step 1: 初译", "🕵️‍♂️ Step 2: 审校", "✨ Step 3: 定稿"])
    
    with tab_t:
        t_names = list(st.session_state.translator_profiles.keys())
        sel_t = st.selectbox("选择初译模板", options=t_names, index=t_names.index(st.session_state.active_t) if st.session_state.active_t in t_names else 0)
        t_text = st.text_area("编辑初译模板内容", value=st.session_state.translator_profiles[sel_t], height=180)
        new_t_name = st.text_input("💾 另存为新初译模板 (选填)")

    with tab_r:
        r_names = list(st.session_state.reviewer_profiles.keys())
        sel_r = st.selectbox("选择审校模板", options=r_names, index=r_names.index(st.session_state.active_r) if st.session_state.active_r in r_names else 0)
        r_text = st.text_area("编辑审校模板内容", value=st.session_state.reviewer_profiles[sel_r], height=180)
        new_r_name = st.text_input("💾 另存为新审校模板 (选填)")
        
    with tab_i:
        i_names = list(st.session_state.improver_profiles.keys())
        sel_i = st.selectbox("选择定稿模板", options=i_names, index=i_names.index(st.session_state.active_i) if st.session_state.active_i in i_names else 0)
        i_text = st.text_area("编辑定稿模板内容", value=st.session_state.improver_profiles[sel_i], height=180)
        new_i_name = st.text_input("💾 另存为新定稿模板 (选填)")

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
            
        save_config({
            "api_config": {"active_env": st.session_state.active_env, "envs": st.session_state.api_envs, "current_model": st.session_state.selected_model},
            "skills": {
                "translator_profiles": st.session_state.translator_profiles, "active_translator": st.session_state.active_t,
                "reviewer_profiles": st.session_state.reviewer_profiles, "active_reviewer": st.session_state.active_r,
                "improver_profiles": st.session_state.improver_profiles, "active_improver": st.session_state.active_i
            }
        })
        st.success("配置已保存并生效！")
        st.rerun()


# ==================== 页面头部 ====================
header_col1, header_col2, header_col3 = st.columns([6, 3, 1])
with header_col1:
    st.title("🧬 医药法规翻译 Agent")
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


# ==================== 侧置“品”字形主布局 ====================
left_col, right_col = st.columns([3, 7], gap="medium")
active_turn = st.session_state.messages[-1] if len(st.session_state.messages) > 0 else None

# ----------------- 左侧：Step 1 与 Step 2 -----------------
with left_col:
    with st.container(height=390, border=True):
        st.markdown("**Step 1 · 初步翻译**")
        st.caption(f"🔵 规则：`{st.session_state.active_t}`")
        st.divider()
        if active_turn: st.markdown(active_turn["step1"])
        else: st.caption("暂无内容，发送文本后在此展示第一步初译。")

    with st.container(height=390, border=True):
        st.markdown("**Step 2 · 审校与最小修订**")
        st.caption(f"🔵 规则：`{st.session_state.active_r}`")
        st.divider()
        if active_turn: st.markdown(active_turn["step2"])
        else: st.caption("暂无内容，发送文本后在此展示第二步审校结果。")


# ----------------- 右侧：主页面对话流 -----------------
with right_col:
    chat_container = st.container(height=780, border=False)
    with chat_container:
        for i, msg in enumerate(st.session_state.messages):
            # --- 用户消息 ---
            with st.chat_message("user"):
                if st.session_state.editing_idx == i:
                    edited_val = st.text_area("编辑原文", value=msg["user"], key=f"edit_area_{i}", label_visibility="collapsed")
                    ec1, ec2, _ = st.columns([1, 1, 10])
                    with ec1:
                        if st.button("✔️", key=f"save_edit_{i}"):
                            active_env_data = st.session_state.api_envs.get(st.session_state.active_env, {})
                            s1, s2, s3 = run_agentic_translation(edited_val, st.session_state.selected_model, active_env_data.get("key", ""), active_env_data.get("url", ""), st.session_state.translator_profiles[st.session_state.active_t], st.session_state.reviewer_profiles[st.session_state.active_r], st.session_state.improver_profiles[st.session_state.active_i])
                            st.session_state.messages = st.session_state.messages[:i]
                            st.session_state.messages.append({"user": edited_val, "step1": s1, "step2": s2, "step3": s3, "model": st.session_state.selected_model})
                            st.session_state.editing_idx = None
                            st.rerun()
                    with ec2:
                        if st.button("✖️", key=f"cancel_edit_{i}"):
                            st.session_state.editing_idx = None
                            st.rerun()
                else:
                    st.markdown(msg["user"])
                    # 精确控制纯图标按钮的布局宽度，防止 iframe 被挤压
                    u_b1, u_b2, u_b3, _ = st.columns([1, 1, 1, 15])
                    with u_b1: render_copy_icon_button(msg["user"], key=f"copy_user_{i}")
                    with u_b2:
                        if st.button("✎", key=f"edit_btn_{i}", help="重新编辑此消息"): 
                            st.session_state.editing_idx = i; st.rerun()
                    with u_b3:
                        if st.button("↺", key=f"rewind_btn_{i}", help="回溯并重译当前文本"):
                            active_env_data = st.session_state.api_envs.get(st.session_state.active_env, {})
                            s1, s2, s3 = run_agentic_translation(msg["user"], st.session_state.selected_model, active_env_data.get("key", ""), active_env_data.get("url", ""), st.session_state.translator_profiles[st.session_state.active_t], st.session_state.reviewer_profiles[st.session_state.active_r], st.session_state.improver_profiles[st.session_state.active_i])
                            st.session_state.messages = st.session_state.messages[:i]
                            st.session_state.messages.append({"user": msg["user"], "step1": s1, "step2": s2, "step3": s3, "model": st.session_state.selected_model})
                            st.rerun()

            # --- Agent 回复终稿 ---
            with st.chat_message("assistant"):
                st.caption(f"Model: `{msg.get('model', st.session_state.selected_model)}` | 规则: `{st.session_state.active_i}` · Turn #{i + 1}")
                st.markdown(msg["step3"])
                render_copy_icon_button(msg["step3"], key=f"copy_agent_{i}")

        st.markdown('<div id="bottom-anchor"></div>', unsafe_allow_html=True)

    # 底部输入框
    prompt = st.chat_input("输入需要翻译的临床/法规文本...")
    if prompt:
        active_env_data = st.session_state.api_envs.get(st.session_state.active_env, {})
        exec_key = active_env_data.get("key", "")
        if not exec_key:
            st.error("❌ 当前选中的接口尚未配置凭据，请点击右上角【⚙️ 设置】。")
        else:
            record_model_usage(st.session_state.selected_model)
            with st.spinner(f"⏳ 正在调用 {st.session_state.selected_model} 执行 3-Step 法规翻译..."):
                s1, s2, s3 = run_agentic_translation(prompt, st.session_state.selected_model, exec_key, active_env_data.get("url", ""), st.session_state.translator_profiles[st.session_state.active_t], st.session_state.reviewer_profiles[st.session_state.active_r], st.session_state.improver_profiles[st.session_state.active_i])
                st.session_state.messages.append({"user": prompt, "step1": s1, "step2": s2, "step3": s3, "model": st.session_state.selected_model})
                st.rerun()
