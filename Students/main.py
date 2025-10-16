# main.py
import os
import re
import time
import base64
import json
import tempfile
import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import requests
from github import Github, GithubException

# ---------- Config (ENV) ----------
MY_SECRET = os.getenv("MY_SECRET", "YOLO")
GITHUB_TOKEN = os.getenv("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 ")
GITHUB_USERNAME = os.getenv("gsandeepp")
OPENAI_API_KEY = os.getenv("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")  # optional

if not GITHUB_TOKEN or not GITHUB_USERNAME:
    # We don't raise here to allow local testing without pushing to GitHub,
    # but the GitHub steps will fail if these are not set.
    print("Warning: GITHUB_TOKEN or GITHUB_USERNAME missing - GitHub API steps will fail.")

# GitHub API base
GITHUB_API = "https://api.github.com"

app = FastAPI(title="Auto Deployment Agent")

# --------- Helpers ----------
def sanitize_repo_name(name: str) -> str:
    # keep lowercase, alnum, dash, underscore, max 100 chars
    clean = re.sub(r"[^a-zA-Z0-9\-_.]", "-", name).lower()
    return f"task-{clean[:90]}"

def decode_data_uri(uri: str) -> bytes:
    # data:[<mediatype>][;base64],<data>
    if not uri.startswith("data:"):
        raise ValueError("Not a data URI")
    header, data = uri.split(",", 1)
    if ";base64" in header:
        return base64.b64decode(data)
    else:
        return data.encode()

def now_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

# ---------- LLM + Generators ----------
def generate_from_openai(brief: str) -> Dict[str, str]:
    """If OPENAI_API_KEY is set, call the Chat Completions / Reponses API to generate files.
    Returns dict: {path: content}.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    prompt = f"""
You are a code generator. Produce a minimal static web app (single-page) that satisfies the brief below.
Return a JSON object mapping filenames to file contents. Files should include index.html and optionally script.js or style.css.
Do NOT include any surrounding explanation — only return the JSON.

Brief:
{brief}

Make it robust, minimal, and allow the page to accept URL params (e.g., ?url=...) if applicable.
"""
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o-mini",  # allow optional; user can change
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1200
    }
    # Use the modern Responses endpoint if available
    url = "https://api.openai.com/v1/chat/completions"
    r = requests.post(url, headers=headers, json=payload, timeout=20)
    r.raise_for_status()
    data = r.json()
    # find assistant text
    text = None
    if "choices" in data and len(data["choices"]) > 0:
        text = data["choices"][0]["message"]["content"]
    else:
        raise RuntimeError("OpenAI returned unexpected shape")
    # Try to extract JSON blob from output
    try:
        # sometimes it's fenced; remove backticks
        text_clean = re.sub(r"^```(?:json)?\n", "", text)
        text_clean = re.sub(r"\n```$", "", text_clean)
        files = json.loads(text_clean)
        if not isinstance(files, dict):
            raise ValueError("expected dict")
        return {k: str(v) for k, v in files.items()}
    except Exception as e:
        raise RuntimeError(f"Failed to parse OpenAI response as JSON: {e}\n{text[:500]}")

def fallback_generator(brief: str) -> Dict[str, str]:
    """Deterministic fallback generators for the sample templates in the project.
    Returns a mapping filename -> content.
    """
    b = brief.lower()
    # markdown-to-html template
    if "convert" in b and "markdown" in b:
        index = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Markdown to HTML</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.7.0/highlight.min.js"></script>
</head>
<body>
  <h1>Markdown to HTML - Auto</h1>
  <pre id="source" style="display:none"># Sample Markdown\\n\\nThis is a demo.\\n</pre>
  <div id="markdown-output"></div>
  <script>
    (function(){
      async function load() {
        const params = new URLSearchParams(location.search);
        let md = document.getElementById('source').textContent;
        if (params.get('url')) {
          try {
            const r = await fetch(params.get('url'));
            md = await r.text();
          } catch(e){}
        }
        document.getElementById('markdown-output').innerHTML = marked.parse(md);
        document.querySelectorAll('pre code').forEach((el)=>hljs.highlightElement(el));
      }
      load();
    })();
  </script>
</body>
</html>"""
        return {"index.html": index}

    # sales-sum template
    if "sales" in b and "csv" in b:
        index = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>Sales Summary</title></head>
<body>
  <h1 id="title">Sales Summary</h1>
  <div>Total: <span id="total-sales">0</span></div>
  <script>
    async function load() {
      const params = new URLSearchParams(location.search);
      // tries to load attachments/data.csv if provided as ?url=
      let dataUrl = params.get('url');
      if(!dataUrl) {
        document.getElementById('total-sales').textContent = '0';
        return;
      }
      try {
        const r = await fetch(dataUrl);
        const text = await r.text();
        const lines = text.trim().split('\\n').slice(1);
        const sum = lines.reduce((acc,ln)=>{
          const cols = ln.split(',');
          const sales = parseFloat(cols[cols.length-1] || 0);
          return acc + (isNaN(sales)?0:sales);
        },0);
        document.getElementById('total-sales').textContent = sum.toFixed(2);
      } catch(e){
        document.getElementById('total-sales').textContent = 'error';
      }
    }
    load();
  </script>
</body>
</html>"""
        return {"index.html": index}

    # github-user-created template
    if "github" in b and "created" in b:
        index = """<!doctype html>
<html><head><meta charset="utf-8"><title>GitHub User Lookup</title></head>
<body>
  <form id="github-user-form">
    <input id="username" placeholder="github username"/>
    <button type="submit">Lookup</button>
  </form>
  <div id="github-created-at"></div>
  <script>
  document.getElementById('github-user-form').addEventListener('submit', async (e)=>{
    e.preventDefault();
    const u = document.getElementById('username').value.trim();
    if(!u) return;
    const r = await fetch('https://api.github.com/users/' + encodeURIComponent(u));
    if(!r.ok) { document.getElementById('github-created-at').textContent = 'not found'; return; }
    const j = await r.json();
    const d = new Date(j.created_at);
    const iso = d.toISOString().slice(0,10);
    document.getElementById('github-created-at').textContent = iso;
  });
  </script>
</body></html>"""
        return {"index.html": index}

    # generic fallback
    index = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Auto App</title></head>
<body>
  <h1>Auto-generated App</h1>
  <p>{brief}</p>
  <p>Generated at {now_iso()}</p>
</body>
</html>"""
    return {"index.html": index}


def generate_files_for_brief(brief: str) -> Dict[str, str]:
    # Try OpenAI first, but if it fails or not set, fallback
    if OPENAI_API_KEY:
        try:
            files = generate_from_openai(brief)
            if isinstance(files, dict) and files:
                return files
        except Exception as e:
            print("OpenAI generation failed:", e)
    # fallback deterministic
    return fallback_generator(brief)

# ---------- GitHub integration ----------
def github_client():
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN not set")
    return Github(GITHUB_TOKEN)

def create_or_update_repo_files(repo_name: str, files: Dict[str, bytes], commit_message: str, private: bool=False) -> Dict[str, Any]:
    """
    Create or update files in a public repo. If repo doesn't exist, create it.
    `files` is mapping path-> bytes or str
    Returns dict with repo_url, commit_sha (best-effort), pages_url
    """
    gh = github_client()
    user = gh.get_user()
    repo = None
    try:
        repo = gh.get_repo(f"{GITHUB_USERNAME}/{repo_name}")
        print("Found existing repo:", repo.full_name)
    except GithubException as e:
        if e.status == 404:
            print("Repo not found, creating:", repo_name)
            repo = user.create_repo(repo_name, private=private, auto_init=False)
        else:
            raise

    main_branch = "main"
    # Ensure repo has an initial commit: just create files
    created_or_updated = []
    for path, content in files.items():
        # content must be string
        if isinstance(content, bytes):
            b64 = base64.b64encode(content).decode()
            content_str = base64.b64decode(b64).decode('latin1')  # produce str
        else:
            content_str = str(content)
        try:
            existing = None
            try:
                existing = repo.get_contents(path, ref=main_branch)
            except GithubException:
                existing = None
            if existing:
                repo.update_file(path, commit_message, content_str, existing.sha, branch=main_branch)
                created_or_updated.append((path, "updated"))
            else:
                repo.create_file(path, commit_message, content_str, branch=main_branch)
                created_or_updated.append((path, "created"))
        except GithubException as e:
            # Some large or binary files might fail with text approach; fallback to the contents API directly
            raise RuntimeError(f"GitHub file operation failed for {path}: {e}")
    # attempt to get latest commit sha of main
    commit_sha = None
    try:
        commits = repo.get_commits()
        if commits.totalCount > 0:
            commit_sha = commits[0].sha
    except Exception:
        pass

    repo_url = f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
    pages_url = f"https://{GITHUB_USERNAME}.github.io/{repo_name}/"
    return {"repo_url": repo_url, "commit_sha": commit_sha or "unknown", "pages_url": pages_url, "created": created_or_updated}

def enable_github_pages(repo_name: str) -> None:
    """Enable Pages via REST API to set source branch to main / root"""
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN not set")
    url = f"{GITHUB_API}/repos/{GITHUB_USERNAME}/{repo_name}/pages"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    body = {"source": {"branch": "main", "path": "/"}}
    resp = requests.post(url, headers=headers, json=body, timeout=10)
    if resp.status_code not in (201, 202):
        # If 201/202 not returned, maybe Pages already exists; try PUT to update
        resp_put = requests.put(url, headers=headers, json=body, timeout=10)
        if resp_put.status_code not in (200, 201, 202):
            # raise error for debugging
            raise RuntimeError(f"Failed to enable GitHub Pages: {resp.status_code} {resp.text}")

def wait_for_pages(pages_url: str, timeout_seconds: int = 300, poll_interval: int = 5) -> bool:
    """Poll pages_url until HTTP 200 or timeout. Return True if reachable."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            r = requests.get(pages_url, timeout=10)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(poll_interval)
    return False

# ---------- Evaluation callback ----------
def post_evaluation_with_retries(evaluation_url: str, payload: dict, deadline_seconds: int = 600) -> Dict[str, Any]:
    """Post to evaluation_url with exponential backoff until success or deadline_seconds passed.
    Returns dict with status_code and response_text.
    """
    start = time.time()
    attempt = 0
    sleep = 1
    last_exc = None
    while time.time() - start < deadline_seconds:
        try:
            r = requests.post(evaluation_url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
            if r.status_code == 200:
                return {"success": True, "status_code": 200, "response": r.text}
            else:
                # server responded but not 200; retry with backoff
                last_exc = f"status {r.status_code}: {r.text}"
        except Exception as e:
            last_exc = str(e)
        # backoff
        time.sleep(sleep)
        attempt += 1
        sleep = min(sleep * 2, 60)
    return {"success": False, "status_code": None, "error": last_exc}

# ---------- Request model ----------
class Attachment(BaseModel):
    name: str
    url: str

class TaskRequest(BaseModel):
    email: str
    secret: str
    task: Optional[str] = None
    round: int = 1
    nonce: Optional[str] = None
    brief: Optional[str] = None
    checks: Optional[List[str]] = None
    evaluation_url: Optional[str] = None
    attachments: Optional[List[Attachment]] = None

# ---------- Endpoint ----------
@app.post("/", status_code=200)
async def receive_request(req: Request):
    data = await req.json()
    # validate basic shape
    try:
        task_req = TaskRequest(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    # secret check
    if task_req.secret != MY_SECRET:
        return {"status": "error", "reason": "Invalid secret"}

    # Determine repo name
    task_name = task_req.task or f"anon-{int(time.time())}"
    repo_name = sanitize_repo_name(task_name)

    brief = task_req.brief or "Auto-generated simple site"
    # Generate files (index.html etc.)
    try:
        generated = generate_files_for_brief(brief)
    except Exception as e:
        # fallback safe output
        print("Generation error:", e)
        generated = {"index.html": f"<html><body><h1>Generation failed</h1><pre>{str(e)}</pre></body></html>"}

    # Add README and LICENSE
    readme = f"# {repo_name}\n\nAuto-generated from brief:\n\n```\n{brief}\n```\n\nGenerated at {now_iso()}\n"
    license_txt = "MIT License\n\nCopyright (c) " + str(datetime.datetime.utcnow().year)
    generated.setdefault("README.md", readme)
    generated.setdefault("LICENSE", license_txt)

    # Handle attachments: decode and add under /attachments/
    if task_req.attachments:
        for att in task_req.attachments:
            try:
                data_bytes = decode_data_uri(att.url)
                # If it's textual, try to decode; otherwise base64-store binary as string (GitHub create_file expects text)
                # We'll store binary as base64 text to avoid corruption. Mark with .base64 suffix.
                ext = os.path.splitext(att.name)[1]
                path = f"attachments/{att.name}"
                try:
                    # try text
                    content_str = data_bytes.decode("utf-8")
                    generated[path] = content_str
                except Exception:
                    # store as base64 with special suffix
                    generated[path + ".base64"] = base64.b64encode(data_bytes).decode()
            except Exception as e:
                print(f"Attachment decode failed for {att.name}: {e}")

    # Convert all values to str for GitHub file create API
    files_for_github = {}
    for k, v in generated.items():
        if isinstance(v, bytes):
            try:
                files_for_github[k] = v.decode("utf-8")
            except Exception:
                files_for_github[k] = base64.b64encode(v).decode()
        else:
            files_for_github[k] = str(v)

    # For round 2: try updating existing repo; else create new
    try:
        gh_result = create_or_update_repo_files(repo_name, files_for_github, commit_message=f"auto: round {task_req.round} update")
    except Exception as e:
        return {"status": "error", "reason": f"GitHub operation failed: {e}"}

    # Try enable pages
    try:
        enable_github_pages(repo_name)
    except Exception as e:
        # continue; pages enabling sometimes returns 201 later or requires more permissions
        print("Enable pages warning:", e)

    pages_url = gh_result["pages_url"]
    pages_ok = wait_for_pages(pages_url, timeout_seconds=300, poll_interval=5)

    payload = {
        "email": task_req.email,
        "task": task_req.task,
        "round": task_req.round,
        "nonce": task_req.nonce,
        "repo_url": gh_result["repo_url"],
        "commit_sha": gh_result.get("commit_sha"),
        "pages_url": pages_url
    }

    eval_result = {}
    if task_req.evaluation_url:
        eval_result = post_evaluation_with_retries(task_req.evaluation_url, payload, deadline_seconds=600)
    else:
        eval_result = {"success": False, "error": "No evaluation_url provided"}

    result = {
        "status": "ok",
        "repo_url": gh_result["repo_url"],
        "commit_sha": gh_result.get("commit_sha"),
        "pages_url": pages_url,
        "pages_live": pages_ok,
        "evaluation": eval_result
    }
    return result
