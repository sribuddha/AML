import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.bff.config import BASE_DIR
from src.bff.routes.generate import _run_step

WORK_DIR = BASE_DIR / "work"


@pytest.fixture
def client():
    app = FastAPI()
    from src.bff.routes.generate import router
    app.include_router(router)
    with TestClient(app) as c:
        yield c


class TestRunStep:
    @patch("scripts.generate_upload_data.generate", new_callable=AsyncMock)
    async def test_upload_step(self, mock_gen, tmp_path):
        step = {"type": "upload", "count": 10, "bad_rate": 5}
        output = tmp_path / "out.csv"
        await _run_step(step, "2026-05-01", output)
        mock_gen.assert_called_once_with(10, 5, "2026-05-01", output)

    @patch("scripts.generate_stage1_fraud_data.generate", new_callable=AsyncMock)
    async def test_stage1_step(self, mock_gen, tmp_path):
        step = {"type": "stage1", "count": 20, "bad_rate": 0}
        output = tmp_path / "out.csv"
        await _run_step(step, "2026-05-01", output)
        mock_gen.assert_called_once_with(20, "2026-05-01", output)

    @patch("scripts.generate_stage2_fraud_data.generate", new_callable=AsyncMock)
    async def test_stage2_step(self, mock_gen, tmp_path):
        step = {"type": "stage2", "count": 15, "bad_rate": 0}
        output = tmp_path / "out.csv"
        await _run_step(step, "2026-05-01", output)
        mock_gen.assert_called_once_with(15, "2026-05-01", output)

    @patch("scripts.test_generate_fraud_data.generate", new_callable=AsyncMock)
    async def test_synthetic_step(self, mock_gen, tmp_path):
        step = {"type": "synthetic", "count": 30, "bad_rate": 0}
        output = tmp_path / "out.csv"
        await _run_step(step, "2026-05-01", output)
        manifest = output.with_suffix(".manifest.json")
        mock_gen.assert_called_once_with(30, str(output), str(manifest), False)

    async def test_unknown_step(self, tmp_path):
        step = {"type": "unknown", "count": 1, "bad_rate": 0}
        output = tmp_path / "out.csv"
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await _run_step(step, "2026-05-01", output)
        assert exc.value.status_code == 400


class TestGenerateEndpoint:
    def test_generate_no_steps(self, client):
        resp = client.post("/api/generate", json={"steps": []})
        assert resp.status_code == 400
        assert "At least one step" in resp.json()["detail"]

    @patch("src.bff.routes.generate._run_step", new_callable=AsyncMock)
    def test_generate_success(self, mock_run, client):
        resp = client.post("/api/generate", json={"steps": [{"type": "upload", "count": 10}]})
        assert resp.status_code == 200
        data = resp.json()
        assert "download_url" in data
        assert "filename" in data

    @patch("src.bff.routes.generate._run_step", new_callable=AsyncMock)
    def test_generate_file_download_found(self, mock_run, client, tmp_path):
        csv_file = WORK_DIR / "test_download.csv"
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        csv_file.write_text("col1,col2\nval1,val2\n")

        resp = client.get("/api/generate/download/test_download.csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_generate_file_download_not_found(self, client):
        resp = client.get("/api/generate/download/nonexistent.csv")
        assert resp.status_code == 404

    def test_generate_eval_file_found(self, client, tmp_path):
        eval_file = WORK_DIR / "test_eval.csv"
        eval_file.parent.mkdir(parents=True, exist_ok=True)
        eval_file.write_text("")
        eval_path = eval_file.with_suffix(".eval")
        eval_path.write_text(json.dumps({"source_txn_id": "T1", "expected_escalate": True}) + "\n")

        resp = client.get("/api/generate/eval/test_eval.csv")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["source_txn_id"] == "T1"

    def test_generate_eval_manifest_found(self, client, tmp_path):
        manifest = WORK_DIR / "test_manifest.csv"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("")
        manifest_path = manifest.with_suffix(".manifest.json")
        manifest_path.write_text(json.dumps({"TXN001": "high_value"}))

        resp = client.get("/api/generate/eval/test_manifest.csv")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["source_txn_id"] == "TXN001"

    def test_generate_eval_not_found(self, client):
        resp = client.get("/api/generate/eval/nonexistent.csv")
        assert resp.status_code == 404

    def test_preview_csv_found(self, client, tmp_path):
        csv_file = WORK_DIR / "test_preview.csv"
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        csv_file.write_text("col1,col2\nv1,v2\nv3,v4\n")

        resp = client.get("/api/generate/preview/test_preview.csv")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fieldnames"] == ["col1", "col2"]
        assert len(data["rows"]) == 2

    def test_preview_csv_not_found(self, client):
        resp = client.get("/api/generate/preview/nonexistent.csv")
        assert resp.status_code == 404

    def test_preview_csv_limit(self, client, tmp_path):
        csv_file = WORK_DIR / "test_preview_limit.csv"
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        lines = ["col1"] + [f"v{i}" for i in range(10)]
        csv_file.write_text("\n".join(lines))

        resp = client.get("/api/generate/preview/test_preview_limit.csv?limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["rows"]) == 3
