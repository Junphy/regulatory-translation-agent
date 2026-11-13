# agent_core.py
"""
反思式三步翻译流程：初译 -> 审校（reflection）-> 定稿（improvement）。

三个步骤是对 andrewyng/translation-agent 的 src/translation_agent/utils.py
中【单块路径】的复刻，user 模板与参考项目逐字一致。
与参考项目的全部偏离都用 "# DEVIATION" 标出，共 5 处：

1. get_completion 增加 client 参数（支持界面里配置的 base_url 与 API Key），去掉未被三步使用的 json_mode。
2. 三个 one_chunk_* 函数的第一个参数是 llm（见 make_llm），其余参数与参考一致，末尾多一个 extra_rules。
3. extra_rules（界面里的 profile 内容）追加在 system 消息的角色句之后；为空时与参考完全一致。
4. 不做分块：输入长度由使用者自行控制，因此没有 translate() 入口与 multichunk_* 函数。
5. 语言方向由 detect_languages 自动判断，country 固定为空字符串（走参考项目的无 country 分支）。
"""
import re
from typing import Callable, Tuple

from openai import OpenAI


def get_completion(
    client,  # DEVIATION: 参考项目使用模块级全局 client，这里由调用方传入
    prompt: str,
    system_message: str = "You are a helpful assistant.",
    model: str = "gpt-4-turbo",
    temperature: float = 0.3,
) -> str:
    """Generate a completion using an OpenAI-compatible API."""

    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        top_p=1,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def make_llm(client, model: str) -> Callable[..., str]:  # DEVIATION
    """把 client 与 model 绑定成 llm(prompt, system_message) 调用。"""

    def llm(prompt: str, system_message: str = "You are a helpful assistant.") -> str:
        return get_completion(client, prompt, system_message=system_message, model=model)

    return llm


def with_rules(system_message: str, extra_rules: str = "") -> str:  # DEVIATION
    """把附加规则追加到 system 消息之后；规则为空时原样返回，与参考项目一致。"""

    extra_rules = (extra_rules or "").strip()
    if not extra_rules:
        return system_message
    return f"{system_message}\n\n{extra_rules}"


def one_chunk_initial_translation(
    llm, source_lang: str, target_lang: str, source_text: str, extra_rules: str = ""
) -> str:
    """Translate the entire text as one chunk using an LLM."""

    system_message = f"You are an expert linguist, specializing in translation from {source_lang} to {target_lang}."

    translation_prompt = f"""This is an {source_lang} to {target_lang} translation, please provide the {target_lang} translation for this text. \
Do not provide any explanations or text apart from the translation.
{source_lang}: {source_text}

{target_lang}:"""

    translation = llm(translation_prompt, system_message=with_rules(system_message, extra_rules))

    return translation


def one_chunk_reflect_on_translation(
    llm,
    source_lang: str,
    target_lang: str,
    source_text: str,
    translation_1: str,
    country: str = "",
    extra_rules: str = "",
) -> str:
    """Use an LLM to reflect on the translation, treating the entire text as one chunk."""

    system_message = f"You are an expert linguist specializing in translation from {source_lang} to {target_lang}. \
You will be provided with a source text and its translation and your goal is to improve the translation."

    if country != "":
        reflection_prompt = f"""Your task is to carefully read a source text and a translation from {source_lang} to {target_lang}, and then give constructive criticism and helpful suggestions to improve the translation. \
The final style and tone of the translation should match the style of {target_lang} colloquially spoken in {country}.

The source text and initial translation, delimited by XML tags <SOURCE_TEXT></SOURCE_TEXT> and <TRANSLATION></TRANSLATION>, are as follows:

<SOURCE_TEXT>
{source_text}
</SOURCE_TEXT>

<TRANSLATION>
{translation_1}
</TRANSLATION>

When writing suggestions, pay attention to whether there are ways to improve the translation's \n\
(i) accuracy (by correcting errors of addition, mistranslation, omission, or untranslated text),\n\
(ii) fluency (by applying {target_lang} grammar, spelling and punctuation rules, and ensuring there are no unnecessary repetitions),\n\
(iii) style (by ensuring the translations reflect the style of the source text and take into account any cultural context),\n\
(iv) terminology (by ensuring terminology use is consistent and reflects the source text domain; and by only ensuring you use equivalent idioms {target_lang}).\n\

Write a list of specific, helpful and constructive suggestions for improving the translation.
Each suggestion should address one specific part of the translation.
Output only the suggestions and nothing else."""

    else:
        reflection_prompt = f"""Your task is to carefully read a source text and a translation from {source_lang} to {target_lang}, and then give constructive criticisms and helpful suggestions to improve the translation. \

The source text and initial translation, delimited by XML tags <SOURCE_TEXT></SOURCE_TEXT> and <TRANSLATION></TRANSLATION>, are as follows:

<SOURCE_TEXT>
{source_text}
</SOURCE_TEXT>

<TRANSLATION>
{translation_1}
</TRANSLATION>

When writing suggestions, pay attention to whether there are ways to improve the translation's \n\
(i) accuracy (by correcting errors of addition, mistranslation, omission, or untranslated text),\n\
(ii) fluency (by applying {target_lang} grammar, spelling and punctuation rules, and ensuring there are no unnecessary repetitions),\n\
(iii) style (by ensuring the translations reflect the style of the source text and take into account any cultural context),\n\
(iv) terminology (by ensuring terminology use is consistent and reflects the source text domain; and by only ensuring you use equivalent idioms {target_lang}).\n\

Write a list of specific, helpful and constructive suggestions for improving the translation.
Each suggestion should address one specific part of the translation.
Output only the suggestions and nothing else."""

    reflection = llm(reflection_prompt, system_message=with_rules(system_message, extra_rules))
    return reflection


def one_chunk_improve_translation(
    llm,
    source_lang: str,
    target_lang: str,
    source_text: str,
    translation_1: str,
    reflection: str,
    extra_rules: str = "",
) -> str:
    """Use the reflection to improve the translation, treating the entire text as one chunk."""

    system_message = f"You are an expert linguist, specializing in translation editing from {source_lang} to {target_lang}."

    prompt = f"""Your task is to carefully read, then edit, a translation from {source_lang} to {target_lang}, taking into
account a list of expert suggestions and constructive criticisms.

The source text, the initial translation, and the expert linguist suggestions are delimited by XML tags <SOURCE_TEXT></SOURCE_TEXT>, <TRANSLATION></TRANSLATION> and <EXPERT_SUGGESTIONS></EXPERT_SUGGESTIONS> \
as follows:

<SOURCE_TEXT>
{source_text}
</SOURCE_TEXT>

<TRANSLATION>
{translation_1}
</TRANSLATION>

<EXPERT_SUGGESTIONS>
{reflection}
</EXPERT_SUGGESTIONS>

Please take into account the expert suggestions when editing the translation. Edit the translation by ensuring:

(i) accuracy (by correcting errors of addition, mistranslation, omission, or untranslated text),
(ii) fluency (by applying {target_lang} grammar, spelling and punctuation rules and ensuring there are no unnecessary repetitions), \
(iii) style (by ensuring the translations reflect the style of the source text)
(iv) terminology (inappropriate for context, inconsistent use), or
(v) other errors.

Output only the new translation and nothing else."""

    translation_2 = llm(prompt, with_rules(system_message, extra_rules))

    return translation_2


# ==================== 语言方向自动判断（参考项目没有这一步，由调用方显式传参） ====================
# DEVIATION: 参考项目要求调用方传入 source_lang、target_lang；这里根据文本自动判断。
# 规则：只统计汉字个数与英文单词个数（忽略数字、标点、单位符号），汉字个数不少于英文单词个数时视为中文。
# 这是启发式规则，只支持中英互译；没有汉字时一律视为英文。
_HAN_CHAR = re.compile(r"[一-鿿]")
_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")

_DIRECTION_LABELS = {
    ("Chinese", "English"): "中译英",
    ("English", "Chinese"): "英译中",
}


def detect_languages(text: str) -> Tuple[str, str]:
    """返回 (source_lang, target_lang)。"""

    han_count = len(_HAN_CHAR.findall(text))
    latin_word_count = len(_LATIN_WORD.findall(text))
    if han_count > 0 and han_count >= latin_word_count:
        return "Chinese", "English"
    return "English", "Chinese"


def run_agentic_translation(source_text, model_name, api_key, base_url, trans_skill, rev_skill, imp_skill):
    """
    按参考项目 one_chunk_translate_text 的顺序依次执行三步。

    DEVIATION: 参考项目只返回最终译文；界面需要展示每一步，所以这里返回
    (初译, 审校意见, 定稿, 方向标签)。trans_skill、rev_skill、imp_skill 是界面里选中的
    profile 内容，作为附加规则追加到对应步骤的 system 消息之后。
    """
    client = OpenAI(api_key=api_key, base_url=base_url)
    llm = make_llm(client, model_name)

    source_lang, target_lang = detect_languages(source_text)
    country = ""  # DEVIATION: 固定为空，走参考项目的无 country 分支（不要求口语风格）

    translation_1 = one_chunk_initial_translation(
        llm, source_lang, target_lang, source_text, trans_skill
    )

    reflection = one_chunk_reflect_on_translation(
        llm, source_lang, target_lang, source_text, translation_1, country, rev_skill
    )

    translation_2 = one_chunk_improve_translation(
        llm, source_lang, target_lang, source_text, translation_1, reflection, imp_skill
    )

    direction = _DIRECTION_LABELS[(source_lang, target_lang)]
    return translation_1, reflection, translation_2, direction
