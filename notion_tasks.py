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
    "shorts": "Shorts Downloader",
    "shorts downloader": "Shorts Downloader",
    "🎬 shorts downloader": "Shorts Downloader",
    "anime": "⛩️ Anime Downloader",
    "feedback": "💬 Feedback",
    "core": "⚡ Core System"
}


def send_task(
    name: str,
    status: Optional[str] = "Inbox",
    task_type: Optional[str] = None,
    project: Optional[str] = None,
    rice_score: Optional[float] = None,
    description: Optional[str] = None,
    token: Optional[str] = None,
    database_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates and sends a task to the Notion database.
    """
    api_token = (token or os.getenv("NOTION_TOKEN") or "").strip() or NOTION_TOKEN
    target_db_id = (database_id or os.getenv("NOTION_DATABASE_ID") or "").strip() or DATABASE_ID

    if not api_token or api_token == "your_notion_token_here":
        raise ValueError("Відсутній токен NOTION_TOKEN у змінних оточення (Variables на Railway).")
    if not target_db_id or target_db_id == "your_database_id_here":
        raise ValueError("Відсутній ідентифікатор бази NOTION_DATABASE_ID у змінних оточення.")

    properties: Dict[str, Any] = {
        "Name": {
            "title": [
                {
                    "type": "text",
                    "text": {"content": name[:2000]}
                }
            ]
        }
    }

    if status:
        properties["Status"] = {"select": {"name": status}}

    if task_type:
        properties["Type"] = {"select": {"name": task_type}}

    if project:
        # Standardize project names if short alias is given
        clean_proj = PROJECT_OPTIONS.get(project.lower(), project)
        properties["Project"] = {"select": {"name": clean_proj}}

    if rice_score is not None:
        try:
            properties["RICE Score"] = {"number": float(rice_score)}
        except (ValueError, TypeError):
            pass

    payload: Dict[str, Any] = {
        "parent": {
            "database_id": target_db_id
        },
        "properties": properties
    }

    if description:
        payload["children"] = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": description[:2000]}
                        }
                    ]
                }
            }
        ]

    req = urllib.request.Request(
        "https://api.notion.com/v1/pages",
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
            return {
                "success": True,
                "task_id": data.get("id"),
                "url": data.get("url"),
                "data": data
            }
    except urllib.error.HTTPError as err:
        err_msg = err.read().decode("utf-8")
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
    Returns parsed dictionary or None if prefix doesn't match.
    """
    if not text or not isinstance(text, str):
        return None

    stripped = text.strip()
    norm = stripped.replace("—", "-").replace("–", "-")

    # 1. Match 'Бах - -' або 'Бах --' або 'Бах -' або 'Бах — —'
    match_bug = re.match(r"^(?:бах|пах)\s*(?:-\s*)+(.+)$", norm, re.IGNORECASE | re.DOTALL)
    if match_bug:
        clean = match_bug.group(1).strip()
        first_line = clean.split("\n", 1)[0].strip()
        desc = f"⚠️ Priority: High\n\nOriginal text:\n{stripped}"
        return {
            "type": "Bug",
            "title": first_line if first_line else clean,
            "rice_score": 90.0,
            "description": desc,
            "priority": "High"
        }

    # 2. Match 'ідея -' або 'ідея —'
    match_idea = re.match(r"^(?:ідея|идея|idea)\s*(?:-\s*)+(.+)$", norm, re.IGNORECASE | re.DOTALL)
    if match_idea:
        clean = match_idea.group(1).strip()
        first_line = clean.split("\n", 1)[0].strip()
        desc = f"💡 Idea description:\n{stripped}"
        return {
            "type": "Idea",
            "title": first_line if first_line else clean,
            "rice_score": 50.0,
            "description": desc,
            "priority": "Medium"
        }

    # 3. Match 'думка -' або 'думка —'
    match_thought = re.match(r"^(?:думка|мысль|thought)\s*(?:-\s*)+(.+)$", norm, re.IGNORECASE | re.DOTALL)
    if match_thought:
        clean = match_thought.group(1).strip()
        first_line = clean.split("\n", 1)[0].strip()

        fix_keywords = ["фікс", "виправ", "поправ", "баг", "помилк", "лаг", "глюк", "криво", "fix", "bug"]
        is_fix = any(k in clean.lower() for k in fix_keywords)
        task_type = "Fix" if is_fix else "Feature"

        desc = f"💭 Thought / Feedback:\n{stripped}"
        return {
            "type": task_type,
            "title": first_line if first_line else clean,
            "rice_score": 60.0,
            "description": desc,
            "priority": "Medium"
        }

    return None


def triage_with_llm(raw_text: str, project: Optional[str] = None) -> Dict[str, Any]:
    """
    Triages raw text via LLM (OpenAI / Gemini if API key available)
    or falls back to deterministic NLP heuristic.
    """
    openai_key = os.getenv("OPENAI_API_KEY")

    if openai_key:
        try:
            prompt = (
                "You are an agile triage assistant. Analyze this raw user task/idea/feedback message:\n"
                f"'''{raw_text}'''\n\n"
                "Extract structured task information in JSON format with fields:\n"
                "- title: concise, clear title in the original language (max 80 chars)\n"
                "- type: one of exactly ['Bug', 'Feature', 'Fix', 'Idea']\n"
                "- rice_score: estimated number (e.g. between 10 and 200)\n"
                "- description: well-formulated description in the original language\n"
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
                    "title": parsed.get("title", raw_text[:80]),
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

    lines = raw_text.strip().split("\n")
    first_line = lines[0].strip()
    title = first_line[:80]

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
        "title": title if title else "Новий відгук / ідея",
        "type": task_type,
        "rice_score": score,
        "description": f"Оригінальне повідомлення:\n{raw_text}"
    }
