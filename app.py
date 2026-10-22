import os
import json
import re
import streamlit as st
import translation_agent as ta

st.set_page_config(page_title="医药法规智能翻译 Agent", page_icon="💊", layout="wide")

# 加载配置
def load_config():
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "model_config": {"current_model": "gemini-3.5-flash-lite"},
        "skills": {
            "regulatory_translator": "You are an expert regulatory translator specializing in life sciences, pharmacological, and clinical documents.",
            "regulatory_reviewer": "You are an elite English-Chinese regulatory reviewer."
        }
    }

config = load_config()

# 侧边栏配置
st.sidebar.markdown("### ⚙️ 系统配置")
api_key = st.sidebar.text_input("Gemini API Key", type="password", placeholder="输入您的 API Key...")
model_choice = st.sidebar.selectbox(
    "选择驱动模型",
    ["gemini-3.5-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🧠 医药 Skill 管理")
trans_skill = st.sidebar.text_area("Translator Skill", value=config["skills"]["regulatory_translator"], height=150)
rev_skill = st.sidebar.text_area("Reviewer Skill", value=config["skills"]["regulatory_reviewer"], height=150)

# 主界面
st.title("💊 医药法规智能翻译 Agent")
st.markdown("支持英中双向自动识别。输入英文自动译为中文（CDE规范），输入中文自动译为英文（FDA/ICH规范）。")

def auto_detect_language(text):
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    if chinese_chars > 2 or (len(text.strip()) > 0 and chinese_chars / len(text.strip()) > 0.05):
        return "Chinese", "English", "United States"
    else:
        return "English", "Chinese", "China"

# 初始化聊天历史
if "messages" not in st.session_state:
    st.session_state.messages = []

# 展示历史对话
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 接收用户输入
if prompt := st.chat_input("在此输入或粘贴需要翻译的临床/法规文本..."):
    if not api_key:
        st.error("❌ 请先在左侧边栏输入您的 Gemini API Key")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("⏳ 正在执行【初译 -> 反思审校 -> 定稿】工作流..."):
                try:
                    os.environ["OPENAI_API_KEY"] = api_key
                    os.environ["OPENAI_BASE_URL"] = "https://generativelanguage.googleapis.com/v1beta/openai/"
                    
                    # 动态修改底层模型
                    utils_file = "/usr/local/lib/python3.10/site-packages/translation_agent/utils.py"
                    if os.path.exists(utils_file):
                        with open(utils_file, "r", encoding="utf-8") as f:
                            content = f.read()
                        content = re.sub(r'model="[^"]+"', f'model="{model_choice}"', content)
                        with open(utils_file, "w", encoding="utf-8") as f:
                            f.write(content)

                    source_lang, target_lang, country = auto_detect_language(prompt)
                    
                    translation = ta.translate(
                        source_lang=source_lang,
                        target_lang=target_lang,
                        source_text=prompt,
                        country=country 
                    )
                    
                    result_md = f"**【识别方向: {source_lang} ➡️ {target_lang} | 模型: {model_choice}】**\n\n{translation}"
                    st.markdown(result_md)
                    st.session_state.messages.append({"role": "assistant", "content": result_md})
                except Exception as e:
                    err_msg = f"❌ 翻译出错: {str(e)}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})
