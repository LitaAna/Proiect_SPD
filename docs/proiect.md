# Proiectarea si evaluarea unui sistem de cache distribuit pentru o aplicatie web

## Problema si obiective

Citirile repetate ale produselor produc accesari repetate ale bazei de date. Proiectul studiaza daca un cache comun in memorie reduce timpul de raspuns si cum influenteaza distribuirea cererilor performanta.

## Arhitectura de referinta

Client → o instanta API → MongoDB. Fiecare cerere citeste baza principala. Acesta este fluxul secvential al unei cereri; serverul poate procesa cereri concurente chiar si cu o singura instanta.

## Arhitectura distribuita

Client → Nginx → API 1 / API 2 → Redis comun → MongoDB la cache miss.

Instantele API sunt procese independente. Redis si MongoDB sunt servicii separate, accesate prin retea. Redis pastreaza copii temporare; MongoDB pastreaza datele persistente. Nginx distribuie cererile. Redis nu este impartit in shard-uri in aceasta versiune.

## Tehnologii

- Python/FastAPI: API HTTP; operatiile sincrone sunt executate de framework intr-un pool de fire.
- MongoDB: documente persistente si index unic pentru ID-ul produsului.
- Redis: chei `product:{id}`, valori JSON, TTL si limita de memorie de 128 MB cu allkeys-lru.
- Nginx: distribuirea cererilor intre instante.
- Docker Compose: mediu reproductibil cu servicii separate.
- HTTPX/asyncio: generator de incarcare cu mai multi clienti concurenti.

## Metodologie experimentala

Panoul `/proiect` permite acum lansarea experimentelor, urmarirea progresului, consultarea graficelor si exportul JSON/CSV. Serviciul `lab` genereaza cereri HTTP folosind acelasi motor ca scriptul CLI (`app/benchmark.py`), intr-un container separat de tintele masurate. Rezultatele sunt salvate in colectia MongoDB `experiments`.

Ambele configuratii masurate de dashboard trec prin Nginx. Ruta `/single/` foloseste o singura instanta; ruta normala foloseste doua. Fiecare rulare incepe cu cheile produselor sterse, apoi optional preincarcate. Ordinea configuratiilor este inversata intre repetari. Se pastreaza distributia uniforma reproductibila a ID-urilor. TTL poate fi configurat per experiment; acesta nu modifica permanent TTL-ul implicit al catalogului.

In raport trebuie precizat ca timpii dashboardului provin din containerul laborator, iar testele CLI locale provin din Windows. Nu se combina aceste masuratori intr-o singura comparatie. Graficele arata media indicatorilor pe rulari; inclusiv media p95, nu percentila globala. Istoricul marcheaza testele oprite, esuate sau intrerupte. Masuratorile scurte de verificare nu sunt rezultate finale.

Compara cele patru combinatii: una/doua instante, fara/cu cache. Separa cache gol de cache cald. Foloseste aceleasi date si aceeasi distributie de cereri; fixeaza concurenta, volumul cererilor si TTL. Repeta testele de minimum trei ori. Documenteaza CPU, RAM, versiunile software si limitarile resurselor Docker. Generatorul de trafic ruleaza pe acelasi calculator, ceea ce poate influenta rezultatele.

Masoara latenta medie, p95, cereri reusite pe secunda, erori si rata de hit. Pentru memorie colecteaza separat `docker compose exec redis redis-cli INFO memory` si `docker stats --no-stream`. Acestea sunt instantanee, nu varfuri masurate continuu.

## Optimizari de evaluat ulterior

1. TTL 10/60/300 secunde: rata de hit si actualitatea datelor.
2. Set activ de 100/1000/10000 produse: efectul reutilizarii datelor.
3. Concurenta 1/10/50/100: identificarea limitelor de scalare.

## Rezultate

Verificare preliminara din 10 noiembrie 2026, doua instante API, 10.000 produse in MongoDB, 500 cereri distribuite uniform peste 100 produse, concurenta 10:

| Configuratie | Cereri reusite/s | Medie ms | p95 ms | Erori | Rata hit |
|---|---:|---:|---:|---:|---:|
| Fara cache | 324,35 | 27,95 | 92,38 | 0 | — |
| Cu cache | 360,39 | 25,69 | 80,51 | 0 | 80% |

Acestea sunt teste scurte de functionare, cu o singura rulare per configuratie, nu rezultate finale sau o demonstratie statistica a accelerarii. Fisierele brute sunt in `results/smoke-no-cache.json` si `results/smoke-cache.json`. Sunt necesare repetari, controlul incalzirii si celelalte configuratii inainte de concluzii.

## Structura prezentarii

1. Problema si obiective.
2. Fluxul de referinta.
3. Arhitectura distribuita.
4. Cache-aside, TTL si invalidare.
5. Demonstratie practica.
6. Metodologia experimentala.
7. Grafice cu rezultate reale.
8. Optimizari, limite si concluzii.
