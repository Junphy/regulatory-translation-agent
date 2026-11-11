from openai import OpenAI

def fetch_openai_models(api_key, base_url):
    # 增加这两行：强制清除前后可能存在的多余空格、换行符或不可见字符
    api_key = api_key.strip() if api_key else api_key
    base_url = base_url.strip() if base_url else base_url
    
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        models = [m.id.replace("models/", "") for m in client.models.list().data if not any(kw in m.id.lower() for kw in ["embedding", "tts", "whisper", "dall-e", "image", "vision", "audio", "aqa", "realtime", "moderation", "instruct", "babbage", "davinci", "curie", "ada", "search", "similarity", "text-", "rerank", "question"])]
        return True, sorted(list(set(models)), reverse=True) if models else ["未获取到文本模型，请手动输入"]
    except Exception as e: 
        return False, str(e)
