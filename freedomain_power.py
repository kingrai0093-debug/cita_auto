#!/usr/bin/env python3
"""
freedomain_power.py — Full-power automation: bulk register + DNS + website + TLS
Uses DigitalPlat FreeDomain public service AND self-hosted Domain-OSS.

Covers entire tutorial path (LEARN.md):
  Category A: registration, delegation, renewal
  Category B: DNS, website, email, operations, advanced

Usage:
  # 1) Self-hosted (FULL API control — recommended for power users)
  DOMAIN_OSS_URL=http://127.0.0.1:8080 DPO_API_KEY=dpo_xxx ZONE_ID=1 python3 freedomain_power.py --self-hosted --labels app1,app2 --ipv4 1.2.3.4

  # 2) Public free domains (dash.domain.digitalplat.org)
  python3 freedomain_power.py --public --email you@example.com --password xxx --labels myblog,myshop --suffix dpdns.org --ns mary.ns.cloudflare.com,oliver.ns.cloudflare.com

  # 3) Full stack: domain + DNS + verify + ACME
  python3 freedomain_power.py --self-hosted --acme --domain-id 1 --acme-value "challenge-token"

See: digitalplat_sdk.py for library API.
"""
import argparse, json, os, sys, time, subprocess
from typing import List

try:
    from digitalplat_sdk import DomainOSSClient, PublicFreeDomain, validate_label, ALLOWED_RECORD_TYPES
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from digitalplat_sdk import DomainOSSClient, PublicFreeDomain, validate_label, ALLOWED_RECORD_TYPES


def run_self_hosted(args):
    c = DomainOSSClient(base_url=args.base, api_key=args.api_key)
    print(f"[=] Connected to {args.base}")
    print(f"[=] OpenAPI {c.openapi()['info']}")

    domains, meta = c.list_domains()
    print(f"[=] Existing: {len(domains)}/{meta.get('total', '?')} domains")

    # bulk create
    labels = [s.strip() for s in args.labels.split(",") if s.strip()]
    result = c.bulk_create_domains(labels, zone_id=args.zone_id, delay=args.delay)
    created = result["created"]

    # wire DNS for each created domain
    for d in created:
        print(f"\n[DNS] Wiring {d.name} (id={d.id})")
        try:
            if args.ipv4:
                c.ensure_website(d.id, ipv4=args.ipv4, ipv6=args.ipv6, ttl=args.ttl)
            # optional extra records
            if args.cname_target:
                c.create_record(d.id, "app", "CNAME", args.cname_target, args.ttl)
            if args.txt_value:
                c.create_record(d.id, "@", "TXT", args.txt_value, args.ttl)
            # verify via dig (tutorial/advanced/6.3)
            try:
                out = subprocess.run(["dig", "+short", "A", d.name], capture_output=True, text=True, timeout=10)
                print(f"  dig A {d.name} -> {out.stdout.strip() or '(pending propagation)'}")
            except Exception:
                pass
            # export
            c.export_json(d.id, f"./{d.label}.records.json")
        except Exception as e:
            print(f"  [!] DNS wiring failed for {d.name}: {e}")

    # ACME demo
    if args.acme and args.acme_value and created:
        target = created[0]
        if args.domain_id:
            target_id = args.domain_id
        else:
            target_id = target.id
        print(f"\n[ACME] Publishing challenge on domain {target_id}")
        data = c.create_acme_challenge(target_id, args.acme_value)
        print(f"  token={data['token'][:16]}...  name={data['name']}")
        print(f"  Validate: dig TXT {data['name']}")
        if args.acme_cleanup:
            time.sleep(5)
            c.delete_acme_challenge(target_id, data["token"])
            print("  cleaned up")

    # summary
    print("\n" + "="*60)
    print(f"Created {len(result['created'])} domains, {len(result['failed'])} failed")
    for f in result["failed"]:
        print(f"  x {f['label']}: {f['error'][:120]}")
    all_domains = c.list_all_domains()
    print(f"Total now: {len(all_domains)}")
    for d in all_domains[-10:]:
        print(f"  - {d.name} [{d.status}] zone={d.zone}")

    # metrics (admin)
    if args.metrics:
        try:
            print("\n[METRICS]\n" + c.metrics())
        except Exception as e:
            print(f"metrics failed (need admin:metrics scope): {e}")


def run_public(args):
    pf = PublicFreeDomain(email=args.email, password=args.password)
    print(f"[=] Public FreeDomain → {pf.DASH}")
    if args.email and args.password:
        ok = pf.login()
        print(f"[=] Login {'OK' if ok else 'FAILED — check credentials / Cloudflare'}")
        if not ok:
            print("  Hint: if Cloudflare blocks, run with browser automation or create session_cookies")
    labels = [s.strip() for s in args.labels.split(",") if s.strip()]
    ns = [s.strip() for s in args.ns.split(",") if s.strip()] if args.ns else []
    for label in labels:
        print(f"\n[CHECK] {label}.{args.suffix}")
        avail = pf.check_availability(label, args.suffix)
        print(f"  availability: {json.dumps(avail)[:400]}")
        if ns:
            print(f"[REGISTER] {label}.{args.suffix} -> {ns}")
            try:
                res = pf.register(label, args.suffix, ns)
                print(f"  result: {json.dumps(res)[:600]}")
            except Exception as e:
                print(f"  [!] {e}")
        # dig verify (tutorial/platform/1.3)
        fqdn = f"{label}.{args.suffix}"
        try:
            out = subprocess.run(["dig", "NS", fqdn, "+short"], capture_output=True, text=True, timeout=10)
            print(f"  dig NS {fqdn} -> {out.stdout.strip() or '(delegation pending)'}")
        except Exception:
            pass
    print("\n[LIST] domains in account:")
    for d in pf.list_domains()[:20]:
        print(f"  - {d}")


def main():
    ap = argparse.ArgumentParser(description="DigitalPlat FreeDomain — full power automation")
    ap.add_argument("--self-hosted", action="store_true", help="use self-hosted Domain-OSS REST API")
    ap.add_argument("--public", action="store_true", help="use public dash.domain.digitalplat.org")
    ap.add_argument("--base", default=os.getenv("DOMAIN_OSS_URL", "http://127.0.0.1:8080"))
    ap.add_argument("--api-key", default=os.getenv("DPO_API_KEY", ""))
    ap.add_argument("--zone-id", type=int, default=int(os.getenv("ZONE_ID", "1")))
    ap.add_argument("--labels", default="demo" + str(int(time.time()) % 10000),
                    help="comma-separated labels (e.g. app1,app2,blog)")
    ap.add_argument("--suffix", default="dpdns.org", help="public suffix (dpdns.org, us.kg, qzz.io, xx.kg, qd.je)")
    ap.add_argument("--ns", default="", help="comma-separated nameservers for public registration")
    ap.add_argument("--email", default=os.getenv("DP_EMAIL", ""), help="public dashboard email")
    ap.add_argument("--password", default=os.getenv("DP_PASSWORD", ""), help="public dashboard password")
    ap.add_argument("--ipv4", default="192.0.2.10", help="A record target for website")
    ap.add_argument("--ipv6", default="", help="optional AAAA")
    ap.add_argument("--ttl", type=int, default=300)
    ap.add_argument("--cname-target", default="", help="extra CNAME target e.g. app.example.com")
    ap.add_argument("--txt-value", default="", help="extra TXT value")
    ap.add_argument("--delay", type=float, default=0.6, help="delay between bulk creates (s)")
    ap.add_argument("--acme", action="store_true", help="demo ACME DNS-01 publish/cleanup")
    ap.add_argument("--acme-value", default="", help="ACME challenge value")
    ap.add_argument("--acme-cleanup", action="store_true", help="auto cleanup ACME challenge after publish")
    ap.add_argument("--domain-id", type=int, default=0, help="domain id for ACME (else first created)")
    ap.add_argument("--metrics", action="store_true", help="fetch /api/v1/metrics (admin:metrics)")
    args = ap.parse_args()

    if args.self_hosted:
        if not args.api_key:
            ap.error("--self-hosted requires DPO_API_KEY (create in Dashboard → Account & security)")
        run_self_hosted(args)
    elif args.public:
        run_public(args)
    else:
        # auto-detect: prefer self-hosted if key present
        if args.api_key:
            run_self_hosted(args)
        else:
            print("No --self-hosted/--public specified and no DPO_API_KEY — defaulting to --public demo")
            run_public(args)


if __name__ == "__main__":
    main()
