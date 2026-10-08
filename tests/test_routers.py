"""Tests for src/routers — HTTP endpoint smoke tests."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestCoreRoutes:
    """Verify core (static) routes respond."""

    def test_about_page(self, client):
        resp = client.get('/about')
        assert resp.status_code in (200, 302)

    def test_services_page(self, client):
        resp = client.get('/our-services')
        assert resp.status_code in (200, 302)

    def test_service_detail_path_traversal(self, client):
        """Path traversal or special character in service_alias should redirect or return 404 safely."""
        resp = client.get('/services/..%2F..%2Fetc')
        assert resp.status_code in (302, 404)

        resp2 = client.get('/services/bad..alias')
        assert resp2.status_code in (302, 404)


class TestShopRoutes:
    """Verify shop routes respond."""

    def test_home_page(self, client):
        resp = client.get('/')
        assert resp.status_code == 200

    def test_shop_list(self, client):
        resp = client.get('/shops')
        assert resp.status_code == 200

    def test_shop_detail_invalid(self, client):
        """Non-existent shop should redirect or return error."""
        resp = client.get('/shops/999999')
        assert resp.status_code in (302, 404)

    def test_new_shop_get(self, auth_client):
        """Admin-protected route — requires auth."""
        resp = auth_client.get('/dashboard/shops/new')
        assert resp.status_code == 200

    def test_new_shop_get_unauthenticated(self, client):
        """Unauthenticated access should redirect to login."""
        resp = client.get('/dashboard/shops/new')
        assert resp.status_code == 302

    def test_search_api(self, client):
        resp = client.get('/api/search?q=test')
        assert resp.status_code == 200

    def test_search_by_tag(self, client):
        """Tag search route should render successfully without template errors."""
        resp = client.get('/search/tag/hardware')
        assert resp.status_code == 200

    def test_tag_mutation_unauthenticated(self, client):
        """Tag modification API must be protected and reject unauthenticated requests."""
        resp = client.post('/api/tag/add', json={'name': 'unauthorized_tag'})
        assert resp.status_code in (302, 401)


class TestBuyerRoutes:
    """Verify buyer routes respond."""

    def test_buyer_list(self, auth_client):
        resp = auth_client.get('/dashboard/buyers')
        assert resp.status_code == 200

    def test_buyer_list_unauthenticated(self, client):
        resp = client.get('/dashboard/buyers')
        assert resp.status_code == 302

    def test_new_buyer_get(self, auth_client):
        resp = auth_client.get('/dashboard/buyers/new')
        assert resp.status_code == 200

    def test_buyer_detail_invalid(self, auth_client):
        resp = auth_client.get('/dashboard/buyers/999999')
        assert resp.status_code in (302, 404)


class TestInventoryRoutes:
    """Verify inventory routes respond."""

    def test_inventory_list(self, auth_client):
        resp = auth_client.get('/dashboard/inventory')
        assert resp.status_code == 200

    def test_new_inventory_get(self, auth_client):
        resp = auth_client.get('/dashboard/inventory/new')
        assert resp.status_code == 200


class TestPurchaseRoutes:
    """Verify purchase routes respond."""

    def test_purchase_list(self, auth_client):
        resp = auth_client.get('/dashboard/purchases')
        assert resp.status_code == 200

    def test_new_purchase_get(self, auth_client):
        resp = auth_client.get('/dashboard/purchases/new')
        assert resp.status_code == 200


class TestSalesRoutes:
    """Verify sales routes respond."""

    def test_sale_list(self, auth_client):
        resp = auth_client.get('/dashboard/sales')
        assert resp.status_code == 200

    def test_new_sale_get(self, auth_client):
        resp = auth_client.get('/dashboard/sales/new')
        assert resp.status_code == 200


class TestWorkOrderRoutes:
    """Verify work order routes respond."""

    def test_work_order_list(self, auth_client):
        resp = auth_client.get('/dashboard/work-orders')
        assert resp.status_code == 200

    def test_new_work_order_get(self, auth_client):
        resp = auth_client.get('/dashboard/work-orders/new')
        assert resp.status_code == 200


class TestLanguageRoute:
    """Verify language switching."""

    def test_set_language_bn(self, client):
        resp = client.get('/set_lang/bn')
        assert resp.status_code == 302  # redirect

    def test_set_language_en(self, client):
        resp = client.get('/set_lang/en')
        assert resp.status_code == 302

    def test_set_language_invalid(self, client):
        resp = client.get('/set_lang/fr')
        assert resp.status_code == 302  # still redirects, just doesn't set


class TestErrorHandlers:
    """Verify error handlers respond correctly."""

    def test_404_html(self, client):
        resp = client.get('/nonexistent-page-xyz')
        assert resp.status_code == 404

    def test_404_api(self, client):
        resp = client.get('/api/nonexistent-xyz')
        assert resp.status_code == 404
        data = resp.get_json()
        assert data is not None
        assert 'error' in data

    def test_405_api(self, client):
        """POST to a GET-only endpoint should return 405."""
        resp = client.post('/api/search')
        assert resp.status_code == 405

    def test_405_handler_redirects_to_existing_endpoint(self, client):
        """405 HTML handler must redirect to a registered endpoint (shops.index)."""
        resp = client.get('/')
        assert resp.status_code == 200
        import inspect
        from main import method_not_allowed, ratelimit_handler
        assert 'shops.index' in inspect.getsource(method_not_allowed)
        assert 'core.index' not in inspect.getsource(method_not_allowed)
        assert 'core.index' not in inspect.getsource(ratelimit_handler)
