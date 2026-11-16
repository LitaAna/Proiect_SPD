"""Verificare integrata optionala. Necesita Docker Compose pornit."""
import json
import time
import urllib.error
import urllib.request

BASE = "http://localhost:8080"


def call(path, payload=None):
    request = urllib.request.Request(BASE + path, data=json.dumps(payload).encode() if payload is not None else None,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def finished(job_id):
    for _ in range(100):
        job = call('/lab/experiments/' + job_id)
        if job['status'] not in ('running', 'queued'):
            return job
        time.sleep(0.2)
    raise AssertionError('Experimentul nu s-a incheiat la timp')


settings = {"requests": 10000, "concurrency": 5, "products": 8, "repeats": 1,
            "mode": "single-cache", "cache_state": "cold", "ttl": 60}
job_id = call('/lab/experiments', settings)['id']
try:
    call('/lab/experiments', settings)
except urllib.error.HTTPError as error:
    assert error.code == 409, error.code
else:
    raise AssertionError('Doua experimente au fost acceptate simultan')
call('/lab/experiments/' + job_id + '/stop', {})
assert finished(job_id)['status'] == 'cancelled'
settings.update(requests=100, cache_state='warm', repeats=2)
job_id = call('/lab/experiments', settings)['id']
job = finished(job_id)
assert job['status'] == 'completed', job
assert len(job['results']) == 2
for run in job['results']:
    assert run['successful_requests'] == 100
    assert not run['errors']
    assert run['hit_rate'] == 1, run
assert any(saved['id'] == job_id for saved in call('/lab/experiments'))
print('OK: refuz teste simultane, oprire, preincalzire, doua repetari, rezultate persistate.')
