"""Motor comun pentru CLI si laborator: incarcare HTTP cu concurenta fixa."""
import asyncio
import math
import random
import time
from collections import Counter

import httpx


async def measure(url, requests=5000, concurrency=10, products=100,
                  use_cache=True, ttl=60, progress=None, cancelled=None):
    rng = random.Random(42)
    queue = asyncio.Queue()
    for _ in range(requests):
        queue.put_nowait(rng.randint(1, products))
    latencies, errors, hits, instances = [], Counter(), Counter(), Counter()
    completed = 0
    last_update = 0
    async with httpx.AsyncClient(timeout=10, limits=httpx.Limits(
        max_connections=concurrency, max_keepalive_connections=concurrency
    )) as client:
        async def worker():
            nonlocal completed, last_update
            while not (cancelled and cancelled()):
                try:
                    product_id = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                start = time.perf_counter()
                try:
                    response = await client.get(f"{url}/products/{product_id}",
                                                params={"use_cache": use_cache, "cache_ttl": ttl})
                    if response.status_code == 200:
                        latencies.append((time.perf_counter() - start) * 1000)
                        hits[response.headers.get("X-Cache", "UNKNOWN")] += 1
                        instances[response.headers.get("X-Instance", "UNKNOWN")] += 1
                    else:
                        errors[str(response.status_code)] += 1
                except httpx.HTTPError as exc:
                    errors[type(exc).__name__] += 1
                completed += 1
                now = time.perf_counter()
                if progress and (now - last_update > 0.5 or completed == requests):
                    last_update = now
                    progress(completed)

        start = time.perf_counter()
        await asyncio.gather(*(worker() for _ in range(concurrency)))
        elapsed = time.perf_counter() - start
    ordered = sorted(latencies)
    cache_reads = hits["HIT"] + hits["MISS"]
    return {"elapsed_seconds": elapsed, "attempted_requests": completed,
            "successful_requests": len(latencies), "errors": dict(errors),
            "successful_requests_per_second": len(latencies) / elapsed if elapsed else 0,
            "mean_ms": sum(latencies) / len(latencies) if latencies else None,
            "p95_ms": ordered[math.ceil(0.95 * len(ordered)) - 1] if ordered else None,
            "cache": dict(hits), "instances": dict(instances),
            "hit_rate": hits["HIT"] / cache_reads if cache_reads else None}
