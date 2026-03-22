"""Integration tests for notification preferences and alert rule API endpoints."""
import pytest


class TestNotificationPrefsAPI:
    def test_get_prefs_default(self, app_client):
        resp = app_client.get("/api/notifications/preferences", headers={"X-User-Id": "testuser"})
        assert resp.status_code == 200
        data = resp.json()
        assert "emails" in data
        assert "smtp_configured" in data

    def test_save_and_get_prefs(self, app_client):
        resp = app_client.post("/api/notifications/preferences",
            json={"emails": ["a@b.com", "c@d.com"]},
            headers={"X-User-Id": "testuser"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["emails"] == ["a@b.com", "c@d.com"]

        resp2 = app_client.get("/api/notifications/preferences", headers={"X-User-Id": "testuser"})
        assert resp2.json()["emails"] == ["a@b.com", "c@d.com"]

    def test_prefs_dedup(self, app_client):
        resp = app_client.post("/api/notifications/preferences",
            json={"emails": ["A@B.com", "a@b.com", "  A@B.COM  "]},
            headers={"X-User-Id": "testuser"})
        assert resp.status_code == 200
        assert resp.json()["emails"] == ["a@b.com"]


class TestAlertChannelsAPI:
    def test_get_channels(self, app_client):
        resp = app_client.get("/api/alerts/channels", headers={"X-User-Id": "testuser"})
        assert resp.status_code == 200
        data = resp.json()
        assert "email" in data
        assert "telegram" in data


class TestExpiryRulesAPI:
    def test_get_empty_rules(self, app_client):
        resp = app_client.get("/api/expiry-rules", headers={"X-User-Id": "testuser"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_rule(self, app_client):
        resp = app_client.post("/api/expiry-rules",
            json={"category": "fd", "rule_type": "days_before_maturity", "days": 30},
            headers={"X-User-Id": "testuser"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "fd"
        assert data["rule_type"] == "days_before_maturity"
        assert data["days"] == 30
        assert data["enabled"] is True
        assert data["id"]

    def test_create_and_list_rules(self, app_client):
        app_client.post("/api/expiry-rules",
            json={"category": "fd", "rule_type": "on_maturity"},
            headers={"X-User-Id": "testuser"})
        app_client.post("/api/expiry-rules",
            json={"category": "rd", "rule_type": "days_before_maturity", "days": 15},
            headers={"X-User-Id": "testuser"})

        resp = app_client.get("/api/expiry-rules", headers={"X-User-Id": "testuser"})
        assert len(resp.json()) == 2

    def test_filter_by_category(self, app_client):
        app_client.post("/api/expiry-rules",
            json={"category": "fd", "rule_type": "on_maturity"},
            headers={"X-User-Id": "testuser"})
        app_client.post("/api/expiry-rules",
            json={"category": "si", "rule_type": "on_expiry"},
            headers={"X-User-Id": "testuser"})

        resp = app_client.get("/api/expiry-rules", params={"category": "fd"},
            headers={"X-User-Id": "testuser"})
        rules = resp.json()
        assert len(rules) == 1
        assert rules[0]["category"] == "fd"

    def test_delete_rule(self, app_client):
        resp = app_client.post("/api/expiry-rules",
            json={"category": "ppf", "rule_type": "on_maturity"},
            headers={"X-User-Id": "testuser"})
        rule_id = resp.json()["id"]

        del_resp = app_client.delete(f"/api/expiry-rules/{rule_id}",
            headers={"X-User-Id": "testuser"})
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] == rule_id

    def test_delete_nonexistent(self, app_client):
        resp = app_client.delete("/api/expiry-rules/nonexistent",
            headers={"X-User-Id": "testuser"})
        assert resp.status_code == 404

    def test_get_rule_types(self, app_client):
        resp = app_client.get("/api/expiry-rules/types", headers={"X-User-Id": "testuser"})
        assert resp.status_code == 200
        data = resp.json()
        assert "fd" in data
        assert "rd" in data
        assert "si" in data
        assert "insurance" in data


class TestUserSettingsAPI:
    def test_get_defaults(self, app_client):
        resp = app_client.get("/api/user-settings", headers={"X-User-Id": "testuser"})
        assert resp.status_code == 200
        assert resp.json()["page_refresh_interval"] == 600

    def test_save_and_get(self, app_client):
        resp = app_client.post("/api/user-settings",
            json={"page_refresh_interval": 300},
            headers={"X-User-Id": "testuser"})
        assert resp.status_code == 200
        assert resp.json()["page_refresh_interval"] == 300

        resp2 = app_client.get("/api/user-settings", headers={"X-User-Id": "testuser"})
        assert resp2.json()["page_refresh_interval"] == 300
