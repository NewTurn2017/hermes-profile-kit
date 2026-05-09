# research profile

Deep research with web search and citations. Opus-class. CLI only.

## What this profile is good at
- Multi-source research with synthesis
- Comparing technologies, products, papers
- Long-form reports with cited claims

## Why Opus?
Research is one of the few cases where Opus's reasoning depth pays off in fewer back-and-forth turns. Auxiliary model is Sonnet (not Haiku) because web summarization quality affects final report quality more than it affects coding.

## Recommended search providers

The free web_search tool works, but dedicated providers give better results:

```bash
# Brave (general)
echo "BRAVE_SEARCH_API_KEY=BSA..." >> ~/.hermes/profiles/research/.env

# Exa (semantic, good for finding similar pages)
echo "EXA_API_KEY=..." >> ~/.hermes/profiles/research/.env

# Tavily (research-tuned)
echo "TAVILY_API_KEY=..." >> ~/.hermes/profiles/research/.env
```

Hermes will use them automatically when available.

## Cost awareness

Opus is expensive. Tips:
- Set a session budget mentally before starting
- Use `/background` for long research tasks so you can do other work in parallel
- For small lookups, use the `coder` or `assistant` profile instead

## Example session

```bash
research chat
> "최근 6개월 LLM agent 프레임워크 동향 정리. Hermes, Letta, AutoGen, LangGraph 비교 포함. 한국어로."
```

The agent will search broadly first, then narrow, then synthesize. Reports go to `~/Documents/research-reports/` if you save them.
