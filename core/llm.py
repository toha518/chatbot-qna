# core/llm.py — LLM: load config, call API with failover, build prompts

import os
import json
import time as _time
import httpx

# LLM config (diisi dari .env pas load_llm_config)
LLM_APIS: list[str] = []
LLM_KEYS: list[str] = []
LLM_MODELS: list[str] = []


def load_responses() -> dict:
    """
    Baca file prompts/responses.json — semua teks jawaban statis.
    Ganti di sini aja, semua file .py otomatis dapet update.
    """
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
    path = os.path.join(base, "responses.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_llm_config() -> int:
    """
    Baca LLM config dari .env.
    Format: LLM_API_1, LLM_API_KEY_1, LLM_MODEL_1 (dst sampai 50)
    """
    global LLM_APIS, LLM_KEYS, LLM_MODELS
    LLM_APIS = []
    LLM_KEYS = []
    LLM_MODELS = []

    for i in range(1, 51):
        api = os.getenv(f"LLM_API_{i}")
        key = os.getenv(f"LLM_API_KEY_{i}")
        model = os.getenv(f"LLM_MODEL_{i}")
        if api and key and model:
            LLM_APIS.append(api)
            LLM_KEYS.append(key)
            LLM_MODELS.append(model)

    count = len(LLM_APIS)
    if count == 0:
        print("[LLM] ⚠️  TIDAK ADA LLM CONFIG! Set LLM_API_1, LLM_API_KEY_1, LLM_MODEL_1 di .env")
    else:
        print(f"[LLM] {count} provider loaded")
    return count


def load_prompts():
    """
    Baca file prompts dari folder prompts/.
    Returns (identity_dict, system_template_str, greeting_template_str, acronyms_str).
    """
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")

    with open(os.path.join(base, "identity.json"), "r", encoding="utf-8") as f:
        identity = json.load(f)

    with open(os.path.join(base, "system.md"), "r", encoding="utf-8") as f:
        system_template = f.read()

    with open(os.path.join(base, "greeting.md"), "r", encoding="utf-8") as f:
        greeting_template = f.read()

    # Load acronyms file kalo ada
    acronyms = ""
    acr_path = os.path.join(base, "acronyms.md")
    if os.path.exists(acr_path):
        with open(acr_path, "r", encoding="utf-8") as f:
            acronyms = f.read()

    return identity, system_template, greeting_template, acronyms


def build_greeting_prompt(greeting_template: str, identity: dict, user_query: str, acronyms: str = "") -> list[dict]:
    """Buat messages list untuk greeting"""
    topics_str = ", ".join(identity["topics"])
    system_content = greeting_template.format(
        name=identity["name"],
        role=identity["role"],
        topics=topics_str,
        acronyms=acronyms
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_query}
    ]


def build_system_prompt(system_template: str, identity: dict, acronyms: str = "") -> str:
    """Render system prompt dengan identitas bot"""
    topics_line = ", ".join(identity["topics"])
    topics_checklist = "\n".join(f"{i+1}. {t}" for i, t in enumerate(identity["topics"]))
    personality = identity.get("personality", "")
    return system_template.format(
        name=identity["name"],
        role=identity["role"],
        topics=topics_line,
        topics_checklist=topics_checklist,
        topics_line=topics_line,
        personality=personality,
        acronyms=acronyms
    )


async def call_llm(messages: list[dict], timeout: int = 30):
    """
    Panggil LLM dengan failover chain.
    Returns tuple (jawaban, model_name, provider_name, time_ms).
    """
    for i in range(len(LLM_APIS)):
        try:
            api = LLM_APIS[i]
            key = LLM_KEYS[i]
            model = LLM_MODELS[i]
            t0 = _time.time()

            # Pakai library ollama langsung kalo lokal
            if "localhost:11434" in api or "127.0.0.1:11434" in api:
                from ollama import chat
                response = chat(model=model, messages=messages)
                elapsed = int((_time.time() - t0) * 1000)
                print(f"[LLM] ✅ Provider {i+1} — {model} (Ollama lokal) [{elapsed}ms]")
                return response.message.content, model, f"ollama:{i+1}", elapsed

            # API eksternal — pake httpx
            async with httpx.AsyncClient(timeout=timeout) as client:
                payload = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": 2000,
                    "temperature": 0.1
                }

                if "deepseek" in model.lower():
                    payload["thinking"] = {"type": "disabled"}

                headers = {}
                if key and key != "***":
                    headers["Authorization"] = f"Bearer {key}"

                resp = await client.post(api, json=payload, headers=headers)
                result = resp.json()

                if "choices" not in result or not result["choices"]:
                    err_msg = result.get("error", {}).get("message", str(result))
                    raise Exception(f"API {resp.status_code}: {err_msg}")

                elapsed = int((_time.time() - t0) * 1000)
                print(f"[LLM] ✅ Provider {i+1} — {model} [{elapsed}ms]")
                return result["choices"][0]["message"]["content"], model, f"provider:{i+1}", elapsed

        except Exception as e:
            print(f"[LLM] ❌ Provider {i+1} — {LLM_MODELS[i]} gagal: {e}")
            continue

    return None, "", "", 0
