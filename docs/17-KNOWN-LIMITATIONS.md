# 17 — Known Limitations (living document)

## Anticipated (from design; to be confirmed or retired by experiments)
- PaySim and Elliptic are synthetic/anonymised; results do not transfer to real banks. ULB features are PCA-anonymised (explanations limited to V-names).
- PaySim has no real timestamps, little repeat-sender history, and leakage-prone balance fields; behavioral and graph signals may be weak there.
- ULB has no account IDs, so behavioral/graph/duplicate modules cannot be evaluated on it.
- Unsupervised detectors produce false positives; LOF/OC-SVM scale poorly (subsampling required).
- SHAP/LIME are approximations, can be unstable, and are not causal proof.
- Graph algorithms (cycles, betweenness) are expensive on millions of edges; bounded search and subset projections are used.
- OCR accuracy depends on scan quality; evaluated only on a synthetic/public sample.
- Risk weights/thresholds are research proposals, not regulatory standards; calibrated only on the available labels.
- Email notifications use console/SMTP-test backend unless configured.
- Real-time event streaming (Kafka) is not implemented; API ingestion is micro-batch.
- Host Python/Node versions differ from the containerised runtime (D-002).

## Discovered during implementation
- Phase 2: the Users/Audit/Login pages were type-checked, built and unit-tested (auth guards, login form, API client) but **not driven in a real browser**; the API behind them was exercised end-to-end with real logins. Browser E2E (Playwright) is planned for Phase 13/15.
- Audit trigger can be removed by a database superuser; production DB roles should not be superuser (Phase 16).
- No password-change self-service or forced password rotation yet; only admin reset.
- Access tokens are not revocable before their 15-minute expiry (refresh tokens are). Role/permission changes apply on the next request because permissions load per request.
- `/ws/echo/` is still an unauthenticated Phase 1 smoke route; ticket-authenticated WebSockets arrive with Phase 4 (import progress) and Phase 11 (alerts).
- Frontend lint reports 3 fast-refresh warnings (context + hook exported from the same file).
