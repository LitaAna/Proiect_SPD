import logging
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field
from pymongo import MongoClient
from redis import Redis
from redis.exceptions import RedisError
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.catalog import CATALOG

logger = logging.getLogger(__name__)
mongo = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"), serverSelectionTimeoutMS=3000)
products = mongo.memory_cache.products
cache = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True,
                       socket_connect_timeout=0.2, socket_timeout=0.2)
TTL = int(os.getenv("CACHE_TTL", "60"))


class Product(BaseModel):
    id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(ge=0, allow_inf_nan=False)
    description: str = Field(default="", max_length=10000)
    category: str = "Altele"
    image: str = "/static/images/headphones.jpg"
    badge: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    products.create_index("id", unique=True)
    yield
    mongo.close()
    cache.close()


app = FastAPI(title="Cache distribuit pentru produse", lifespan=lifespan)
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def homepage():
    return FileResponse(STATIC / "index.html")


@app.get("/proiect", include_in_schema=False)
def project_page():
    return FileResponse(STATIC / "project.html")


@app.get("/catalog", response_model=list[Product])
def catalog():
    return list(products.find({"id": {"$in": [p["id"] for p in CATALOG]}}, {"_id": 0}).sort("id", 1))


@app.post("/demo/catalog")
def seed_catalog():
    """Actualizeaza numai produsele demonstrative 1–8, pastrand restul datelor."""
    from pymongo import UpdateOne
    products.bulk_write([UpdateOne({"id": p["id"]}, {"$set": p}, upsert=True) for p in CATALOG])
    try:
        cache.delete(*(f"product:{p['id']}" for p in CATALOG))
    except RedisError:
        logger.warning("Cache-ul catalogului nu a putut fi invalidat")
    return {"updated": len(CATALOG)}


@app.get("/health")
def health():
    mongo.admin.command("ping")
    try:
        redis_ok = bool(cache.ping())
    except RedisError:
        redis_ok = False
    return {"mongo": True, "redis": redis_ok, "instance": socket.gethostname()}


@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: int, response: Response, use_cache: bool = True,
                cache_ttl: Annotated[int, Query(ge=1, le=600)] = TTL):
    key = f"product:{product_id}"
    response.headers["X-Instance"] = socket.gethostname()
    if use_cache:
        try:
            value = cache.get(key)
            if value:
                response.headers["X-Cache"] = "HIT"
                return Product.model_validate_json(value)
        except RedisError:
            logger.warning("Redis indisponibil; citire din MongoDB")
    product = products.find_one({"id": product_id}, {"_id": 0})
    if product is None:
        raise HTTPException(404, "Produs inexistent")
    result = Product(**product)
    response.headers["X-Cache"] = "MISS" if use_cache else "BYPASS"
    if use_cache:
        try:
            cache.set(key, result.model_dump_json(), ex=cache_ttl)
        except RedisError:
            logger.warning("Rezultatul nu a putut fi salvat in cache")
    return result


@app.put("/products/{product_id}", response_model=Product)
def put_product(product_id: int, product: Product):
    if product_id != product.id:
        raise HTTPException(400, "ID-ul din URL trebuie sa coincida cu ID-ul produsului")
    products.replace_one({"id": product_id}, product.model_dump(), upsert=True)
    try:
        cache.delete(f"product:{product_id}")
    except RedisError:
        logger.warning("Invalidare esuata; datele vechi pot ramane pana la TTL")
    return product


@app.post("/demo/seed")
def seed(count: int = Query(default=1000, ge=1, le=100000)):
    from pymongo import UpdateOne
    operations = [UpdateOne({"id": i}, {"$setOnInsert": {
        "id": i, "name": f"Produs {i}", "price": round(10 + i * 0.13, 2),
        "description": "Produs demonstrativ pentru evaluarea cache-ului. " * 20,
    }}, upsert=True) for i in range(1, count + 1)]
    result = products.bulk_write(operations)
    return {"inserted": result.upserted_count, "requested": count}


@app.delete("/demo/cache")
def clear_cache():
    # Redis este dedicat exclusiv acestui proiect demonstrativ.
    cache.flushdb()
    return {"cleared": True}
