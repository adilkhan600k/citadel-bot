# Runners of the Day (runners.py, v2)

Posts a daily recap to 🏃・runners (`runners_channel.txt`, override with the `RUNNERS_CHANNEL_ID` env var). It covers Solana coins **launched in the last 24h** that reached a **$1M market cap** in that window. Recap only, not advice.

    python3 runners.py --dry   # no post, no state write; writes runners_preview.png
    python3 runners.py         # needs the DISCORD_BOT_TOKEN env var

- **Launch time:**
  - pump.fun mints use the pump.fun `created_timestamp` (`coins-v3/{mint}`).
  - Other mints use their earliest DEX pool.
  - pump.fun mints with no verifiable launch time are skipped and counted.
- **Safety filters:**
  - Liquidity ≥ $8K and 24h volume ≥ $50K.
  - Market cap / liquidity ≤ 80.
  - At least 150 holders.
  - Top-10 holders own less than 90%.
  - Not flagged as a honeypot.
  - Not posted in the last 5 days (`runners_state.json`).
- **Who's behind it:**
  - Creator wallet (pump.fun `creator`, otherwise the GeckoTerminal developer address), linked to Solscan.
  - Dev's other launches from pump.fun `coins-v2/user-created-coins` (up to a 50-coin sample): launches this week, how many hit $1M, how many died under $50K. Flagged as first launch, serial launcher or mostly dead.
  - Dev holding % from GeckoTerminal. Shown as "unclear" when it conflicts with the top-10 share.
  - X, Telegram and website links from pump.fun, DexScreener and GeckoTerminal.
- **Why it ran:**
  - The coin's own description.
  - A Google News RSS headline from the last 48h, used only if it contains the coin name.
  - Otherwise: "No clear news, likely pure meme/social momentum."
- **Output:** the top 6 coins in detail, coins 7–10 compact. The embed is trimmed to stay under 5,800 characters.
- **Sources:** all free and keyless (GeckoTerminal, DexScreener, pump.fun frontend API, Google News RSS). Solscan and Helius APIs need keys, so they are only linked. Dependencies: stdlib + Pillow.
- **Backup:** v1 is in `runners_v1_backup.py`.
