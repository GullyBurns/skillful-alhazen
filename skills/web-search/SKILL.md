---
name: web-search
description: Search the web using SearXNG (self-hosted metasearch - no API key needed)
---

# Web Search Skill

Use this skill whenever you need to search the web. SearXNG aggregates results from Google, DuckDuckGo, Bing, and other engines. No API key required.

**Triggers:** "search for", "look up", "find information about", "what is", "who is", "google", "search the web"

## Search

```bash
curl -s "${SEARXNG_URL:-http://localhost:8888}/search?q=QUERY&format=json" | python3 -c "
import sys, json
r = json.load(sys.stdin)
results = r.get('results', [])[:5]
print(f'{len(results)} results:\n')
for x in results:
    print(x.get('title',''))
    print(x.get('url',''))
    print(x.get('content','')[:300])
    print()
"
```

Replace `QUERY` with URL-encoded search terms — spaces as `+`, e.g. `Gully+Burns+neuroscience`.

## Notes

- Results are already ranked by relevance
- Use `[:10]` instead of `[:5]` to get more results
- For site-specific search, add `site:example.com` to the query
- `SEARXNG_URL` is set automatically per environment (localhost:8888 on macmini, searxng:8080 on VPS)
