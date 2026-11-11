# config_manager.py
import os
import json
import streamlit as st
from prompts import DEFAULT_TRANSLATOR, DEFAULT_REVIEWER, DEFAULT_IMPROVER

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
            with open("config.json", "r", encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return default_cfg

def save_config(config_data):
    with open("config.json", "w", encoding="utf-8") as f: 
        json.dump(config_data, f, ensure_ascii=False, indent=4)

def init_session_state():
    config = load_config()
    api_cfg = config.get("api_config", {})
    if "api_envs" not in st.session_state: st.session_state.api_envs = api_cfg.get("envs", {})
    if "active_env" not in st.session_state: st.session_state.active_env = api_cfg.get("active_env", "Gemini 原生接口 (默认)")
    if "selected_model" not in st.session_state: st.session_state.selected_model = api_cfg.get("current_model", "gemini-2.5-flash")
    if "available_models" not in st.session_state: st.session_state.available_models = [st.session_state.selected_model]
    if "model_history" not in st.session_state: st.session_state.model_history = [{"id": st.session_state.selected_model, "count": 1}]

    skills_cfg = config.get("skills", {})
    if "translator_profiles" not in st.session_state: st.session_state.translator_profiles = skills_cfg.get("translator_profiles", {"标准初译 (默认)": DEFAULT_TRANSLATOR})
    if "reviewer_profiles" not in st.session_state: st.session_state.reviewer_profiles = skills_cfg.get("reviewer_profiles", {"严格审校 (默认)": DEFAULT_REVIEWER})
    if "improver_profiles" not in st.session_state: st.session_state.improver_profiles = skills_cfg.get("improver_profiles", {"规则定稿 (默认)": DEFAULT_IMPROVER})
    if "active_t" not in st.session_state: st.session_state.active_t = skills_cfg.get("active_translator", "标准初译 (默认)")
    if "active_r" not in st.session_state: st.session_state.active_r = skills_cfg.get("active_reviewer", "严格审校 (默认)")
    if "active_i" not in st.session_state: st.session_state.active_i = skills_cfg.get("active_improver", "规则定稿 (默认)")

    if "messages" not in st.session_state: st.session_state.messages = []
    if "editing_idx" not in st.session_state: st.session_state.editing_idx = None

def record_model_usage(model_name: str):
    model_name = model_name.strip()
    if not model_name: return
    new_list = [item for item in st.session_state.model_history if item["id"] != model_name]
    existing = next((item for item in st.session_state.model_history if item["id"] == model_name), {"count": 0})
    new_list.insert(0, {"id": model_name, "count": existing["count"] + 1})
    st.session_state.model_history = new_list
    st.session_state.selected_model = model_name
