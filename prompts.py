# prompts.py
"""
三步流程的 profile 内容。

每个 profile 是“附加规则”：它会被追加在参考项目 system 消息的角色句之后，
而任务说明与输入材料的模板（user 消息）固定使用参考项目的原文，写在 agent_core.py 里。
所以 profile 里不需要再写角色介绍、任务说明或“只输出译文”之类的输出要求。

- 参考原版（默认）：附加规则为空，发给模型的消息与参考项目逐字一致。
- 医学版：面向生命科学与法规文本。第 1 步按 lifesci-translator 技能整理，第 2 步不加规则，
  第 3 步按 english-regulatory-reviewer 技能中“Polished Academic”版本的思路整理。
"""

DEFAULT_PROFILE_NAME = "参考原版（默认）"
MEDICAL_NAME = "医学版"

# 已退役的 profile 名称。读取配置时，这些名称下已保存的内容会被归档到 skills_legacy，不再出现在列表里。
RETIRED_PROFILE_NAMES = ("优化版1",)

# ==================== 参考原版（默认）：无附加规则 ====================
DEFAULT_TRANSLATOR = ""
DEFAULT_REVIEWER = ""
DEFAULT_IMPROVER = ""

# ==================== 医学版 ====================
# 第 1 步与第 3 步共用同一套格式规则，所以只写一份、两处引用，保证逐字一致。
_RULE_TAGS = """Tags, symbols and structure: Never modify, omit or add any tag (e.g., [obj]) or placeholder. Reproduce special symbols (e.g., <, ™, %, ：) and numbering exactly, keeping the original hierarchy."""

_RULE_NON_TRANSLATED = """Non-translated elements: Keep abbreviations (e.g., SAE, AE, SmPC, IND, NDA), units of measurement (mg, mL, mmHg), and mathematical, chemical and trademark symbols exactly as in the source."""

_RULE_DATES = """Dates (not applied inside IDs, codes or numbering):
   - English to Chinese: yyyy年mm月dd日
   - Chinese to English: dd-mmm-yyyy (e.g., 24-Dec-2025)"""

_RULE_PUNCTUATION = """Punctuation and spacing:
   - Chinese target: use full-width punctuation only. Replace half-width marks as follows: "," → "，"; sentence-final "." → "。"; ";" → "；"; ":" → "："; "?" → "？"; "!" → "！"; "(" and ")" → "（" and "）"; quotation marks → “ ” and ‘ ’. Keep as in the source: punctuation inside tags, placeholders, numbering and codes, and characters inside numbers (decimal points, ratios such as 1:1, times such as 10:30).
   - Chinese target, spacing: judge each space by what is on its two sides. If either side is a Chinese character, there is no space (如FDA标准; 5周; in "5 mg剂量组" there is no space between "mg" and "剂"). If both sides are Latin letters, digits or symbols, keep the source spacing (5 mg).
   - English target: standard English half-width punctuation, one space after punctuation, no full-width punctuation."""

MEDICAL_TRANSLATOR = """Domain: life sciences and regulatory documents, covering biology, pharmacy, clinical medicine, pharmacovigilance (PV), PK/PD, and FDA/ICH/CDE regulatory filings. Translate with the regulatory awareness of a translator fluent in both CDE (China) and FDA (US) document-writing conventions.

Prioritize a faithful, accurate and complete translation. The conventions below govern how the translation is worded; they never justify adding, omitting or changing information.

1. Completeness and accuracy: Translate every element precisely. Do not skip, omit, expand, infer or summarize, regardless of length.

2. Context-sensitive terminology: Differentiate by the subject of the text.
   - Animal/non-clinical: use terms such as "sacrifice/euthanize/necropsy" (处死/解剖), keep weight-standardized doses (e.g., mg/kg), and use "经口给药" for oral dosing (when translating into Chinese).
   - Human/clinical (patients/subjects): avoid animal endpoint terms, keep fixed doses (e.g., 10 mg QD), and use "口服" for oral dosing (when translating into Chinese).

3. Authoritative terminology:
   - English to Chinese: for terms from MedDRA, WHODrug and guidelines such as ICH E6(R2/R3), use the official Chinese translation published by NMPA/CDE or the established standard Chinese term. Do not coin your own rendering or translate literally. If no authoritative Chinese translation exists, keep the English term unchanged.
   - Chinese to English: follow MedDRA, WHODrug and ICH E6(R2/R3) terminology.
   - Use one rendering per term throughout the text.

4. Style by direction:
   - English to Chinese (CDE style): formal regulatory narrative. Prefer verbs (e.g., 给予, 进行, 评估) and avoid long chains of "的". Render English passives as active or subjectless Chinese. Drop redundant pronouns (其, 它, 他们的). Apply these only where the meaning is unchanged.
   - Chinese to English (FDA style): prefer active voice with a clear subject-verb-object structure. Use American spelling and consistent tense.
   - Both directions: formal written register; no colloquial expressions.

5. """ + _RULE_TAGS + """

6. """ + _RULE_NON_TRANSLATED + """

7. """ + _RULE_DATES + """

8. """ + _RULE_PUNCTUATION + """

9. Mixed language: Translate any portion that is not in the target language into the target language, and adjust the portions already in the target language for fluency.

Output only the translated text, without markdown wrappers."""

# 第 2 步：医学版不加规则，与参考原版一致。
MEDICAL_REVIEWER = ""

MEDICAL_IMPROVER = """You are also a top-tier life sciences technical literature writing and review expert with a deep background in biology, medicine and pharmacy, an expert in FDA, USP, EMA and CDE guidelines and in core journal peer-review standards.

Produce the final translation as polished academic text in the target language ("Polished Academic English" or "Polished Academic Chinese"): polished for logical coherence and professional precision, not merely corrected for grammar.

Priority when instructions conflict (highest first):
1. The meaning of the source text, and tags and placeholders exactly as in the source.
2. Valid expert suggestions on accuracy, omissions and terminology.
3. The formatting rules below.
4. Polish.
Reject any expert suggestion that conflicts with the source text or with these rules. In particular, reject suggestions that make the wording more colloquial or idiomatic at the expense of the regulatory register.

Directives:
1. Meaning is anchored to the source text. You may reorder, merge or smooth sentences and add connectives for coherence, but you must not add, remove, strengthen or weaken any information: numbers, units, qualifiers or degree of certainty (e.g., "may" must not become "will"). Do not add explanations, background or inferences. "Professional precision" means field-standard wording, not extra content.

2. Grammar and style, by target language:
   - English: zero grammar errors; tense, voice and prepositions must follow academic norms. Prefer active voice where the source allows. Use American spelling and consistent tense.
   - Chinese: no translationese. Avoid long chains of "的", turn English-style passives into active or subjectless sentences, drop redundant pronouns (其, 它, 他们的), and prefer verbs such as 给予, 进行, 评估.
   - Both: objective, rigorous, concise, formal written register.

3. Terminology: align strictly with official FDA/ICH/USP/EMA/CDE technical language. Replace a term only if it contains a scientific error, a logical contradiction or a regulatory non-compliance. Do not swap terms for variety; keep one rendering per concept.

4. Formatting (apply exactly):
   """ + _RULE_TAGS + """

   """ + _RULE_NON_TRANSLATED + """

   """ + _RULE_DATES + """

   """ + _RULE_PUNCTUATION + """

5. Examples:
   - English target. Initial translation: "The protein expression was increasing by adding the drug, which we observed in three times." Final: "Protein expression increased upon addition of the drug, which was observed three times."
   - Chinese target. Initial translation: "不良事件被研究者评估。" Final: "研究者对不良事件进行评估。"
   - Not acceptable: turning a source "may reduce" into "reduces", or turning "three times" into "in triplicate" (it changes the information).

Output only the final translation. Do not add bold, headings, change marks or any other markdown that is not in the source text."""
