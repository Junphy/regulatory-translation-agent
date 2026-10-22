import os
import json
import re
import requests
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="医药法规智能翻译 Agent", page_icon="💊", layout="centered")

# ==================== 界面样式优化（左右气泡对话） ====================
st.markdown("""
<style>
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
</style>
""", unsafe_allow_html=True)

# ==================== 配置与状态管理 ====================
def load_config():
    default_cfg = {
        "api_config": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "current_model": "gemini-2.5-flash"
        },
        "skills": {}
    }
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_cfg
    return default_cfg

def save_config(config_data):
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)

config = load_config()

# 初始化全局会话状态 (API 部分)
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "base_url" not in st.session_state:
    st.session_state.base_url = config.get("api_config", {}).get("base_url", "https://generativelanguage.googleapis.com/v1beta/openai/")
if "available_models" not in st.session_state:
    st.session_state.available_models = [config.get("api_config", {}).get("current_model", "gemini-2.5-flash")]
if "selected_model" not in st.session_state:
    st.session_state.selected_model = config.get("api_config", {}).get("current_model", "gemini-2.5-flash")

# 初始化全局会话状态 (多模板 Skill 部分)
skills_cfg = config.get("skills", {})
if "translator_profiles" not in skills_cfg:
    st.session_state.translator_profiles = {"默认初译规则": skills_cfg.get("regulatory_translator", "You are an expert regulatory translator specializing in life sciences, pharmacological, and clinical documents. Your translations must strictly adhere to ICH, FDA, and CDE terminologies and formatting standards.")}
    st.session_state.reviewer_profiles = {"默认审校规则": skills_cfg.get("regulatory_reviewer", "You are an elite English-Chinese regulatory reviewer. Focus ONLY on deviations from ICH/FDA/CDE guidelines, incorrect medical terminology, or lack of scientific precision.")}
    st.session_state.active_t = "默认初译规则"
    st.session_state.active_r = "默认审校规则"
else:
    st.session_state.translator_profiles = skills_cfg.get("translator_profiles", {})
    st.session_state.reviewer_profiles = skills_cfg.get("reviewer_profiles", {})
    st.session_state.active_t = skills_cfg.get("active_translator", "默认初译规则")
    st.session_state.active_r = skills_cfg.get("active_reviewer", "默认审校规则")

if "messages" not in st.session_state:
    st.session_state.messages = []

# ==================== 通用 API 模型获取 ====================
def fetch_openai_models(api_key, base_url):
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        models_page = client.models.list()
        
        models = []
        for m in models_page.data:
            if any(kw in m.id.lower() for kw in ["embedding", "tts", "whisper", "dall-e", "image", "vision", "audio"]):
                continue
            models.append(m.id)
            
        models = sorted(list(set(models)), reverse=True)
        return True, models if models else ["未获取到文本模型，请手动输入"]
    except Exception as e:
        return False, str(e)

# ==================== 设置弹窗 ====================
@st.dialog("⚙️ 系统与模型配置", width="large")
def show_settings_dialog():
    st.markdown("#### 1. API 接口配置与模型探测")
    url_input = st.text_input("接口地址 (Base URL)", value=st.session_state.base_url, placeholder="例如: https://api.openai.com/v1")
    key_input = st.text_input("API 凭据 / 密码", value=st.session_state.api_key, type="password")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🧪 测试连接并获取模型列表"):
            if not key_input.strip() or not url_input.strip():
                st.warning("请确保填写了完整的地址和凭据")
            else:
                with st.spinner("正在连通接口..."):
                    success, result = fetch_openai_models(key_input.strip(), url_input.strip())
                    if success:
                        st.session_state.api_key = key_input.strip()
                        st.session_state.base_url = url_input.strip()
                        st.session_state.available_models = result
                        st.success(f"✅ 验证成功！自动识别到 {len(result)} 个可用模型。")
                    else:
                        st.error(f"❌ 自动拉取失败: {result}。您仍可在右侧手动输入模型名称。")
                        
    with col2:
        current_idx = 0
        if st.session_state.selected_model in st.session_state.available_models:
            current_idx = st.session_state.available_models.index(st.session_state.selected_model)
        selected = st.selectbox("从拉取列表中选择模型", options=st.session_state.available_models, index=current_idx)
        manual_model = st.text_input("或手动输入指定模型名称 (覆盖上方选择)", value="", placeholder="例如: gpt-4o")
        final_model = manual_model.strip() if manual_model.strip() else selected

    st.markdown("---")
    st.markdown("#### 2. Skill 提示词模板管理")
    
    tab_t, tab_r = st.tabs(["🗣️ Translator (初译规则)", "🕵️‍♂️ Reviewer (审校标准)"])
    
    with tab_t:
        t_names = list(st.session_state.translator_profiles.keys())
        current_t_idx = t_names.index(st.session_state.active_t) if st.session_state.active_t in t_names else 0
        sel_t = st.selectbox("选择要生效的初译模板", options=t_names, index=current_t_idx, key="sel_t")
        t_text = st.text_area("编辑模板内容 (直接修改下方内容即可)", value=st.session_state.translator_profiles[sel_t], height=120, key="txt_t")
        new_t_name = st.text_input("💾 另存为新初译模板 (选填)", placeholder="例如：临床方案专用翻译", key="new_t")

    with tab_r:
        r_names = list(st.session_state.reviewer_profiles.keys())
        current_r_idx = r_names.index(st.session_state.active_r) if st.session_state.active_r in r_names else 0
        sel_r = st.selectbox("选择要生效的审校模板", options=r_names, index=current_r_idx, key="sel_r")
        r_text = st.text_area("编辑模板内容 (直接修改下方内容即可) ", value=st.session_state.reviewer_profiles[sel_r], height=120, key="txt_r")
        new_r_name = st.text_input("💾 另存为新审校模板 (选填)", placeholder="例如：严格 FDA 规范审校", key="new_r")

    if st.button("✅ 保存全部配置并生效", type="primary"):
        st.session_state.api_key = key_input.strip()
        st.session_state.base_url = url_input.strip()
        st.session_state.selected_model = final_model
        
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
                "base_url": st.session_state.base_url,
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
    if st.button("⚙️ 设置", help="配置 API、模型与多模板 Skill"):
        show_settings_dialog()

# 显示当前激活的综合状态
status_text = f"🌐 接口: `{st.session_state.base_url.split('://')[-1].split('/')[0]}` | 🤖 模型: `{st.session_state.selected_model}`"
if st.session_state.api_key:
    status_text += " | 🟢 凭据就绪"
else:
    status_text += " | 🔴 未配置凭据 (点击右上角 ⚙️ 设置)"
st.caption(status_text)
st.caption(f"✍️ 当前生效规则 ➡️ **初译**: `{st.session_state.active_t}` | **审校**: `{st.session_state.active_r}`")

# ==================== 翻译工作流 ====================
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

def run_agentic_translation(source_text, source_lang, target_lang, country, model, api_key, base_url, trans_skill, rev_skill):
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    init_prompt = f"Translate the following {source_lang} text into {target_lang} for {country}:\n\n{source_text}"
    init_translation = call_llm(client, model, trans_skill, init_prompt)
    
    review_prompt = f"Source Text ({source_lang}):\n{source_text}\n\nTranslation ({target_lang}):\n{init_translation}\n\nCritique this translation strictly against regulatory requirements, terminology consistency (ICH/FDA/CDE), and scientific accuracy."
    critique = call_llm(client, model, rev_skill, review_prompt)
    
    improve_prompt = f"Source Text ({source_lang}):\n{source_text}\n\nInitial Translation:\n{init_translation}\n\nReviewer Critique:\n{critique}\n\nProvide the final, polished translation incorporating the critique above. Output ONLY the final translation without conversational text."
    final_translation = call_llm(client, model, trans_skill, improve_prompt)
    
    return final_translation

# ==================== 消息渲染与接收 ====================
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("在此输入或粘贴需要翻译的临床/法规文本..."):
    if not st.session_state.api_key or not st.session_state.base_url:
        st.error("❌ 尚未配置 API 接口与凭据，请点击右上角【⚙️ 设置】进行配置。")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner(f"⏳ 正在通过 {st.session_state.base_url.split('://')[-1].split('/')[0]} 调用【{st.session_state.selected_model}】执行三阶段反思工作流..."):
                try:
                    source_lang, target_lang, country = auto_detect_language(prompt)
                    
                    active_t_skill = st.session_state.translator_profiles[st.session_state.active_t]
                    active_r_skill = st.session_state.reviewer_profiles[st.session_state.active_r]
                    
                    translation = run_agentic_translation(
                        source_text=prompt,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        country=country,
                        model=st.session_state.selected_model,
                        api_key=st.session_state.api_key,
                        base_url=st.session_state.base_url,
                        trans_skill=active_t_skill,
                        rev_skill=active_r_skill
                    )
                    
                    result_md = f"**【识别方向: {source_lang} ➡️ {target_lang} | 模型: {st.session_state.selected_model}】**\n\n{translation}"
                    st.markdown(result_md)
                    st.session_state.messages.append({"role": "assistant", "content": result_md})
                except Exception as e:
                    err_msg = f"❌ 翻译出错: {str(e)}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})
