"""
بوت تيليجرام يرسل يوميًا 10 أكواد بايثون (خوارزميات/حلول مسائل)
مصدر الأكواد: مستودع TheAlgorithms/Python على GitHub
يشتغل عبر GitHub Actions (cron) بدون سيرفر.
"""

import os
import json
import random
import time
import requests

# ============ إعدادات ============
GITHUB_REPO = "TheAlgorithms/Python"
GITHUB_BRANCH = "master"
FILES_PER_DAY = 10
MAX_CODE_CHARS = 3500  # تيليجرام يحدد 4096 حرف بالرسالة، نخلي هامش أمان

# مجلدات نتجنبها (مو أكواد "حل مسألة"، غالبًا اختبارات/بيانات)
EXCLUDED_DIR_PREFIXES = (
    "scripts/",
    ".github/",
    "web_programming/",  # يحتاج مكتبات خارجية أحيانًا، اختياري تستبعده
)
EXCLUDED_FILENAME_PARTS = ("test_", "__init__.py", ".broken.txt", "conftest.py")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]  # مثال: @mychannel أو -1001234567890

STATE_FILE = "sent_files.json"  # يحفظ أسماء الملفات المُرسلة قبل عشان ما تتكرر


# ============ أدوات مساعدة ============
def load_sent_files():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_sent_files(sent_set):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(sent_set), f, ensure_ascii=False, indent=2)


def get_all_python_files():
    """يجيب قائمة كل ملفات .py بالمستودع عبر GitHub Trees API (طلب وحد فقط)."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/git/trees/{GITHUB_BRANCH}?recursive=1"
    headers = {"Accept": "application/vnd.github+json"}
    # لو عندك GitHub token حط بمتغير بيئة GITHUB_TOKEN لرفع حد الطلبات (اختياري)
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    tree = resp.json()["tree"]

    files = []
    for item in tree:
        if item["type"] != "blob":
            continue
        path = item["path"]
        if not path.endswith(".py"):
            continue
        if any(path.startswith(prefix) for prefix in EXCLUDED_DIR_PREFIXES):
            continue
        if any(part in path for part in EXCLUDED_FILENAME_PARTS):
            continue
        files.append(path)
    return files


def fetch_raw_code(path):
    """يجيب محتوى الملف الخام من raw.githubusercontent.com"""
    url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{path}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def format_message(path, code):
    """يجهز نص الرسالة بصيغة Markdown مع كود بلوك."""
    title = path.split("/")[-1]
    category = "/".join(path.split("/")[:-1]) or "general"

    if len(code) > MAX_CODE_CHARS:
        code = code[:MAX_CODE_CHARS] + "\n# ... (تم الاقتصاص، شوف الملف كامل بالرابط)"

    source_link = f"https://github.com/{GITHUB_REPO}/blob/{GITHUB_BRANCH}/{path}"

    message = (
        f"🐍 *{title}*\n"
        f"📂 التصنيف: `{category}`\n\n"
        f"```python\n{code}\n```\n"
        f"🔗 [المصدر الكامل]({source_link})"
    )
    return message


def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=30)
    if not resp.ok:
        print(f"⚠️ فشل الإرسال: {resp.status_code} - {resp.text}")
    resp.raise_for_status()
    return resp.json()


# ============ المنطق الرئيسي ============
def main():
    sent_files = load_sent_files()
    all_files = get_all_python_files()

    # استبعد اللي انبعث قبل
    available = [f for f in all_files if f not in sent_files]

    # لو خلصت كل الملفات، صفّر السجل وابدأ من جديد
    if len(available) < FILES_PER_DAY:
        print("♻️ خلصت كل الملفات، يتم تصفير السجل والبدء من جديد.")
        sent_files = set()
        available = all_files

    chosen = random.sample(available, min(FILES_PER_DAY, len(available)))

    print(f"📦 تم اختيار {len(chosen)} ملف لهذا اليوم.")

    for i, path in enumerate(chosen, start=1):
        try:
            code = fetch_raw_code(path)
            message = format_message(path, code)
            send_to_telegram(message)
            sent_files.add(path)
            print(f"✅ ({i}/{len(chosen)}) تم إرسال: {path}")
        except Exception as e:
            print(f"❌ فشل إرسال {path}: {e}")
        time.sleep(3)  # نتفادى rate limit تيليجرام

    save_sent_files(sent_files)
    print("🎉 انتهى الإرسال لهذا اليوم.")


if __name__ == "__main__":
    main()
