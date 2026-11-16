"""Serviciu local dedicat monitorizarii si testelor; nu face parte din upstream-ul masurat."""
import asyncio
import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient
from redis import Redis
from redis.exceptions import RedisError

from app.benchmark import measure

mongo = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"), serverSelectionTimeoutMS=2000)
database = mongo.memory_cache
jobs = database.experiments
redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True,
                       socket_connect_timeout=0.5, socket_timeout=0.5)
TARGETS = {"single": "http://gateway/single", "distributed": "http://gateway"}
lock = threading.Lock()
stop = threading.Event()
worker_thread = None
logger = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app):
    jobs.create_index("created_at")
    jobs.update_many({"status": {"$in": ["queued", "running"]}},
                     {"$set": {"status": "interrupted", "message": "Serviciul a fost repornit; test incomplet."}})
    yield
    stop.set()
    if worker_thread:
        await asyncio.to_thread(worker_thread.join, 12)
    mongo.close()
    redis.close()


app = FastAPI(title="Laborator cache", lifespan=lifespan)


class Experiment(BaseModel):
    requests: int = Field(default=2000, ge=100, le=20000)
    concurrency: int = Field(default=10, ge=1, le=100)
    products: int = Field(default=100, ge=1, le=10000)
    repeats: int = Field(default=1, ge=1, le=5)
    ttl: int = Field(default=60, ge=1, le=600)
    mode: str = Field(default="all", pattern="^(all|single-cache|single-no-cache|distributed-cache|distributed-no-cache)$")
    cache_state: str = Field(default="cold", pattern="^(cold|warm)$")


def clear_products():
    # Se elimina doar cheile de produs; baza persistenta nu este modificata.
    for key in redis.scan_iter(match="product:*", count=100):
        redis.delete(key)


async def execute(job_id, settings):
    modes = ["single-no-cache", "single-cache", "distributed-no-cache", "distributed-cache"] if settings.mode == "all" else [settings.mode]
    total = len(modes) * settings.repeats
    results = []
    jobs.update_one({"_id": job_id}, {"$set": {"status": "running", "total_runs": total}})
    for repeat in range(settings.repeats):
        # Inversarea ordinii intre repetari reduce efectul ordinii fixe.
        for mode in modes if repeat % 2 == 0 else list(reversed(modes)):
            if stop.is_set():
                break
            use_cache = not mode.endswith("no-cache")
            topology = "distributed" if mode.startswith("distributed") else "single"
            url = TARGETS[topology]
            jobs.update_one({"_id": job_id}, {"$set": {"current_mode": mode, "current_repeat": repeat + 1,
                "current_requests": 0, "completed_runs": len(results), "phase": "preparing"}})
            # Ambele configuratii cer Redis disponibil pentru un experiment controlat.
            clear_products()
            if use_cache and settings.cache_state == "warm":
                async with httpx.AsyncClient(timeout=10) as client:
                    for product_id in range(1, settings.products + 1):
                        if stop.is_set():
                            break
                        response = await client.get(f"{url}/products/{product_id}", params={"cache_ttl": settings.ttl})
                        response.raise_for_status()
            if stop.is_set():
                break
            jobs.update_one({"_id": job_id}, {"$set": {"phase": "measuring"}})

            def progress(count):
                jobs.update_one({"_id": job_id}, {"$set": {"current_requests": count}})

            report = await measure(url, settings.requests, settings.concurrency, settings.products,
                                   use_cache, settings.ttl, progress, stop.is_set)
            report.update({"mode": mode, "repeat": repeat + 1, "partial": stop.is_set(), "finished_at": now()})
            results.append(report)
            jobs.update_one({"_id": job_id}, {"$set": {"results": results, "completed_runs": len(results)}})
    jobs.update_one({"_id": job_id}, {"$set": {"status": "cancelled" if stop.is_set() else "completed",
                    "finished_at": now(), "phase": "finished"}})


def work(job_id, settings):
    try:
        asyncio.run(execute(job_id, settings))
    except Exception as exc:
        logger.exception("Experiment esuat")
        jobs.update_one({"_id": job_id}, {"$set": {"status": "failed", "message": str(exc), "finished_at": now()}})
    finally:
        lock.release()


@app.post("/lab/experiments", status_code=202)
def start(settings: Experiment):
    global worker_thread
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "Un experiment rulează deja. Așteaptă finalizarea sau oprește-l.")
    try:
        available = database.products.count_documents({"id": {"$gte": 1, "$lte": settings.products}})
        if available != settings.products:
            raise HTTPException(400, f"Lipsesc produse între ID 1 și {settings.products}. Folosește «Pregătește datele». ")
        redis.ping()
        stop.clear()
        job_id = uuid.uuid4().hex
        jobs.insert_one({"_id": job_id, "created_at": now(), "status": "queued", "configuration": settings.model_dump(),
                         "results": [], "completed_runs": 0, "current_requests": 0,
                         "methodology": {"generator": "dedicated-lab-container", "targets": TARGETS,
                                         "latencies": "successful HTTP responses only", "seed": 42,
                                         "distribution": "uniform IDs 1..N", "timeout_seconds": 10}})
        worker_thread = threading.Thread(target=work, args=(job_id, settings), daemon=True)
        worker_thread.start()
        return {"id": job_id}
    except HTTPException:
        lock.release()
        raise
    except Exception as exc:
        lock.release()
        raise HTTPException(503, "MongoDB sau Redis nu este disponibil pentru test.") from exc


@app.get("/lab/experiments")
def history():
    return [serialize(job) for job in jobs.find().sort("created_at", -1).limit(50)]


def serialize(job):
    job["id"] = job.pop("_id")
    return job


@app.get("/lab/experiments/{job_id}")
def experiment(job_id: str):
    job = jobs.find_one({"_id": job_id})
    if not job:
        raise HTTPException(404, "Experiment inexistent")
    return serialize(job)


@app.post("/lab/experiments/{job_id}/stop")
def cancel(job_id: str):
    job = jobs.find_one({"_id": job_id})
    if not job:
        raise HTTPException(404, "Experiment inexistent")
    if job["status"] in ("queued", "running"):
        stop.set()
    return {"stopping": job["status"] in ("queued", "running")}


@app.get("/lab/status")
async def status():
    state = {"updated_at": now(), "services": {}, "redis": None, "keys": []}
    async with httpx.AsyncClient(timeout=2) as client:
        async def probe(name, url):
            try:
                response = await client.get(url + "/health")
                response.raise_for_status()
                state["services"][name] = {"online": True, "instance": response.json().get("instance")}
            except (httpx.HTTPError, ValueError):
                state["services"][name] = {"online": False}
        await asyncio.gather(probe("API 1", "http://api1:8000"), probe("API 2", "http://api2:8000"),
                             probe("Nginx", "http://gateway"))
    def storage_state():
        try:
            mongo.admin.command("ping")
            state["services"]["MongoDB"] = {"online": True, "products": database.products.estimated_document_count()}
        except Exception:
            state["services"]["MongoDB"] = {"online": False}
        try:
            memory = redis.info("memory")
            state["services"]["Redis"] = {"online": True}
            state["redis"] = {"used_memory": memory.get("used_memory", 0), "maxmemory": memory.get("maxmemory", 0),
                              "keys_total": redis.dbsize(), "policy": memory.get("maxmemory_policy", "—")}
            # Esantion limitat, fara KEYS * pe server.
            cursor, keys = redis.scan(0, match="product:*", count=100)
            state["keys_truncated"] = cursor != 0 or len(keys) > 50
            keys = sorted(keys)[:50]
            pipe = redis.pipeline(transaction=False)
            for key in keys:
                pipe.ttl(key)
                pipe.strlen(key)
            values = pipe.execute()
            state["keys"] = [{"key": key, "ttl": values[i * 2], "bytes": values[i * 2 + 1]}
                             for i, key in enumerate(keys) if values[i * 2] != -2]
        except RedisError:
            state["services"]["Redis"] = {"online": False}
            state["redis"] = None
    await asyncio.to_thread(storage_state)
    return state
