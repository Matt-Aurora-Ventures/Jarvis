# Jarvis Sniper Production Smoke (2026-02-14T12:19:12Z)

- Base: `https://kr8tiv.web.app`
- Output: `jarvis-sniper\debug\e2e-smoke-20260214-121709`

## Backtest CORS Probe
```json
{
  "tagUrl": "https://fh-ae9e97edb812fd26---ssrkr8tiv-wrmji3msqa-uc.a.run.app",
  "probe": {
    "ok": false,
    "status": 404,
    "ct": "application/json",
    "bodyHead": "{\"runId\":\"ui-smoke-nonexistent\",\"state\":\"unknown\",\"monitorUnavailable\":false,\"runMissing\":true,\"retryable\":false,\"code\":\"RUN_NOT_FOUND\",\"err"
  }
}
```

## Page Errors
- `Failed to fetch`
- `Failed to fetch`
- `Failed to fetch`

## Console Warnings/Errors
- `error` https://dexscreener.com/solana/NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/hype/reactions/dexPair/solana:A6KHMiFzn9AM7VKBtVP4fZNY9bCo2jP63R9dphaW1vrq' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/hype/reactions/dexPair/solana:A6KHMiFzn9AM7VKBtVP4fZNY9bCo2jP63R9dphaW1vrq:0:0 Failed to load resource: net::ERR_FAILED
- `error` https://dexscreener.com/solana/NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/dex/trending/v6?chainId=solana&timeframeKey=h6' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/dex/trending/v6?chainId=solana&timeframeKey=h6:0:0 Failed to load resource: net::ERR_FAILED
- `warning` https://dexscreener.com/tv/v27.001/bundles/library.97ddeff81f861d17f06e.js:140:1880 SymbolInfo validation: unsupported timezone "America/Costa_Rica"
- `error` https://dexscreener.com/solana/NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/dex/chart/amm/v3/pumpfundex/bars/solana/A6KHMiFzn9AM7VKBtVP4fZNY9bCo2jP63R9dphaW1vrq?res=15&cb=329&q=So11111111111111111111111111111111111111112' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/dex/chart/amm/v3/pumpfundex/bars/solana/A6KHMiFzn9AM7VKBtVP4fZNY9bCo2jP63R9dphaW1vrq?res=15&cb=329&q=So11111111111111111111111111111111111111112:0:0 Failed to load resource: net::ERR_FAILED
- `error` https://dexscreener.com/solana/NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/dex/chart/amm/v3/pumpfundex/bars/solana/A6KHMiFzn9AM7VKBtVP4fZNY9bCo2jP63R9dphaW1vrq?res=15&cb=329&q=So11111111111111111111111111111111111111112' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/dex/chart/amm/v3/pumpfundex/bars/solana/A6KHMiFzn9AM7VKBtVP4fZNY9bCo2jP63R9dphaW1vrq?res=15&cb=329&q=So11111111111111111111111111111111111111112:0:0 Failed to load resource: net::ERR_FAILED
- `error` https://dexscreener.com/solana/NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/dex/chart/amm/v3/pumpfundex/bars/solana/A6KHMiFzn9AM7VKBtVP4fZNY9bCo2jP63R9dphaW1vrq?res=15&cb=329&q=So11111111111111111111111111111111111111112' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/dex/chart/amm/v3/pumpfundex/bars/solana/A6KHMiFzn9AM7VKBtVP4fZNY9bCo2jP63R9dphaW1vrq?res=15&cb=329&q=So11111111111111111111111111111111111111112:0:0 Failed to load resource: net::ERR_FAILED
- `warning` https://dexscreener.com/tv/v27.001/bundles/library.97ddeff81f861d17f06e.js:39:1548 Unknown subscription symbol=Punch/SOL, resolution=15, key=1
- `warning` https://dexscreener.com/tv/v27.001/bundles/library.97ddeff81f861d17f06e.js:39:1548 Unknown subscription symbol=Punch/SOL, resolution=15, key=0
- `error` https://dexscreener.com/solana/7pskt3A1Zsjhngazam7vHWjWHnfgiRump916Xj7ABAGS?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/hype/reactions/dexPair/solana:FiNu5nSFwvjQbAFDESxDxvLhQJa3H7QYBrLUqFRB27v9' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/hype/reactions/dexPair/solana:FiNu5nSFwvjQbAFDESxDxvLhQJa3H7QYBrLUqFRB27v9:0:0 Failed to load resource: net::ERR_FAILED
- `error` https://dexscreener.com/solana/7pskt3A1Zsjhngazam7vHWjWHnfgiRump916Xj7ABAGS?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/dex/trending/v6?chainId=solana&timeframeKey=h6' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/dex/trending/v6?chainId=solana&timeframeKey=h6:0:0 Failed to load resource: net::ERR_FAILED
- `warning` https://dexscreener.com/tv/v27.001/bundles/library.97ddeff81f861d17f06e.js:140:1880 SymbolInfo validation: unsupported timezone "America/Costa_Rica"
- `error` https://dexscreener.com/solana/7pskt3A1Zsjhngazam7vHWjWHnfgiRump916Xj7ABAGS?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/dex/chart/amm/v3/meteora/bars/solana/FiNu5nSFwvjQbAFDESxDxvLhQJa3H7QYBrLUqFRB27v9?res=15&cb=329&q=So11111111111111111111111111111111111111112' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/dex/chart/amm/v3/meteora/bars/solana/FiNu5nSFwvjQbAFDESxDxvLhQJa3H7QYBrLUqFRB27v9?res=15&cb=329&q=So11111111111111111111111111111111111111112:0:0 Failed to load resource: net::ERR_FAILED
- `error` https://dexscreener.com/solana/7pskt3A1Zsjhngazam7vHWjWHnfgiRump916Xj7ABAGS?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/dex/chart/amm/v3/meteora/bars/solana/FiNu5nSFwvjQbAFDESxDxvLhQJa3H7QYBrLUqFRB27v9?res=15&cb=329&q=So11111111111111111111111111111111111111112' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/dex/chart/amm/v3/meteora/bars/solana/FiNu5nSFwvjQbAFDESxDxvLhQJa3H7QYBrLUqFRB27v9?res=15&cb=329&q=So11111111111111111111111111111111111111112:0:0 Failed to load resource: net::ERR_FAILED
- `error` https://dexscreener.com/solana/7pskt3A1Zsjhngazam7vHWjWHnfgiRump916Xj7ABAGS?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/dex/chart/amm/v3/meteora/bars/solana/FiNu5nSFwvjQbAFDESxDxvLhQJa3H7QYBrLUqFRB27v9?res=15&cb=329&q=So11111111111111111111111111111111111111112' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/dex/chart/amm/v3/meteora/bars/solana/FiNu5nSFwvjQbAFDESxDxvLhQJa3H7QYBrLUqFRB27v9?res=15&cb=329&q=So11111111111111111111111111111111111111112:0:0 Failed to load resource: net::ERR_FAILED
- `warning` https://dexscreener.com/tv/v27.001/bundles/library.97ddeff81f861d17f06e.js:39:1548 Unknown subscription symbol=GAS/SOL, resolution=15, key=1
- `warning` https://dexscreener.com/tv/v27.001/bundles/library.97ddeff81f861d17f06e.js:39:1548 Unknown subscription symbol=GAS/SOL, resolution=15, key=0
- `error` https://dexscreener.com/solana/XsqE9cRRpzxcGKDXj1BJ7Xmg4GRhZoyY1KpmGSxAWT2?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/hype/reactions/dexPair/solana:5MGvNj9RNKNmzwp1LtZuQkZonEYtKJ3JuiyNQEUU2DsF' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/hype/reactions/dexPair/solana:5MGvNj9RNKNmzwp1LtZuQkZonEYtKJ3JuiyNQEUU2DsF:0:0 Failed to load resource: net::ERR_FAILED
- `error` https://dexscreener.com/solana/XsqE9cRRpzxcGKDXj1BJ7Xmg4GRhZoyY1KpmGSxAWT2?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/dex/trending/v6?chainId=solana&timeframeKey=h6' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/dex/trending/v6?chainId=solana&timeframeKey=h6:0:0 Failed to load resource: net::ERR_FAILED
- `warning` https://dexscreener.com/tv/v27.001/bundles/library.97ddeff81f861d17f06e.js:140:1880 SymbolInfo validation: unsupported timezone "America/Costa_Rica"
- `error` https://dexscreener.com/solana/XsqE9cRRpzxcGKDXj1BJ7Xmg4GRhZoyY1KpmGSxAWT2?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/dex/chart/amm/v3/solamm/bars/solana/5MGvNj9RNKNmzwp1LtZuQkZonEYtKJ3JuiyNQEUU2DsF?res=15&cb=329&q=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/dex/chart/amm/v3/solamm/bars/solana/5MGvNj9RNKNmzwp1LtZuQkZonEYtKJ3JuiyNQEUU2DsF?res=15&cb=329&q=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v:0:0 Failed to load resource: net::ERR_FAILED
- `error` https://dexscreener.com/solana/XsqE9cRRpzxcGKDXj1BJ7Xmg4GRhZoyY1KpmGSxAWT2?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/dex/chart/amm/v3/solamm/bars/solana/5MGvNj9RNKNmzwp1LtZuQkZonEYtKJ3JuiyNQEUU2DsF?res=15&cb=329&q=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/dex/chart/amm/v3/solamm/bars/solana/5MGvNj9RNKNmzwp1LtZuQkZonEYtKJ3JuiyNQEUU2DsF?res=15&cb=329&q=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v:0:0 Failed to load resource: net::ERR_FAILED
- `error` https://dexscreener.com/solana/XsqE9cRRpzxcGKDXj1BJ7Xmg4GRhZoyY1KpmGSxAWT2?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/dex/chart/amm/v3/solamm/bars/solana/5MGvNj9RNKNmzwp1LtZuQkZonEYtKJ3JuiyNQEUU2DsF?res=15&cb=329&q=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/dex/chart/amm/v3/solamm/bars/solana/5MGvNj9RNKNmzwp1LtZuQkZonEYtKJ3JuiyNQEUU2DsF?res=15&cb=329&q=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v:0:0 Failed to load resource: net::ERR_FAILED
- `error` https://dexscreener.com/solana/XsqE9cRRpzxcGKDXj1BJ7Xmg4GRhZoyY1KpmGSxAWT2?embed=1&theme=dark&trades=0&info=0:0:0 Access to fetch at 'https://io.dexscreener.com/dex/pair-details/v4/solana/5mgvnj9rnknmzwp1ltzuqkzoneytkj3juiynqeuu2dsf' from origin 'https://dexscreener.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
- `error` https://io.dexscreener.com/dex/pair-details/v4/solana/5mgvnj9rnknmzwp1ltzuqkzoneytkj3juiynqeuu2dsf:0:0 Failed to load resource: net::ERR_FAILED
- `warning` https://dexscreener.com/tv/v27.001/bundles/library.97ddeff81f861d17f06e.js:39:1548 Unknown subscription symbol=MCDx/USDC, resolution=15, key=1

## Network Failures (>=400 or requestfailed)
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/gj4pB2QL1VoDw96Tsz2DtFKFMsKowjcT4WC71USpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/BCG4MBb279NJnJh9iFGooKbKzihymv7gVuEUtcdzpump.png`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/hype/reactions/dexPair/solana:A6KHMiFzn9AM7VKBtVP4fZNY9bCo2jP63R9dphaW1vrq`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/dex/trending/v6?chainId=solana&timeframeKey=h6`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/dex/chart/amm/v3/pumpfundex/bars/solana/A6KHMiFzn9AM7VKBtVP4fZNY9bCo2jP63R9dphaW1vrq?res=15&cb=329&q=So11111111111111111111111111111111111111112`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/dex/chart/amm/v3/pumpfundex/bars/solana/A6KHMiFzn9AM7VKBtVP4fZNY9bCo2jP63R9dphaW1vrq?res=15&cb=329&q=So11111111111111111111111111111111111111112`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/dex/chart/amm/v3/pumpfundex/bars/solana/A6KHMiFzn9AM7VKBtVP4fZNY9bCo2jP63R9dphaW1vrq?res=15&cb=329&q=So11111111111111111111111111111111111111112`
- `GET`  failure=net::ERR_ABORTED `https://firestore.googleapis.com/google.firestore.v1.Firestore/Listen/channel?gsessionid=e-NenEWy2vwgPj1tTFClZZygiDwNPQPVB4nNY_HaA2X3vkYzen3YVg&VER=8&database=projects%2Fdex-screener-16543%2Fdatabases%2F(default)&RID=rpc&SID=Ft1_2u4bQh1kOE3_W314YA&CI=0&AID=0&TYPE=xmlhttp&zx=4p5zlgnr875n&t=1`
- `GET`  failure=net::ERR_ABORTED `https://firestore.googleapis.com/google.firestore.v1.Firestore/Write/channel?gsessionid=appWkESAoQKcKvbf07MgtZOPMpEWVOuMzaW5HbvkryuNyAS3Etd4Nw&VER=8&database=projects%2Fdex-screener-16543%2Fdatabases%2F(default)&RID=rpc&SID=ck1C3-Y9c86xjGEYG_MktQ&CI=0&AID=0&TYPE=xmlhttp&zx=bu7bt0nu5pvv&t=1`
- `GET`  failure=net::ERR_ABORTED `https://firestore.googleapis.com/google.firestore.v1.Firestore/Listen/channel?gsessionid=e-NenEWy2vwgPj1tTFClZZygiDwNPQPVB4nNY_HaA2X3vkYzen3YVg&VER=8&database=projects%2Fdex-screener-16543%2Fdatabases%2F(default)&RID=rpc&SID=Ft1_2u4bQh1kOE3_W314YA&CI=0&AID=14&TYPE=xmlhttp&zx=pv2012y5fj0k&t=1`
- `GET`  failure=net::ERR_ABORTED `https://firestore.googleapis.com/google.firestore.v1.Firestore/Write/channel?gsessionid=appWkESAoQKcKvbf07MgtZOPMpEWVOuMzaW5HbvkryuNyAS3Etd4Nw&VER=8&database=projects%2Fdex-screener-16543%2Fdatabases%2F(default)&RID=rpc&SID=ck1C3-Y9c86xjGEYG_MktQ&CI=0&AID=2&TYPE=xmlhttp&zx=r0hx64p0v6fv&t=1`
- `GET`  failure=net::ERR_ABORTED `https://kr8tiv.web.app/api/graduations`
- `GET`  failure=net::ERR_ABORTED `https://kr8tiv.web.app/api/tv-screener`
- `GET`  failure=net::ERR_ABORTED `https://kr8tiv.web.app/api/macro`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/hype/reactions/dexPair/solana:FiNu5nSFwvjQbAFDESxDxvLhQJa3H7QYBrLUqFRB27v9`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/dex/trending/v6?chainId=solana&timeframeKey=h6`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/dex/chart/amm/v3/meteora/bars/solana/FiNu5nSFwvjQbAFDESxDxvLhQJa3H7QYBrLUqFRB27v9?res=15&cb=329&q=So11111111111111111111111111111111111111112`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/dex/chart/amm/v3/meteora/bars/solana/FiNu5nSFwvjQbAFDESxDxvLhQJa3H7QYBrLUqFRB27v9?res=15&cb=329&q=So11111111111111111111111111111111111111112`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/dex/chart/amm/v3/meteora/bars/solana/FiNu5nSFwvjQbAFDESxDxvLhQJa3H7QYBrLUqFRB27v9?res=15&cb=329&q=So11111111111111111111111111111111111111112`
- `GET`  failure=net::ERR_ABORTED `https://firestore.googleapis.com/google.firestore.v1.Firestore/Write/channel?gsessionid=Q9s5Z0PPq93xtWFmlsjJ3C77diqg9X49v5KAz-qdwJGqL6_db-sybg&VER=8&database=projects%2Fdex-screener-16543%2Fdatabases%2F(default)&RID=rpc&SID=dwdo7nFW9a-Uj7azTFyPSg&CI=0&AID=0&TYPE=xmlhttp&zx=e3w6zsvz04u4&t=1`
- `GET`  failure=net::ERR_ABORTED `https://firestore.googleapis.com/google.firestore.v1.Firestore/Listen/channel?gsessionid=WTZ-OB2Ym2RmJgHJ4P7fSwnWCkc48_UrylYSnb8BTfKQt_MEVYPJnA&VER=8&database=projects%2Fdex-screener-16543%2Fdatabases%2F(default)&RID=rpc&SID=dxEHXvUen4JUoQKhUGKAEQ&CI=0&AID=0&TYPE=xmlhttp&zx=1aka8n68nnd&t=1`
- `GET`  failure=net::ERR_ABORTED `https://firestore.googleapis.com/google.firestore.v1.Firestore/Write/channel?gsessionid=Q9s5Z0PPq93xtWFmlsjJ3C77diqg9X49v5KAz-qdwJGqL6_db-sybg&VER=8&database=projects%2Fdex-screener-16543%2Fdatabases%2F(default)&RID=rpc&SID=dwdo7nFW9a-Uj7azTFyPSg&CI=0&AID=2&TYPE=xmlhttp&zx=ehtpyjohntmo&t=1`
- `GET`  failure=net::ERR_ABORTED `https://firestore.googleapis.com/google.firestore.v1.Firestore/Listen/channel?gsessionid=WTZ-OB2Ym2RmJgHJ4P7fSwnWCkc48_UrylYSnb8BTfKQt_MEVYPJnA&VER=8&database=projects%2Fdex-screener-16543%2Fdatabases%2F(default)&RID=rpc&SID=dxEHXvUen4JUoQKhUGKAEQ&CI=0&AID=23&TYPE=xmlhttp&zx=q52x067fqqy0&t=1`
- `GET`  failure=net::ERR_ABORTED `https://kr8tiv.web.app/api/tv-screener`
- `GET`  failure=net::ERR_ABORTED `https://kr8tiv.web.app/api/macro`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/hype/reactions/dexPair/solana:5MGvNj9RNKNmzwp1LtZuQkZonEYtKJ3JuiyNQEUU2DsF`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/dex/trending/v6?chainId=solana&timeframeKey=h6`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/dex/chart/amm/v3/solamm/bars/solana/5MGvNj9RNKNmzwp1LtZuQkZonEYtKJ3JuiyNQEUU2DsF?res=15&cb=329&q=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/dex/chart/amm/v3/solamm/bars/solana/5MGvNj9RNKNmzwp1LtZuQkZonEYtKJ3JuiyNQEUU2DsF?res=15&cb=329&q=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/dex/chart/amm/v3/solamm/bars/solana/5MGvNj9RNKNmzwp1LtZuQkZonEYtKJ3JuiyNQEUU2DsF?res=15&cb=329&q=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`
- `GET`  failure=net::ERR_FAILED `https://io.dexscreener.com/dex/pair-details/v4/solana/5mgvnj9rnknmzwp1ltzuqkzoneytkj3juiynqeuu2dsf`
- `GET`  failure=net::ERR_ABORTED `https://firestore.googleapis.com/google.firestore.v1.Firestore/Listen/channel?gsessionid=2i4RF3ptxhYordIWYWb62ujmNnwJgX9k8OYfzDRiweKWFFMIlINWsg&VER=8&database=projects%2Fdex-screener-16543%2Fdatabases%2F(default)&RID=rpc&SID=O0lOKYKBATReqhNW-6MHQw&CI=0&AID=0&TYPE=xmlhttp&zx=uqz6wmvwojmo&t=1`
- `GET`  failure=net::ERR_ABORTED `https://firestore.googleapis.com/google.firestore.v1.Firestore/Write/channel?gsessionid=T_KsyytlCGzDKjQc3fSBU0st7oIq5oR-3pj2NUrBL1Bn_30alchCKw&VER=8&database=projects%2Fdex-screener-16543%2Fdatabases%2F(default)&RID=rpc&SID=dWvtEX8bfZMNsQFbtjQtaw&CI=0&AID=0&TYPE=xmlhttp&zx=adc1lj41gxh7&t=1`
- `GET`  failure=net::ERR_ABORTED `https://firestore.googleapis.com/google.firestore.v1.Firestore/Listen/channel?gsessionid=2i4RF3ptxhYordIWYWb62ujmNnwJgX9k8OYfzDRiweKWFFMIlINWsg&VER=8&database=projects%2Fdex-screener-16543%2Fdatabases%2F(default)&RID=rpc&SID=O0lOKYKBATReqhNW-6MHQw&CI=0&AID=23&TYPE=xmlhttp&zx=jogbk3rx3kp5&t=1`
- `GET`  failure=net::ERR_ABORTED `https://firestore.googleapis.com/google.firestore.v1.Firestore/Write/channel?gsessionid=T_KsyytlCGzDKjQc3fSBU0st7oIq5oR-3pj2NUrBL1Bn_30alchCKw&VER=8&database=projects%2Fdex-screener-16543%2Fdatabases%2F(default)&RID=rpc&SID=dWvtEX8bfZMNsQFbtjQtaw&CI=0&AID=2&TYPE=xmlhttp&zx=jc7jqffguvzw&t=1`
- `GET`  failure=net::ERR_ABORTED `https://kr8tiv.web.app/api/macro`
- `GET`  failure=net::ERR_ABORTED `https://kr8tiv.web.app/api/bags/intel?limit=200`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/BCG4MBb279NJnJh9iFGooKbKzihymv7gVuEUtcdzpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/gj4pB2QL1VoDw96Tsz2DtFKFMsKowjcT4WC71USpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/ARfjgcj1FCocaNG47nfTuzC1W1yJQCnvebFTebwJpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/2Mexkemd4X6h2wqZjjPQwwFdGBbfvnWUWty6cHyMpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/Dfua5tSEoUTLhXv2Xqt84FJGSsLoPVonMSvWWruXpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/YfbdoN7Cj9ypBSVfuaR7YJLEFnKLsSc6G6U8MFcpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/6ZfYRYpwSmgufraa314ihiUKwrh8F6TDosB1Ja76pump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/4udCASKskpYNymxwXAwMR4En15vtUXwT7P5vc3fjpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/7ASpUGEgCh5DtpYPHDGgUodvJrsX1rQ8qYePCXYbpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/9HfXEN5uAy2VgGzaLGMv27u3mcFbtFknFiN6eUP8pump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/32TrrNye7SMfzzoeewavngyE9YkZxJm4JeZ3ErRfpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/iY1cT6AfrysEyQ59tsWh1tEoSexY4z3B5oWra2kpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/EirpkRcuj7oQvTZZgWXuCmQtGvbdHt7hx6Gk5n1Jpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/7neejYzH7CToTfaP2dC1ZSAsytbdDKUdJXA6V1vN1CVM.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/6RLKHhdsTwWqz7kRkdigL4488sNYJAYJR3589zjLpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/Fe1AVhwKzdGScBaMjfKkhG8UgZiLPpxBqGtmDrnrpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/4hScCMqemprkdLyEgxwyMSGaBgTXNqP89BzFxPAFpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/4U3GNDhwR2E1Sd5arHr54LERch8MvhwEDTNAuNpDpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/Fu7rsbRLnNZz3PW4TpbqmDo4AZUcf87p1YjmHArvpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/D6eQLSkvUpMqBqXhUGNMnVATbwTZkMEBCnud95pRpump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/8DnUod63SEwEyzFLXrgK1D3pQcDPHwKf3q1rC1Fepump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/AxrZ1ZBMmK73Zt935rSs7PCoeHeZsgYntAZfzF7upump.png`
- `GET`  failure=net::ERR_BLOCKED_BY_ORB `https://cdn.dexscreener.com/tokens/solana/EtEuhiNxyBXTMp1rW78LvAQupvafJBgMa666V8YVpump.png`
