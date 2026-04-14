import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import re
import time
import threading
import requests
import pandas as pd
from datetime import datetime, date
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import smtplib
from email.message import EmailMessage

# =========================
# GLOBAL STATE
# =========================

PROCESSED_FILES = set()
AGENT_EMAIL_MAP = {}
LAST_SUMMARY_DATE = None

# =========================
# CONFIG
# =========================

BASE_DIR = os.getcwd()
TRANSCRIPTS_DIR = os.path.join(BASE_DIR, "transcripts")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
AGENT_REPORTS_DIR = os.path.join(REPORTS_DIR, "agents")
CONFIG_DIR = os.path.join(BASE_DIR, "config")

MASTER_REPORT_PATH = os.path.join(REPORTS_DIR, "qa_master_report.xlsx")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "phi"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_EMAIL = "YOUR_EMAIL@gmail.com"
SMTP_PASSWORD = "YOUR_APP_PASSWORD"

TL_EMAIL = "tl@example.com"
QA_EMAIL = "qa@example.com"

DAILY_EMAIL_HOUR = 19
DAILY_EMAIL_MINUTE = 0

# =========================
# QA PROMPT
# =========================

QA_PROMPT = """
You are a Call Quality Assurance (QA) Auditor.

Evaluate the call transcript strictly based on the QA parameters below.
Do not assume anything not present in the transcript.

QA PARAMETERS:

1. Call Opening (Max 20)
2. Introduction & Purpose of Call (Max 5)
3. Probing Skills (Max 10)
4. DM Identification / Contact Confirmation (Max 15)
5. Product Knowledge & Value Pitch (Max 20)
6. Handling Objections (Max 20)
7. CRM Tagging (Max 10)

Transcript:
<<<
{transcript}
>>>

You MUST include a section exactly titled:

Call Summary:
<one professional paragraph>

If Call Summary is missing, the response is invalid.
Do NOT include explanations, puzzles, or meta discussion.
Do NOT write anything after Call Summary.

"""

# =========================
# LOAD AGENT EMAILS
# =========================

def load_agent_emails():
    path = os.path.join(CONFIG_DIR, "agents.csv")
    if not os.path.exists(path):
        print("⚠️ agents.csv not found")
        return

    df = pd.read_csv(path)
    for _, r in df.iterrows():
        AGENT_EMAIL_MAP[r["agent_id"]] = r["email"]

    print("✅ Agent email map loaded")

# =========================
# UTILITIES
# =========================

def parse_filename(name):
    m = re.match(r'^(\d{2}-\d{2}-\d{4})_(\d+)\.txt$', name)
    if not m:
        raise ValueError("Invalid filename format")
    return datetime.strptime(m.group(1), "%d-%m-%Y").date(), int(m.group(2))


def wait_for_file(path, retries=10):
    for _ in range(retries):
        if os.path.exists(path):
            return True
        time.sleep(0.5)
    return False

# =========================
# LLM
# =========================

def analyze_call(transcript, retries=2):
    prompt = QA_PROMPT.format(transcript=transcript)

    for attempt in range(1, retries + 1):
        try:
            r = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=300
            )
            r.raise_for_status()
            return r.json()["response"]

        except requests.exceptions.ReadTimeout:
            print(f"⚠️ Ollama timeout (attempt {attempt}/{retries})")
            time.sleep(2)

        except Exception as e:
            print("❌ Ollama error:", e)
            break

    raise RuntimeError("LLM failed after retries")

# =========================
# PARSING (ROBUST)
# =========================

def extract_by_max(text, max_score):
    match = re.search(rf"(\d+)\s*/\s*{max_score}", text)
    if not match:
        return 0

    score = int(match.group(1))
    return min(score, max_score)


def extract_summary(text):
    if "summary" not in text.lower():
        return "No summary provided"

    parts = re.split(r"call summary\s*:", text, flags=re.IGNORECASE)
    return parts[-1].strip() if len(parts) > 1 else "No summary provided"

# =========================
# EXCEL
# =========================

COLUMNS = [
    "Date",
    "Agent ID",
    "Call No",
    "Call Opening (20)",
    "Introduction & Purpose (5)",
    "Probing Skills (10)",
    "DM Identification (15)",
    "Product Knowledge (20)",
    "Handling Objections (20)",
    "CRM Tagging (10)",
    "Total QA Score",
    "Call Summary"
]

def update_excel(path, row):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        df = pd.read_excel(path)
    else:
        df = pd.DataFrame(columns=COLUMNS)

    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_excel(path, index=False)

# =========================
# CORE PROCESS
# =========================

def process_file(path):
    filename = os.path.basename(path)
    agent_id = os.path.basename(os.path.dirname(path))

    try:
        call_date, call_no = parse_filename(filename)
    except ValueError:
        print(f"❌ Invalid filename: {filename}")
        return
    with open(path, encoding="utf-8") as f:
        transcript = f.read().strip()

    try:
        result = analyze_call(transcript)
    except Exception as e:
        print(f"❌ QA skipped (LLM failure): {e}")
        return

    # 🔍 DEBUG: SHOW RAW LLM OUTPUT
    print("\n===== RAW LLM OUTPUT START =====\n")
    print(result)
    print("\n===== RAW LLM OUTPUT END =====\n")

    scores = {
        "Call Opening (20)": extract_by_max(result, 20),
        "Introduction & Purpose (5)": extract_by_max(result, 5),
        "Probing Skills (10)": extract_by_max(result, 10),
        "DM Identification (15)": extract_by_max(result, 15),
        "Product Knowledge (20)": extract_by_max(result, 20),
        "Handling Objections (20)": extract_by_max(result, 20),
        "CRM Tagging (10)": extract_by_max(result, 10),
    }

    total_score = sum(scores.values())

    row = {
        "Date": call_date,
        "Agent ID": agent_id,
        "Call No": call_no,
        **scores,
        "Total QA Score": total_score,
        "Call Summary": extract_summary(result)
    }

    update_excel(MASTER_REPORT_PATH, row)
    update_excel(os.path.join(AGENT_REPORTS_DIR, f"{agent_id}.xlsx"), row)

    print(f"✅ QA Completed: {filename}")

# =========================
# SAFE PROCESSING
# =========================

def safe_process(path):
    if path in PROCESSED_FILES:
        return

    if wait_for_file(path):
        process_file(path)
        PROCESSED_FILES.add(path)

# =========================
# DAILY SUMMARY EMAIL
# =========================

def send_email(to, cc, attachment):
    msg = EmailMessage()
    msg["From"] = SMTP_EMAIL
    msg["To"] = to
    msg["Cc"] = ", ".join(cc)
    msg["Subject"] = "[QA] Daily Summary"
    msg.set_content("Attached is the daily QA summary.")

    with open(attachment, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=os.path.basename(attachment)
        )

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as s:
        s.login(SMTP_EMAIL, SMTP_PASSWORD)
        s.send_message(msg, to_addrs=[to] + cc)

def daily_summary_loop():
    global LAST_SUMMARY_DATE
    while True:
        now = datetime.now()
        if (
            now.hour == DAILY_EMAIL_HOUR
            and now.minute == DAILY_EMAIL_MINUTE
            and LAST_SUMMARY_DATE != date.today()
        ):
            if os.path.exists(MASTER_REPORT_PATH):
                send_email(TL_EMAIL, [QA_EMAIL], MASTER_REPORT_PATH)

            for agent, email in AGENT_EMAIL_MAP.items():
                agent_path = os.path.join(AGENT_REPORTS_DIR, f"{agent}.xlsx")
                if os.path.exists(agent_path):
                    send_email(email, [TL_EMAIL, QA_EMAIL], agent_path)

            LAST_SUMMARY_DATE = date.today()

        time.sleep(30)

# =========================
# WATCHDOG
# =========================

class Handler(FileSystemEventHandler):
    def on_created(self, e):
        if e.src_path.endswith(".txt"):
            safe_process(e.src_path)

# =========================
# START
# =========================

if __name__ == "__main__":
    load_agent_emails()

    threading.Thread(target=daily_summary_loop, daemon=True).start()

    observer = Observer()
    observer.schedule(Handler(), TRANSCRIPTS_DIR, recursive=True)
    observer.start()

    print("✅ QA System running (Parameter-Based Daily Summary Mode)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
