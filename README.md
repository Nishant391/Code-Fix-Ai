# CodeFix AI

A dark-themed web app for analyzing code, automatically fixing syntax bugs, and explaining errors across **Python, JavaScript, Java, C++, and C**.

## Features
- **Smart Offline Mode (Zero Setup)**: Auto-fixes common syntax errors (missing colons, unclosed brackets/quotes, missing semicolons, keyword typos, etc.) without requiring any API key or internet connection.
- **Multi-Provider AI Integration**: Connect **Google Gemini (Free tier)**, **Groq (Free & fast Llama 3.3)**, **OpenAI (GPT-4o)**, or **Ollama (100% Free & Local)** directly from the UI or via `.env`.
- **In-Browser AI Settings**: One-click configuration and connection testing right in the web app.

---

## Quick Start (Windows)

1. Open the `CodeFix_AI` folder in your terminal:
   ```powershell
   cd CodeFix_AI
   ```
2. Activate the virtual environment:
   ```powershell
   .\.venv\Scripts\python.exe app.py
   ```
3. Open **http://127.0.0.1:5000** in your web browser.

---

## Why didn't my code get fixed originally?
1. **Offline Mode**: Without an AI key, CodeFix AI uses local heuristic rules. It fixes syntax errors (missing colons, brackets, parentheses, quotes, semicolons in Java/C/C++/JS, and built-in typos).
2. **Deep / Logical Bugs**: Complex bugs, runtime errors, or advanced logic require an AI provider.

### How to Enable Full AI Debugging:
You can configure an AI key right inside the web interface:
1. Click the **"⚙ Offline Mode" / "AI Settings"** button in the top-right corner of the website.
2. Select your preferred provider:
   - **Google Gemini (Recommended & Free)**: Get a free API key at [Google AI Studio](https://aistudio.google.com/apikey).
   - **Groq (Free & Fast)**: Get a free API key at [Groq Console](https://console.groq.com/keys).
   - **OpenAI**: Get a key at [OpenAI Platform](https://platform.openai.com/api-keys).
   - **Ollama**: Run models locally (e.g. `ollama run llama3`) with zero API keys.
3. Click **"Test Connection"**, then **"Save & Apply"**.
