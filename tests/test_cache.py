import unittest
from unittest.mock import Mock, patch

from fastapi import Response
from redis.exceptions import ConnectionError

from app import main


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.product = main.Product(id=1, name="Exemplu", price=10)

    def test_miss_populates_cache_and_hit_skips_database(self):
        with patch.object(main, "cache") as cache, patch.object(main, "products") as products:
            cache.get.return_value = None
            products.find_one.return_value = self.product.model_dump()
            response = Response()
            self.assertEqual(main.get_product(1, response), self.product)
            self.assertEqual(response.headers["X-Cache"], "MISS")
            cache.set.assert_called_once_with("product:1", self.product.model_dump_json(), ex=main.TTL)
            products.find_one.reset_mock()
            cache.get.return_value = self.product.model_dump_json()
            response = Response()
            self.assertEqual(main.get_product(1, response), self.product)
            self.assertEqual(response.headers["X-Cache"], "HIT")
            products.find_one.assert_not_called()

    def test_redis_failure_falls_back_to_database(self):
        with patch.object(main, "cache") as cache, patch.object(main, "products") as products:
            cache.get.side_effect = ConnectionError("offline")
            cache.set.side_effect = ConnectionError("offline")
            products.find_one.return_value = self.product.model_dump()
            self.assertEqual(main.get_product(1, Response()), self.product)

    def test_update_invalidates_cache(self):
        with patch.object(main, "cache") as cache, patch.object(main, "products") as products:
            main.put_product(1, self.product)
            products.replace_one.assert_called_once()
            cache.delete.assert_called_once_with("product:1")


if __name__ == "__main__":
    unittest.main()
