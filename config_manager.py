# config_manager.py
import os
import copy
import json
import streamlit as st
from prompts import DEFAULT_PROFILE_NAME, MEDICAL_NAME, RETIRED_PROFILE_NAMES, BUILTIN_SCHEMES

# ==================== 方案（prompt 组合）的存储格式与迁移 ====================
# 版本 1（最初）：profile 是整段 system prompt。
# 版本 2：三步各有一份 profile 字典，内容是“附加规则”（追加在 system 消息之后）。
# 版本 3（当前）：“方案”= 初译规则 + 定稿规则，一键同时切换；第 2 步（审校）不再有规则。
#   skills = {"profile_schema": 3, "schemes": {名称: {"translator": ..., "improver": ...}},
#             "active_scheme": 名称, "skills_legacy": {...}}
# 旧配置里的内容不会被删除：转换不了或不再使用的部分归档到 skills_legacy。
PROFILE_SCHEMA_VERSION = 3
_V1_KEYS = ("translator_profiles", "active_translator", "reviewer_profiles", "active_reviewer", "improver_profiles", "active_improver")
COMBO_SCHEME_NAME = "上次使用的组合"


def _scheme(translator="", improver=""):
    return {"translator": translator or "", "improver": improver or ""}


def _schemes_from_v2(cfg, legacy):
    """第二版三份 profile 字典 -> 方案。返回 (schemes, active, legacy)。"""
    t = dict(cfg.get("translator_profiles") or {})
    r = dict(cfg.get("reviewer_profiles") or {})
    i = dict(cfg.get("improver_profiles") or {})

    # 第 2 步不再有规则：非空的自定义审校规则归档，不丢弃
    custom_r = {name: text for name, text in r.items() if text and name != DEFAULT_PROFILE_NAME}
    if custom_r:
        legacy = {**legacy, "reviewer_profiles_v2": {"profiles": custom_r, "active": cfg.get("active_reviewer")}}

    # 初译与定稿里的同名模板合并成同一个方案；只出现在一边的，另一边视为空（参考原版）
    schemes = {}
    for name in dict.fromkeys(list(t) + list(i)):
        if name != DEFAULT_PROFILE_NAME:
            schemes[name] = _scheme(t.get(name), i.get(name))

    active_t = cfg.get("active_translator") or DEFAULT_PROFILE_NAME
    active_i = cfg.get("active_improver") or DEFAULT_PROFILE_NAME
    if active_t == active_i:
        return schemes, active_t, legacy

    # 以前两步可以选不同名字的模板：把当时正在使用的组合保存成一个方案，使用效果不变
    text = lambda d, n: "" if n == DEFAULT_PROFILE_NAME else d.get(n, "")  # noqa: E731
    schemes[COMBO_SCHEME_NAME] = _scheme(text(t, active_t), text(i, active_i))
    return schemes, COMBO_SCHEME_NAME, legacy


def _retire_schemes(schemes, active, legacy):
    """已退役名称（prompts.RETIRED_PROFILE_NAMES）下的方案归档到 legacy["retired_profiles"]，并从列表中移除。
    注意：这些名称被保留，用户若另存为同名方案，下次读取时也会被归档。"""
    retired = {name: dict(v) for name, v in dict(legacy.get("retired_profiles", {})).items()}
    for name in RETIRED_PROFILE_NAMES:
        if name in schemes:
            retired[name] = schemes.pop(name)
    if retired:
        legacy = {**legacy, "retired_profiles": retired}
    if active in RETIRED_PROFILE_NAMES:
        active = None
    return schemes, active, legacy


def _migrate_skills(skills_cfg):
    """返回 (当前格式的 skills 配置, 需要保留的归档)。"""
    legacy = dict(skills_cfg.get("skills_legacy", {}))
    version = skills_cfg.get("profile_schema")
    if version == PROFILE_SCHEMA_VERSION:
        schemes = {n: dict(s) for n, s in (skills_cfg.get("schemes") or {}).items() if isinstance(s, dict)}
        active = skills_cfg.get("active_scheme")
    elif version == 2:
        schemes, active, legacy = _schemes_from_v2(skills_cfg, legacy)
    else:
        # 版本 1：整段 system prompt，直接沿用会与参考模板重复，所以归档并重置
        old = {k: skills_cfg[k] for k in _V1_KEYS if k in skills_cfg}
        if old:
            legacy["v1_full_prompt_profiles"] = old
        schemes, active = {}, None
    schemes, active, legacy = _retire_schemes(schemes, active, legacy)
    return {"profile_schema": PROFILE_SCHEMA_VERSION, "schemes": schemes, "active_scheme": active}, legacy


def _build_schemes(saved):
    """内置方案放在最前面：默认方案固定为参考原版（界面中只读）；医学版允许用户修改并保留。"""
    saved = {n: s for n, s in (saved or {}).items() if isinstance(s, dict)}
    result = {
        DEFAULT_PROFILE_NAME: dict(BUILTIN_SCHEMES[DEFAULT_PROFILE_NAME]),
        MEDICAL_NAME: saved.get(MEDICAL_NAME) or dict(BUILTIN_SCHEMES[MEDICAL_NAME]),
    }
    for name, s in saved.items():
        result.setdefault(name, s)
    return {name: _scheme(s.get("translator"), s.get("improver")) for name, s in result.items()}


def _valid_active(name, schemes):
    """激活项指向不存在的方案时回退到默认，避免用名字取方案时出错。"""
    return name if name in schemes else DEFAULT_PROFILE_NAME

DEFAULT_ENV_NAME = "Gemini 原生接口 (默认)"

# ==================== API 密钥：不落盘 ====================
# 密钥只有两个来源：1) 设置界面里输入（只保留在当前浏览器会话里）；2) Streamlit Secrets。
# config.json 里不再保存、也不再读取密钥（旧版本会把密钥明文写进该文件）。

def _without_keys(config_data):
    """写入文件前强制清空所有接口的密钥，调用方无法绕过。"""
    data = copy.deepcopy(config_data)
    for env in data.get("api_config", {}).get("envs", {}).values():
        if isinstance(env, dict):
            env["key"] = ""
    return data

def secret_api_key(env_name):
    """从 Streamlit Secrets 读取密钥；没有配置则返回空字符串。
    优先读 [api_keys] 表里与接口名同名的条目；默认接口也可以用顶层的 GEMINI_API_KEY。"""
    try:
        table = st.secrets.get("api_keys", {})
        if table and table.get(env_name):
            return str(table[env_name]).strip()
        if env_name == DEFAULT_ENV_NAME and st.secrets.get("GEMINI_API_KEY"):
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass  # 没有配置任何 Secrets 时，访问 st.secrets 会抛出异常
    return ""

def resolve_api_key_with_source(env_name):
    """返回 (密钥, 来源)。来源为 "session"（本次会话输入）、"secrets" 或 ""（没有密钥）。"""
    typed = (st.session_state.api_envs.get(env_name) or {}).get("key", "")
    if typed:
        return typed, "session"
    secret = secret_api_key(env_name)
    if secret:
        return secret, "secrets"
    return "", ""

def resolve_api_key(env_name):
    return resolve_api_key_with_source(env_name)[0]

def api_key_source(env_name):
    return resolve_api_key_with_source(env_name)[1]

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
        json.dump(_without_keys(config_data), f, ensure_ascii=False, indent=4)

def init_session_state():
    config = load_config()
    api_cfg = config.get("api_config", {})
    if "api_envs" not in st.session_state:
        envs_cfg = api_cfg.get("envs", {})
        # 文件里的密钥一律不使用；若发现旧版本留下的明文密钥，界面会提示（保存配置后文件中的密钥会被清除）
        st.session_state.api_envs = {name: {**(env or {}), "key": ""} for name, env in envs_cfg.items()}
        st.session_state.plaintext_key_warning = any((env or {}).get("key") for env in envs_cfg.values())
    if "active_env" not in st.session_state: st.session_state.active_env = api_cfg.get("active_env", "Gemini 原生接口 (默认)")
    if "selected_model" not in st.session_state: st.session_state.selected_model = api_cfg.get("current_model", "gemini-2.5-flash")
    if "available_models" not in st.session_state: st.session_state.available_models = [st.session_state.selected_model]
    if "model_history" not in st.session_state: st.session_state.model_history = [{"id": st.session_state.selected_model, "count": 1}]

    skills_cfg, legacy = _migrate_skills(config.get("skills", {}))
    if "skills_legacy" not in st.session_state: st.session_state.skills_legacy = legacy
    if "schemes" not in st.session_state: st.session_state.schemes = _build_schemes(skills_cfg.get("schemes"))
    if "active_scheme" not in st.session_state: st.session_state.active_scheme = _valid_active(skills_cfg.get("active_scheme"), st.session_state.schemes)

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
