import unittest
from unittest.mock import patch

import httpx

from app.benchmark import measure


class BenchmarkTests(unittest.IsolatedAsyncioTestCase):
    async def test_counts_success_errors_hits_and_instances(self):
        client_class = httpx.AsyncClient
        def handle(request):
            if request.url.path.endswith('/1'):
                return httpx.Response(200, json={"id": 1}, headers={"X-Cache": "HIT", "X-Instance": "a"})
            return httpx.Response(404)
        def client(**kwargs):
            return client_class(transport=httpx.MockTransport(handle), **kwargs)
        with patch('app.benchmark.httpx.AsyncClient', side_effect=client):
            report = await measure('http://test', requests=100, concurrency=5, products=2)
        self.assertEqual(report['attempted_requests'], 100)
        self.assertEqual(report['successful_requests'] + report['errors']['404'], 100)
        self.assertEqual(report['instances']['a'], report['successful_requests'])
        self.assertEqual(report['hit_rate'], 1)
        self.assertGreater(report['successful_requests_per_second'], 0)

    async def test_cancelled_before_start_has_no_fake_measurements(self):
        report = await measure('http://test', requests=100, cancelled=lambda: True)
        self.assertEqual(report['attempted_requests'], 0)
        self.assertIsNone(report['mean_ms'])
        self.assertIsNone(report['p95_ms'])
        self.assertIsNone(report['hit_rate'])
