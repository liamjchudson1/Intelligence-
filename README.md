# Cultural Intelligence Platform

Autonomous platform that monitors social media and niche communities to identify emerging cultural signals before they go mainstream. Powered by Claude AI for analysis and insight generation.

## Architecture

```
culturalintel/
  monitors/       # Data collection from Reddit, Twitter/X, Discord, forums
  analysis/       # Claude-powered signal extraction and scoring
  publishing/     # Report generation (Markdown + HTML)
  learning/       # Prediction tracking and feedback loop
  delivery/       # Email (Beehiiv), Slack, Teams webhook distribution
  verticals/      # Pluggable vertical configs (sports_betting, etc.)
  pipeline.py     # Orchestrator tying all modules together
  scheduler.py    # APScheduler-based recurring job runner
  cli.py          # Command-line interface
```

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run for a vertical
culturalintel run sports_betting

# Save report to file
culturalintel run sports_betting -o report.md

# Start scheduler (recurring)
culturalintel schedule

# List available verticals
culturalintel list

# Run feedback loop
culturalintel feedback sports_betting --days 14
```

## Adding a New Vertical

1. Create `culturalintel/verticals/<name>/config.json`
2. Define keywords, subreddits, Twitter queries, forum configs
3. Run `culturalintel run <name>`

See `culturalintel/verticals/sports_betting/config.json` for a complete example.

## Pipeline Flow

1. **Monitor** - Collect posts from configured platforms
2. **Analyse** - Claude identifies signals, scores by growth/commercial potential
3. **Publish** - Generate formatted intelligence report
4. **Learn** - Evaluate past predictions against outcomes
5. **Deliver** - Distribute via email, Slack, Teams

## Required API Keys

- `ANTHROPIC_API_KEY` - Claude API (required)
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` - Reddit API
- `TWITTER_BEARER_TOKEN` - Twitter/X API v2
- `DISCORD_BOT_TOKEN` - Discord bot
- `BEEHIIV_API_KEY` - Email delivery
- `SLACK_WEBHOOK_URL` / `TEAMS_WEBHOOK_URL` - Chat webhooks

## Tests

```bash
pytest
```
