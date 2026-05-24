# Testing Instructions

- [Prerequisites](#prerequisites)
- [Kick Off](#kick-off)
  - [Basic Run](#basic-run)
  - [Triage Run](#triage-run)
  - [Full Run (with SAR)](#full-run-with-sar)
- [Human Review](#human-review)

---

## Prerequisites

1. Seed the database:

```powershell
python -m scripts.seed_db
```

2. Start the server:

```powershell
python -m uvicorn src.bff.app:app --reload --port 8000
```

3. Set your API key in `.env` (triage / full runs only).

---

## Kick Off

### Basic Run

1. Generate files:

```powershell
python -m scripts.generate_upload_data --count 20 --bad-rate 2 --output work\test.csv
```

2. Append transactions that trigger deterministic rules:

```powershell
python -m scripts.generate_stage1_fraud_data --count 6 --output work\test.csv
```

3. Shuffle so flagged rows aren't clustered:

```powershell
python -m scripts.data_scrambler work\test.csv
```

4. Upload:

```powershell
$r = curl.exe -s -X POST http://localhost:8000/api/uploads -F "file=@work\test.csv" | ConvertFrom-Json
$id = $r.upload_id
```

5. Validate:

```powershell
python -m scripts.report_upload --upload-id $id
```

---

### Triage Run

1. Generate CSV only:

```powershell
python -m scripts.generate_triage_dataset --count 300 --clean-count 100 --days 60 --triage-only --generate-only
```

2. Upload:

```powershell
$r = curl.exe -s -X POST http://localhost:8000/api/uploads -F "file=@work\triage.csv" | ConvertFrom-Json
$id = $r.upload_id
```

3. Validate:

```powershell
python -m scripts.report_upload --upload-id $id
```

4. Compare LLM against expectations:

```powershell
python -m scripts.evaluate_stage2 --upload-id $id --eval work\triage.eval
```

---

### Full Run (with SAR)

1. Generate CSV only:

```powershell
python -m scripts.generate_triage_dataset --count 300 --clean-count 100 --days 60 --generate-only
```

2. Upload:

```powershell
$r = curl.exe -s -X POST http://localhost:8000/api/uploads -F "file=@work\triage.csv" | ConvertFrom-Json
$id = $r.upload_id
```

3. Validate:

```powershell
python -m scripts.report_upload --upload-id $id
```

4. Compare LLM against expectations:

```powershell
python -m scripts.evaluate_stage2 --upload-id $id --eval work\triage.eval
```

---

## Human Review

1. List SARs pending review:

```powershell
curl.exe -s "http://localhost:8000/api/sar?upload_id=$id&status=pending_review" | ConvertFrom-Json | Select-Object -ExpandProperty items | Format-Table id, transaction_id, status, content
```

2. Review a single SAR:

```powershell
curl.exe -s -X PATCH "http://localhost:8000/api/sar/<sar-id>/review" -H "Content-Type: application/json" -d '{\"action\":\"approve\",\"notes\":\"Approved\"}'
```

3. Or approve all pending:

```powershell
$ids = curl.exe -s "http://localhost:8000/api/sar?upload_id=$id&status=pending_review" | ConvertFrom-Json | Select-Object -ExpandProperty items
$ids | ForEach-Object {
  $body = @{action="approve"; notes="Approved"}
  $r = Invoke-RestMethod -Uri "http://localhost:8000/api/sar/$($_.id)/review" -Method PATCH -ContentType "application/json" -Body ($body | ConvertTo-Json -Compress)
  Write-Host "$($_.id): $($r.status)"
}
```
