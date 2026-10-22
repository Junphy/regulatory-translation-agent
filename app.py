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
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "api_config": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "current_model": "gemini-2.5-flash"
        },
        "skills": {} # 兼容空情况
    }

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

# 初始化全局会话状态 (多模板 Skill 部分 - 自动兼容旧版 config 结构)
skills_cfg = config.get("skills", {})
if "translator_profiles" not in skills_cfg:
    # 从旧版单配置升级为多模板配置
    st.session_state.translator_profiles = {"默认初译规则": skills_cfg.get("regulatory_translator", "You are an expert regulatory translator specializing in life sciences, pharmacological, and clinical documents. Your translations must strictly adhere to ICH, FDA, and CDE terminologies and formatting standards.")}
    st.session_state.reviewer_profiles = {"默认审校规则": skills_cfg.get("regulatory_reviewer", "You are an elite English-Chinese regulatory reviewer. Focus ONLY on deviations from ICH/FDA/CDE guidelines, incorrect medical terminology, or lack of scientific precision.")}
    st.session_state.active_t = "默认初译规则"
    st.session_state.active_r = "默认审校规则"
else:
    st.session_state.translator_profiles = skills_cfg["translator_profiles"]
    st.session_state.reviewer_profiles = skills_cfg["reviewer_profiles"]
    st.session_state.active_t = skills_cfg["active_translator"]
    st.session_state.active_r = skills_cfg["active_reviewer"]

if "messages" not in st.session_state:
    st.session_state.messages = []

# ==================== 通用 API 连通测试与模型获取 ====================
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
    key_input = st.text_input("API 凭据 / 密码", value=st.session_state.api_key, type="password", placeholder="输入 API Key 或访问密码...")
    
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
