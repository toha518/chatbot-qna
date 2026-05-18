with open('/home/ubuntu/chatbot/server.py', 'r') as f:
    content = f.read()

# Fix greeting error fallback
content = content.replace(
    'jawaban = f"Halo! Saya Cici Anova, asisten Q&A BPS Provinsi Kepulauan Bangka Belitung. Ada yang bisa saya bantu?"',
    'jawaban = ("Halo! Saya Cici Anova, asisten Q&A resmi BPS Provinsi Kepulauan Bangka Belitung. "
               "Saya bisa bantu menjawab pertanyaan seputar SOBAT, GC PBI, GC PLN, FASIH, "
               "dan Pengolahan SE2026. Silakan tanya saya seputar itu ya!")'
)

# Add retry to main DeepSeek call
old_main = """    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                DEEPSEEK_API,
                json={"model": MODEL, "messages": messages, "max_tokens": 500},
                headers={"Authorization": f"Bearer {API_KEY}"}
            )
        result = resp.json()
        jawaban = result["choices"][0]["message"]["content"]
    except Exception as e:
        jawaban = f"Maaf, terjadi error: {str(e)}\""""

new_main = """    async def call_deepseek(msgs, timeout=120):
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                DEEPSEEK_API,
                json={"model": MODEL, "messages": msgs, "max_tokens": 500},
                headers={"Authorization": f"Bearer {API_KEY}"}
            )
        return resp.json()["choices"][0]["message"]["content"]

    try:
        jawaban = await call_deepseek(messages)
    except Exception as e:
        try:
            await asyncio.sleep(1)
            jawaban = await call_deepseek(messages)
        except Exception as e2:
            jawaban = f"Maaf, terjadi error. Silakan coba lagi.\""""

if old_main in content:
    content = content.replace(old_main, new_main)
    print("✅ Main DeepSeek retry added")
else:
    print("⚠️ Main DeepSeek section not found, trying partial match...")
    # Find the try block
    import re
    match = re.search(r'    try:\n        async with httpx\.AsyncClient\(timeout=120\) as client:\n            resp = await client\.post\(', content)
    if match:
        print(f"  Found at position {match.start()}")

with open('/home/ubuntu/chatbot/server.py', 'w') as f:
    f.write(content)

import ast
ast.parse(content)
print("✅ Syntax OK")
