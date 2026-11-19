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
- Phase 3: performance was measured once on 1M random rows, not on 6.36M PaySim rows or under concurrent load. Page-number paging gets slow at very deep pages (use `?cursor=`).
- Search is exact-match only (D-026). The transaction UI uses page-number paging only; it does not yet expose keyset mode.
- Phase 3 pages (Transactions, detail, account) are type-checked, built and component-tested, and the APIs were exercised live, but the pages were not opened in a browser.
- Datasets can be listed and created via API but there is no dataset-creation UI yet (arrives with the import wizard in Phase 4).
- Phase 4: import throughput is ~12k rows/s at 1M rows (target 20k) and was not measured at 6.36M rows; the real PaySim file has not been imported (needs your Kaggle download). Excel imports were tested with small files only (read-only streaming, but openpyxl is slower than CSV; limit 100 MB).
- Cancelling or failing an import keeps the rows from already-committed chunks (by design, for resume); there is no automatic rollback of a partial import.
- A job whose worker died stays `running` until someone force-resumes it (the UI offers this after 60 s without progress); there is no automatic stale-job reaper yet.
- Only the first 10,000 row errors per import are stored; the CSV error export covers only those.
- CSV row estimate for the progress bar counts newlines, so it can be off for files with line breaks inside quoted cells; the bar caps at 100%.
- Uploaded files stay on disk (`media/imports/`) after import; retention/cleanup is Phase 16. In production, upload storage must be shared between web and worker (volume/S3).
- No antivirus scan hook on uploads (type/size/magic-byte checks only).
- The backend test run prints a harmless teardown warning ("test database is being accessed by other users") after the async WebSocket tests.
- The import wizard and detail pages are component-tested and the API/WebSocket path was exercised live, but the pages were not opened in a browser.
