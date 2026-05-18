"""
Test Anti-Spam Cici Anova
Simulasi dari sisi API (localhost:8000/chat)
Setiap test pake chat_id unik biar gak saling ganggu.
"""
import httpx
import time

BASE = "http://localhost:8000"

def p(section, msg, ok=True):
    icon = "✅" if ok else "❌"
    print(f"  {icon} {msg}")
    return ok

def unique_cid(prefix):
    return f"{prefix}-{int(time.time()*1000)}"

async def test_health():
    print("\n[1] HEALTH CHECK")
    async with httpx.AsyncClient() as c:
        resp = await c.get(f"{BASE}/health")
    data = resp.json()
    return p(1, f"Status: {data['status']}, Q&A: {data['total_qna']}", ok=data['status'] == 'ok')

async def test_duplicate_exact():
    print("\n[2] DUPLICATE EXACT MATCH")
    cid = unique_cid("t2")
    async with httpx.AsyncClient() as c:
        r1 = await c.post(f"{BASE}/chat", json={"pertanyaan": "Cara daftar SOBAT", "chat_id": cid})
        r2 = await c.post(f"{BASE}/chat", json={"pertanyaan": "Cara daftar SOBAT", "chat_id": cid})
    p(2, f"Pertama: skor={r1.json()['skor']:.3f}")
    is_blocked = r2.json()["jawaban"] == "" and r2.json()["skor"] == 0
    return p(2, f"Kedua (exact): {'DIBLOKIR ✅' if is_blocked else 'LOLOS ❌'}", ok=is_blocked)

async def test_duplicate_fuzzy():
    print("\n[3] DUPLICATE FUZZY (normalize + similarity > 0.9)")
    cid = unique_cid("t3")
    async with httpx.AsyncClient() as c:
        r1 = await c.post(f"{BASE}/chat", json={"pertanyaan": "Cara daftar SOBAT!!", "chat_id": cid})
        r2 = await c.post(f"{BASE}/chat", json={"pertanyaan": "cara daftar sobat", "chat_id": cid})
    p(3, f"Pertama: 'Cara daftar SOBAT!!' → skor={r1.json()['skor']:.3f}")
    is_blocked = r2.json()["jawaban"] == "" and r2.json()["skor"] == 0
    return p(3, f"Kedua: 'cara daftar sobat' → {'DIBLOKIR ✅' if is_blocked else 'LOLOS ❌'}", ok=is_blocked)

async def test_not_duplicate():
    print("\n[4] BUKAN DUPLICATE (beda pertanyaan)")
    cid = unique_cid("t4")
    async with httpx.AsyncClient() as c:
        r1 = await c.post(f"{BASE}/chat", json={"pertanyaan": "Cara daftar SOBAT", "chat_id": cid})
        r2 = await c.post(f"{BASE}/chat", json={"pertanyaan": "Reset password mitra error", "chat_id": cid})
    p(4, f"Pertama: 'Cara daftar SOBAT' → skor={r1.json()['skor']:.3f}")
    is_answered = r2.json()["jawaban"] != ""
    return p(4, f"Kedua: 'Reset password mitra error' → {'DIJAWAB ✅' if is_answered else 'DIBLOKIR ❌'}", ok=is_answered)

async def test_rate_limit():
    print("\n[5] RATE LIMIT — 20/min + warning sekali, sisanya silent")
    cid = unique_cid("t5")
    blocked_at = None
    got_warning = False
    silent_ok = False

    async with httpx.AsyncClient() as c:
        for i in range(25):
            msg = f"{i}{chr(65+i)}{chr(90-i)}{int(time.time())}{i**2}"
            resp = await c.post(f"{BASE}/chat", json={
                "pertanyaan": msg, "chat_id": cid
            })
            data = resp.json()
            if "⚠" in data["jawaban"] or "batas chat" in data["jawaban"]:
                blocked_at = i + 1
                got_warning = True
                # Cek silent setelah warning
                r2 = await c.post(f"{BASE}/chat", json={"pertanyaan": "setelah block 1", "chat_id": cid})
                r3 = await c.post(f"{BASE}/chat", json={"pertanyaan": "setelah block 2", "chat_id": cid})
                silent_ok = (r2.json()["jawaban"] == "" and r2.json()["skor"] == 0 and
                             r3.json()["jawaban"] == "" and r3.json()["skor"] == 0)
                break

    ok = blocked_at is not None and blocked_at <= 22 and got_warning and silent_ok
    details = f"Blok ke-{blocked_at}, warning={'✅' if got_warning else '❌'}, silent={'✅' if silent_ok else '❌'}"
    return p(5, details, ok=ok)

async def test_trusted_owner():
    print("\n[6] TRUSTED OWNER (lolos semua)")
    cid = "1267972859"  # Owner ID — trusted, unique by nature
    blocked = False

    async with httpx.AsyncClient() as c:
        for i in range(25):
            resp = await c.post(f"{BASE}/chat", json={
                "pertanyaan": f"Test owner nomor {i}",
                "chat_id": cid
            })
            data = resp.json()
            if "block" in data["jawaban"].lower() or (data["jawaban"] == "" and data["skor"] == 0):
                blocked = True
                break

    return p(6, f"25 pesan cepat owner → {'DIBLOKIR ❌' if blocked else 'LOLOS SEMUA ✅'}", ok=not blocked)

async def test_session_isolation():
    print("\n[7] SESSION ISOLASI — beda chat_id = beda tracking")
    ts = int(time.time() * 1000)
    cid_a = f"t7a-{ts}"
    cid_b = f"t7b-{ts}"
    teks = "Cara daftar SOBAT"

    async with httpx.AsyncClient() as c:
        r1 = await c.post(f"{BASE}/chat", json={"pertanyaan": teks, "chat_id": cid_a})
        p(7, f"Chat A (pertama): skor={r1.json()['skor']:.3f}")

        r2 = await c.post(f"{BASE}/chat", json={"pertanyaan": teks, "chat_id": cid_a})
        is_dup = r2.json()["jawaban"] == "" and r2.json()["skor"] == 0
        p(7, f"Chat A (lagi): {'DIBLOKIR ✅' if is_dup else 'lolos ❌'}", ok=is_dup)

        r3 = await c.post(f"{BASE}/chat", json={"pertanyaan": teks, "chat_id": cid_b})
        is_answered = r3.json()["jawaban"] != ""
        p(7, f"Chat B (beda session): {'DIJAWAB ✅' if is_answered else 'DIBLOKIR ❌'}", ok=is_answered)

    return is_dup and is_answered

async def run_all():
    print("=" * 55)
    print("  🧪 ANTI-SPAM TEST — CICI ANOVA")
    print("=" * 55)

    results = []
    results.append(await test_health())
    results.append(await test_duplicate_exact())
    results.append(await test_duplicate_fuzzy())
    results.append(await test_not_duplicate())
    results.append(await test_rate_limit())
    results.append(await test_trusted_owner())
    results.append(await test_session_isolation())

    passed = sum(results)
    total = len(results)

    print("\n" + "=" * 55)
    print(f"  📊 HASIL: {passed}/{total} lulus")
    if passed == total:
        print("  🎉 SEMUA TEST LULUS!")
    else:
        print(f"  ⚠️  {total - passed} test gagal")
    print("=" * 55)

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_all())
