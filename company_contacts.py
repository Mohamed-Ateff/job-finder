"""A company's own email addresses for applying, from its public website.

Most postings don't give an address. The company's website usually does, on its careers or contact
page. For a LinkedIn job: the job page names the company, the company's LinkedIn page names its website,
and the website's home, careers and contact pages are read for email addresses. Only addresses on the
company's own domain are kept (so a web designer's or a plugin's address isn't), HR and careers
addresses first. A handful of polite requests per company, made once and then remembered by the app.
"""

from __future__ import annotations

import re
import time
from urllib.parse import parse_qs, unquote, urljoin, urlparse

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/131.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}
LINKEDIN_POSTING = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Pages worth reading on a company's site, by what their links say.
PAGE_WORDS = re.compile(r"career|jobs?\b|join|hiring|vacanc|recruit|work[- ]with|contact|about|وظائف|توظيف|اتصل|تواصل", re.I)
COMMON_PAGES = ("/careers", "/contact", "/contact-us", "/jobs")
# HR and hiring addresses come first; then general ones; never no-reply or privacy ones.
HIRING = re.compile(r"^(?:hr|careers?|jobs?|recruit\w*|talent\w*|hiring|people|cv|resumes?|join\w*|apply|work|employment|vacanc\w*)[._-]?\w*@", re.I)
GENERAL = re.compile(r"^(?:info|contact|hello|hi|office|admin|enquir\w*|inquir\w*|team|support)@", re.I)
SKIP = re.compile(r"^(?:no-?reply|donotreply|privacy|dpo|gdpr|abuse|postmaster|webmaster|legal|security)@"
                  r"|\.(?:png|jpe?g|gif|webp|svg)$|@(?:\dx\.|sentry|wixpress|example|domain|email)\.", re.I)
NOT_COMPANY_SITES = ("linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com",
                     "bit.ly", "linktr.ee", "wuzzuf.net", "bayt.com", "indeed.com", "glassdoor.com")


def _get(url: str, timeout: float = 10.0):
    import requests

    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
            return None
        r.encoding = r.encoding or "utf-8"
        return r
    except Exception:  # noqa: BLE001 - an unreachable page just has no addresses
        return None


def domain_of(url: str) -> str:
    host = (urlparse(url if "//" in url else f"https://{url}").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def linkedin_company_site(job_url: str, pause: float = 1.0) -> str | None:
    """The company's website for a LinkedIn job: "" when LinkedIn doesn't name one, None when LinkedIn
    couldn't be read (blocked or offline) - so a failed read isn't remembered as "no website"."""
    from bs4 import BeautifulSoup

    match = re.search(r"linkedin\.com/jobs/view/(?:[^/?#]*-)?(\d{6,})", job_url or "")
    if not match:
        return ""
    r = _get(LINKEDIN_POSTING.format(id=match.group(1)))
    if r is None:
        return None
    link = BeautifulSoup(r.text, "html.parser").select_one(
        "a.topcard__org-name-link, a[data-tracking-control-name='public_jobs_topcard-org-name']")
    if not link or "linkedin.com/company/" not in link.get("href", ""):
        return ""
    time.sleep(pause)
    page = _get(link["href"].split("?")[0])
    if page is None:
        return None
    site = BeautifulSoup(page.text, "html.parser").select_one("a[data-tracking-control-name='about_website']")
    if not site:
        return ""
    href = site.get("href", "")
    if "linkedin.com/redir" in href:                    # LinkedIn wraps it: ...redirect?url=https%3A%2F%2Facme.com
        href = unquote(parse_qs(urlparse(href).query).get("url", [""])[0])
    return href if href.startswith(("http://", "https://")) else ""


def _emails_in(html: str) -> list[str]:
    from html import unescape

    text = re.sub(r"\s*[\[(]\s*at\s*[\])]\s*", "@", unescape(html), flags=re.I)     # "hr [at] acme.com"
    text = re.sub(r"(@[A-Za-z0-9-]+)\s*[\[(]\s*dot\s*[\])]\s*", r"\1.", text, flags=re.I)  # "acme [dot] com"
    found = re.findall(r"mailto:([^\"'?>\s]+)", text) + EMAIL_RE.findall(text)
    return [unquote(e).strip(".").lower() for e in found]


def site_emails(site: str, most_pages: int = 5) -> list[str]:
    """Email addresses on a company's website, on its own domain: hiring ones first."""
    from bs4 import BeautifulSoup

    domain = domain_of(site)
    if not domain or any(domain == d or domain.endswith(f".{d}") for d in NOT_COMPANY_SITES):
        return []
    home = _get(site, timeout=8)
    if not home:
        return []
    found = _emails_in(home.text)
    base = home.url
    links = []
    for a in BeautifulSoup(home.text, "html.parser").find_all("a", href=True):
        href = urljoin(base, a["href"]).split("#")[0]
        if domain_of(href) == domain and PAGE_WORDS.search(f"{a.get_text(' ', strip=True)} {href}"):
            links.append(href)
    links += [urljoin(base, p) for p in COMMON_PAGES]
    pages = list(dict.fromkeys(u for u in links if u.rstrip("/") != base.rstrip("/")))[:most_pages]
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max(1, len(pages))) as pool:      # a few pages at once, not one by one
        for page in pool.map(lambda u: _get(u, timeout=6), pages):
            if page:
                found += _emails_in(page.text)
    domains = {domain, domain_of(base)}                 # the site may have moved to a new name
    # Only the company's role addresses (hr@, careers@, info@ ...), never a person's own address.
    own = [e for e in dict.fromkeys(found)
           if not SKIP.search(e) and (HIRING.match(e) or GENERAL.match(e))
           and any(e.split("@")[1] == d or e.split("@")[1].endswith(f".{d}") for d in domains if d)]
    return sorted(own, key=lambda e: 0 if HIRING.match(e) else 1)[:3]
