import os
import json
import re
import requests
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

# ==================== 1. 页面基础配置（开启宽屏适配侧置“品”字布局） ====================
st.set_page_config(
    page_title="医药法规智能翻译 Agent",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================== 默认 Skill 提示词预设 ====================
DEFAULT_TRANSLATOR = """You are a specialized translation engine for life sciences, clinical medicine, pharmacovigilance, and FDA/ICH/CDE regulatory documents. 

Core Directives:
1. Completeness & Accuracy: Translate every element precisely. Strict adherence to ICH/FDA/CDE terminology. Differentiate clinical (patients/subjects, fixed dose) vs non-clinical (animals, weight-standardized dose, sacrifice/necropsy) context.
2. Non-Translated Elements: Keep abbreviations (e.g., SAE, AE), units of measurement, and math/chemistry symbols exactly as in the source. Ignore but precisely restore any tags or placeholders.
3. Formatting Rules: 
   - EN to ZH: Use full-width punctuation. No space between Chinese characters and numbers/English letters. Keep a half-width space between a number and an English unit (e.g., 5 mg). Convert dates to "yyyy年mm月dd日".
   - ZH to EN: Use standard English punctuation and spacing. Convert dates to "dd-mmm-yyyy".

Output ONLY the pure translated text. Do not expand, infer, add conversational filler, or output markdown wrappers unless explicitly requested."""

DEFAULT_REVIEWER = """You are a top-tier life sciences technical literature and regulatory reviewer, expert in FDA, EMA, and CDE guidelines. Your task is to carefully read the source text and its initial translation, and provide constructive critique to improve the translation.

Strict Constraints for Critique:
1. Rule Compliance Check: Strictly evaluate if the initial translation followed all required formatting and translation rules:
   - Completeness & Tags: No omissions. Tags/placeholders must be accurately restored to their original positions.
   - Terminology Context: Correct distinction between clinical (patients, fixed dose) and non-clinical (animals, weight-standardized dose, sacrifice/necropsy).
   - Non-Translated Elements: Abbreviations (e.g., SAE) and units must remain exactly as in the source.
   - Formatting & Dates: Check date conversions (EN to ZH: "yyyy年mm月dd日"; ZH to EN: "dd-mmm-yyyy"), spacing (half-width space between number and English unit, e.g., "5 mg", but no space before Chinese units), and punctuation (full-width for ZH, standard for EN).
2. Minimalist Approach: Maximize the retention of the initial translation's wording, provided it perfectly aligns with the grammar, meaning, and the rules above.
3. Industry Standard Compliance: Point out and correct terms ONLY if there are scientific errors, logical contradictions, or non-compliance with official ICH/FDA/CDE terminology.
4. Scientific Rigor: Ensure tense, voice, and preposition usage fully comply with academic and clinical norms. Maintain an objective and concise tone.

Focus ONLY on deviations from regulatory guidelines, incorrect medical terminology, formatting rule violations, or lack of scientific precision. Do not output conversational filler."""

# ==================== 界面样式与右下角直达底部按钮注入 ====================
st.markdown("""
<style>
    /* 气泡聊天样式微调 */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        flex-direction: row-reverse;
        text-align: right;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stMarkdownContainer"] {
        background-color: #e8f0fe;
        color: #1a73e8;
        padding: 12px 16px;
        border-radius: 16px 4px 16px 16px;
        display: inline-block;
        text-align: left;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stMarkdownContainer"] {
        background-color: #f1f3f4;
        color: #202124;
        padding: 12px 16px;
        border-radius: 4px 16px 16px 16px;
        display: inline-block;
    }

    /* 右下角悬浮一键直达底部按钮 + 滚动条 */
    .floating-nav {
        position: fixed;
        bottom: 28px;
        right: 28px;
        z-index: 99999;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        background: rgba(15, 23, 42, 0.85);
        backdrop-filter: blur(8px);
        padding: 10px 8px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        box-shadow: 0 8px 24px rgba(0,0,0,0.25);
    }
    .scroll-track {
        width: 6px;
        height: 48px;
        background: rgba(255,255,255,0.15);
        border-radius: 999px;
        overflow: hidden;
        position: relative;
    }
    .scroll-bar-fill {
        width: 100%;
        background: #38bdf8;
        height: 100%;
        border-radius: 999px;
    }
    .jump-bottom-btn {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: #2563eb;
        color: white !important;
        display: flex;
        align-items: center;
        justify-content: center;
        text-decoration: none !important;
        font-size: 16px;
        transition: all 0.2s;
        cursor: pointer;
    }
    .jump-bottom-btn:hover {
        background: #1d4ed8;
        transform: translateY(2px);
    }
</style>

<!-- 右下角悬浮直达底部组件 -->
<div class="floating-nav" title="直达页面最底部">
    <div class="scroll-track"><div class="scroll-bar-fill"></div></div>
    <a href="#bottom-anchor" class="jump-bottom-btn" title="一键直达最底部">⏬</a>
</div>
""", unsafe_allow_html=True)


# ==================== 配置与状态管理 ====================
def load_config():
    default_cfg = {
        "api_config": {
            "active_env": "Gemini 原生接口 (默认)",
            "envs": {
                "Gemini 原生接口 (默认)": {
                    "url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                    "key": ""
                }
            },
            "current_model": "gemini-2.5-flash"
        },
        "skills": {}
    }
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if "envs" not in data.get("api_config", {}):
                    old_url = data.get("api_config", {}).get("base_url", "https://generativelanguage.googleapis.com/v1beta/openai/")
                    data["api_config"] = default_cfg["api_config"]
                    if old_url != "https://generativelanguage.googleapis.com/v1beta/openai/":
                        data["api_config"]["envs"]["自定义历史接口"] = {"url": old_url, "key": ""}
                        data["api_config"]["active_env"] = "自定义历史接口"
                return data
        except Exception:
            return default_cfg
    return default_cfg

def save_config(config_data):
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)

config = load_config()

# === 初始化 API 环境状态 ===
api_cfg = config.get("api_config", {})
if "api_envs" not in st.session_state:
    st.session_state.api_envs = api_cfg.get("envs", {})
if "active_env" not in st.session_state:
    st.session_state.active_env = api_cfg.get("active_env", "Gemini 原生接口 (默认)")
if "selected_model" not in st.session_state:
    st.session_state.selected_model = api_cfg.get("current_model", "gemini-2.5-flash")
if "available_models" not in st.session_state:
    st.session_state.available_models = [st.session_state.selected_model]

# === 初始化基于使用历史的模型列表 (MRU 策略) ===
if "model_history" not in st.session_state:
    st.session_state.model_history = [{"id": st.session_state.selected_model, "count": 1}]

# === 初始化 Skill 状态 ===
skills_cfg = config.get("skills", {})
if "translator_profiles" not in skills_cfg or not skills_cfg.get("translator_profiles"):
    st.session_state.translator_profiles = {"标准法规与临床翻译 (默认)": DEFAULT_TRANSLATOR}
    st.session_state.reviewer_profiles = {"严格监管及规则核对审校 (默认)": DEFAULT_REVIEWER}
    st.session_state.active_t = "标准法规与临床翻译 (默认)"
    st.session_state.active_r = "严格监管及规则核对审校 (默认)"
else:
    st.session_state.translator_profiles = skills_cfg.get("translator_profiles", {"标准法规与临床翻译 (默认)": DEFAULT_TRANSLATOR})
    st.session_state.reviewer_profiles = skills_cfg.get("reviewer_profiles", {"严格监管及规则核对审校 (默认)": DEFAULT_REVIEWER})
    st.session_state.active_t = skills_cfg.get("active_translator", "标准法规与临床翻译 (默认)")
    st.session_state.active_r = skills_cfg.get("active_reviewer", "严格监管及规则核对审校 (默认)")

# === 对话与导航状态管理 ===
if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_turn_idx" not in st.session_state:
    st.session_state.selected_turn_idx = -1

if "editing_idx" not in st.session_state:
    st.session_state.editing_idx = None


# ==================== 工具函数 ====================
def record_model_usage(model_name: str):
    """记录模型使用历史并置顶 (MRU 策略)"""
    model_name = model_name.strip()
    if not model_name:
        return
    existing_count = 0
    new_list = []
    for item in st.session_state.model_history:
        if item["id"] == model_name:
            existing_count = item["count"]
        else:
            new_list.append(item)
    new_list.insert(0, {"id": model_name, "count": existing_count + 1})
    st.session_state.model_history = new_list
    st.session_state.selected_model = model_name


def render_copy_icon_button(text_to_copy: str, key: str):
    """渲染纯图标复制按钮"""
    safe_text = json.dumps(text_to_copy)
    components.html(
        f"""
        <button id="btn_{key}" title="复制到剪贴板" style="
            background: transparent;
            border: 1px solid rgba(148, 163, 184, 0.35);
            border-radius: 8px;
            padding: 4px 9px;
            cursor: pointer;
            font-size: 14px;
            line-height: 1.2;
            color: inherit;
        " onclick='
            navigator.clipboard.writeText({safe_text});
            const b = document.getElementById("btn_{key}");
            b.innerText = "✅";
            setTimeout(() => {{ b.innerText = "📋"; }}, 1200);
        '>📋</button>
        """,
        height=34,
        width=46,
    )


def fetch_openai_models(api_key, base_url):
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        models_page = client.models.list()
        models = []
        excluded_keywords = [
            "embedding", "tts", "whisper", "dall-e", "image", "vision", "audio", 
            "aqa", "realtime", "moderation", "instruct", "babbage", "davinci", 
            "curie", "ada", "search", "similarity", "text-", "rerank", "question"
        ]
        for m in models_page.data:
            name = m.id.lower()
            if any(kw in name for kw in excluded_keywords):
                continue
            clean_id = m.id.replace("models/", "")
            models.append(clean_id)
        models = sorted(list(set(models)), reverse=True)
        return True, models if models else ["未获取到文本模型，请手动输入"]
    except Exception as e:
        return False, str(e)


# ==================== 设置弹窗 ====================
@st.dialog("⚙️ 系统与模型配置", width="large")
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
    
    if is_default:
        curr_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    else:
        curr_url = st.session_state.api_envs.get(edit_target, {}).get("url", "")
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
    st.markdown("#### 2. Skill 提示词模板管理")
    tab_t, tab_r = st.tabs(["🗣️ Translator (初译规则)", "🕵️‍♂️ Reviewer (审校标准)"])
    
    with tab_t:
        t_names = list(st.session_state.translator_profiles.keys())
        current_t_idx = t_names.index(st.session_state.active_t) if st.session_state.active_t in t_names else 0
        sel_t = st.selectbox("选择初译模板", options=t_names, index=current_t_idx, key="sel_t")
        t_text = st.text_area("编辑初译模板内容", value=st.session_state.translator_profiles[sel_t], height=180, key="txt_t")
        new_t_name = st.text_input("💾 另存为新初译模板 (选填)", key="new_t")

    with tab_r:
        r_names = list(st.session_state.reviewer_profiles.keys())
        current_r_idx = r_names.index(st.session_state.active_r) if st.session_state.active_r in r_names else 0
        sel_r = st.selectbox("选择审校模板", options=r_names, index=current_r_idx, key="sel_r")
        r_text = st.text_area("编辑审校模板内容", value=st.session_state.reviewer_profiles[sel_r], height=180, key="txt_r")
        new_r_name = st.text_input("💾 另存为新审校模板 (选填)", key="new_r")

    if st.button("✅ 保存全部配置并生效", type="primary"):
        st.session_state.api_envs[edit_target] = {"url": url_input.strip(), "key": key_input.strip()}
        st.session_state.active_env = edit_target
        record_model_usage(final_model)
        
        if new_t_name.strip():
            st.session_state.translator_profiles[new_t_name.strip()] = t_text
            st.session_state.active_t = new_t_name.strip()
        else:
            st.session_state.translator_profiles[sel_t] = t_text
            st.session_state.active_t = sel_t
            
        if new_r_name.strip():
            st.session_state.reviewer_profiles[new_r_name.strip()] = r_text
            st.session_state.active_r = new_r_name.strip()
        else:
            st.session_state.reviewer_profiles[sel_r] = r_text
            st.session_state.active_r = sel_r
            
        new_config = {
            "api_config": {
                "active_env": st.session_state.active_env,
                "envs": st.session_state.api_envs,
                "current_model": st.session_state.selected_model
            },
            "skills": {
                "translator_profiles": st.session_state.translator_profiles,
                "reviewer_profiles": st.session_state.reviewer_profiles,
                "active_translator": st.session_state.active_t,
                "active_reviewer": st.session_state.active_r
            }
        }
        save_config(new_config)
        st.success("配置已保存并生效！")
        st.rerun()


# ==================== 顶部导航栏 ====================
header_col1, header_col2 = st.columns([5, 1])
with header_col1:
    st.title("💊 医药法规翻译 Agent")
with header_col2:
    st.write("")
    if st.button("⚙️ 设置", help="管理 API 接口、模型与多模板 Skill"):
        show_settings_dialog()

# 状态提示
curr_active_key = st.session_state.api_envs.get(st.session_state.active_env, {}).get("key", "")
if curr_active_key:
    status_text = f"🟢 **接口**: `{st.session_state.active_env}` | 🤖 **当前模型**: `{st.session_state.selected_model}`"
else:
    status_text = f"🔴 **未配置 API 凭据** (请点击右上角 ⚙️ 设置)"
st.caption(status_text)
st.caption(f"✍️ **当前规则** ➡️ 初译: `{st.session_state.active_t}` | 审校: `{st.session_state.active_r}`")


# ==================== 核心翻译管线函数 ====================
def auto_detect_language(text):
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    if chinese_chars > 2 or (len(text.strip()) > 0 and chinese_chars / len(text.strip()) > 0.05):
        return "Chinese", "English", "United States"
    else:
        return "English", "Chinese", "China"

def call_llm(client, model, system_prompt, user_prompt):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content

def run_agentic_translation(source_text, model_name, api_key, base_url, trans_skill, rev_skill):
    client = OpenAI(api_key=api_key, base_url=base_url)
    source_lang, target_lang, country = auto_detect_language(source_text)
    
    # Step 1: 初译
    init_prompt = f"Translate the following {source_lang} text into {target_lang} for {country}:\n\n{source_text}"
    init_translation = call_llm(client, model_name, trans_skill, init_prompt)
    
    # Step 2: 审校
    review_prompt = f"Source Text ({source_lang}):\n{source_text}\n\nTranslation ({target_lang}):\n{init_translation}\n\nCritique this translation strictly against regulatory requirements, terminology consistency (ICH/FDA/CDE), and scientific accuracy."
    critique = call_llm(client, model_name, rev_skill, review_prompt)
    
    # Step 3: 终稿润色
    improve_prompt = f"Source Text ({source_lang}):\n{source_text}\n\nInitial Translation:\n{init_translation}\n\nReviewer Critique:\n{critique}\n\nProvide the final, polished translation incorporating the critique above. Output ONLY the final translation without conversational text."
    final_translation = call_llm(client, model_name, trans_skill, improve_prompt)
    
    step1_display = f"**【Step 1 忠实初译 ({source_lang} ➡️ {target_lang})】**\n\n{init_translation}"
    step2_display = f"**【Step 2 审校与法规规则核对】**\n\n{critique}"
    step3_display = f"{final_translation}"
    
    return step1_display, step2_display, step3_display


# ==================== 侧置“品”字形主布局 (左 30% : 右 70%) ====================
left_col, right_col = st.columns([3, 7], gap="medium")

# 获取当前激活检视轮次的数据
active_turn = None
if st.session_state.messages:
    idx = st.session_state.selected_turn_idx
    if idx < 0 or idx >= len(st.session_state.messages):
        idx = len(st.session_state.messages) - 1
    active_turn = st.session_state.messages[idx]

# ----------------- 左侧：上下两个独立视窗（Step 1 与 Step 2） -----------------
with left_col:
    with st.container(height=390, border=True):
        h1_c1, h1_c2 = st.columns([8, 2])
        with h1_c1:
            st.markdown("**Step 1 · 初步翻译**")
        with h1_c2:
            if active_turn:
                render_copy_icon_button(active_turn["step1"], key="copy_step1")
        st.divider()
        if active_turn:
            st.markdown(active_turn["step1"])
        else:
            st.caption("暂无内容，发送文本后在此展示第一步初译结果。")

    with st.container(height=390, border=True):
        h2_c1, h2_c2 = st.columns([8, 2])
        with h2_c1:
            st.markdown("**Step 2 · 审校与最小修订**")
        with h2_c2:
            if active_turn:
                render_copy_icon_button(active_turn["step2"], key="copy_step2")
        st.divider()
        if active_turn:
            st.markdown(active_turn["step2"])
        else:
            st.caption("暂无内容，发送文本后在此展示第二步审校结果。")


# ----------------- 右侧：主页面工作区（历史模型快捷栏 + 对话流 + Step 3） -----------------
with right_col:
    # 1. 顶部：基于使用历史的模型快捷切换栏 (MRU)
    top_cols = st.columns([6.5, 3.5])
    with top_cols[0]:
        if st.session_state.model_history:
            hist_cols = st.columns(min(len(st.session_state.model_history), 5))
            for i, item in enumerate(st.session_state.model_history[:5]):
                m_id = item["id"]
                m_cnt = item["count"]
                is_curr = (m_id == st.session_state.selected_model)
                btn_label = f"{'🟢 ' if is_curr else ''}{m_id} ({m_cnt})"
                if hist_cols[i].button(btn_label, key=f"hist_m_{i}", help="点击切换至此历史模型"):
                    record_model_usage(m_id)
                    st.rerun()
    with top_cols[1]:
        manual_quick_model = st.text_input(
            "快捷切换模型",
            value=st.session_state.selected_model,
            label_visibility="collapsed",
            placeholder="输入或切换模型名称..."
        )
        if manual_quick_model and manual_quick_model != st.session_state.selected_model:
            record_model_usage(manual_quick_model)
            st.rerun()

    st.divider()

    # 2. 中部：主对话流区域
    chat_container = st.container(height=620, border=False)
    with chat_container:
        for i, msg in enumerate(st.session_state.messages):
            # --- 用户消息 ---
            with st.chat_message("user"):
                if st.session_state.editing_idx == i:
                    edited_val = st.text_area("编辑原文", value=msg["user"], key=f"edit_area_{i}", label_visibility="collapsed")
                    ec1, ec2, _ = st.columns([1, 1, 10])
                    with ec1:
                        if st.button("✔️", key=f"save_edit_{i}", help="保存修改并重新翻译"):
                            active_env_data = st.session_state.api_envs.get(st.session_state.active_env, {})
                            s1, s2, s3 = run_agentic_translation(
                                edited_val, st.session_state.selected_model,
                                active_env_data.get("key", ""), active_env_data.get("url", ""),
                                st.session_state.translator_profiles[st.session_state.active_t],
                                st.session_state.reviewer_profiles[st.session_state.active_r]
                            )
                            st.session_state.messages[i] = {
                                "user": edited_val, "step1": s1, "step2": s2, "step3": s3, "model": st.session_state.selected_model
                            }
                            st.session_state.messages = st.session_state.messages[:i + 1]
                            st.session_state.selected_turn_idx = i
                            st.session_state.editing_idx = None
                            st.rerun()
                    with ec2:
                        if st.button("✖️", key=f"cancel_edit_{i}", help="取消编辑"):
                            st.session_state.editing_idx = None
                            st.rerun()
                else:
                    st.markdown(msg["user"])
                    # 纯图标操作按钮：复制(📋) | 编辑(✏️) | Rewind回溯(⏪)
                    u_b1, u_b2, u_b3, _ = st.columns([1, 1, 1, 11])
                    with u_b1:
                        render_copy_icon_button(msg["user"], key=f"copy_user_{i}")
                    with u_b2:
                        if st.button("✏️", key=f"edit_btn_{i}", help="编辑此条消息"):
                            st.session_state.editing_idx = i
                            st.rerun()
                    with u_b3:
                        if st.button("⏪", key=f"rewind_btn_{i}", help="Rewind：回溯到此轮并重译"):
                            active_env_data = st.session_state.api_envs.get(st.session_state.active_env, {})
                            s1, s2, s3 = run_agentic_translation(
                                msg["user"], st.session_state.selected_model,
                                active_env_data.get("key", ""), active_env_data.get("url", ""),
                                st.session_state.translator_profiles[st.session_state.active_t],
                                st.session_state.reviewer_profiles[st.session_state.active_r]
                            )
                            st.session_state.messages = st.session_state.messages[:i]
                            st.session_state.messages.append({
                                "user": msg["user"], "step1": s1, "step2": s2, "step3": s3, "model": st.session_state.selected_model
                            })
                            st.session_state.selected_turn_idx = len(st.session_state.messages) - 1
                            st.rerun()

            # --- Agent 回复终稿 (Step 3) ---
            with st.chat_message("assistant"):
                st.caption(f"Model: `{msg.get('model', st.session_state.selected_model)}` · Turn #{i + 1}")
                st.markdown(msg["step3"])
                # 纯图标操作按钮：复制(📋) | 左侧检视(👁️)
                a_b1, a_b2, _ = st.columns([1, 1, 12])
                with a_b1:
                    render_copy_icon_button(msg["step3"], key=f"copy_agent_{i}")
                with a_b2:
                    if st.button("👁️", key=f"inspect_btn_{i}", help="在左侧窗口查看该轮的 Step 1 和 Step 2"):
                        st.session_state.selected_turn_idx = i
                        st.rerun()

        # 底部滚动锚点
        st.markdown('<div id="bottom-anchor"></div>', unsafe_allow_html=True)

    # 3. 底部输入框
    prompt = st.chat_input("输入需要翻译的临床/法规文本...")
    if prompt:
        active_env_data = st.session_state.api_envs.get(st.session_state.active_env, {})
        exec_key = active_env_data.get("key", "")
        exec_url = active_env_data.get("url", "")
        
        if not exec_key or not exec_url:
            st.error("❌ 当前选中的接口尚未配置凭据，请点击右上角【⚙️ 设置】进行完善。")
        else:
            record_model_usage(st.session_state.selected_model)
            with st.spinner(f"⏳ 正在通过【{st.session_state.active_env}】调用 {st.session_state.selected_model} 执行三阶段法规翻译..."):
                try:
                    s1, s2, s3 = run_agentic_translation(
                        prompt, st.session_state.selected_model,
                        exec_key, exec_url,
                        st.session_state.translator_profiles[st.session_state.active_t],
                        st.session_state.reviewer_profiles[st.session_state.active_r]
                    )
                    st.session_state.messages.append({
                        "user": prompt,
                        "step1": s1,
                        "step2": s2,
                        "step3": s3,
                        "model": st.session_state.selected_model
                    })
                    st.session_state.selected_turn_idx = len(st.session_state.messages) - 1
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 翻译出错: {str(e)}")
