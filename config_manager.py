# config_manager.py
import os
import json
import streamlit as st
from prompts import (
    DEFAULT_PROFILE_NAME, MEDICAL_NAME, RETIRED_PROFILE_NAMES,
    DEFAULT_TRANSLATOR, DEFAULT_REVIEWER, DEFAULT_IMPROVER,
    MEDICAL_TRANSLATOR, MEDICAL_REVIEWER, MEDICAL_IMPROVER,
)

# profile 的格式版本。版本 2 起，profile 内容是“附加规则”（追加在 system 消息之后）；
# 旧版配置里保存的是整段 system prompt，直接沿用会与参考模板重复，所以读取时归档并重置。
PROFILE_SCHEMA_VERSION = 2
_PROFILE_KEYS = ("translator_profiles", "active_translator", "reviewer_profiles", "active_reviewer", "improver_profiles", "active_improver")
_PROFILE_DICT_KEYS = ("translator_profiles", "reviewer_profiles", "improver_profiles")

def _retire_profiles(skills_cfg, legacy):
    """已退役名称（prompts.RETIRED_PROFILE_NAMES）下保存的内容归档到 legacy["retired_profiles"]，并从列表中移除。
    注意：这些名称被保留，用户若另存为同名模板，下次读取时也会被归档。"""
    skills_cfg = dict(skills_cfg)
    retired = {name: dict(v) for name, v in dict(legacy.get("retired_profiles", {})).items()}
    for key in _PROFILE_DICT_KEYS:
        if key not in skills_cfg:
            continue
        profiles = dict(skills_cfg[key] or {})
        for name in RETIRED_PROFILE_NAMES:
            if name in profiles:
                retired.setdefault(name, {})[key] = profiles.pop(name)
        skills_cfg[key] = profiles
    if retired:
        legacy = {**legacy, "retired_profiles": retired}
    return skills_cfg, legacy

def _migrate_skills(skills_cfg):
    """返回 (当前格式的 skills 配置, 需要保留的归档)。旧配置不会被删除，只是归档到 skills_legacy。"""
    legacy = dict(skills_cfg.get("skills_legacy", {}))
    if skills_cfg.get("profile_schema") == PROFILE_SCHEMA_VERSION:
        return _retire_profiles(skills_cfg, legacy)
    old = {k: skills_cfg[k] for k in _PROFILE_KEYS if k in skills_cfg}
    if old:
        legacy["v1_full_prompt_profiles"] = old
    return {"profile_schema": PROFILE_SCHEMA_VERSION}, legacy

def _build_profiles(saved, default_text, medical_text):
    profiles = dict(saved or {})
    profiles[DEFAULT_PROFILE_NAME] = default_text  # 默认 profile 固定为参考原版，界面中只读
    profiles.setdefault(MEDICAL_NAME, medical_text)  # 用户对医学版的修改会被保留
    return profiles

def _valid_active(name, profiles):
    """激活项指向不存在的模板时回退到默认，避免用名字取模板时出错。"""
    return name if name in profiles else DEFAULT_PROFILE_NAME

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

    skills_cfg, legacy = _migrate_skills(config.get("skills", {}))
    if "skills_legacy" not in st.session_state: st.session_state.skills_legacy = legacy
    if "translator_profiles" not in st.session_state: st.session_state.translator_profiles = _build_profiles(skills_cfg.get("translator_profiles"), DEFAULT_TRANSLATOR, MEDICAL_TRANSLATOR)
    if "reviewer_profiles" not in st.session_state: st.session_state.reviewer_profiles = _build_profiles(skills_cfg.get("reviewer_profiles"), DEFAULT_REVIEWER, MEDICAL_REVIEWER)
    if "improver_profiles" not in st.session_state: st.session_state.improver_profiles = _build_profiles(skills_cfg.get("improver_profiles"), DEFAULT_IMPROVER, MEDICAL_IMPROVER)
    if "active_t" not in st.session_state: st.session_state.active_t = _valid_active(skills_cfg.get("active_translator"), st.session_state.translator_profiles)
    if "active_r" not in st.session_state: st.session_state.active_r = _valid_active(skills_cfg.get("active_reviewer"), st.session_state.reviewer_profiles)
    if "active_i" not in st.session_state: st.session_state.active_i = _valid_active(skills_cfg.get("active_improver"), st.session_state.improver_profiles)

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
