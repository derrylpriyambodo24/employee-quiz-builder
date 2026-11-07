"""Diagnostic: checks your .env, lists available models, and sends one tiny request.
Run:  python check_llm.py
"""
import os

from dotenv import load_dotenv
from openai import APIStatusError, OpenAI

load_dotenv()
key = os.getenv("LLM_API_KEY", "")
base = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
model = os.getenv("LLM_MODEL", "gemini-flash-latest")

print("Key loaded:", bool(key), "| length:", len(key), "| starts with:", key[:4] if key else "-")
print("Base URL  :", base)
print("Model     :", model)
if key != key.strip() or '"' in key or "'" in key:
    print("WARNING: key has spaces or quotes. Remove them in .env")

client = OpenAI(api_key=key, base_url=base)

print("\n--- Available models (flash/lite) ---")
try:
    for m in client.models.list():
        if "flash" in m.id.lower():
            print(m.id)
except Exception as err:
    print("Could not list models:", err)

print("\n--- Test request ---")
try:
    r = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": "Say OK"}]
    )
    print("SUCCESS:", r.choices[0].message.content)
except APIStatusError as err:
    print("FAILED:", err.status_code, err.response.text)
except Exception as err:
    print("FAILED:", err)
