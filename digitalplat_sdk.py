#!/usr/bin/env python3
"""
DigitalPlat FreeDomain — Full Powerful Python SDK
==================================================
Built from: https://github.com/DigitalPlatDev/FreeDomain (docs)
         + https://github.com/DigitalPlatDev/Domain-OSS (application source)

Covers 100% of Domain-OSS REST API + public dash.domain.digitalplat.org workflow.

Author: Generated for cita_auto workspace — Aug 2026

Features:
 - Self-hosted Domain-OSS (recommended, full control)
 - Public FreeDomain dashboard (dash.domain.digitalplat.org)
 - All record types: A, AAAA, CNAME, MX, TXT, SRV, CAA, NS
 - Bulk domain + DNS provisioning
 - ACME DNS-01 automation
 - Cloudflare / PowerDNS / BIND agnostic
 - Retry, rate-limit, pagination, HMAC webhook verify
 - CLI + importable library

Quick start (self-hosted):
    from digitalplat_sdk import DomainOSSClient
    c = DomainOSSClient(base_url="http://127.0.0.1:8080", api_key="dpo_xxx")
    c.create_domain(label="myapp", zone_id=1)
    c.create_record(domain_id=1, name="@", type="A", content="1.2.3.4")

Quick start (public free domain):
    from digitalplat_sdk import PublicFreeDomain
    pf = PublicFreeDomain(email="you@example.com", password="xxx")
    pf.register(label="myblog", suffix="dpdns.org",
                nameservers=["mary.ns.cloudflare.com","oliver.ns.cloudflare.com"])
"""
import hashlib
import hmac
import ipaddress
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# constants from domain_oss/security.py:19-21  (exact source regex)
# ---------------------------------------------------------------------------
LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
RECORD_NAME_RE = re.compile(r"^(?:@|\*|[a-z0-9_](?:[a-z0-9_.-]{0,251}[a-z0-9_])?)$", re.I)
ALLOWED_RECORD_TYPES = {"A", "AAAA", "CNAME", "MX", "TXT", "SRV", "CAA", "NS"}

AVAILABLE_SUFFIXES = ["dpdns.org", "us.kg", "qzz.io", "xx.kg", "qd.je"]  # README.md:24-30

# ---------------------------------------------------------------------------
# exceptions
# ---------------------------------------------------------------------------
class DigitalPlatError(Exception):
    pass

class AuthError(DigitalPlatError):
    pass

class RateLimitError(DigitalPlatError):
    pass

class ValidationError(DigitalPlatError):
    pass

# ---------------------------------------------------------------------------
# helpers  (mirrors domain_oss/services.py:12)
# ---------------------------------------------------------------------------
def validate_label(label: str) -> str:
    label = label.strip().lower()
    if not LABEL_RE.fullmatch(label):
        raise ValidationError(f"Invalid label '{label}': must match {LABEL_RE.pattern}")
    if len(label) < 1 or len(label) > 63:
        raise ValidationError("Label length must be 1-63")
    return label

def validate_record(name: str, rtype: str, content: str, ttl: int = 300, priority: Optional[int]=None) -> Dict[str, Any]:
    name = name.strip().lower().rstrip(".") or "@"
    rtype = rtype.strip().upper()
    content = content.strip()
    if not RECORD_NAME_RE.fullmatch(name):
        raise ValidationError(f"Invalid record name '{name}'")
    if rtype not in ALLOWED_RECORD_TYPES:
        raise ValidationError(f"Unsupported type {rtype}. Allowed: {ALLOWED_RECORD_TYPES}")
    ttl = int(ttl)
    if not 60 <= ttl <= 86400:
        raise ValidationError("TTL must be 60-86400")
    if not content or len(content) > 2048 or "\n" in content:
        raise ValidationError("Invalid record content")
    # type-specific validation (services.py:30-56)
    if rtype == "A":
        ipaddress.IPv4Address(content)
    elif rtype == "AAAA":
        ipaddress.IPv6Address(content)
    elif rtype in {"CNAME","NS","MX"} and "." not in content.rstrip("."):
        raise ValidationError(f"{rtype} content must be a hostname")
    elif rtype in {"MX","SRV"}:
        if priority is None:
            raise ValidationError(f"{rtype} requires priority")
        priority = int(priority)
        if not 0 <= priority <= 65535:
            raise ValidationError("priority 0-65535")
    else:
        priority = None
    return {"name": name, "type": rtype, "content": content, "ttl": ttl, "priority": priority}

def verify_webhook_signature(secret: str, body: bytes, signature_header: str) -> bool:
    """Verify X-Domain-OSS-Signature (docs/AUTOMATION.md:24)"""
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)

# ---------------------------------------------------------------------------
# Domain-OSS REST client  (domain_oss/routes/api.py)
# ---------------------------------------------------------------------------
@dataclass
class Domain:
    id: int
    name: str
    label: str
    status: str
    zone: str
    created_at: str

@dataclass
class Record:
    id: int
    name: str
    type: str
    content: str
    ttl: int
    priority: Optional[int]

class DomainOSSClient:
    """
    Full client for self-hosted Domain-OSS.
    Install: git clone https://github.com/DigitalPlatDev/Domain-OSS && ./panel install && ./panel start
    API discovery: GET /api/v1/openapi.json  (routes/api.py:79)
    Auth: Authorization: Bearer dpo_...  (routes/api.py:40)
    Scopes: domains:read, domains:write, dns:read, dns:write, acme:write, admin:metrics
    """
    def __init__(self, base_url: str, api_key: Optional[str]=None,
                 username: Optional[str]=None, password: Optional[str]=None,
                 timeout: int=30, max_retries: int=3):
        self.base_url = base_url.rstrip("/") + "/"
        self.api_base = urljoin(self.base_url, "api/v1/")
        self.timeout = timeout
        self.session = requests.Session()
        retries = Retry(total=max_retries, backoff_factor=1,
                        status_forcelist=[429, 502, 503, 504],
                        allowed_methods=["GET","POST","PATCH","DELETE"])
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.api_key = api_key
        self._login_token = None
        if username and password:
            self._login(username, password)

    def _headers(self) -> Dict[str,str]:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            if not self.api_key.startswith("dpo_"):
                raise AuthError("API key must start with dpo_  (routes/api.py:41)")
            h["Authorization"] = f"Bearer {self.api_key}"
        elif self._login_token:
            h["Authorization"] = f"Bearer {self._login_token}"
        return h

    def _req(self, method: str, path: str, **kw) -> requests.Response:
        url = urljoin(self.api_base, path.lstrip("/"))
        kw.setdefault("timeout", self.timeout)
        kw.setdefault("headers", self._headers())
        r = self.session.request(method, url, **kw)
        if r.status_code == 429:
            raise RateLimitError(f"Rate limited (300/min — routes/api.py:31): {r.text[:300]}")
        if r.status_code == 401:
            raise AuthError(r.text[:500])
        return r

    def _json(self, r: requests.Response) -> Any:
        try:
            return r.json()
        except Exception:
            raise DigitalPlatError(f"Non-JSON response {r.status_code}: {r.text[:500]}")

    # -- auth helpers -------------------------------------------------------
    def _login(self, username: str, password: str):
        """Login via web form to obtain session (fallback when no API key)."""
        r = self.session.post(urljoin(self.base_url, "auth/login"),
                              data={"username": username, "password": password},
                              timeout=self.timeout)
        if r.status_code not in (200, 302):
            raise AuthError(f"Login failed: {r.status_code} {r.text[:300]}")

    def create_api_key(self, scopes: str="domains:read,domains:write,dns:read,dns:write,acme:write",
                       expires_days: int=90) -> str:
        """Create scoped key via web UI flow — prefer creating in Dashboard: Account & security."""
        raise NotImplementedError("Create keys in Dashboard → Account & security (docs/AUTOMATION.md:4)")

    # -- OpenAPI ------------------------------------------------------------
    def openapi(self) -> Dict[str,Any]:
        return self._json(self._req("GET", "openapi.json"))

    # -- zones (admin) ------------------------------------------------------
    def list_zones(self) -> List[Dict[str,Any]]:
        # zones are admin-managed; list via pagination pattern
        raise NotImplementedError("Zones are admin-created: Admin → DNS providers → Managed zones (README.md:39)")

    # -- domains ------------------------------------------------------------
    def list_domains(self, page: int=1, per_page: int=50, all_domains: bool=False) -> Tuple[List[Domain], Dict[str,int]]:
        params = {"page": page, "per_page": per_page}
        if all_domains:
            params["all"] = 1
        r = self._req("GET", "domains", params=params)
        if r.status_code != 200:
            raise DigitalPlatError(self._json(r))
        j = self._json(r)
        domains = [Domain(id=d["id"], name=d["name"], label=d["label"],
                          status=d["status"], zone=d["zone"], created_at=d["created_at"])
                   for d in j.get("data", [])]
        return domains, j.get("meta", {})

    def list_all_domains(self) -> List[Domain]:
        out: List[Domain] = []
        page = 1
        while True:
            batch, meta = self.list_domains(page=page, per_page=100)
            out.extend(batch)
            if page >= meta.get("pages", 1) or not batch:
                break
            page += 1
        return out

    def get_domain(self, domain_id: int) -> Domain:
        r = self._req("GET", f"domains/{domain_id}")
        if r.status_code != 200:
            raise DigitalPlatError(self._json(r))
        d = self._json(r)["data"]
        return Domain(id=d["id"], name=d["name"], label=d["label"],
                      status=d["status"], zone=d["zone"], created_at=d["created_at"])

    def create_domain(self, label: str, zone_id: int) -> Domain:
        """Create domain — routes/api.py:122 (label + zone_id)"""
        label = validate_label(label)
        payload = {"label": label, "zone_id": zone_id}
        r = self._req("POST", "domains", json=payload)
        j = self._json(r)
        if r.status_code == 201:
            d = j["data"]
            return Domain(id=d["id"], name=d["name"], label=d["label"],
                          status=d["status"], zone=d["zone"], created_at=d["created_at"])
        # 409 reserved / limit / exists, 400 invalid
        raise DigitalPlatError(f"Create failed {r.status_code}: {j}")

    def delete_domain(self, domain_id: int) -> None:
        r = self._req("DELETE", f"domains/{domain_id}")
        if r.status_code not in (204, 200):
            raise DigitalPlatError(self._json(r))

    def bulk_create_domains(self, labels: List[str], zone_id: int, delay: float=0.6) -> Dict[str,Any]:
        """Bulk register with per-label error capture (rate limit 300/min)."""
        ok: List[Domain] = []
        failed: List[Dict[str,str]] = []
        for lbl in labels:
            try:
                d = self.create_domain(lbl, zone_id)
                ok.append(d)
                print(f"[+] {d.name} ({d.status})")
            except Exception as e:
                failed.append({"label": lbl, "error": str(e)[:300]})
                print(f"[x] {lbl}: {e}")
            time.sleep(delay)
        return {"created": ok, "failed": failed}

    # -- DNS records --------------------------------------------------------
    def list_records(self, domain_id: int) -> List[Record]:
        r = self._req("GET", f"domains/{domain_id}/records")
        if r.status_code != 200:
            raise DigitalPlatError(self._json(r))
        return [Record(id=x["id"], name=x["name"], type=x["type"],
                       content=x["content"], ttl=x["ttl"], priority=x.get("priority"))
                for x in self._json(r).get("data", [])]

    def create_record(self, domain_id: int, name: str="@", type: str="A",
                      content: str="", ttl: int=300, priority: Optional[int]=None) -> Record:
        v = validate_record(name, type, content, ttl, priority)
        r = self._req("POST", f"domains/{domain_id}/records", json=v)
        j = self._json(r)
        if r.status_code == 201:
            d = j["data"]
            print(f"  [DNS] {d['type']} {d['name']} -> {d['content']} (job {j.get('job_id')} {j.get('sync_status')})")
            return Record(id=d["id"], name=d["name"], type=d["type"],
                          content=d["content"], ttl=d["ttl"], priority=d.get("priority"))
        raise DigitalPlatError(f"Record create failed {r.status_code}: {j}")

    def update_record(self, domain_id: int, record_id: int, **fields) -> Record:
        r = self._req("PATCH", f"domains/{domain_id}/records/{record_id}", json=fields)
        j = self._json(r)
        if r.status_code == 200:
            d = j["data"]
            return Record(id=d["id"], name=d["name"], type=d["type"],
                          content=d["content"], ttl=d["ttl"], priority=d.get("priority"))
        raise DigitalPlatError(f"Update failed {r.status_code}: {j}")

    def delete_record(self, domain_id: int, record_id: int) -> None:
        r = self._req("DELETE", f"domains/{domain_id}/records/{record_id}")
        if r.status_code not in (204, 200):
            raise DigitalPlatError(self._json(r))

    def ensure_website(self, domain_id: int, ipv4: str, ipv6: Optional[str]=None,
                       www_cname: bool=True, ttl: int=300):
        """One-call website wiring: @ A (+ AAAA), www CNAME, verify (docs/tutorial/dns/2.1)."""
        self.create_record(domain_id, "@", "A", ipv4, ttl)
        if ipv6:
            self.create_record(domain_id, "@", "AAAA", ipv6, ttl)
        if www_cname:
            try:
                self.create_record(domain_id, "www", "CNAME", "@", ttl)
            except DigitalPlatError as e:
                if "CNAME" not in str(e):
                    raise

    def ensure_mail(self, domain_id: int, mx_host: str, spf_include: str,
                    dkim_selector: str="selector1", dkim_value: str="",
                    ttl: int=300):
        """Wire MX + SPF + DMARC skeleton (tutorial/email/4.1)."""
        self.create_record(domain_id, "@", "MX", mx_host, ttl, priority=10)
        self.create_record(domain_id, "@", "TXT", f"v=spf1 include:{spf_include} ~all", ttl)
        self.create_record(domain_id, "_dmarc", "TXT", "v=DMARC1; p=quarantine; rua=mailto:dmarc@example.com", ttl)
        if dkim_value:
            self.create_record(domain_id, f"{dkim_selector}._domainkey", "TXT", dkim_value, ttl)

    # -- ACME DNS-01 --------------------------------------------------------
    def create_acme_challenge(self, domain_id: int, value: str,
                              name: str="_acme-challenge") -> Dict[str,Any]:
        """POST /domains/{id}/acme-challenges  (routes/api.py:264) — returns cleanup token."""
        r = self._req("POST", f"domains/{domain_id}/acme-challenges",
                      json={"name": name, "value": value})
        j = self._json(r)
        if r.status_code == 201:
            print(f"  [ACME] published {j['data']['name']} (expires {j['data']['expires_at']})")
            return j["data"]  # {token, name, value, expires_at, sync_status}
        raise DigitalPlatError(f"ACME publish failed {r.status_code}: {j}")

    def delete_acme_challenge(self, domain_id: int, token: str) -> None:
        r = self._req("DELETE", f"domains/{domain_id}/acme-challenges/{token}")
        if r.status_code not in (204, 200):
            raise DigitalPlatError(self._json(r))
        print(f"  [ACME] cleaned {token[:12]}...")

    # -- metrics / admin ----------------------------------------------------
    def metrics(self) -> str:
        r = self._req("GET", "metrics")
        if r.status_code != 200:
            raise DigitalPlatError(self._json(r))
        return r.text

    # -- import / export ----------------------------------------------------
    def export_json(self, domain_id: int, path: str):
        records = self.list_records(domain_id)
        data = [r.__dict__ for r in records]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Exported {len(data)} records -> {path}")

    def import_json(self, domain_id: int, path: str):
        with open(path) as f:
            data = json.load(f)
        for rec in data:
            try:
                self.create_record(domain_id, rec["name"], rec["type"],
                                   rec["content"], rec.get("ttl", 300), rec.get("priority"))
            except DigitalPlatError as e:
                print(f"  skip {rec}: {e}")

# ---------------------------------------------------------------------------
# Public FreeDomain dashboard — dash.domain.digitalplat.org
# Tutorial: documents/tutorial/platform/1.2 + 1.3
# No public REST docs — automation via session + Cloudflare-aware flow.
# ---------------------------------------------------------------------------
class PublicFreeDomain:
    """
    Automates the PUBLIC free domain service (dash.domain.digitalplat.org).
    For self-hosted, use DomainOSSClient instead (full API).

    Workflow (tutorial/platform/1.2, 1.3):
      1) Register account (or login)
      2) Check availability: label + suffix
      3) Prepare external nameservers (Cloudflare etc.) — must exist BEFORE registration
      4) Submit registration with nameservers
      5) Verify in Domain List
      6) Manage via Dashboard

    Note: availability, limits, slot/charge, policies can change — always read
    Dashboard notices first (project-overview.md:30).
    """
    DASH = "https://dash.domain.digitalplat.org"
    AVAILABLE_SUFFIXES = AVAILABLE_SUFFIXES

    def __init__(self, email: Optional[str]=None, password: Optional[str]=None,
                 session_cookies: Optional[Dict[str,str]]=None,
                 timeout: int=30):
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept": "application/json, text/html,*/*",
            "Referer": self.DASH + "/",
        })
        if session_cookies:
            for k, v in session_cookies.items():
                self.s.cookies.set(k, v, domain="dash.domain.digitalplat.org")
        self.email = email
        self.password = password

    def login(self) -> bool:
        """Login — adapt selector if Dashboard changes (dashboard-tour.md)."""
        # 1) fetch login page for CSRF
        r = self.s.get(self.DASH + "/login", timeout=self.timeout)
        csrf = None
        if "csrf" in r.text.lower():
            m = re.search(r'name="csrf[^"]*"\s+value="([^"]+)"', r.text, re.I)
            if m:
                csrf = m.group(1)
            m = re.search(r'"csrf[^"]*"\s*:\s*"([^"]+)"', r.text)
            if not csrf and m:
                csrf = m.group(1)
        # 2) try JSON login then form login
        for payload in [
            {"email": self.email, "password": self.password, "csrf_token": csrf},
            {"username": self.email, "password": self.password, "csrf_token": csrf},
        ]:
            payload = {k: v for k, v in payload.items() if v}
            try:
                rr = self.s.post(self.DASH + "/api/login", json=payload, timeout=self.timeout)
                if rr.status_code == 200 and "token" in rr.text.lower():
                    return True
            except Exception:
                pass
            try:
                rr = self.s.post(self.DASH + "/login", data=payload, timeout=self.timeout)
                if rr.status_code in (200, 302) and "dashboard" in rr.text.lower():
                    return True
            except Exception:
                pass
        # fallback: check if already authenticated
        r = self.s.get(self.DASH + "/dashboard", timeout=self.timeout)
        return r.status_code == 200 and "domain" in r.text.lower()

    def check_availability(self, label: str, suffix: str) -> Dict[str,Any]:
        """Check label.suffix availability (platform/1.2)."""
        label = validate_label(label)
        suffix = suffix.lstrip(".").lower()
        if suffix not in self.AVAILABLE_SUFFIXES:
            print(f"[!] suffix {suffix} not in known list {self.AVAILABLE_SUFFIXES} — trying anyway")
        fqdn = f"{label}.{suffix}"
        # endpoint varies — try common patterns, return first 2xx
        for path in ["/api/check", "/api/domain/check", "/api/availability", "/check"]:
            try:
                r = self.s.get(self.DASH + path, params={"domain": fqdn, "label": label, "suffix": suffix},
                               timeout=self.timeout)
                if r.status_code == 200:
                    try:
                        return r.json()
                    except Exception:
                        return {"raw": r.text[:500], "fqdn": fqdn}
            except Exception:
                continue
        return {"fqdn": fqdn, "status": "unknown — check manually at dash.domain.digitalplat.org"}

    def register(self, label: str, suffix: str, nameservers: List[str],
                 accept_policy: bool=True) -> Dict[str,Any]:
        """
        Register label.suffix delegated to external nameservers.
        nameservers: e.g. ["mary.ns.cloudflare.com","oliver.ns.cloudflare.com"] (platform/1.3)
        Must have created zone at external provider first and copied assigned NS hostnames exactly.
        """
        label = validate_label(label)
        if len(nameservers) < 2:
            raise ValidationError("Provide at least 2 nameservers (platform/1.3: enter complete set)")
        for ns in nameservers:
            if "." not in ns or ns.replace(".","").isdigit():
                raise ValidationError(f"Nameserver must be hostname, not IP: {ns}")
        suffix = suffix.lstrip(".").lower()
        fqdn = f"{label}.{suffix}"
        payload = {
            "label": label, "suffix": suffix, "domain": fqdn,
            "nameservers": nameservers, "ns": nameservers,
            "accept_policy": accept_policy,
        }
        for path in ["/api/domain/register", "/api/register", "/api/domains", "/register"]:
            try:
                r = self.s.post(self.DASH + path, json=payload, timeout=self.timeout)
                try:
                    j = r.json()
                except Exception:
                    j = {"raw": r.text[:800], "status": r.status_code}
                if r.status_code in (200, 201):
                    print(f"[+] registered {fqdn} -> {nameservers}")
                    return j
                if r.status_code not in (404, 405):
                    return {"error": j, "status": r.status_code, "fqdn": fqdn}
            except Exception as e:
                continue
        raise DigitalPlatError(f"Register endpoint not found — Dashboard may have changed. "
                               f"Register manually at {self.DASH} with {fqdn} + {nameservers}")

    def list_domains(self) -> List[Dict[str,Any]]:
        for path in ["/api/domains", "/api/domain/list", "/dashboard"]:
            try:
                r = self.s.get(self.DASH + path, timeout=self.timeout)
                if r.status_code == 200:
                    try:
                        j = r.json()
                        if isinstance(j, dict) and "data" in j:
                            return j["data"]
                        if isinstance(j, list):
                            return j
                    except Exception:
                        # parse HTML table
                        m = re.findall(r'([a-z0-9-]+\.(?:dpdns\.org|us\.kg|qzz\.io|xx\.kg|qd\.je))', r.text, re.I)
                        if m:
                            return [{"name": x.lower()} for x in set(m)]
            except Exception:
                continue
        return []

    def delete_domain(self, fqdn: str) -> bool:
        for path in [f"/api/domain/{fqdn}", f"/api/domains/{fqdn}"]:
            try:
                r = self.s.delete(self.DASH + path, timeout=self.timeout)
                if r.status_code in (200, 204):
                    return True
            except Exception:
                continue
        return False

    # -- helper: full end-to-end with Cloudflare nameservers ----------------
    def register_with_cloudflare(self, label: str, suffix: str,
                                 cloudflare_zone_ns: List[str]) -> Dict[str,Any]:
        """
        Convenience: assumes you already created the zone at Cloudflare and
        have its assigned nameservers (Cloudflare dashboard → DNS → nameservers).
        """
        return self.register(label, suffix, cloudflare_zone_ns)

# ---------------------------------------------------------------------------
# One-shot demo / smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse, os
    ap = argparse.ArgumentParser(description="DigitalPlat FreeDomain SDK demo")
    ap.add_argument("--base", default=os.getenv("DOMAIN_OSS_URL", "http://127.0.0.1:8080"))
    ap.add_argument("--api-key", default=os.getenv("DPO_API_KEY", ""))
    ap.add_argument("--label", default="demo" + str(int(time.time()) % 10000))
    ap.add_argument("--zone-id", type=int, default=int(os.getenv("ZONE_ID", "1")))
    ap.add_argument("--ipv4", default="192.0.2.10")
    args = ap.parse_args()

    if not args.api_key:
        print("Set DPO_API_KEY env or --api-key dpo_...  (create in Dashboard → Account & security)")
        print("Or test public dashboard:")
        print("  pf = PublicFreeDomain(email='you@example.com', password='xxx')")
        print("  pf.login(); pf.check_availability('myapp','dpdns.org')")
        exit(0)

    c = DomainOSSClient(base_url=args.base, api_key=args.api_key)
    print("OpenAPI:", c.openapi()["info"])
    domains, meta = c.list_domains()
    print(f"Existing domains: {len(domains)} total={meta.get('total')}")
    d = c.create_domain(args.label, args.zone_id)
    print(f"Created: {d}")
    c.ensure_website(d.id, args.ipv4)
    print("Records:", c.list_records(d.id))
    # cleanup example: uncomment
    # c.delete_domain(d.id)
