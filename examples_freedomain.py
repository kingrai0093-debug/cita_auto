#!/usr/bin/env python3
"""
examples_freedomain.py — 7 powerful examples using DigitalPlat FreeDomain SDK
Each example is self-contained. Run: python3 examples_freedomain.py <1..7>
"""
import os, time

# 1. Bulk create 20 domains + wire DNS + verify propagation
def ex1_bulk():
    from digitalplat_sdk import DomainOSSClient
    c = DomainOSSClient("http://127.0.0.1:8080", api_key=os.getenv("DPO_API_KEY"))
    labels = [f"shop{i:02d}" for i in range(20)]
    res = c.bulk_create_domains(labels, zone_id=1)
    for d in res["created"]:
        c.ensure_website(d.id, "203.0.113.10")   # A + www CNAME
        c.create_record(d.id, "api", "A", "203.0.113.11", ttl=300)

# 2. Wildcard + CAA + TXT verification (LETSENCRYPT)
def ex2_security():
    from digitalplat_sdk import DomainOSSClient
    c = DomainOSSClient("http://127.0.0.1:8080", api_key=os.getenv("DPO_API_KEY"))
    d = c.create_domain("secure", zone_id=1)
    c.create_record(d.id, "*", "A", "203.0.113.20")  # wildcard (if zone.allow_wildcard)
    c.create_record(d.id, "@", "CAA", '0 issue "letsencrypt.org"')
    c.create_record(d.id, "@", "TXT", "google-site-verification=abc123")

# 3. Email stack: MX + SPF + DKIM + DMARC (tutorial/email/4.1)
def ex3_email():
    from digitalplat_sdk import DomainOSSClient
    c = DomainOSSClient("http://127.0.0.1:8080", api_key=os.getenv("DPO_API_KEY"))
    d = c.create_domain("mailtest", zone_id=1)
    c.ensure_mail(d.id, mx_host="mail.example.com.", spf_include="mail.example.com",
                  dkim_value="v=DKIM1; k=rsa; p=MIIB...")

# 4. ACME DNS-01 fully automated (certbot hook replacement)
def ex4_acme():
    from digitalplat_sdk import DomainOSSClient
    import subprocess
    c = DomainOSSClient("http://127.0.0.1:8080", api_key=os.getenv("DPO_API_KEY"))
    # certbot passes CERTBOT_VALIDATION to hook
    value = os.getenv("CERTBOT_VALIDATION", "dummy-acme-value")
    domain_id = int(os.getenv("DOMAIN_ID", "1"))
    data = c.create_acme_challenge(domain_id, value)
    # wait for propagation
    time.sleep(15)
    subprocess.run(["dig", "TXT", data["name"]], check=False)
    # after certbot validates, cleanup:
    # c.delete_acme_challenge(domain_id, data["token"])

# 5. Terraform-style infra as code (JSON import/export)
def ex5_infra_as_code():
    from digitalplat_sdk import DomainOSSClient
    c = DomainOSSClient("http://127.0.0.1:8080", api_key=os.getenv("DPO_API_KEY"))
    d = c.create_domain("iac", zone_id=1)
    c.import_json(d.id, "./infra.records.json")  # versioned DNS state
    c.export_json(d.id, "./iac.snapshot.json")

# 6. Public free domain (dash.domain.digitalplat.org) — free forever
def ex6_public():
    from digitalplat_sdk import PublicFreeDomain
    pf = PublicFreeDomain(email=os.getenv("DP_EMAIL"), password=os.getenv("DP_PASSWORD"))
    assert pf.login(), "login failed"
    # Must create Cloudflare zone first, copy its NS
    ns = ["mary.ns.cloudflare.com", "oliver.ns.cloudflare.com"]
    pf.register("myawesomeblog", "dpdns.org", ns)
    pf.register("myawesomeblog", "us.kg", ns)  # same label, different suffix
    print(pf.list_domains())

# 7. Monitoring + webhook HMAC verify (docs/AUTOMATION.md:24)
def ex7_ops():
    from digitalplat_sdk import DomainOSSClient, verify_webhook_signature
    import hmac, hashlib
    c = DomainOSSClient("http://127.0.0.1:8080", api_key=os.getenv("DPO_API_KEY"))
    print(c.metrics())  # needs admin:metrics scope
    # webhook verify example
    secret = "whsec_xxx"
    body = b'{"event":"domain.created","domain":"test.dpdns.org"}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(secret, body, sig)

if __name__ == "__main__":
    import sys
    n = sys.argv[1] if len(sys.argv) > 1 else "1"
    fn = {"1": ex1_bulk, "2": ex2_security, "3": ex3_email, "4": ex4_acme,
          "5": ex5_infra_as_code, "6": ex6_public, "7": ex7_ops}[n]
    fn()
