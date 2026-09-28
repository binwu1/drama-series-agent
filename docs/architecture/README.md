# Hermes Drama Loop — architecture index

1. [DECISIONS.md](DECISIONS.md) — Web shell, gates, async, S4–S7 scope  
2. [s1-enrich-contract.md](s1-enrich-contract.md) — one-liner → literary + cast Accept  
3. [s1-asset-studio.md](s1-asset-studio.md) — Mode C preview/edit/upload/regen before Accept  
4. [s2-s3-sequence.md](s2-s3-sequence.md) — jsonl/Comfy async + next episode  
5. [s4-s7-scope.md](s4-s7-scope.md) — review / maintain / deliver / resume  

Contracts: [`../contracts/`](../contracts/)

```text
React Hermes Shell (Chat + status + workbench)
         │ HTTP/SSE
FastAPI Series Agent (LLM + tools)
         │
Workers: literary | image | build_jsonl | comfy
         │ JobEvent
EventBus ──► workbench Job panel + series_runtime.json
```

Streamlit Home/History/Cast remain; Hermes stage radios are not the product shell (see D1-bis).
