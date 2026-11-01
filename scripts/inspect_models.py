import os
import sys
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.core.config import get_settings

settings = get_settings()
api_key = settings.GEMINI_API_KEY
if not api_key:
    print("ERROR: GEMINI_API_KEY is not set.")
    sys.exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
resp = httpx.get(url, timeout=10.0)

print(f"Catalog HTTP Status: {resp.status_code}")
if resp.status_code != 200:
    print(f"Error: {resp.text}")
    sys.exit(1)

data = resp.json()
models = data.get("models", [])
all_names = [m.get("name", "").replace("models/", "") for m in models]

print(f"Total models available to this key: {len(all_names)}")

print("\n--- All models supporting generateContent ---")
gen_models = []
for m in models:
    name = m.get("name", "").replace("models/", "")
    methods = m.get("supportedGenerationMethods", [])
    if "generateContent" in methods:
        gen_models.append(name)
        display = m.get("displayName", "")
        desc = m.get("description", "")[:60]
        print(f"  • {name:<30} | {display}")

print("\n--- Specific Model Checks ---")
print(f"gemini-3.8-flash available: {'gemini-3.8-flash' in all_names}")
print(f"gemini-3.6-flash available: {'gemini-3.6-flash' in all_names}")
print(f"All 3.x models: {[n for n in all_names if n.startswith('gemini-3')]}")
print(f"All Flash models: {[n for n in gen_models if 'flash' in n.lower()]}")

