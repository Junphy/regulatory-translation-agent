if prompt := st.chat_input("在此输入或粘贴需要翻译的临床/法规文本..."):
        if not st.session_state.api_key or not st.session_state.base_url:
            st.error("❌ 尚未配置 API 接口与凭据，请点击右上角【⚙️ 设置】进行配置。")
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner(f"⏳ 正在通过 {st.session_state.base_url.split('://')[-1].split('/')[0]} 调用【{st.session_state.selected_model}】执行三阶段反思工作流..."):
                    try:
                        source_lang, target_lang, country = auto_detect_language(prompt)
                        active_t_skill = st.session_state.translator_profiles.get(st.session_state.active_t, "")
                        active_r_skill = st.session_state.reviewer_profiles.get(st.session_state.active_r, "")
                        
                        translation = run_agentic_translation(
                            source_text=prompt, source_lang=source_lang, target_lang=target_lang,
                            country=country, model=st.session_state.selected_model,
                            api_key=st.session_state.api_key, base_url=st.session_state.base_url,
                            trans_skill=active_t_skill, rev_skill=active_r_skill
                        )
                        
                        result_md = f"**【识别方向: {source_lang} ➡️ {target_lang} | 模型: {st.session_state.selected_model}】**\n\n{translation}"
                        st.markdown(result_md)
                        st.session_state.messages.append({"role": "assistant", "content": result_md})
                    except Exception as e:
                        err_msg = f"❌ 翻译出错: {str(e)}"
                        st.error(err_msg)
                        st.session_state.messages.append({"role": "assistant", "content": err_msg})

except Exception as fatal_error:
    st.error("🚨 页面渲染遇到严重错误！极有可能是配置文件异常。")
    st.code(traceback.format_exc())
