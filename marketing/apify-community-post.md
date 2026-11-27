# Archived Apify community draft

Status: archived and not for publication. This draft was never posted. The active customer route uses the [free demonstration](../docs/check-crawler-data-before-embedding.md), the Apify Store listing and the existing integration-question form. No community account or signup is required. The original proposed message is retained below as history.

---

**Check a help-center dataset before refreshing a RAG index**

Disclosure: I maintain RAG Knowledge Base Sync & QA on Apify.

Here is a reproducible example for teams that already have extracted documentation. Five fictional records contain one duplicate row, one missing-text row and one conflicting source key. The walkthrough shows the exact findings and a corrected three-record input:
https://github.com/millgrah719/rag-knowledge-base-sync-recipes/blob/main/docs/check-crawler-data-before-embedding.md

The local Python preflight is free: no signup, API key, dependencies or uploaded data. From the downloaded repository, run:
```bash
python3 tools/rag_preflight.py examples/rag-preflight-input.json
```

The optional hosted Actor prepares stable source-linked chunks, reports supported recorded source failures and compares eligible full snapshots. Its readiness decision keeps partial or rejected input out of automatic handoff:
https://apify.com/millgrah/rag-knowledge-base-sync-qa

US$0.50 per completed non-demo report, plus Apify usage; up to 500 source rows. Fictional demo mode has no product-event charge, although platform usage may apply. The local preflight does not reproduce the full Actor validation or generate chunks.

Bring your existing crawler and indexing workflow. The report checks supplied records; it cannot prove a crawl captured the whole source, create embeddings or update your vector database. Advance a baseline only after your destination accepts the update.

For recurring help-center imports, which input failure would be most useful to demonstrate next?
