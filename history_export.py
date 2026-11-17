# history_export.py
"""运行记录与评估导出。

为什么不直接用 st.session_state.messages：回溯重译和编辑原文会截断并覆盖对话，
上一次的结果就丢了，没法做新旧 prompt 的对比；messages 里也只存了方案名，方案规则改过
但名字不变时，分不清是哪一版 prompt 跑的。所以这里另外维护一份“只追加、不覆盖”的运行记录，
每次调用（成功或失败）追加一条，并给方案规则存一份快照与短版本号。

记录只保存在当前浏览器会话里（刷新页面或会话过期即丢失），不写入 config.json，也不含 API 密钥。
"""
import hashlib
import json
import re
from collections import OrderedDict
from datetime import datetime, timezone

import streamlit as st

LOG_KEY = "run_log"
NO_RULES_LABEL = "无附加规则"


def scheme_version_id(scheme):
    """方案规则的短版本号：规则文字有任何改动，版本号就变。两份规则都为空时返回“无附加规则”。"""
    translator = (scheme or {}).get("translator", "") or ""
    improver = (scheme or {}).get("improver", "") or ""
    if not translator.strip() and not improver.strip():
        return NO_RULES_LABEL
    return hashlib.sha1((translator + "\0" + improver).encode("utf-8")).hexdigest()[:6]


def _runs():
    return st.session_state.setdefault(LOG_KEY, [])


def log_run(source_text, scheme_name, scheme, model, env_name, direction_setting, result, error, seconds):
    """追加一条运行记录。result 是 (初译, 审校意见, 定稿, 方向标签) 或 None；error 是中文错误说明或 None。"""
    runs = _runs()
    entry = {
        "seq": len(runs) + 1,
        "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seconds": round(float(seconds), 1),
        "source": source_text,
        "scheme": scheme_name,
        "version": scheme_version_id(scheme),
        "rules": {"translator": (scheme or {}).get("translator", "") or "",
                  "improver": (scheme or {}).get("improver", "") or ""},
        "model": model,
        "interface": env_name,
        "direction_setting": direction_setting,
        "direction": None, "step1": None, "step2": None, "step3": None,
        "error": error or None,
    }
    if result is not None:
        entry["step1"], entry["step2"], entry["step3"], entry["direction"] = result[0], result[1], result[2], result[3]
    runs.append(entry)


def run_count():
    """(运行总数, 其中失败数, 不同原文条数)。"""
    runs = _runs()
    return len(runs), sum(1 for r in runs if r["error"]), len({_norm(r["source"]) for r in runs})


def clear_runs():
    st.session_state[LOG_KEY] = []


# ---------------------------------------------------------------- 导出
def _norm(text):
    return (text or "").replace("\r\n", "\n").strip()


def _fence(text):
    """用比内容里最长的反引号串更长的围栏包起来，译文里即使有 ``` 也不会破坏结构。"""
    longest = max([len(m) for m in re.findall(r"`+", text or "")] + [2])
    f = "`" * (longest + 1)
    return f"{f}text\n{text or ''}\n{f}"


def _letter(i):
    return chr(ord("a") + i) if i < 26 else str(i + 1)


def _hhmmss(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M:%S")
    except ValueError:
        return iso


def _select(runs, include_failed):
    return [r for r in runs if include_failed or not r["error"]]


def _group(runs):
    """按原文分组，编号按首次出现的顺序；组内按时间顺序，用 a、b、c 标运行。"""
    groups = OrderedDict()
    for r in runs:
        groups.setdefault(_norm(r["source"]), []).append(r)
    out = []
    for n, (_, items) in enumerate(groups.items(), start=1):
        for i, r in enumerate(items):
            r = dict(r)
            r["case_id"] = n
            r["run_id"] = f"{n}-{_letter(i)}"
            items[i] = r
        out.append((n, items))
    return out


def _version_text(r):
    return f"{r['scheme']}（{r['version']}）" if r["version"] != NO_RULES_LABEL else f"{r['scheme']}（{NO_RULES_LABEL}）"


def build_markdown(runs, include_failed=False, include_rules=True):
    runs = _select(runs, include_failed)
    groups = _group(runs)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    lines = ["# 翻译评估记录", "",
             f"- 导出时间：{now}（UTC）",
             f"- 共 {len(groups)} 条原文、{len(runs)} 次运行（{'已包含' if include_failed else '不含'}调用失败的运行）",
             "- 流程：Step 1 初译 → Step 2 审校 → Step 3 定稿（Step 2 固定使用参考项目原文，没有附加规则）",
             "- 版本号是方案规则（Step 1 与 Step 3 的附加规则）的短哈希：规则有任何改动，版本号就变；“无附加规则”即与参考项目逐字一致",
             ""]
    if not groups:
        lines.append("（没有可导出的运行记录）")
        return "\n".join(lines) + "\n"

    lines += ["## 汇总", "", "| 编号 | 方向 | 运行次数 | 方案（版本）× 次数 |", "|---|---|---|---|"]
    for n, items in groups:
        dirs = list(OrderedDict.fromkeys(r["direction"] for r in items if r["direction"]))
        combos = OrderedDict()
        for r in items:
            combos[_version_text(r)] = combos.get(_version_text(r), 0) + 1
        lines.append(f"| {n} | {' / '.join(dirs) or '—'} | {len(items)} | " + "；".join(f"{k} × {v}" for k, v in combos.items()) + " |")
    lines.append("")

    for n, items in groups:
        dirs = list(OrderedDict.fromkeys(r["direction"] for r in items if r["direction"]))
        lines += ["---", "", f"## 编号 {n} · {' / '.join(dirs) or '方向未知'}", "", "**原文**", "", _fence(items[0]["source"]), ""]
        for r in items:
            head = f"### {r['run_id']} · 方案：{_version_text(r)} · 模型：{r['model']} · 方向：{r['direction'] or r['direction_setting']} · {_hhmmss(r['time_utc'])} UTC · 用时 {r['seconds']} 秒"
            lines += [head, ""]
            if r["error"]:
                lines += ["**调用失败**", "", _fence(r["error"]), ""]
            else:
                lines += ["**第 1 步 初译**", "", _fence(r["step1"]), "",
                          "**第 2 步 审校意见**", "", _fence(r["step2"]), "",
                          "**第 3 步 定稿**", "", _fence(r["step3"]), ""]
            lines += ["**我认为的问题：**", "", "（留空，可在此补充）", ""]

    versions = OrderedDict()
    for _, items in groups:
        for r in items:
            versions.setdefault((r["scheme"], r["version"]), r["rules"])
    lines += ["---", "", "## 附：方案版本说明", ""]
    for (name, ver), rules in versions.items():
        title = f"{name}（{ver}）"
        if ver == NO_RULES_LABEL:
            lines += [f"### {title}", "", "Step 1 与 Step 3 都没有附加规则，与参考项目逐字一致。", ""]
        elif include_rules:
            lines += [f"### {title}", "", "**Step 1 初译附加规则**", "", _fence(rules["translator"]), "",
                      "**Step 3 定稿附加规则**", "", _fence(rules["improver"]), ""]
        else:
            lines += [f"### {title}", "", "（未附规则全文）", ""]
    return "\n".join(lines).rstrip() + "\n"


def build_json(runs, include_failed=False, include_rules=True):
    runs = _select(runs, include_failed)
    out_runs = []
    for _, items in _group(runs):
        for r in items:
            r = dict(r)
            if not include_rules:
                r["rules"] = None
            out_runs.append(r)
    payload = {"exported_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "note": "version 是方案规则（Step 1 与 Step 3 附加规则）的短哈希；case_id 按原文首次出现顺序编号，run_id 为 编号-a/b/c。",
               "runs": out_runs}
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
