import os
import json
import re
import requests
import streamlit as st
from openai import OpenAI

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
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = []
            for m in data.get("models", []):
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    model_id = m["name"].replace("models/", "")
                    models.append(model_id)
            return True, models
        else:
            err_msg = response.json().get("error", {}).get("message", "API Key 校验失败")
            return False, f"HTTP {response.status_code}: {err_msg}"
    except Exception as e:
        return False, str(e)

# ==================== 设置弹窗 ====================
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

# ==================== 顶部导航栏 ====================
header_col1, header_col2 = st.columns([5, 1])
with header_col1:
    st.title("💊 医药法规翻译 Agent")
with header_col2:
    st.write("")
    if st.button("⚙️ 设置", help="配置 API Key、模型与 Skill 规则"):
        show_settings_dialog()

status_text = f"当前模型: `{st.session_state.selected_model}`"
if st.session_state.api_key:
    status_text += " | 🟢 API 已就绪"
else:
    status_text += " | 🔴 未配置 API Key (点击右上角 ⚙️ 设置)"
st.caption(status_text)

# ==================== 原生 Agent 反思翻译引擎 ====================
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

def run_agentic_translation(source_text, source_lang, target_lang, country, model, api_key, trans_skill, rev_skill):
    client = OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    
    # 阶段 1：初译 (Initial Translation)
    init_prompt = f"Translate the following {source_lang} text into {target_lang} for {country}:\n\n{source_text}"
    init_translation = call_llm(client, model, trans_skill, init_prompt)
    
    # 阶段 2：反思审校 (Reflection Critique)
    review_prompt = f"""Source Text ({source_lang}):
{source_text}

Translation ({target_lang}):
{init_translation}

Critique this translation strictly against regulatory requirements, terminology consistency (ICH/FDA/CDE), and scientific accuracy."""
    critique = call_llm(client, model, rev_skill, review_prompt)
    
    # 阶段 3：根据审校意见定稿 (Refinement)
    improve_prompt = f"""Source Text ({source_lang}):
{source_text}

Initial Translation:
{init_translation}

Reviewer Critique:
{critique}

Provide the final, polished translation incorporating the critique above. Output ONLY the final translation without conversational text."""
    final_translation = call_llm(client, model, trans_skill, improve_prompt)
    
    return final_translation

# ==================== 交互对话框 ====================
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("在此输入或粘贴需要翻译的临床/法规文本..."):
    if not st.session_state.api_key:
        st.error("❌ 尚未配置 API Key，请点击右上角【⚙️ 设置】填入并验证您的密钥。")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner(f"⏳ 正在使用【{st.session_state.selected_model}】执行三阶段反思翻译工作流..."):
                try:
                    source_lang, target_lang, country = auto_detect_language(prompt)
                    
                    translation = run_agentic_translation(
                        source_text=prompt,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        country=country,
                        model=st.session_state.selected_model,
                        api_key=st.session_state.api_key,
                        trans_skill=st.session_state.trans_skill,
                        rev_skill=st.session_state.rev_skill
                    )
                    
                    result_md = f"**【识别方向: {source_lang} ➡️ {target_lang} | 驱动模型: {st.session_state.selected_model}】**\n\n{translation}"
                    st.markdown(result_md)
                    st.session_state.messages.append({"role": "assistant", "content": result_md})
                except Exception as e:
                    err_msg = f"❌ 翻译出错: {str(e)}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})
