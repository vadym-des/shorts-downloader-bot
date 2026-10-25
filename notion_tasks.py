"""
Notion Tasks Integration Module
Provides utilities to send, search and triage tasks for Notion Database: ⚡ All Projects Tasks
"""

import os
import re
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List

NOTION_TOKEN = (os.getenv("NOTION_TOKEN") or "").strip() or "ntn_EJl484363475gcsSSAUDnylFa5MX6Ix3sNta4cTXsXu0FR"
DATABASE_ID = (os.getenv("NOTION_DATABASE_ID") or "").strip() or "404002e3-147b-8117-8b20-f3c1d3c23c1e"
NOTION_API_VERSION = "2022-06-28"

PROJECT_OPTIONS = {
    "shorts": "🎬 Shorts Downloader",
    "shorts downloader": "🎬 Shorts Downloader",
    "🎬 shorts downloader": "🎬 Shorts Downloader",
    "anime": "⛩️ Anime Downloader",
    "anime downloader": "⛩️ Anime Downloader",
    "⛩️ anime downloader": "⛩️ Anime Downloader",
    "feedback": "💬 Feedback",
    "💬 feedback": "💬 Feedback",
    "core": "⚡ Core System",
    "⚡ core system": "⚡ Core System"
}


def extract_concise_title(text: str, max_len: int = 60, max_words: int = 8) -> str:
    """
    Extracts a concise, key title (up to max_words / max_len chars) for the 'Name' property:
    - Takes the first non-empty line.
    - Strips leading bullet points or markdown symbols.
    - If longer than max_len chars or more than max_words words:
      truncates neatly along word boundary (to 55-60 chars) and appends '...'.
    """
    if not text:
        return "Нове завдання"

    clean_lines = [l.strip() for l in str(text).strip().splitlines() if l.strip()]
    if not clean_lines:
        return "Нове завдання"

    first_line = clean_lines[0]
    first_line = re.sub(r"^[#\-\*\s]+", "", first_line).strip()
    words = first_line.split()

    if not words:
        return "Нове завдання"

    # If within limits (<= max_len and <= max_words), return as is
    if len(first_line) <= max_len and len(words) <= max_words:
        return first_line

    # Truncate to at most max_words
    truncated = words[:max_words]
    candidate = " ".join(truncated)

    # Ensure candidate + '...' fits within max_len (e.g. 60 chars)
    limit = max_len - 3
    if len(candidate) > limit:
        candidate = candidate[:limit]
        if " " in candidate:
            candidate = candidate.rsplit(" ", 1)[0]

    return candidate.rstrip(".,;:- ") + "..."


def build_text_blocks(text: str) -> List[Dict[str, Any]]:
    """
    Generates paragraph blocks for full page content without truncating text.
    Handles Notion API's 2000 character limit per rich_text item by chunking safely.
    """
    if not text:
        return []

    blocks = []
    paragraphs = text.split("\n\n")

    for para in paragraphs:
        cleaned = para.strip()
        if not cleaned:
            continue

        while cleaned:
            chunk = cleaned[:1900]
            cleaned = cleaned[1900:]
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": chunk}
                        }
                    ]
                }
            })

    return blocks


def build_media_blocks(media_urls: Optional[List[str]]) -> List[Dict[str, Any]]:
    """
    Creates Notion image/video blocks from URLs.
    """
    if not media_urls:
        return []

    blocks = []
    for url in media_urls:
        if not url or not isinstance(url, str):
            continue
        u = url.strip()
        if not u:
            continue

        is_video = any(u.lower().endswith(ext) for ext in [".mp4", ".mov", ".m4v", ".webm", ".avi"])
        block_type = "video" if is_video else "image"

        blocks.append({
            "object": "block",
            "type": block_type,
            block_type: {
                "type": "external",
                "external": {"url": u}
            }
        })

    return blocks


def send_task(
    name: str,
    status: Optional[str] = "Inbox",
    task_type: Optional[str] = None,
    project: Optional[str] = "🎬 Shorts Downloader",
    rice_score: Optional[float] = None,
    description: Optional[str] = None,
    media_urls: Optional[List[str]] = None,
    token: Optional[str] = None,
    database_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates and sends a task to the Notion database.
    - name: concise title for the 'Name' property (title).
    - description: full, untruncated content placed inside page body.
    - media_urls: optional list of photo/video URLs placed as media blocks.
    """
    api_token = (token or os.getenv("NOTION_TOKEN") or "").strip() or NOTION_TOKEN
    target_db_id = (database_id or os.getenv("NOTION_DATABASE_ID") or "").strip() or DATABASE_ID

    if not api_token or api_token == "your_notion_token_here":
        raise ValueError("Відсутній токен NOTION_TOKEN у змінних оточення (Variables на Railway).")
    if not target_db_id or target_db_id == "your_database_id_here":
        raise ValueError("Відсутній ідентифікатор бази NOTION_DATABASE_ID у змінних оточення.")

    # Concise title for Name property (<= 60 chars / 8 words)
    final_title = extract_concise_title(name, max_len=60, max_words=8)

    properties: Dict[str, Any] = {
        "Name": {
            "title": [
                {
                    "type": "text",
                    "text": {"content": final_title}
                }
            ]
        }
    }

    if status:
        properties["Status"] = {"select": {"name": status}}

    if task_type:
        properties["Type"] = {"select": {"name": task_type}}

    if project:
        clean_proj = PROJECT_OPTIONS.get(project.lower(), project)
        properties["Project"] = {"select": {"name": clean_proj}}

    if rice_score is not None:
        try:
            properties["RICE Score"] = {"number": float(rice_score)}
        except (ValueError, TypeError):
            pass

    children_blocks: List[Dict[str, Any]] = []

    # 1. Full description inside page body without truncation
    full_body = description if description else name
    if full_body:
        children_blocks.extend(build_text_blocks(full_body))

    # 2. Photos / media blocks
    if media_urls:
        children_blocks.extend(build_media_blocks(media_urls))

    payload: Dict[str, Any] = {
        "parent": {
            "database_id": target_db_id
        },
        "properties": properties
    }

    if children_blocks:
        payload["children"] = children_blocks

    def _execute_request(req_payload):
        req = urllib.request.Request(
            "https://api.notion.com/v1/pages",
            data=json.dumps(req_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "Notion-Version": NOTION_API_VERSION,
                "User-Agent": "NotionTasksClient/1.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        data = _execute_request(payload)
        return {
            "success": True,
            "task_id": data.get("id"),
            "url": data.get("url"),
            "data": data
        }
    except urllib.error.HTTPError as err:
        err_msg = err.read().decode("utf-8")
        # Fallback: if media blocks failed (e.g., Notion rejected external URL format),
        # retry by appending media links inside text blocks instead
        if media_urls and ("image" in err_msg.lower() or "video" in err_msg.lower() or "external" in err_msg.lower()):
            fallback_text = (description or "") + "\n\n📎 Прикріплені медіа:\n" + "\n".join(media_urls)
            payload["children"] = build_text_blocks(fallback_text)
            try:
                data = _execute_request(payload)
                return {
                    "success": True,
                    "task_id": data.get("id"),
                    "url": data.get("url"),
                    "data": data
                }
            except Exception:
                pass
        raise RuntimeError(f"Notion API error [{err.code}]: {err_msg}")
    except Exception as err:
        raise RuntimeError(f"Failed to send task to Notion: {err}")


def search_tasks(
    query: str = "",
    project: Optional[str] = None,
    max_results: int = 10,
    token: Optional[str] = None,
    database_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Searches tasks in the Notion database filtered by title and/or project,
    sorted by RICE Score descending.
    """
    api_token = (token or os.getenv("NOTION_TOKEN") or "").strip() or NOTION_TOKEN
    target_db_id = (database_id or os.getenv("NOTION_DATABASE_ID") or "").strip() or DATABASE_ID

    if not api_token or api_token == "your_notion_token_here":
        raise ValueError("Відсутній токен NOTION_TOKEN у змінних оточення (Variables на Railway).")
    if not target_db_id or target_db_id == "your_database_id_here":
        raise ValueError("Відсутній ідентифікатор бази NOTION_DATABASE_ID у змінних оточення.")

    payload: Dict[str, Any] = {
        "page_size": max(1, min(max_results, 50)),
        "sorts": [
            {
                "property": "RICE Score",
                "direction": "descending"
            }
        ]
    }

    filters = []
    clean_query = query.strip()
    if clean_query:
        filters.append({
            "property": "Name",
            "title": {
                "contains": clean_query
            }
        })

    if project:
        clean_proj = PROJECT_OPTIONS.get(project.lower(), project)
        filters.append({
            "property": "Project",
            "select": {
                "equals": clean_proj
            }
        })

    if len(filters) == 1:
        payload["filter"] = filters[0]
    elif len(filters) > 1:
        payload["filter"] = {"and": filters}

    req = urllib.request.Request(
        f"https://api.notion.com/v1/databases/{target_db_id}/query",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_API_VERSION,
            "User-Agent": "NotionTasksClient/1.0"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = []
            for item in data.get("results", []):
                props = item.get("properties", {})
                title_list = props.get("Name", {}).get("title", [])
                name = title_list[0].get("text", {}).get("content", "Без назви") if title_list else "Без назви"

                status_obj = props.get("Status", {}).get("select") or {}
                status = status_obj.get("name", "Не вказано")

                type_obj = props.get("Type", {}).get("select") or {}
                task_type = type_obj.get("name", "Не вказано")

                project_obj = props.get("Project", {}).get("select") or {}
                proj_name = project_obj.get("name", "Не вказано")

                rice_score = props.get("RICE Score", {}).get("number")

                results.append({
                    "id": item.get("id"),
                    "name": name,
                    "status": status,
                    "type": task_type,
                    "project": proj_name,
                    "rice_score": rice_score,
                    "url": item.get("url")
                })
            return results
    except urllib.error.HTTPError as err:
        err_msg = err.read().decode("utf-8")
        raise RuntimeError(f"Notion API error [{err.code}]: {err_msg}")
    except Exception as err:
        raise RuntimeError(f"Failed to search tasks in Notion: {err}")


def get_tasks_by_project(
    project_name: str,
    max_results: int = 20,
    token: Optional[str] = None,
    database_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves tasks filtered strictly by Project name and sorted descending by RICE Score.
    """
    clean_proj = PROJECT_OPTIONS.get(project_name.lower(), project_name)
    return search_tasks(query="", project=clean_proj, max_results=max_results, token=token, database_id=database_id)


def parse_task_prefix(text: str) -> Optional[Dict[str, Any]]:
    """
    Inspects text for prefixes:
    - 'Бах — —', 'бах --', 'бах - -' -> Type='Bug', Priority='High'
    - 'ідея —', 'ідея -' -> Type='Idea'
    - 'думка —', 'думка -' -> Type='Fix' or 'Feature'
    Returns parsed dictionary with:
    - 'title': concise title for 'Name' property (up to 7-10 words / 60 chars)
    - 'description': full untruncated content for page body
    """
    if not text or not isinstance(text, str):
        return None

    stripped = text.strip()
    norm = stripped.replace("—", "-").replace("–", "-")

    # 1. Match 'Бах - -' або 'Бах --' або 'Бах -'
    match_bug = re.match(r"^(?:бах|пах)\s*(?:-\s*)+(.+)$", norm, re.IGNORECASE | re.DOTALL)
    if match_bug:
        clean = match_bug.group(1).strip()
        title = extract_concise_title(clean, max_len=60, max_words=10)
        desc = f"⚠️ **Priority: High**\n\n{clean}"
        return {
            "type": "Bug",
            "title": title,
            "rice_score": 120.0,
            "description": desc,
            "raw_text": clean,
            "priority": "High"
        }

    # 2. Match 'ідея -' або 'ідея —'
    match_idea = re.match(r"^(?:ідея|идея|idea)\s*(?:-\s*)+(.+)$", norm, re.IGNORECASE | re.DOTALL)
    if match_idea:
        clean = match_idea.group(1).strip()
        title = extract_concise_title(clean, max_len=60, max_words=10)
        desc = f"💡 **Idea:**\n\n{clean}"
        return {
            "type": "Idea",
            "title": title,
            "rice_score": 50.0,
            "description": desc,
            "raw_text": clean,
            "priority": "Medium"
        }

    # 3. Match 'думка -' або 'думка —'
    match_thought = re.match(r"^(?:думка|мысль|thought)\s*(?:-\s*)+(.+)$", norm, re.IGNORECASE | re.DOTALL)
    if match_thought:
        clean = match_thought.group(1).strip()
        title = extract_concise_title(clean, max_len=60, max_words=10)

        fix_keywords = ["фікс", "виправ", "поправ", "баг", "помилк", "лаг", "глюк", "криво", "fix", "bug"]
        is_fix = any(k in clean.lower() for k in fix_keywords)
        task_type = "Fix" if is_fix else "Feature"

        desc = f"💭 **{task_type} Thought:**\n\n{clean}"
        return {
            "type": task_type,
            "title": title,
            "rice_score": 60.0 if is_fix else 45.0,
            "description": desc,
            "raw_text": clean,
            "priority": "Medium"
        }

    return None


def triage_with_llm(raw_text: str, project: Optional[str] = None) -> Dict[str, Any]:
    """
    Triages raw text via LLM (OpenAI / Gemini if API key available)
    or falls back to deterministic NLP heuristic.
    Generates a concise title (<= 60 chars) and preserves the full text for description.
    """
    openai_key = os.getenv("OPENAI_API_KEY")

    if openai_key:
        try:
            prompt = (
                "You are an agile triage assistant. Analyze this raw user task/idea/feedback message:\n"
                f"'''{raw_text}'''\n\n"
                "Extract structured task information in JSON format with fields:\n"
                "- title: concise, punchy title summarizing the task (up to 7-10 words, max 60 chars) in the original language\n"
                "- type: one of exactly ['Bug', 'Feature', 'Fix', 'Idea']\n"
                "- rice_score: estimated number (e.g. between 10 and 200)\n"
                "- description: well-formulated, full description in the original language preserving all details\n"
                "Respond ONLY with valid JSON."
            )
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps({
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2
                }).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                t_type = parsed.get("type", "Idea")
                if t_type not in ["Bug", "Feature", "Fix", "Idea"]:
                    t_type = "Idea"
                return {
                    "title": extract_concise_title(parsed.get("title", ""), max_len=60, max_words=10),
                    "type": t_type,
                    "rice_score": float(parsed.get("rice_score", 50.0)),
                    "description": parsed.get("description", raw_text)
                }
        except Exception:
            pass

    prefix_data = parse_task_prefix(raw_text)
    if prefix_data:
        return {
            "title": prefix_data["title"],
            "type": prefix_data["type"],
            "rice_score": prefix_data.get("rice_score", 50.0),
            "description": prefix_data.get("description", raw_text)
        }

    title = extract_concise_title(raw_text, max_len=60, max_words=10)

    lower = raw_text.lower()
    if any(k in lower for k in ["помилк", "error", "fail", "падає", "краш", "не робить", "не працює"]):
        task_type = "Bug"
        score = 95.0
    elif any(k in lower for k in ["фікс", "виправ", "поправ"]):
        task_type = "Fix"
        score = 70.0
    elif any(k in lower for k in ["додай", "зроби", "функція", "нове", "хочу", "feature"]):
        task_type = "Feature"
        score = 55.0
    else:
        task_type = "Idea"
        score = 40.0

    return {
        "title": title,
        "type": task_type,
        "rice_score": score,
        "description": f"Оригінальне повідомлення:\n\n{raw_text}"
    }
