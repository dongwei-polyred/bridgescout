# Devpost submission — BridgeScout (for computerUse / Wd)

> Executor has **no browser**. Parent should dispatch **computerUse** with this checklist.
> Login email: `dw835496386@gmail.com` (OTP via Gmail MCP `user-Gmail` if needed).
> Hackathon: https://qloo.devpost.com/ — deadline Oct 30, 2026 11:45pm EDT.

## Steps

1. Open https://qloo.devpost.com/ and **Sign in** (Google or email). If not registered for the hackathon, click **Register**.
2. Sidebar → **Start project** (or Enter a submission).
3. Fill fields as below. Click **Submit project** when complete (Draft ≠ submitted).

## Field values (English)

| Field | Value |
| --- | --- |
| **Project name** | BridgeScout |
| **Tagline / elevator pitch** | Where in the world will your brand be loved? A Qloo-powered agent that picks first overseas cities, neighbourhoods, and partners from cultural taste. |
| **Demo / website URL** | https://bridgescout.onrender.com |
| **Repo URL** | https://github.com/dongwei-polyred/bridgescout |
| **Built with** (tags) | Python, FastAPI, Qloo, Uvicorn, Docker, Render, OpenAI-compatible LLM (optional) |
| **Open source license** | MIT (file present in repo About / root LICENSE) |

### Description (paste)

```
BridgeScout is an agent for small consumer brands going abroad ("出海").

Tell it what your customers already love ("we're like Pop Mart + Sanrio"), and it uses Qloo's cultural taste graph to answer what a $20k market-research study would: which city first, which neighbourhood for the pop-up, which shops to pitch, which brands to co-brand with, which artists/podcasts sit next to your audience, and who that audience is. Every claim links to the exact Qloo request behind it (evidence E1…En).

Why Qloo is required: an LLM alone will say "launch in Los Angeles" for every Asian lifestyle brand. BridgeScout instead measures, per city, how strongly the local population over-indexes on your reference entities, then maps that affinity down to neighbourhood heatmap cells and cross-domain partners (places, brands, artists, podcasts). Swap the references and the answer changes — because taste changes.

Agent loop (tool-calling planner with scripted fallback):
- resolve_references → Qloo /search
- taste_dna → /v2/insights (tags)
- suggest_markets / score_markets → destinations + location affinity
- hotspots → heatmap
- local_partners → place | brand | artist | podcast
- audience → demographics

Live demo (Render): https://bridgescout.onrender.com
Source: https://github.com/dongwei-polyred/bridgescout
Landing / runbook: https://dongwei-polyred.github.io/bridgescout/
```

### Custom questions

Answer any required custom questions along the lines of:
- **How does this use Qloo?** Every recommendation is grounded in Qloo Insights (search, tags, destinations, heatmaps, partners, demographics); the UI cites each API call.
- **Is it agentic?** Yes — LLM tool-calling planner when `LLM_API_KEY` is set; otherwise a complete scripted planner still calls the same Qloo tools.

## After submit

- Confirm status shows **Submitted** (not Draft).
- Copy the project URL (e.g. `https://devpost.com/software/bridgescout`) back into `/workspace/hackathons/qloo/SHIP_REPORT.md` section 3.
- Do **not** paste any API keys into Devpost fields.
