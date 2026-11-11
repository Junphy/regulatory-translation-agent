# agent_core.py
import re
from openai import OpenAI

def auto_detect_language(text):
    if len(re.findall(r'[\u4e00-\u9fff]', text)) > 2 or (len(text.strip()) > 0 and len(re.findall(r'[\u4e00-\u9fff]', text)) / len(text.strip()) > 0.05):
        return "Chinese", "English", "United States"
    return "English", "Chinese", "China"

def call_llm(client, model, system_prompt, user_prompt):
    response = client.chat.completions.create(
        model=model, 
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], 
        temperature=0.3
    )
    return response.choices[0].message.content

def run_agentic_translation(source_text, model_name, api_key, base_url, trans_skill, rev_skill, imp_skill):
    client = OpenAI(api_key=api_key, base_url=base_url)
    source_lang, target_lang, country = auto_detect_language(source_text)
    
    init_prompt = f"Translate the following {source_lang} text into {target_lang} for {country}:\n\n{source_text}"
    init_translation = call_llm(client, model_name, trans_skill, init_prompt)
    
    review_prompt = f"Source Text ({source_lang}):\n{source_text}\n\nInitial Translation ({target_lang}):\n{init_translation}\n\nCritique this translation strictly against regulatory requirements, terminology consistency, and accuracy."
    critique = call_llm(client, model_name, rev_skill, review_prompt)
    
    improve_prompt = f"Source Text ({source_lang}):\n{source_text}\n\nInitial Translation:\n{init_translation}\n\nReviewer Critique:\n{critique}\n\nProvide the final, polished translation incorporating the critique above. Output ONLY the final translation without conversational text."
    final_translation = call_llm(client, model_name, imp_skill, improve_prompt)
    
    return f"{init_translation}", f"{critique}", final_translation
