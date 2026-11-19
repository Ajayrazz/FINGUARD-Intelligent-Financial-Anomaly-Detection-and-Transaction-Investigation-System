# 10 — Security and RBAC

## Controls (from Part 3.8 / research §19)
| Control | Design |
|---|---|
| Authentication | SimpleJWT: access 15 min (kept in memory), refresh 8 h in httpOnly+Secure+SameSite=Strict cookie, rotation + blacklist; logout blacklists; login throttle + lockout (5 failures → 15 min) |
| Password hashing | bcrypt-compatible (`BCryptSHA256PasswordHasher`); Django validators (length ≥ 12, common-password) — Argon2 alternative in D-009 |
| RBAC | Role → permission codenames; DRF `HasPerm('resource.action')` permission class on every view; default deny; object-level checks |
| Transport | HTTPS in production (HSTS, secure cookies); dev over HTTP |
| Input validation | DRF serializers; upload validation: extension + MIME + magic bytes, size limits, filename sanitisation, random storage names, no execution, optional AV scan hook |
| SQLi | Django ORM only; raw SQL (COPY/bulk) uses parameters/`copy` API, never string-formatted |
| CSV/Excel injection | Exported CSV/XLSX cells beginning `= + - @` are escaped; imports read with `openpyxl` read-only, formulas not evaluated |
| Audit | `audit.log()` on auth events, CRUD on sensitive resources, config changes, exports, case actions; append-only |
| Masking | Account refs masked (`C12…89`) for roles lacking `accounts.view_unmasked`; PII-like fields masked in logs |
| Evidence storage | Files outside web root, served via authenticated download view; sha256 recorded; private bucket in prod |
| Sessions | token expiry; refresh rotation; WS tickets single-use, 30 s |
| Rate limiting | DRF throttles (anon/login/user/export); Redis-backed |
| Secrets | env vars only; `.env.example` committed, `.env` ignored; production secrets via platform secret store |
| Headers/CORS | strict CORS allow-list, CSP for SPA, `X-Content-Type-Options`, clickjacking protection |
| Backup/recovery | `pg_dump` schedule + restore drill documented (Phase 16); Neo4j rebuildable from PG |
| Retention | configurable retention for uploads, report files, ephemeral exports; audit/case records retained per policy; deletion actions audited |
| ML/model safety | joblib/pickle artifacts loaded only from trusted storage with sha256 verification |

## Permission matrix (R read · C create · U update · D delete · A assign · E escalate · V resolve · X close · — none)
| Resource | Super Admin | Fin. Analyst | Fraud Investigator | Auditor | Management |
|---|---|---|---|---|---|
| Users / Roles | R C U D | — | — | R | — |
| System/risk/model config | R C U | R | R | R | R (risk only) |
| Datasets / imports | R C U | R C | R | R | — |
| Transactions | R | R, status update | R | R | aggregate only |
| Accounts / behavior | R | R | R | R | aggregate only |
| Detection runs / predictions | R C | R C(run) | R | R | — |
| Model versions / training | R C U (activate) | R | R | R | R (performance) |
| Graph | R C | R | R | R | — |
| Duplicates / invoices | R C U | R C U review | R C U review | R | — |
| Risk assessments | R | R | R | R | R aggregate |
| Explanations | R C | R C | R C | R | — |
| Alerts | R | R A(self) E ack | R A E ack | R | R aggregate |
| Cases | R | R C (from alert), comment | R C U A E V X, notes, evidence | R (read-only incl. history) | aggregate stats only |
| Reports | R C | R C (own types) | R C (case reports) | R C (audit reports) | R C (organizational) |
| Audit logs | R | — | — (own case history only) | R | — |

Notes: *No role may delete transactions, audit logs, or case history.* Deactivate instead of delete users. Closing a case requires `cases.close` and a recorded outcome. Resolution (`V`) and closure (`X`) are separate actions; Investigator resolves, a second permission (Investigator lead or Super Admin) may be required to close — configurable (D-014, needs approval). Matrix is encoded as data (seeded `Role`/`Permission` rows) and verified by a generated test that iterates every endpoint × role.

## Threat considerations
IDOR on case/evidence IDs (object checks + tests); mass assignment (explicit serializer fields); JWT theft (short access life, cookie refresh); privilege escalation via role edit (only Super Admin; audited; cannot remove last Super Admin); WS subscription hijack (permission re-check); malicious uploads/zip-bombs/polyglot PDFs (limits, parse in worker with timeouts); log injection; SSRF none (no URL fetches); denial via huge graph queries (depth/limit caps, query timeouts).

## Phase 5D additions
New permissions: `models.read`, `detection.read`, `detection.run`. Defaults: analyst — all three; investigator and auditor — `models.read`, `detection.read`; management — none (aggregates come in Phase 14). Model artifacts are pickle/joblib files, which execute code when loaded: the loader only opens files inside `ML_ARTIFACTS_DIR` whose SHA-256 equals the registered hash, so a swapped or tampered file fails the run (tested) and is audited. Run creation, completion and failure are written to the audit log. Predictions are model scores and never carry the dataset's ground-truth label (D-018).

## Phase 6 additions
New permissions: `behavior.read` (analyst, investigator, auditor), `behavior.run` (analyst). Management has none. Runs are audited (created / completed / failed). Behavior endpoints return amounts and counterparty identifiers, so they require the same read-level trust as transaction access; no ground-truth label is returned.
