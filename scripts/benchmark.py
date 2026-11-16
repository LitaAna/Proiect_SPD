"""Test de incarcare cu concurenta fixa; salveaza masuratori reale in JSON."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.benchmark import measure


async def run(args):
    report = await measure(args.url, args.requests, args.concurrency, args.products,
                           not args.no_cache, args.ttl)
    report["configuration"] = vars(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--requests", type=int, default=5000)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--products", type=int, default=100)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--ttl", type=int, default=60)
    parser.add_argument("--output", default="results/benchmark.json")
    arguments = parser.parse_args()
    if min(arguments.requests, arguments.concurrency, arguments.products) < 1:
        parser.error("requests, concurrency si products trebuie sa fie pozitive")
    if not 1 <= arguments.ttl <= 600:
        parser.error("ttl trebuie sa fie intre 1 si 600")
    asyncio.run(run(arguments))
