import json
import os
import shutil
from datetime import date, datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from companies import COMPANIES
from custom_url_tools import custom_download_pdfs, custom_monitor_pdfs
from downloader import download_pdfs, is_financial
from monitor import check_for_changes
from bse import BSE

app = FastAPI(title="S&P Financial Agent API", version="1.0")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
SNAPSHOTS_DIR = os.path.join(BASE_DIR, "snapshots")


@app.get("/status")
def status():
    return {
        "status": "running",
        "time": str(datetime.now()),
        "companies_tracked": len(COMPANIES)
    }


@app.get("/companies")
def list_companies():
    return {"companies": [
        {"name": c["name"], "bse_code": c["bse_code"]}
        for c in COMPANIES
    ]}


@app.post("/run-download")
def run_download(
    limit: int = Query(default=None, description="Number of companies to download. Leave blank for all.")
):
    results = download_pdfs(limit=limit)
    return {"message": "Download complete", "results": results}


@app.post("/run-download/{bse_code}")
def run_download_single(bse_code: str):
    company = next((c for c in COMPANIES if c["bse_code"] == bse_code), None)
    if not company:
        return {"error": f"Company with BSE code {bse_code} not found"}
    results = download_pdfs(company_name=company["name"], bse_code=bse_code)
    return {"message": "Download complete", "results": results}


@app.post("/run-monitor")
def run_monitor(
    limit: int = Query(default=None, description="Number of companies to monitor. Leave blank for all.")
):
    changes = check_for_changes(limit=limit)
    return {"message": "Monitor check complete", "changes": changes}


@app.post("/run-monitor/{bse_code}")
def run_monitor_single(bse_code: str):
    company = next((c for c in COMPANIES if c["bse_code"] == bse_code), None)
    if not company:
        return {"error": f"Company with BSE code {bse_code} not found"}
    changes = check_for_changes(company_name=company["name"], bse_code=bse_code)
    return {"message": "Monitor check complete", "changes": changes}


@app.post("/custom/run-download")
def run_custom_download(
    company_name: str = Query(..., description="Display name for the custom company"),
    source_url: str = Query(..., description="Public page URL containing PDF links"),
):
    results = custom_download_pdfs(company_name=company_name, source_url=source_url)
    return {"message": "Custom URL download complete", "results": results}


@app.post("/custom/run-monitor")
def run_custom_monitor(
    company_name: str = Query(..., description="Display name for the custom company"),
    source_url: str = Query(..., description="Public page URL containing PDF links"),
):
    results = custom_monitor_pdfs(company_name=company_name, source_url=source_url)
    return {"message": "Custom URL monitor complete", "changes": results}


@app.get("/filings/all")
def get_all_filings(
    from_year: int = Query(default=2024),
    to_year: int = Query(default=date.today().year),
    limit: int = Query(default=None, description="Number of companies to fetch. Leave blank for all.")
):
    targets = COMPANIES[:limit] if limit else COMPANIES
    all_filings = []

    with BSE(download_folder='./downloads') as bse:
        for company in targets:
            try:
                response = bse.announcements(
                    scripcode=company["bse_code"],
                    from_date=date(from_year, 1, 1),
                    to_date=date.today()
                )

                announcements = [
                    item for item in response.get('Table', [])
                    if is_financial(item)
                ]

                for item in announcements:
                    all_filings.append({
                        "company": company["name"],
                        "bse_code": company["bse_code"],
                        "headline": item.get('HEADLINE', ''),
                        "date": item.get('NEWS_DT', '')[:10],
                        "category": item.get('CATEGORYNAME', ''),
                        "pdf_url": f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{item.get('ATTACHMENTNAME', '')}"
                    })

            except Exception as e:
                print(f"[ERROR] {company['name']}: {e}")

    all_filings.sort(key=lambda x: x['date'], reverse=True)

    return {
        "total_filings": len(all_filings),
        "companies_fetched": len(targets),
        "from_year": from_year,
        "to_year": to_year,
        "filings": all_filings
    }


@app.get("/filings/{bse_code}")
def get_filings(
    bse_code: str,
    from_year: int = Query(default=2024),
    to_year: int = Query(default=date.today().year)
):
    company = next((c for c in COMPANIES if c["bse_code"] == bse_code), None)
    if not company:
        return {"error": f"Company with BSE code {bse_code} not found"}

    with BSE(download_folder='./downloads') as bse:
        response = bse.announcements(
            scripcode=bse_code,
            from_date=date(from_year, 1, 1),
            to_date=date.today()
        )

    filings = [
        {
            "headline": item.get('HEADLINE', ''),
            "date": item.get('NEWS_DT', '')[:10],
            "category": item.get('CATEGORYNAME', ''),
            "pdf_url": f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{item.get('ATTACHMENTNAME', '')}"
        }
        for item in response.get('Table', [])
        if is_financial(item)
    ]

    return {
        "company": company["name"],
        "bse_code": bse_code,
        "total_filings": len(filings),
        "filings": filings
    }


@app.get("/documents")
def list_documents():
    folder = DOWNLOADS_DIR
    if not os.path.exists(folder):
        return {"documents": {}}
    result = {}
    for company in os.listdir(folder):
        company_path = os.path.join(folder, company)
        if os.path.isdir(company_path):
            files = os.listdir(company_path)
            result[company] = {"files": files, "count": len(files)}
    return {"documents": result}


@app.get("/documents/{company_name}")
def get_company_documents(company_name: str):
    folder = os.path.join(DOWNLOADS_DIR, company_name)
    if not os.path.exists(folder):
        return {"message": f"No documents found for {company_name}"}
    files = os.listdir(folder)
    return {"company": company_name, "files": files, "count": len(files)}


@app.get("/documents/archive/zip")
def download_documents_archive():
    source_dir = DOWNLOADS_DIR
    if not os.path.exists(source_dir):
        raise HTTPException(status_code=404, detail="Downloads folder not found")

    has_files = False
    for _, _, files in os.walk(source_dir):
        if files:
            has_files = True
            break

    if not has_files:
        raise HTTPException(status_code=404, detail="No downloaded filings available")

    archive_dir = os.path.join(SNAPSHOTS_DIR, "archives")
    os.makedirs(archive_dir, exist_ok=True)

    archive_base_name = os.path.join(
        archive_dir, f"filings_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    archive_path = shutil.make_archive(
        base_name=archive_base_name,
        format="zip",
        root_dir=source_dir,
    )

    return FileResponse(
        path=archive_path,
        media_type="application/zip",
        filename=os.path.basename(archive_path),
    )


@app.get("/changes")
def get_changes():
    snapshots_dir = SNAPSHOTS_DIR
    if not os.path.exists(snapshots_dir):
        return {"message": "No snapshots yet"}
    result = {}
    for f in os.listdir(snapshots_dir):
        if f.endswith('.json'):
            company = f.replace('.json', '').replace('_', ' ')
            with open(os.path.join(snapshots_dir, f)) as sf:
                data = json.load(sf)
            result[company] = {"filings_tracked": len(data)}
    return {"snapshots": result}

@app.get("/companies/preview")
def preview_companies(
    limit: int = Query(default=10, description="Number of top BSE companies to preview")
):
    companies = COMPANIES[:limit]
    return {
        "limit": limit,
        "total_fetched": len(companies),
        "companies": companies
    }
