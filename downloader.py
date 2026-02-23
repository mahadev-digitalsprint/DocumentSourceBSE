import os
import requests
from bse import BSE
from datetime import date
from companies import COMPANIES

BOARD_MEETING_RESULT_KEYWORDS = [
    'unaudited financial results',
    'audited financial results',
    'standalone and consolidated',
    'financial results and',
    'results for the quarter',
    'results for quarter',
]

FINANCIAL_KEYWORDS = [
    'unaudited financial results',
    'audited financial results',
    'quarterly results',
    'annual report',
    'investor presentation on',
    'press release on financial results',
    'press release w.r.t. financial results',
    'media statement and investor presentation',
    'media statement and presentation on financial',
    'earnings call',
    'transcript of earnings call',
    'transcript of the discussion on the unaudited',
    'performance review',
    'financial results for the quarter',
    'financial results for quarter',
    'results for the quarter',
]

EXCLUDE_KEYWORDS = [
    'schedule of analyst',
    'schedule of board meeting',
    'board meeting is scheduled',
    'meeting of the board of directors of the company is scheduled',
    'audio recording',
    'audio/video recording',
    'kanto local finance bureau',
    'newspaper advertisement',
    'publication of newspaper',
    'informed the exchange about copy of newspaper',
    'dial-in details',
    'host an earnings call',
    'host a conference call',
    'schedule of earnings call',
    'earnings call in relation',
    'enclosing herewith the schedule',
    'will be participating',
    'participated in the institutional',
    'retail store',
    'center of excellence',
    '5g coverage',
    'partnership',
    'collaboration',
    'strategic',
    'launches',
    'launch of',
    'opens new',
    'selects tcs',
    'taps tcs',
    'deepen',
    'unveil',
    'forge',
    'hackathon',
    're-appointment',
    'reappointment',
    'presentation to be made at',
    'intimation attached',
    'in continuation of our letter',
    'have been uploaded on',
    'uploaded on the website',
    'uploaded on bse',
    'have been uploaded',
]


def is_financial(item):
    category = item.get('CATEGORYNAME', '').lower()
    headline = item.get('HEADLINE', '').lower()

    if any(ex in headline for ex in EXCLUDE_KEYWORDS):
        return False

    if 'result' in category:
        # Even in Result category, exclude vague board meeting outcomes with no financial keyword
        if 'outcome of board meeting' in headline and not any(kw in headline for kw in BOARD_MEETING_RESULT_KEYWORDS):
            return False
        return True

    if 'board meeting' in category:
        return any(kw in headline for kw in BOARD_MEETING_RESULT_KEYWORDS)

    if 'company update' in category:
        return any(kw in headline for kw in FINANCIAL_KEYWORDS)

    return False


def download_pdfs(company_name=None, bse_code=None, limit=None):
    targets = COMPANIES
    if company_name and bse_code:
        targets = [{"name": company_name, "bse_code": bse_code}]
    elif limit:
        targets = COMPANIES[:limit]

    results = {}

    with BSE(download_folder='./downloads') as bse:
        for company in targets:
            name = company["name"]
            code = company["bse_code"]
            print(f"\n[DOWNLOADER] Processing: {name} (BSE: {code})")

            try:
                response = bse.announcements(
                    scripcode=code,
                    from_date=date(2024, 1, 1),
                    to_date=date.today()
                )

                all_announcements = response.get('Table', [])
                announcements = [item for item in all_announcements if is_financial(item)]

                print(f"[DOWNLOADER] Found {len(announcements)} financial filings for {name}")

                folder = os.path.join('downloads', name.replace(' ', '_'))
                os.makedirs(folder, exist_ok=True)

                downloaded = []
                skipped = 0

                for item in announcements:
                    attachment = item.get('ATTACHMENTNAME', '')
                    headline = item.get('HEADLINE', '')
                    date_str = item.get('NEWS_DT', '')[:10]

                    if not attachment:
                        skipped += 1
                        continue

                    pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attachment}"
                    filename = f"{date_str}_{attachment}"
                    save_path = os.path.join(folder, filename)

                    if os.path.exists(save_path):
                        print(f"[EXISTS] {name}: {filename}")
                        continue

                    try:
                        headers = {'User-Agent': 'Mozilla/5.0'}
                        pdf = requests.get(pdf_url, headers=headers, timeout=15)
                        with open(save_path, 'wb') as f:
                            f.write(pdf.content)
                        print(f"[DOWNLOADED] {name}: {headline} ({date_str})")
                        downloaded.append({
                            "file": filename,
                            "headline": headline,
                            "date": date_str
                        })
                    except Exception as e:
                        print(f"[ERROR] {name} - {filename}: {e}")

                results[name] = {
                    "downloaded": downloaded,
                    "count": len(downloaded),
                    "skipped": skipped
                }
                print(f"[DONE] {name}: {len(downloaded)} downloaded, {skipped} skipped")

            except Exception as e:
                print(f"[ERROR] Could not fetch announcements for {name}: {e}")
                results[name] = {"error": str(e)}

    return results


if __name__ == "__main__":
    download_pdfs()