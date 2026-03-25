"""Tests for the FastAPI server endpoints."""

import pytest
from fastapi.testclient import TestClient
from src.api import app


client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "stock-analysis-agent" in data["service"]

    def test_health_has_version(self):
        response = client.get("/")
        data = response.json()
        assert "version" in data


class TestToolsEndpoint:
    def test_tools_returns_list(self):
        response = client.get("/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)
        assert len(data["tools"]) > 0

    def test_tools_have_required_fields(self):
        response = client.get("/tools")
        data = response.json()
        for tool in data["tools"]:
            assert "name" in tool
            assert "desc" in tool


class TestAnalyzeEndpoint:
    def test_analyze_requires_query(self):
        response = client.post("/analyze", json={})
        assert response.status_code == 422  # FastAPI validation error

    def test_analyze_unknown_symbol_rejected(self):
        response = client.post("/analyze", json={"query": "xyzzyxyz"})
        assert response.status_code == 400  # Unknown symbol

    def test_analyze_returns_data_for_valid_symbol(self):
        response = client.post("/analyze", json={
            "query": "analysis",
            "symbol": "AAPL",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert "report" in data or "tool_results" in data

    def test_analyze_llm_mode_flag(self):
        response = client.post("/analyze", json={
            "query": "analysis",
            "symbol": "AAPL",
            "llm": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "data"

    def test_analyze_query_required_message(self):
        response = client.post("/analyze", json={"symbol": "AAPL"})
        assert response.status_code == 422

    def test_analyze_get_method(self):
        response = client.get("/analyze", params={
            "query": "analysis",
            "symbol": "AAPL",
        })
        assert response.status_code == 200

    def test_analyze_period_parameter(self):
        response = client.post("/analyze", json={
            "query": "analysis",
            "symbol": "AAPL",
            "period": "1y",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "1y"
