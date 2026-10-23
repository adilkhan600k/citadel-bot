# citadel-bot

Free scheduled Discord posts for the Citad3l server. GitHub Actions runs the scripts and posts with a bot token stored as a repository secret. The token is never written to the repo.

## Posts

| Post | Command | Schedule |
| --- | --- | --- |
| AI news briefing and pinned AI release calendar | `python ai_intel.py news` and `python ai_intel.py calendar` | 13:00 UTC daily (8:00 AM Chicago while CDT is in effect) |
| Daily meme market report (image + embed) | `python market_signal.py` | 14:00 UTC daily |
| Runners of the Day (Solana coins launched in the last 24h that hit $1M) | `python runners.py` | 14:15 UTC daily |

Each run is its own job. One post failing does not cancel the others. After a run, changed state files (`*_state.json` and `ai_calendar.json`) are committed back to `main` as `github-actions[bot]` with `[skip ci]`. Those commits also keep the repository active so GitHub does not turn the schedule off for inactivity.

Channel ids live in `ai_channels.json`, `market_signal_channel.txt`, and `runners_channel.txt`. Cards use the fonts in `fonts/`. Dependencies are Python 3 and Pillow (`requirements.txt`).

## Add the bot token

1. On GitHub, open this repository.
2. Go to **Settings > Secrets and variables > Actions**.
3. Choose **New repository secret**.
4. Name it `DISCORD_BOT_TOKEN` and paste the bot token as the value.

The workflows pass that secret to the scripts as the `DISCORD_BOT_TOKEN` environment variable.

## Run it manually

1. Open the **Actions** tab.
2. Select **Daily Citad3l posts**.
3. Choose **Run workflow**.
4. Pick `all`, `market`, `ai`, or `runners`.

Manual runs execute the scripts currently on `main`.
