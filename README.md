# regulatory-translation-agent

面向法规与临床文本的三步翻译智能体（初译、审校、定稿），目标是符合 ICH、FDA 与 CDE 的术语和格式要求。

## 与参考项目的关系

本项目复刻 [Andrew Ng 的 Translation Agent](https://github.com/andrewyng/translation-agent)（`src/translation_agent/utils.py`）中的反思式翻译流程，并且**只在 prompt 层做优化**。

核心流程的复刻范围是参考项目的单块路径：`one_chunk_initial_translation`、`one_chunk_reflect_on_translation`、`one_chunk_improve_translation`。三步的 user 模板（任务说明与 XML 标签）与参考项目逐字一致，温度为 0.3，`top_p` 为 1。

## 与参考项目的偏离

以下偏离都在 `agent_core.py` 中以 `DEVIATION` 标出：

- **不做分块**：没有 `translate()` 入口与 `multichunk_*` 函数，输入长度由使用者自行控制，超出模型上限时由接口报错。
- **语言方向自动判断**：参考项目由调用方显式传入语言；这里用 `detect_languages` 根据汉字个数与英文单词个数判断，只支持中英互译。
- **`country` 固定为空**：走参考项目的无 country 分支，不要求“口语风格”。
- **附加规则**：界面里的 profile 内容追加在 system 消息的角色句之后；为空时发给模型的消息与参考项目逐字一致。
- **模型调用**：`get_completion` 增加 `client` 参数以支持自定义 `base_url` 与 API Key，并去掉了三步用不到的 `json_mode`。
- **返回值**：参考项目只返回最终译文；这里返回初译、审校意见、定稿与方向标签，供界面展示。

## Prompt 的组织方式

界面中每一步都可以选择 profile，profile 的内容是“附加规则”：

- **参考原版（默认）**：没有附加规则，只使用参考项目的原文。该 profile 在界面中只读。
- **医学版**：面向生命科学与法规文本。第 1 步（初译）按 CDE/FDA 文风、官方译名优先、标签与符号保护、全角标点与中西文空格规则整理；第 2 步（审校）不加规则，与参考原版一致；第 3 步（定稿）要求保持原文含义的前提下做学术化润色，并规定了审校意见与原文或规则冲突时的取舍。

可以在设置里基于任一模板“另存为新模板”。

## 配置与安全

设置界面会把 API 密钥明文保存到本地的 `config.json`，该文件已被 `.gitignore` 忽略。升级到本版本后首次读取旧版 `config.json` 时，旧 profile 会归档到 `skills_legacy`（点击“保存全部配置并生效”后写入文件），并重置为新的内置 profile。

## 运行

```bash
pip install -r requirements.txt
streamlit run app.py
```
