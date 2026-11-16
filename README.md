# Memory cache pentru aplicații web — evaluare într-o arhitectură distribuită

Proiect individual de sisteme paralele și distribuite. Aplicația implementează accesul la un catalog de produse printr-un cache NoSQL Redis comun mai multor instanțe API și evaluează impactul cache-ului și al distribuirii cererilor asupra performanței.

## Arhitectură și tehnologii

```text
Browser / generator HTTP → Nginx → API 1 / API 2 → Redis (cache)
                                              → MongoDB (date persistente)
```

| Componentă | Rol |
|---|---|
| Python 3.12, FastAPI, Uvicorn | API HTTP; validare Pydantic; acces sincron la stocare, executat în thread pool |
| MongoDB 7.0, PyMongo | Persistența produselor și experimentelor; index unic pe `products.id` |
| Redis 7.4 | Cache partajat; limită 128 MB; politică de evacuare `allkeys-lru` |
| Nginx | Reverse proxy și distribuire round-robin între două instanțe API |
| Serviciul `lab`, HTTPX, asyncio | Generator HTTP concurent separat de instanțele măsurate |
| Docker Compose | Orchestrarea celor șase servicii; rețea internă și volum persistent MongoDB |

Sistemul este distribuit la nivel de servicii și procese; configurația experimentală rulează integral pe același calculator. O singură instanță API poate procesa cereri concurente și nu reprezintă execuție strict secvențială.

## Mecanism de cache

Strategie **cache-aside** pentru `GET /products/{id}`: la `HIT`, răspunsul este deserializat din Redis; la `MISS`, produsul este citit din MongoDB și memorat ca JSON sub cheia `product:{id}`. TTL implicit: **60 s**, configurabil per cerere între 1 și 600 s. `use_cache=false` produce `BYPASS`, cu citire directă din MongoDB. Antetele `X-Cache` și `X-Instance` identifică sursa și instanța răspunsului.

`PUT /products/{id}` actualizează MongoDB și invalidează cheia asociată. La indisponibilitatea Redis, citirile continuă din MongoDB. Lista `/catalog` este citită direct din MongoDB; benchmark-ul măsoară exclusiv detaliile produselor.

## Evaluare experimentală

Panoul `/proiect` oferă starea serviciilor, memoria Redis, un eșantion de chei cu TTL, lansarea și oprirea experimentelor, grafice, istoric MongoDB și export JSON/CSV. Catalogul `/` este aplicația demonstrativă; `/docs` oferă documentația interactivă API.

Se compară **1 API / 2 API × cu cache / fără cache**, prin același Nginx: `/single/` direcționează exclusiv către API 1, iar ruta normală distribuie către ambele instanțe. Rulările sunt succesive, cu cache inițial gol sau preîncărcat, ID-uri uniforme și seed 42. Motorul comun este `app/benchmark.py`; `scripts/benchmark.py` permite execuție CLI.

Indicatori: latență medie, p95, cereri reușite/s, rată HIT, erori și distribuția răspunsurilor între instanțe. Latențele includ numai răspunsurile HTTP 200. Graficele agregă mediile indicatorilor per rulare; media p95 nu este percentila globală. Rezultatele CLI din Windows se analizează separat de cele generate în container.

**Evaluarea realizată:** 5.000 cereri/rulare, 100 produse, TTL 60 s, concurență 1/10/50, trei repetări pentru fiecare dintre cele patru configurații: **36 rulări, 180.000 cereri, zero erori**. Redis a redus latența medie cu **4,81–17,24%**, cu rată HIT **97,92–98%**. Două instanțe au oferit avantaje mai pronunțate la 50 de clienți; la 10 clienți, p95 a crescut față de o instanță. Date brute: `results/evaluare-clienti-{1,10,50}.json`.

## Rulare

Necesită Docker Desktop cu motorul pornit. Din directorul proiectului, în PowerShell:

```powershell
docker compose up --build -d
Invoke-RestMethod -Method Post 'http://localhost:8080/demo/seed?count=10000'
Invoke-RestMethod -Method Post 'http://localhost:8080/demo/catalog'
```

- Catalog: http://localhost:8080/
- Laborator și rezultate: http://localhost:8080/proiect
- Documentație API: http://localhost:8080/docs

Oprire: `docker compose down`; datele MongoDB rămân în volum. Încărcarea catalogului restaurează produsele demonstrative 1–8; se execută înaintea experimentelor.

## Limite

Prototip local fără autentificare, replicare sau failover. Invalidarea nu garantează consistență strictă la citiri și scrieri concurente; dacă invalidarea eșuează, datele vechi pot rămâne până la expirare. Serviciile partajează resursele calculatorului; trei repetări și un singur mediu nu permit generalizarea performanțelor.
