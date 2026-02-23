import hashlib
import json
import os
import re
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
SNAPSHOTS_DIR = os.path.join(BASE_DIR, "snapshots")
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}


def sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    return cleaned.strip("_") or "custom_company"


def sanitize_filename(value: str) -> str:
    value = value.strip().replace("\\", "_").replace("/", "_")
    value = re.sub(r"[^a-zA-Z0-9._-]+", "_", value)
    return value[:180] or "document.pdf"


def extract_pdf_links(source_url: str) -> List[str]:
    parsed_source = urlparse(source_url)
    if parsed_source.path.lower().endswith(".pdf"):
        return [source_url]

    response = requests.get(source_url, headers=REQUEST_HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    links: List[str] = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href:
            continue

        resolved = urljoin(source_url, href)
        path = urlparse(resolved).path.lower()
        if not path.endswith(".pdf"):
            continue

        if resolved in seen:
            continue
        seen.add(resolved)
        links.append(resolved)

    return links


def custom_download_pdfs(company_name: str, source_url: str) -> Dict:
    safe_name = sanitize_name(company_name)
    company_dir = os.path.join(DOWNLOADS_DIR, safe_name)
    os.makedirs(company_dir, exist_ok=True)

    try:
        links = extract_pdf_links(source_url)
    except Exception as exc:
        return {
            "company": company_name,
            "source_url": source_url,
            "status": "error",
            "error": str(exc),
            "saved_to": company_dir,
        }

    downloaded = []
    skipped = 0
    errors = []

    for link in links:
        parsed_path = urlparse(link).path
        basename = os.path.basename(parsed_path) or "document.pdf"
        basename = sanitize_filename(basename)
        if not basename.lower().endswith(".pdf"):
            basename = f"{basename}.pdf"

        digest = hashlib.sha1(link.encode("utf-8")).hexdigest()[:10]
        filename = f"{digest}_{basename}"
        save_path = os.path.join(company_dir, filename)

        if os.path.exists(save_path):
            skipped += 1
            continue

        try:
            pdf_resp = requests.get(link, headers=REQUEST_HEADERS, timeout=25)
            pdf_resp.raise_for_status()
            with open(save_path, "wb") as file_obj:
                file_obj.write(pdf_resp.content)
            downloaded.append({"file": filename, "url": link})
        except Exception as exc:
            errors.append({"url": link, "error": str(exc)})

    return {
        "company": company_name,
        "source_url": source_url,
        "status": "completed",
        "pdf_links_found": len(links),
        "downloaded": downloaded,
        "downloaded_count": len(downloaded),
        "skipped_count": skipped,
        "error_count": len(errors),
        "errors": errors[:10],
        "saved_to": company_dir,
    }


def custom_monitor_pdfs(company_name: str, source_url: str) -> Dict:
    safe_name = sanitize_name(company_name)
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    snapshot_file = os.path.join(SNAPSHOTS_DIR, f"custom_{safe_name}.json")

    try:
        links = extract_pdf_links(source_url)
    except Exception as exc:
        return {
            "company": company_name,
            "source_url": source_url,
            "status": "error",
            "error": str(exc),
            "snapshot_file": snapshot_file,
        }

    current = {
        hashlib.sha1(link.encode("utf-8")).hexdigest()[:12]: link for link in links
    }

    if not os.path.exists(snapshot_file):
        with open(snapshot_file, "w", encoding="utf-8") as file_obj:
            json.dump(current, file_obj, indent=2)
        return {
            "company": company_name,
            "source_url": source_url,
            "status": "first snapshot saved",
            "tracked_links": len(current),
            "snapshot_file": snapshot_file,
        }

    with open(snapshot_file, "r", encoding="utf-8") as file_obj:
        previous = json.load(file_obj)

    new_items = [url for key, url in current.items() if key not in previous]
    removed_items = [url for key, url in previous.items() if key not in current]

    with open(snapshot_file, "w", encoding="utf-8") as file_obj:
        json.dump(current, file_obj, indent=2)

    if not new_items and not removed_items:
        status = "no changes"
    else:
        status = "changes detected"

    return {
        "company": company_name,
        "source_url": source_url,
        "status": status,
        "tracked_links": len(current),
        "new_links_count": len(new_items),
        "removed_links_count": len(removed_items),
        "new_links": new_items[:20],
        "removed_links": removed_items[:20],
        "snapshot_file": snapshot_file,
    }
