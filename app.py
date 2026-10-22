import os
import json
import re
import requests
import streamlit as st
import translation_agent.utils as ta_utils

st.set_page_config(page_title="医药法规智能翻译 Agent", page_icon="💊", layout="centered")

# ==================== 配置与状态管理 ====================
def load_config():
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "model_config": {"current_model": "gemini-2.5-flash"},
        "skills": {
            "regulatory_translator": "You are an expert regulatory translator specializing in life sciences, pharmacological, and clinical documents. Your translations must strictly adhere to ICH, FDA, and CDE terminologies and formatting standards.",
            "regulatory_reviewer": "You are an elite English-Chinese regulatory reviewer. Focus ONLY on deviations from ICH/FDA/CDE guidelines, incorrect medical terminology, or lack of scientific precision."
        }
    }

def save_config(config_data):
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)

config = load_config()

# 初始化全局会话状态
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "available_models" not in st.session_state:
    st.session_state.available_models = [
        config["model_config"].get("current_model", "gemini-2.5-flash"),
        "gemini-2.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]
if "selected_model" not in st.session_state:
    st.session_state.selected_model = config["model_config"].get("current_model", "gemini-2.5-flash")
if "trans_skill" not in st.session_state:
    st.session_state.trans_skill = config["skills"]["regulatory_translator"]
if "rev_skill" not in st.session_state:
    st.session_state.rev_skill = config["skills"]["regulatory_reviewer"]
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==================== API Key 连通测试与模型获取 ====================
def fetch_gemini_models(api_key):
    """向 Google API 测试连通性并拉取支持 generateContent 的模型列表"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = []
            for m in data.get("models", []):
                # 过滤出支持文本生成的模型
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    model_id = m["name"].replace("models/", "")
                    models.append(model_id)
            return True, models
        else:
            err_msg = response.json().get("error", {}).get("message", "API Key 校验失败")
            return False, f"HTTP {response.status_code}: {err_msg}"
    except Exception as e:
        return False, str(e)

# ==================== 设置弹窗（Settings Modal） ====================
@st.dialog("⚙️ 系统与模型配置", width="large")
def show_settings_dialog():
    st.markdown("#### 1. API 凭据与模型连通测试")
    key_input = st.text_input("Gemini API Key", value=st.session_state.api_key, type="password", placeholder="AIzaSy...")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🧪 测试连接并获取模型"):
            if not key_input.strip():
                st.warning("请先输入 API Key")
            else:
                with st.spinner("正在连通 Google AI Studio..."):
                    success, result = fetch_gemini_models(key_input.strip())
                    if success:
                        st.session_state.api_key = key_input.strip()
                        st.session_state.available_models = result
                        st.success(f"✅ 验证成功！获取到 {len(result)} 个可用模型")
                    else:
                        st.error(f"❌ 连通失败: {result}")
                        
    with col2:
        # 下拉选择模型
        current_idx = 0
        if st.session_state.selected_model in st.session_state.available_models:
            current_idx = st.session_state.available_models.index(st.session_state.selected_model)
        
        selected = st.selectbox(
            "选择驱动模型",
            options=st.session_state.available_models,
            index=current_idx
        )
        st.session_state.selected_model = selected

    st.markdown("---")
    st.markdown("#### 2. 医药法规 Skill 提示词管理")
    t_skill = st.text_area("Translator Skill (初译规则)", value=st.session_state.trans_skill, height=120)
    r_skill = st.text_area("Reviewer Skill (审校标准)", value=st.session_state.rev_skill, height=120)

    if st.button("💾 保存全部配置", type="primary"):
        st.session_state.api_key = key_input.strip()
        st.session_state.trans_skill = t_skill
        st.session_state.rev_skill = r_skill
        
        # 写入外部 config.json 持久化
        new_config = {
            "model_config": {"current_model": st.session_state.selected_model},
            "skills": {
                "regulatory_translator": t_skill,
                "regulatory_reviewer": r_skill
            }
        }
        save_config(new_config)
        st.success("配置已保存！")
        st.rerun()

# ==================== 顶部极简导航栏 ====================
header_col1, header_col2 = st.columns([5, 1])
with header_col1:
    st.title("💊 医药法规翻译 Agent")
with header_col2:
    st.write("") # 间距调整
    if st.button("⚙️ 设置", help="配置 API Key、模型与 Skill 规则"):
        show_settings_dialog()

# 当前状态提示胶囊
status_text = f"当前模型: `{st.session_state.selected_model}`"
if st.session_state.api_key:
    status_text += " | 🟢 API 已就绪"
else:
    status_text += " | 🔴 未配置 API Key (点击右上角 ⚙️ 设置)"
st.caption(status_text)

# ==================== 翻译核心逻辑 ====================
def auto_detect_language(text):
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    if chinese_chars > 2 or (len(text.strip()) > 0 and chinese_chars / len(text.strip()) > 0.05):
        return "Chinese", "English", "United States"
    else:
        return "English", "Chinese", "China"

# 渲染历史聊天信息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 接收输入
if prompt := st.chat_input("在此输入或粘贴需要翻译的临床/法规文本..."):
    if not st.session_state.api_key:
        st.error("❌ 尚未配置 API Key，请点击右上角【⚙️ 设置】填入并验证您的密钥。")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner(f"⏳ 正在使用【{st.session_state.selected_model}】执行初译与法规审校..."):
                try:
                    os.environ["OPENAI_API_KEY"] = st.session_state.api_key
                    os.environ["OPENAI_BASE_URL"] = "https://generativelanguage.googleapis.com/v1beta/openai/"

                    # 动态注入所选模型与自定义 Skill
                    import inspect
                    utils_file = inspect.getfile(ta_utils)
                    if os.path.exists(utils_file):
                        with open(utils_file, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        # 替换模型定义
                        content = re.sub(r'model="[^"]+"', f'model="{st.session_state.selected_model}"', content)
                        content = re.sub(r'model:\s*str\s*=\s*"[^"]+"', f'model: str = "{st.session_state.selected_model}"', content)
                        
                        # 注入 Skill 规则
                        content = content.replace("You are an expert linguist, specializing in translation from {source_lang} to {target_lang}.", st.session_state.trans_skill)
                        content = content.replace("You are an expert linguist specializing in translation from {source_lang} to {target_lang}.", st.session_state.trans_skill)
                        content = content.replace("Your task is to carefully read a source text and a translation from {source_lang} to {target_lang}, and then give constructive criticism and helpful suggestions to improve the translation.", st.session_state.rev_skill)
