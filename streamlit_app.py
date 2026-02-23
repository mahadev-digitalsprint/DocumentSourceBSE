import os
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DEFAULT_API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_TIMEOUT = int(os.getenv("API_TIMEOUT_SECONDS", "30"))
NGROK_HEADER = {"ngrok-skip-browser-warning": "true"}


def call_api(
    method: str,
    base_url: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    try:
        response = requests.request(
            method=method,
            url=url,
            params=params,
            headers=NGROK_HEADER,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return True, response.json()
        return True, response.text
    except requests.RequestException as exc:
        message = str(exc)
        if exc.response is not None:
            message = f"{exc} | response: {exc.response.text[:400]}"
        return False, message


def fetch_zip_archive(base_url: str) -> Tuple[bool, Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/documents/archive/zip"
    try:
        response = requests.get(
            url,
            headers=NGROK_HEADER,
            timeout=max(60, DEFAULT_TIMEOUT),
        )
        response.raise_for_status()

        file_name = "filings.zip"
        disposition = response.headers.get("content-disposition", "")
        if "filename=" in disposition:
            file_name = disposition.split("filename=")[-1].strip().strip('"')

        return True, {"file_name": file_name, "content": response.content}
    except requests.RequestException as exc:
        message = str(exc)
        if exc.response is not None:
            message = f"{exc} | response: {exc.response.text[:400]}"
        return False, {"error": message}


@st.cache_data(ttl=120)
def get_companies(base_url: str) -> List[Dict[str, str]]:
    ok, data = call_api("GET", base_url, "/companies")
    if not ok:
        return []
    return data.get("companies", [])


st.set_page_config(page_title="S&P Financial Agent UI", layout="wide")
st.title("S&P Financial Agent")
st.caption("Simple Streamlit UI for your FastAPI service")

with st.sidebar:
    st.subheader("Connection")
    api_base_url = st.text_input("API Base URL", value=DEFAULT_API_BASE_URL).strip()
    if api_base_url.endswith("/"):
        api_base_url = api_base_url[:-1]
    st.code(api_base_url)
    st.caption("Example: http://127.0.0.1:8000 or your ngrok URL")

tabs = st.tabs(["Overview", "Download / Monitor", "Filings", "Documents / Changes"])

with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Check Status", use_container_width=True):
            ok, data = call_api("GET", api_base_url, "/status")
            if ok:
                st.success("API reachable")
                st.json(data)
            else:
                st.error(data)
    with c2:
        if st.button("Load Companies", use_container_width=True):
            companies = get_companies(api_base_url)
            if companies:
                st.success(f"Loaded {len(companies)} companies")
                st.table(companies)
            else:
                st.error("Unable to load companies")

with tabs[1]:
    companies = get_companies(api_base_url)
    options = ["All companies"] + [
        f"{item['name']} ({item['bse_code']})" for item in companies
    ]

    selected = st.selectbox("Target", options=options)
    limit = st.number_input("Limit (for all companies)", min_value=1, value=5, step=1)
    q_params = {"limit": int(limit)}

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Run Download", use_container_width=True):
            if selected == "All companies":
                ok, data = call_api("POST", api_base_url, "/run-download", params=q_params)
            else:
                bse_code = selected.split("(")[-1].replace(")", "")
                ok, data = call_api("POST", api_base_url, f"/run-download/{bse_code}")
            if ok:
                st.success("Download run completed")
                st.json(data)
            else:
                st.error(data)
    with c2:
        if st.button("Run Monitor", use_container_width=True):
            if selected == "All companies":
                ok, data = call_api("POST", api_base_url, "/run-monitor", params=q_params)
            else:
                bse_code = selected.split("(")[-1].replace(")", "")
                ok, data = call_api("POST", api_base_url, f"/run-monitor/{bse_code}")
            if ok:
                st.success("Monitor run completed")
                st.json(data)
            else:
                st.error(data)

    st.divider()
    st.subheader("Custom Company URL")
    custom_company_name = st.text_input(
        "Custom company name",
        value="Custom Company",
        key="custom_company_name",
    )
    custom_source_url = st.text_input(
        "Custom source URL",
        placeholder="https://example.com/investor-relations",
        key="custom_source_url",
    )

    c3, c4 = st.columns(2)
    with c3:
        if st.button("Run Custom Download", use_container_width=True):
            if not custom_company_name.strip() or not custom_source_url.strip():
                st.error("Company name and source URL are required.")
            else:
                ok, data = call_api(
                    "POST",
                    api_base_url,
                    "/custom/run-download",
                    params={
                        "company_name": custom_company_name.strip(),
                        "source_url": custom_source_url.strip(),
                    },
                )
                if ok:
                    st.success("Custom URL download completed")
                    st.json(data)
                else:
                    st.error(data)
    with c4:
        if st.button("Run Custom Monitor", use_container_width=True):
            if not custom_company_name.strip() or not custom_source_url.strip():
                st.error("Company name and source URL are required.")
            else:
                ok, data = call_api(
                    "POST",
                    api_base_url,
                    "/custom/run-monitor",
                    params={
                        "company_name": custom_company_name.strip(),
                        "source_url": custom_source_url.strip(),
                    },
                )
                if ok:
                    st.success("Custom URL monitor completed")
                    st.json(data)
                else:
                    st.error(data)

with tabs[2]:
    st.subheader("All Filings")
    y1, y2, y3 = st.columns(3)
    with y1:
        from_year = st.number_input("From year", min_value=2000, value=2024, step=1)
    with y2:
        to_year = st.number_input("To year", min_value=2000, value=2026, step=1)
    with y3:
        filings_limit = st.number_input("Company limit", min_value=1, value=10, step=1)

    if st.button("Fetch All Filings"):
        ok, data = call_api(
            "GET",
            api_base_url,
            "/filings/all",
            params={
                "from_year": int(from_year),
                "to_year": int(to_year),
                "limit": int(filings_limit),
            },
        )
        if ok:
            st.json(data)
        else:
            st.error(data)

    st.divider()
    st.subheader("Single Company Filings")
    companies = get_companies(api_base_url)
    if companies:
        single_target = st.selectbox(
            "Company",
            options=[f"{item['name']} ({item['bse_code']})" for item in companies],
            key="single_company_filings",
        )
        if st.button("Fetch Company Filings"):
            bse_code = single_target.split("(")[-1].replace(")", "")
            ok, data = call_api(
                "GET",
                api_base_url,
                f"/filings/{bse_code}",
                params={"from_year": int(from_year), "to_year": int(to_year)},
            )
            if ok:
                st.json(data)
            else:
                st.error(data)
    else:
        st.info("Load companies from Overview tab first.")

with tabs[3]:
    c1, c2 = st.columns(2)
    with c1:
        if st.button("List Documents", use_container_width=True):
            ok, data = call_api("GET", api_base_url, "/documents")
            if ok:
                st.json(data)
            else:
                st.error(data)
    with c2:
        if st.button("Check Changes", use_container_width=True):
            ok, data = call_api("GET", api_base_url, "/changes")
            if ok:
                st.json(data)
            else:
                st.error(data)

    st.divider()
    st.subheader("Download All Filings as ZIP")
    if "zip_blob" not in st.session_state:
        st.session_state["zip_blob"] = None
        st.session_state["zip_name"] = "filings.zip"

    if st.button("Generate ZIP", use_container_width=True):
        ok, payload = fetch_zip_archive(api_base_url)
        if ok:
            st.session_state["zip_blob"] = payload["content"]
            st.session_state["zip_name"] = payload["file_name"]
            st.success("ZIP generated. Click download below.")
        else:
            st.error(payload["error"])

    if st.session_state["zip_blob"]:
        st.download_button(
            label="Download Filings ZIP",
            data=st.session_state["zip_blob"],
            file_name=st.session_state["zip_name"],
            mime="application/zip",
            use_container_width=True,
        )
