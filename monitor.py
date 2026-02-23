import os
import json
from bse import BSE
from datetime import date, datetime
from companies import COMPANIES

SNAPSHOTS_DIR = "snapshots"

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


def check_for_changes(company_name=None, bse_code=None, limit=None):
    targets = COMPANIES
    if company_name and bse_code:
        targets = [{"name": company_name, "bse_code": bse_code}]
    elif limit:
        targets = COMPANIES[:limit]

    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    all_changes = {}

    with BSE(download_folder='./downloads') as bse:
        for company in targets:
            name = company["name"]
            code = company["bse_code"]
            snapshot_file = os.path.join(SNAPSHOTS_DIR, f"{name.replace(' ', '_')}.json")

            print(f"\n[MONITOR] Checking: {name}")

            try:
                response = bse.announcements(
                    scripcode=code,
                    from_date=date(2024, 1, 1),
                    to_date=date.today()
                )

                all_announcements = response.get('Table', [])
                announcements = [item for item in all_announcements if is_financial(item)]

                current = {
                    item.get('NEWSID', ''): item.get('HEADLINE', '')
                    for item in announcements
                }

                if not os.path.exists(snapshot_file):
                    with open(snapshot_file, 'w') as f:
                        json.dump(current, f)
                    print(f"[MONITOR] First snapshot saved for {name} — {len(current)} filings tracked")
                    all_changes[name] = {"status": "first snapshot saved"}
                    continue

                with open(snapshot_file, 'r') as f:
                    previous = json.load(f)

                new_items = {k: v for k, v in current.items() if k not in previous}
                removed_items = {k: v for k, v in previous.items() if k not in current}

                if not new_items and not removed_items:
                    print(f"[MONITOR] No changes for {name}")
                    all_changes[name] = {"status": "no changes"}
                else:
                    print(f"\n[MONITOR] *** CHANGES DETECTED for {name} ***")
                    changes = {
                        "status": "changes detected",
                        "new_filings": list(new_items.values()),
                        "removed_filings": list(removed_items.values()),
                        "detected_at": str(datetime.now())
                    }
                    all_changes[name] = changes

                    if new_items:
                        print(f"  NEW FILINGS ({len(new_items)}):")
                        for headline in list(new_items.values())[:5]:
                            print(f"    + {headline}")

                with open(snapshot_file, 'w') as f:
                    json.dump(current, f)

            except Exception as e:
                print(f"[ERROR] {name}: {e}")
                all_changes[name] = {"error": str(e)}

    return all_changes


if __name__ == "__main__":
    check_for_changes()