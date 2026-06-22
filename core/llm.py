# core/llm.py — LLM: load config, call API with failover, build prompts

import os
import json
import asyncio
import time as _time
import httpx

# LLM config (diisi dari .env pas load_llm_config)
LLM_APIS: list[str] = []
LLM_KEYS: list[str] = []
LLM_MODELS: list[str] = []

# Per-provider timeout (detik) — urutan sesuai LLM_APIS.
# Provider 1 (OpenCode): skip cepat kalo lambat.
# Provider 2 (DeepSeek): lebih longgar.
# Provider 3 (Ollama): lokal, timeout besar.
_TIMEOUTS = [8, 12, 30]

# ── Shared httpx client dengan connection pooling ──
_llm_client: httpx.AsyncClient | None = None

async def _get_llm_client():
    global _llm_client
    if _llm_client is None:
        _llm_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            headers={"Content-Type": "application/json"}
        )
        print(f"[LLM] Shared httpx client initialized (pool: max_connections=20, keepalive=10)")
    return _llm_client


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


def load_kbli_template() -> str:
    """Load KBLI prompt template dari prompts/kbli.md"""
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
    path = os.path.join(base, "kbli.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def build_kbli_prompt(kbli_template: str, identity: dict, user_query: str, context: str) -> list[dict]:
    """Buat messages list untuk KBLI lookup"""
    system_content = kbli_template.format(
        name=identity["name"],
        role=identity["role"],
        context=context
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_query}
    ]


def load_kbli_expand_template() -> str:
    """Load KBLI expand prompt template dari prompts/kbli_expand.md"""
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
    path = os.path.join(base, "kbli_expand.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def build_kbli_expand_prompt(template: str, clean_query: str) -> list[dict]:
    """Buat messages list untuk KBLI query expansion"""
    system_content = template.format(text=clean_query)
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": clean_query}
    ]


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
    _resp = load_responses()
    return system_template.format(
        name=identity["name"],
        role=identity["role"],
        topics=topics_line,
        topics_checklist=topics_checklist,
        topics_line=topics_line,
        personality=personality,
        acronyms=acronyms,
        rejection_no_answer=_resp.get("rejection_no_answer", "")
    )


async def call_llm(messages: list[dict], timeout: int = 30):
    """
    Panggil LLM dengan failover chain — skip cepat tanpa retry.
    - Per-provider timeout: Provider 1 = 8s, Provider 2 = 12s, Provider 3+ = 30s
    - Error classification: 401/403 skip, 429/502/503/504 skip cepat
    - Ollama lokal via asyncio.to_thread (non-blocking)
    Returns tuple (jawaban, model_name, provider_name, time_ms).
    """
    for i in range(len(LLM_APIS)):
        p_timeout = _TIMEOUTS[i] if i < len(_TIMEOUTS) else timeout
        try:
            api = LLM_APIS[i]
            key = LLM_KEYS[i]
            model = LLM_MODELS[i]
            t0 = _time.time()

            # ── Ollama lokal — async via thread ──
            if "localhost:11434" in api or "127.0.0.1:11434" in api:
                from ollama import chat
                response = await asyncio.to_thread(chat, model=model, messages=messages)
                elapsed = int((_time.time() - t0) * 1000)
                print(f"[LLM] ✅ Provider {i+1} — {model} (Ollama lokal) [{elapsed}ms]")
                return response.message.content, model, f"ollama:{i+1}", elapsed

            # ── API eksternal ──
            client = await _get_llm_client()
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

            resp = await client.post(api, json=payload, headers=headers, timeout=p_timeout)

            # ── Error Classification — skip cepat ──
            if resp.status_code in (401, 403):
                print(f"[LLM] ❌ Provider {i+1} — {model} — API key error ({resp.status_code}), skip permanent")
                break

            if resp.status_code in (502, 503, 504):
                print(f"[LLM] ❌ Provider {i+1} — {model} — Service down ({resp.status_code}), skip cepat")
                continue

            if resp.status_code == 429:
                print(f"[LLM] ❌ Provider {i+1} — {model} — Rate limited (429), skip ke provider berikutnya")
                continue

            result = resp.json()

            if "choices" not in result or not result["choices"]:
                err_msg = result.get("error", {}).get("message", str(result))
                print(f"[LLM] ❌ Provider {i+1} — {model} — No choices: {err_msg}")
                continue

            elapsed = int((_time.time() - t0) * 1000)
            print(f"[LLM] ✅ Provider {i+1} — {model} [{elapsed}ms]")
            return result["choices"][0]["message"]["content"], model, f"provider:{i+1}", elapsed

        except httpx.TimeoutException:
            print(f"[LLM] ❌ Provider {i+1} — {LLM_MODELS[i]} — Timeout ({p_timeout}s), skip cepat")
            continue

        except httpx.ConnectError:
            print(f"[LLM] ❌ Provider {i+1} — {LLM_MODELS[i]} — Connection error, skip cepat")
            continue

        except Exception as e:
            print(f"[LLM] ❌ Provider {i+1} — {LLM_MODELS[i]} gagal: {e}")
            continue

    return None, "", "", 0
