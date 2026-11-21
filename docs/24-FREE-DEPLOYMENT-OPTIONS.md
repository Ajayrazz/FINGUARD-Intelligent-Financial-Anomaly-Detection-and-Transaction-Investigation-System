# 24 · Free Deployment Options for Testing and Presentation

**Date:** 2026-11-21 · **Status:** Options analysed and a recommendation made; **nothing has been deployed yet** (the Cloudflare Tunnel setup awaits the user's go-ahead).

This note records why the production stack in [doc 14](14-DEPLOYMENT-GUIDE.md) was not put on a paid server for the first external test, which free platforms were considered, and how to run the chosen option. It answers decision **D-015** (hosting target) for the testing/presentation case only.

## 1. Context

* Purpose: a **presentation and test** with about **5 people** who register, sign in and look around. Not a production service.
* The user wants **no cost**.
* The application is not a simple web app. It needs: Django + Daphne (HTTP and WebSockets), a Celery worker and beat, Redis, PostgreSQL, optional Neo4j, and ML libraries (torch, scikit-learn, SHAP). A realistic minimum is **about 4 GB RAM**.
* Login uses a refresh token in an `httpOnly; Secure; SameSite=Strict` cookie, so the **frontend and API must be served from the same site**.
* Self-service signup sends email (confirmation link, approval notice). Links point to `FRONTEND_BASE_URL`, so that value must be the public address testers use.

## 2. Options compared

| Option | Cost | Runs the full stack? | Verdict |
|---|---|---|---|
| **Cloudflare Tunnel from the developer's machine** | Free (no account needed for a quick tunnel) | **Yes**, it is the stack already tested, with its data | **Chosen for the demo** |
| Oracle Cloud "Always Free" VM (ARM, up to 4 cores, 24 GB) | Free; a card is needed for identity verification | Yes, the Compose stack runs unchanged (the image was rehearsed on arm64) | Best free choice if the app must stay up while the laptop is off |
| Railway | One-off trial credit (about $5), then paid | Barely; four or more services and heavy ML memory exhaust the credit quickly | Not free |
| Vercel / Netlify | Free | **No.** Frontend and serverless functions only: no Celery, Redis, WebSockets or long-running Django. Splitting the frontend off also breaks the `SameSite=Strict` cookie (a cross-site setup would be an architecture change) | Not suitable |
| Render / Koyeb free tiers | Free | **No.** About 512 MB RAM, services sleep when idle, no background worker, image too large for the limit | Not suitable |
| AWS / GCP free tier (1 GB VM) | Free for a limited time | **No.** Too small to build or run the stack | Not suitable |
| Paid single VPS (Hetzner, DigitalOcean, Lightsail), roughly $12-25 per month | Paid | Yes (the documented production path in doc 14) | Best for real users, not needed for this demo |

## 3. Recommendation

1. **Presentation with about 5 testers:** Cloudflare Tunnel from the developer's machine. Free, no new build, real HTTPS, one shareable link, ready in about 10 minutes.
2. **Must stay online while the laptop is off:** Oracle Cloud Always Free VM running `docker-compose.prod.yml` (steps in section 5).
3. **Real users later:** a paid VPS with a real domain and a proper mail service (doc 14).

## 4. Option A: Cloudflare Tunnel (chosen)

Prerequisites: the development stack running (`docker compose up -d`, frontend on port 5173 or the production stack on 8443), and the machine staying on and awake during the demo.

1. Install the client: `brew install cloudflared`.
2. Start a quick tunnel to the frontend: `cloudflared tunnel --url http://localhost:5173`. It prints a public `https://<random>.trycloudflare.com` address.
3. Set `FRONTEND_BASE_URL` in `.env` to that address and recreate the backend and worker so account emails link to it: `docker compose up -d --force-recreate backend worker`.
4. Add the tunnel host to `DJANGO_ALLOWED_HOSTS` and `CORS`/`CSRF` trusted origins if the backend rejects it (the dev proxy normally forwards `/api` from the frontend, so this is usually not needed).
5. Check from a phone or another network: landing page, register, confirmation email, approval in **Govern → User Management**, sign in.
6. Share the link. Keep the **Waiting for approval** panel open during the demo, because each new account needs approval.

Limits and cautions:
* The free quick-tunnel address **changes every time** the tunnel restarts; a fixed address needs a free Cloudflare account and a domain.
* The app is only reachable while the machine and tunnel are running.
* The development stack has dev-mode settings (debug-style defaults, relaxed throttles are **not** enabled, but it is not hardened like `production.py`). For anything beyond a short supervised demo, use the production stack (Option B or doc 14).
* Do not leave the tunnel open unattended; it exposes a login page to the internet.
* Never put real financial data in a demo instance.

## 5. Option B: Oracle Cloud Always Free VM (if an always-on host is needed)

1. Create an Oracle Cloud account (free tier; the card is for identity checks only). Choose the home region carefully; it cannot be changed.
2. Create an instance: Ubuntu 24.04, shape **VM.Standard.A1.Flex** with 4 OCPU and 24 GB RAM (within the free allowance), your SSH public key, public IP. "Out of capacity" errors are a known Oracle issue: retry later or try another availability domain.
3. In the VCN security list, allow ingress TCP **80 and 443** (and 22 for SSH).
4. Free domain name: a **DuckDNS** subdomain (for example `finguard-name.duckdns.org`) pointed at the VM IP, or an `<ip-with-dashes>.sslip.io` name that needs no signup. Caddy can issue a real certificate for either.
5. Over SSH: install Docker, copy the project, create `.env.prod` from `.env.prod.example` (generate secrets; set `SITE_ADDRESS`, `FRONTEND_BASE_URL`, SMTP), then follow doc 14 section 3: `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build`, `create_superadmin`, `scripts/smoke.sh`.
6. Schedule `scripts/backup.sh` and copy backups off the VM.

Cautions: the first ARM build takes about 15-20 minutes; Oracle may reclaim idle free instances, so keep backups; secrets (including the SMTP app password) must be typed into `.env.prod` on the server, never pasted into chat or committed.

## 6. Email for the test

* Development default prints mail to the worker log (`docker compose logs worker`).
* For real delivery set in `.env`: `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST=smtp.gmail.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=1`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (a Google **App Password**), `DEFAULT_FROM_EMAIL`. `.env` is gitignored.
* Observed in testing (2026-11-20): SMTP delivery worked (a plain test message arrived). A first message from a new sender with a link may land in spam; check Spam and the sender's Sent folder. Gmail allows about 500 messages a day.
* For real users use a domain mailbox or a mail service with SPF/DKIM (SES, Brevo, Mailgun).
* Any app password that has been pasted into a chat or screenshot must be **revoked** and replaced.

## 7. Decision recorded

| ID | Decision | Status | Reason |
|---|---|---|---|
| D-111 | For the test and presentation (about 5 users) use a free Cloudflare Tunnel to the developer's machine; Oracle Cloud Always Free is the fallback for an always-on host; Vercel, Netlify, Render/Koyeb free and Railway are rejected for this stack | Recommended; awaiting the user's go-ahead | Only options that give the full stack enough memory are a local machine or a free ARM VM; the others cannot run Celery, Redis, WebSockets and the ML libraries, and a split frontend breaks the `SameSite=Strict` cookie. |

## 8. Not done / open

* No tunnel has been started and no public URL exists yet.
* No cloud account, server or domain has been created.
* Let's Encrypt issuance on a real domain, SMTP at scale and Neo4j in production remain untested (doc 14 section 9).
