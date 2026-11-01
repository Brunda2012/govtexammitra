"""AI Study Mentor — modular provider layer.

No provider is configured by default; ask() returns None and the API responds 503
with a clear message. GovtExamMitra never fakes AI responses.

To enable: set environment variables (never committed):
    MENTOR_PROVIDER=openai-compatible
    MENTOR_API_KEY=...            (your key)
    MENTOR_BASE_URL=https://api.openai.com/v1   (any OpenAI-compatible endpoint)
    MENTOR_MODEL=gpt-4o-mini      (or any model the endpoint serves)
Responses are advisory and clearly labelled in the UI; they are never presented
as official evaluations or verified facts.
"""
import json
import os
import urllib.request

SYSTEM_PROMPT = (
    "You are the GovtExamMitra AI study mentor for Indian central government exam "
    "preparation (UPSC CSE, CAPF AC, SSC, CDS, NDA, RRB, EPFO). Explain clearly, cite "
    "syllabus context when relevant, distinguish verified facts from interpretation, and "
    "never invent official syllabus wording, PYQs or notifications. Answers are advisory."
)

def _config():
    provider = os.environ.get("MENTOR_PROVIDER")
    key = os.environ.get("MENTOR_API_KEY")
    if not provider or not key:
        return None
    return {
        "base_url": os.environ.get("MENTOR_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        "model": os.environ.get("MENTOR_MODEL", "gpt-4o-mini"),
        "key": key,
    }

def ask(question: str, context: dict | None = None):
    cfg = _config()
    if not cfg:
        return None
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "system", "content": "Context: " + json.dumps(context)})
    messages.append({"role": "user", "content": question})
    body = json.dumps({"model": cfg["model"], "messages": messages, "temperature": 0.4}).encode()
    req = urllib.request.Request(
        cfg["base_url"] + "/chat/completions", data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + cfg["key"]})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"]
    except Exception:
        return None
    return {"answer": content, "advisory": True,
            "note": "AI-generated, advisory only. Not an official evaluation or verified source."}
