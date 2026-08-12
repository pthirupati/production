"""REST-over-SQL CRUD on the SQL playground sqlite (audit Y3)."""

from django.test import SimpleTestCase

from apps.labs.playground_engine import reset, rest_http_api


class RestOverSqlTests(SimpleTestCase):
    def setUp(self):
        reset("rest-test")

    def tearDown(self):
        reset("rest-test")

    def test_list_products(self):
        status, body = rest_http_api("rest-test", "GET", "/api/products")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(body["items"]), 3)

    def test_create_and_get_product(self):
        status, body = rest_http_api("rest-test", "POST", "/api/products", {
            "sku": "SKU-TEST-1", "name": "Test Part", "price_cents": 100, "stock": 5,
        })
        self.assertEqual(status, 201)
        pid = body["id"]
        status, got = rest_http_api("rest-test", "GET", f"/api/products/{pid}")
        self.assertEqual(status, 200)
        self.assertEqual(got["sku"], "SKU-TEST-1")

    def test_create_order_decrements_stock(self):
        _, products = rest_http_api("rest-test", "GET", "/api/products")
        pid = products["items"][0]["id"]
        before = products["items"][0]["stock"]
        status, order = rest_http_api("rest-test", "POST", "/api/orders", {
            "product_id": pid, "qty": 1,
        })
        self.assertEqual(status, 201)
        _, products2 = rest_http_api("rest-test", "GET", f"/api/products/{pid}")
        self.assertEqual(products2["stock"], before - 1)
        self.assertEqual(order["product_id"], pid)

    def test_unknown_path_404(self):
        status, body = rest_http_api("rest-test", "GET", "/api/widgets")
        self.assertEqual(status, 404)
