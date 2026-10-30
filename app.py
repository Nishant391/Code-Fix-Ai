import ast
import os
import re
import json
import urllib.request
import urllib.error
from flask import Flask, render_template, request, jsonify

# Automatically load .env if present
def load_env_file():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception as e:
            print(f"Notice: Could not read .env: {e}")

load_env_file()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

LANGUAGES = {"Python", "Java", "C++", "C", "JavaScript"}

SYSTEM_PROMPT = """You are CodeFix AI, an elite software engineering and debugging assistant.
Your job is to thoroughly analyze the provided code, detect ALL bugs, and return the complete, working, corrected code.

Key requirements:
1. Detect all issues:
   - Syntax errors, missing brackets, typos, invalid statements.
   - Logic bugs, algorithmic flaws, off-by-one errors, infinite loops, recursion base cases, incorrect conditions.
   - Runtime exceptions (e.g. TypeErrors, NullPointerExceptions, IndexError, NameError, Segmentation faults, Division by zero).
   - Missing imports, undefined variables, incorrect function calls, or mismatched argument types.
2. Produce COMPLETE working code in `fixed_code`:
   - Never use ellipses (...), placeholders, or omit code.
   - Return the full, runnable, fixed program.
   - Keep the original architecture, structure, and intent while fixing all bugs.
3. Return ONLY a single valid JSON object with EXACTLY these keys:
   {
     "language": "<programming language>",
     "status": "fixed" or "clean" or "error",
     "error_type": "<short classification, e.g. LogicError, TypeError, SyntaxError>",
     "error_line": <integer line number where primary bug occurs, or null>,
     "error_message": "<clear concise description of the bug>",
     "explanation": "<detailed explanation of what went wrong and how the fix works>",
     "fixed_code": "<the complete corrected source code>",
     "changes": [
       {"line": <int>, "problem": "<specific bug>", "fix": "<exact change made>"}
     ],
     "output": "<expected output or behavior when run>",
     "notes": "<helpful best practices or edge-case advice>",
     "has_fix": true or false
   }
Ensure `has_fix` is true whenever any correction is made. Do not wrap with extra commentary outside JSON."""

PROVIDER_DEFAULTS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "model": "gemini-1.5-flash",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "openai/gpt-oss-120b",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1/chat/completions",
        "model": "llama3",
    }
}

def clean_json_response(content):
    """Safely extracts JSON from model content, stripping reasoning tags and markdown code fences."""
    content = (content or "").strip()
    # Strip <think>...</think> reasoning blocks from modern reasoning models
    content = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()

    # If wrapped in markdown code fences, attempt extracting inner content
    if "```" in content:
        fences = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
        for candidate in fences:
            candidate = candidate.strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                try:
                    return json.loads(candidate)
                except Exception:
                    pass

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Fallback: search for first { to last }
        match = re.search(r"(\{[\s\S]*\})", content)
        if match:
            return json.loads(match.group(1))
        raise

def call_ai(code, language, config=None):
    """Call OpenAI-compatible AI API (Gemini, Groq, OpenAI, Ollama, Custom) with auto-fallback."""
    cfg = config or {}
    provider = cfg.get("provider", "").strip().lower()

    # If client passed 'none' or empty, detect default from server environment
    if not provider or provider == "none":
        if os.getenv("GROQ_API_KEY"):
            provider = "groq"
        elif os.getenv("GEMINI_API_KEY"):
            provider = "gemini"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"

    api_key = cfg.get("api_key", "").strip()
    if not api_key:
        if provider == "groq":
            api_key = os.getenv("GROQ_API_KEY", "").strip()
        elif provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
        elif provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
        else:
            api_key = (
                os.getenv("GROQ_API_KEY", "").strip() or
                os.getenv("GEMINI_API_KEY", "").strip() or
                os.getenv("OPENAI_API_KEY", "").strip()
            )

    api_key = api_key.strip().strip('"').strip("'")

    # If still no api_key and provider is not ollama, fallback to any available .env key
    if not api_key and provider != "ollama":
        if os.getenv("GROQ_API_KEY"):
            provider = "groq"
            api_key = os.getenv("GROQ_API_KEY", "").strip().strip('"').strip("'")
        elif os.getenv("GEMINI_API_KEY"):
            provider = "gemini"
            api_key = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
            api_key = os.getenv("OPENAI_API_KEY", "").strip().strip('"').strip("'")

    # Determine Endpoint and Model
    base_url = cfg.get("base_url", "").strip()
    model = cfg.get("model", "").strip().strip('"').strip("'")

    # Enforce standard base_url for known managed providers
    if provider in PROVIDER_DEFAULTS:
        if provider != "custom" or not base_url:
            base_url = PROVIDER_DEFAULTS[provider]["base_url"]
        if not model:
            model = PROVIDER_DEFAULTS[provider]["model"]
    elif not base_url:
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions")

    if not model:
        model = os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b" if provider == "groq" else "gpt-4o-mini")

    # Specific sanitization for Google Gemini
    if provider == "gemini":
        if model.lower().startswith("models/"):
            model = model[7:].strip()
        if model.startswith("AIza") or model.startswith("AQ."):
            if not api_key:
                api_key = model
            model = "gemini-1.5-flash"
        if not model.lower().startswith("gemini-"):
            model = "gemini-1.5-flash"

    # Specific sanitization for Groq
    elif provider == "groq":
        if model.startswith("gsk_"):
            if not api_key:
                api_key = model
            model = "openai/gpt-oss-120b"
        if not model or "llama" in model.lower() or model.startswith("gemini") or model.startswith("gpt-"):
            model = "openai/gpt-oss-120b"

    print(f"[DEBUG] call_ai called: provider={provider}, model={model}, has_key={bool(api_key)}")
    # If provider is not Ollama and no api key is available
    if provider != "ollama" and not api_key:
        print("[DEBUG] AI call aborted: no API key")
        return None, "AI API key is missing. Please enter your API key in AI Settings or add GROQ_API_KEY to your .env file."

    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 4096,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Language: {language}\nAnalyze, find all bugs, and return the complete corrected code:\n```{language}\n{code}\n```"}
        ]
    }
    if provider in ("openai", "gemini", "groq"):
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 CodeFixAI/1.0"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        result = clean_json_response(content)

        result.setdefault("language", language)
        result.setdefault("status", "AI analysis complete")
        result.setdefault("error_type", "Review")
        result.setdefault("error_line", None)
        result.setdefault("error_message", "See explanation")
        result.setdefault("explanation", "Review the findings below.")
        result.setdefault("fixed_code", code)
        result.setdefault("changes", [])
        result.setdefault("output", "Code was not executed.")
        result.setdefault("notes", f"Powered by AI ({model}). Always test suggested fixes.")
        result["has_fix"] = result.get("has_fix", result.get("fixed_code", "").strip() != code.strip())
        return result, None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        # Auto-fallback if model not found on Groq: try qwen/qwen3.8-27b
        if provider == "groq" and "model_not_found" in detail and model != "qwen/qwen3.8-27b":
            try:
                payload["model"] = "qwen/qwen3.8-27b"
                req_fb = urllib.request.Request(
                    base_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req_fb, timeout=60) as fb_resp:
                    fb_data = json.loads(fb_resp.read().decode("utf-8"))
                    fb_content = fb_data["choices"][0]["message"]["content"]
                    fb_result = clean_json_response(fb_content)
                    fb_result.setdefault("language", language)
                    fb_result.setdefault("fixed_code", code)
                    fb_result.setdefault("changes", [])
                    fb_result.setdefault("notes", "Powered by AI (qwen/qwen3.8-27b).")
                    fb_result["has_fix"] = fb_result.get("has_fix", fb_result.get("fixed_code", "").strip() != code.strip())
                    return fb_result, None
            except Exception:
                pass
        return None, f"AI API error ({exc.code}): {detail}"
    except Exception as exc:
        return None, f"Could not contact AI service: {exc}"
        result.setdefault("output", "Code was not executed.")
        result.setdefault("notes", f"Powered by AI ({model}). Always test suggested fixes.")
        result["has_fix"] = result.get("has_fix", result.get("fixed_code", "").strip() != code.strip())
        return result, None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        if "unexpected model name format" in detail:
            return None, (
                f"Gemini Model Error: Invalid model name '{model}'. "
                "In AI Settings, set Model Name to 'gemini-1.5-flash' (without 'models/'), "
                "and make sure your API key was not pasted into the Model Name box."
            )
        return None, f"AI API error ({exc.code}): {detail}"
    except Exception as exc:
        return None, f"Could not contact AI service: {exc}"

def local_python_analysis(code):
    """Multi-pass offline rule-based analyzer and auto-fixer for Python."""
    result = {
        "language": "Python",
        "status": "Local syntax check complete",
        "error_type": "No syntax error detected",
        "error_line": None,
        "error_message": "Python's parser did not find a syntax error.",
        "explanation": "This offline check validates Python syntax only. It cannot reliably detect every logical or runtime bug.",
        "fixed_code": code,
        "changes": [],
        "has_fix": False,
        "output": "Code was not executed for safety.",
        "notes": "Offline mode active. Connect an AI API in Settings for comprehensive bug fixing."
    }

    lines = code.splitlines()
    fixed_lines = list(lines)
    changes = []

    # 1. Obvious typos in keywords/functions
    common_typos = {
        r"\bprnt\b": ("print", "Typo in 'print' function name"),
        r"\bture\b": ("True", "Typo in boolean 'True'"),
        r"\bflase\b": ("False", "Typo in boolean 'False'"),
        r"\bnone\b": ("None", "Typo in 'None'"),
        r"\blenght\b": ("len", "Typo in 'len' function name"),
        r"\blentgh\b": ("len", "Typo in 'len' function name"),
        r"\bretrun\b": ("return", "Typo in keyword 'return'")
    }
    for idx, line in enumerate(fixed_lines):
        for pattern, (replacement, reason) in common_typos.items():
            if re.search(pattern, line):
                new_line = re.sub(pattern, replacement, line)
                if new_line != line:
                    changes.append({"line": idx + 1, "problem": reason, "fix": f"Replaced with '{replacement}'"})
                    fixed_lines[idx] = new_line

    # 2. Python 2 style print: print "hello" -> print("hello")
    for idx, line in enumerate(fixed_lines):
        p2_match = re.match(r"^(\s*)print\s+([\"'].*[\"']|\w+.*)$", line)
        if p2_match and not line.strip().startswith("print("):
            indent = p2_match.group(1)
            content = p2_match.group(2)
            fixed_lines[idx] = f"{indent}print({content})"
            changes.append({"line": idx + 1, "problem": "Python 2 print statement syntax.", "fix": f"Changed to print({content})"})

    # 3. Assignment inside if / elif / while: if a = 5: -> if a == 5:
    for idx, line in enumerate(fixed_lines):
        cond_match = re.match(r"^(\s*(?:if|elif|while)\s+)(.+?)\s*=\s*([^=].*?)(:\s*(?:#.*)?)$", line)
        if cond_match:
            prefix, left, right, suffix = cond_match.groups()
            fixed_lines[idx] = f"{prefix}{left} == {right}{suffix}"
            changes.append({"line": idx + 1, "problem": "Assignment '=' used instead of comparison '=='.", "fix": "Changed '=' to '=='"})

    # 4. Missing colons on compound statements (def, if, elif, else, for, while, class, try, except, finally, with)
    colon_keywords = r"^(def\s+|class\s+|if\s+|elif\s+|else\b|for\s+|while\s+|try\b|except\b|finally\b|with\s+|async\s+def\s+|async\s+for\s+|async\s+with\s+)"
    for idx, line in enumerate(fixed_lines):
        stripped = line.rstrip()
        content_part = re.sub(r"#.*$", "", stripped).rstrip()
        if content_part and re.match(colon_keywords, content_part.lstrip()) and not content_part.endswith(":"):
            comment = stripped[len(content_part):]
            fixed_lines[idx] = content_part + ":" + comment
            changes.append({"line": idx + 1, "problem": "Missing colon ':' at the end of statement.", "fix": "Added ':' at the end of the line."})

    # 5. Fix unclosed quotes and brackets
    for idx, line in enumerate(fixed_lines):
        sq_count = line.count("'") - line.count("\\'")
        dq_count = line.count('"') - line.count('\\"')
        if dq_count % 2 != 0:
            fixed_lines[idx] = fixed_lines[idx] + '"'
            changes.append({"line": idx + 1, "problem": 'Unterminated double quote (").', "fix": 'Appended closing quote (").'})
        elif sq_count % 2 != 0:
            fixed_lines[idx] = fixed_lines[idx] + "'"
            changes.append({"line": idx + 1, "problem": "Unterminated single quote (').", "fix": "Appended closing quote (')."})

        open_p = fixed_lines[idx].count("(") - fixed_lines[idx].count(")")
        open_b = fixed_lines[idx].count("[") - fixed_lines[idx].count("]")
        open_c = fixed_lines[idx].count("{") - fixed_lines[idx].count("}")
        if open_p > 0:
            fixed_lines[idx] = fixed_lines[idx] + (")" * open_p)
            changes.append({"line": idx + 1, "problem": f"Missing {open_p} closing parenthesis ')'.", "fix": f"Added {open_p} ')'."})
        if open_b > 0:
            fixed_lines[idx] = fixed_lines[idx] + ("]" * open_b)
            changes.append({"line": idx + 1, "problem": f"Missing {open_b} closing bracket ']'.", "fix": f"Added {open_b} ']'."})
        if open_c > 0:
            fixed_lines[idx] = fixed_lines[idx] + ("}" * open_c)
            changes.append({"line": idx + 1, "problem": f"Missing {open_c} closing brace '}}'.", "fix": f"Added {open_c} '}}'."})

    # Validate with AST parser
    current_code = "\n".join(fixed_lines)
    try:
        ast.parse(current_code)
        if changes:
            result.update({
                "status": "Syntax fixes applied",
                "error_type": "Syntax Correction",
                "error_line": changes[0]["line"] if changes else None,
                "error_message": changes[0]["problem"] if changes else "Fixed common syntax mistakes.",
                "explanation": f"Detected and resolved {len(changes)} syntax issue(s) locally. The code now passes Python syntax parsing.",
                "fixed_code": current_code,
                "changes": changes,
                "has_fix": True,
                "notes": "Fix generated with offline heuristics. Connect an AI provider in Settings for deeper analysis."
            })
        return result
    except SyntaxError as exc:
        line_num = exc.lineno or 1
        msg = exc.msg or "Syntax error"

        # Check indentation error
        if isinstance(exc, IndentationError) or "indented block" in msg:
            if 0 < line_num <= len(fixed_lines):
                fixed_lines[line_num - 1] = "    " + fixed_lines[line_num - 1]
                changes.append({"line": line_num, "problem": "IndentationError: block was not indented.", "fix": "Added indentation (4 spaces)."})
                current_code = "\n".join(fixed_lines)
                try:
                    ast.parse(current_code)
                    result.update({
                        "status": "Indentation error fixed",
                        "error_type": "IndentationError",
                        "error_line": line_num,
                        "error_message": msg,
                        "explanation": f"Fixed indentation error on line {line_num}.",
                        "fixed_code": current_code,
                        "changes": changes,
                        "has_fix": True,
                        "notes": "Code now passes Python syntax parsing."
                    })
                    return result
                except Exception:
                    pass

        # If we could not produce clean code that parses
        result.update({
            "status": "Syntax error detected (Offline)",
            "error_type": type(exc).__name__,
            "error_line": line_num,
            "error_message": msg,
            "explanation": f"Python reported '{msg}' on line {line_num}. Offline heuristic rules could not automatically resolve this issue. Connect an AI API in Settings to receive intelligent fixes for complex bugs.",
            "fixed_code": current_code if changes else code,
            "changes": changes,
            "has_fix": False,
            "notes": "To automatically fix complex syntax, logical errors, and runtime bugs, configure a free AI key (Gemini/Groq) in Settings."
        })
        return result

def local_c_family_analysis(code, language):
    """Offline heuristic checker & fixer for C, C++, Java, and JavaScript."""
    result = {
        "language": language,
        "status": "Local check complete",
        "error_type": "No issue detected",
        "error_line": None,
        "error_message": "Basic syntax looks consistent.",
        "explanation": f"Validated basic {language} syntax (semicolons, brackets, common keywords).",
        "fixed_code": code,
        "changes": [],
        "has_fix": False,
        "output": "Code was not executed.",
        "notes": "Offline mode active. Connect an AI API in Settings for comprehensive compilation and runtime checks."
    }

    lines = code.splitlines()
    fixed_lines = list(lines)
    changes = []

    typos = {}
    if language == "JavaScript":
        typos = {
            r"\bconsol\.log\b": ("console.log", "Typo in 'console.log'"),
            r"\bfuntion\b": ("function", "Typo in 'function' keyword"),
            r"\bretrun\b": ("return", "Typo in 'return' keyword"),
            r"\bdocumnet\b": ("document", "Typo in 'document'"),
            r"\bconts\b": ("const", "Typo in 'const'")
        }
    elif language == "Java":
        typos = {
            r"\bSystem\.out\.printl\b": ("System.out.println", "Typo in 'System.out.println'"),
            r"\bSytem\b": ("System", "Typo in 'System'"),
            r"\bString\[\]\s+arg\b": ("String[] args", "Standard main arguments parameter name"),
            r"\bretrun\b": ("return", "Typo in 'return' keyword")
        }
    elif language in ("C++", "C"):
        typos = {
            r"\bprntf\b": ("printf", "Typo in 'printf'"),
            r"\binclude\s*<stdio\b(?!\.h>)": ("include <stdio.h>", "Typo in standard header"),
            r"\binclude\s*<iostream\b(?!>)": ("include <iostream>", "Typo in standard header"),
            r"\bstd::coutn\b": ("std::cout", "Typo in 'std::cout'"),
            r"\bretrun\b": ("return", "Typo in 'return' keyword")
        }

    for idx, line in enumerate(fixed_lines):
        for pat, (rep, reason) in typos.items():
            if re.search(pat, line):
                new_l = re.sub(pat, rep, line)
                if new_l != line:
                    changes.append({"line": idx + 1, "problem": reason, "fix": f"Replaced with '{rep}'"})
                    fixed_lines[idx] = new_l

    # Check missing semicolons for statement lines
    statement_triggers = (
        r"\b(return|break|continue|throw)\b",
        r"\b(System\.out\.(?:println|print|printf)|printf|puts|cout|cin)\b",
        r"^\s*(int|float|double|char|bool|long|short|auto|const|let|var|String|std::string)\s+\w+\s*=?",
        r"^\s*\w+(\.\w+)?\s*=\s*.+"
    )

    for idx, line in enumerate(fixed_lines):
        raw = line.rstrip()
        stripped = re.sub(r"//.*$", "", raw).rstrip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.endswith(";") or stripped.endswith("{") or stripped.endswith("}") or stripped.endswith(":"):
            continue
        if re.search(r"^\s*(public|private|protected|class|struct|interface|enum|if|else|for|while|switch|case|default)\b", stripped):
            continue

        is_stmt = any(re.search(pat, stripped) for pat in statement_triggers)
        if not is_stmt and re.search(r"\w+\(.*\)$", stripped):
            is_stmt = True

        if is_stmt:
            comment = raw[len(stripped):]
            fixed_lines[idx] = stripped + ";" + comment
            changes.append({"line": idx + 1, "problem": f"Missing semicolon ';' at the end of statement in {language}.", "fix": "Added ';' at the end of the line."})

    # Unmatched braces & parentheses
    all_text = "\n".join(fixed_lines)
    open_c = all_text.count("{") - all_text.count("}")
    open_p = all_text.count("(") - all_text.count(")")
    if open_p > 0:
        fixed_lines[-1] = fixed_lines[-1] + (")" * open_p)
        changes.append({"line": len(fixed_lines), "problem": f"Missing {open_p} closing parenthesis ')'.", "fix": f"Added {open_p} ')'."})
    if open_c > 0:
        for _ in range(open_c):
            fixed_lines.append("}")
        changes.append({"line": len(fixed_lines), "problem": f"Missing {open_c} closing brace '}}'.", "fix": f"Added {open_c} '}}'."})

    fixed_code = "\n".join(fixed_lines)
    if changes:
        result.update({
            "status": "Syntax fixes applied",
            "error_type": "Syntax Correction",
            "error_line": changes[0]["line"],
            "error_message": changes[0]["problem"],
            "explanation": f"Detected and resolved {len(changes)} common syntax issue(s) for {language}.",
            "fixed_code": fixed_code,
            "changes": changes,
            "has_fix": True,
            "notes": "Offline heuristic fix. Connect an AI API in Settings for comprehensive compiler errors and logic fixes."
        })
    else:
        result.update({
            "status": "No basic syntax errors found",
            "error_type": "Static check passed",
            "explanation": f"Basic syntax check (semicolons, braces, common keywords) looks clean. To find subtle compiler errors, logical bugs, or incorrect outputs, connect an AI API in Settings.",
            "fixed_code": code,
            "has_fix": False
        })
    return result

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/config")
def get_config():
    """Return whether server has a default AI key and default provider settings."""
    load_env_file()
    has_env_key = bool(
        os.getenv("OPENAI_API_KEY") or
        os.getenv("GEMINI_API_KEY") or
        os.getenv("GROQ_API_KEY")
    )
    provider = "openai"
    if os.getenv("GROQ_API_KEY"):
        provider = "groq"
    elif os.getenv("GEMINI_API_KEY"):
        provider = "gemini"

    return jsonify({
        "has_server_key": has_env_key,
        "default_provider": provider,
        "default_model": PROVIDER_DEFAULTS.get(provider, {}).get("model", "gpt-4o-mini")
    })

@app.post("/api/test_ai")
def test_ai():
    """Quickly test an AI connection."""
    body = request.get_json(silent=True) or {}
    provider = body.get("provider", "openai")
    api_key = body.get("api_key", "").strip() or os.getenv("OPENAI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
    model = body.get("model", "")
    base_url = body.get("base_url", "")

    test_config = {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "base_url": base_url
    }
    result, error = call_ai("print('Hello')", "Python", test_config)
    if error:
        return jsonify({"success": False, "error": error}), 400
    return jsonify({
        "success": True,
        "message": f"Successfully connected to AI provider! ({result.get('notes', 'Connected')})"
    })

@app.post("/api/debug")
def debug():
    body = request.get_json(silent=True) or {}
    code = body.get("code", "")
    language = body.get("language", "Python")
    mode = body.get("mode", "fix")
    ai_config = body.get("ai_config", None)
    print(f"[DEBUG] /api/debug called: code_len={len(code)}, language={language}, ai_config={ai_config}", flush=True)

    if not isinstance(code, str) or not code.strip():
        return jsonify({"error": "Paste some code first."}), 400
    if len(code) > 100_000:
        return jsonify({"error": "Code is too long. Please keep it under 100,000 characters."}), 413
    if language not in LANGUAGES:
        return jsonify({"error": "Please choose a supported language."}), 400

    # 1. Try AI Analysis if configured or requested
    ai_result, ai_warning = call_ai(code, language, ai_config)
    if ai_result:
        print("[DEBUG] AI call succeeded!", flush=True)
        result = ai_result
        if mode == "explain":
            result["fixed_code"] = code
        return jsonify(result)

    # 1b. If client config failed, but server has a key in .env, attempt server AI
    if ai_config:
        print(f"[DEBUG] Client AI call failed ({ai_warning}). Attempting server fallback key...", flush=True)
        server_result, server_warning = call_ai(code, language, config=None)
        if server_result:
            print("[DEBUG] Server fallback AI succeeded!", flush=True)
            result = server_result
            if mode == "explain":
                result["fixed_code"] = code
            return jsonify(result)

    print(f"[DEBUG] Falling back to offline engine. ai_warning={ai_warning}", flush=True)
    # 2. Smart Offline Analysis
    if language == "Python":
        result = local_python_analysis(code)
    else:
        result = local_c_family_analysis(code, language)

    result["ai_notice"] = ai_warning
    if mode == "explain":
        result["fixed_code"] = code
    return jsonify(result)

@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "Request too large. Please use a smaller code sample."}), 413

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
