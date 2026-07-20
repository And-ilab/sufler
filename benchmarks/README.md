# Sufler benchmarks

## ASR hotword benchmark

Suite `suites/asr_hotword.py` maps to **FR-ASR-09**: specialized dictionaries
must improve recognition of banking terms, abbreviations, and contractions.

The canonical dataset is `datasets/asr_bank_terms.json` and contains exactly
50 terms. The benchmark compares two transcript sets generated from the same
audio samples:

1. ASR without hotword boost;
2. the same ASR/model/configuration with the banking dictionary enabled.

The suite evaluates results; it does not fabricate transcripts or emulate a
vendor-specific boost implementation.

### Recognition input

Both input files use dataset IDs:

```json
{
  "recognitions": [
    {
      "id": "bank-001",
      "text": "оплата через ерип"
    },
    {
      "id": "bank-002",
      "text": "подключить м банкинг"
    }
  ]
}
```

A compact object is also supported:

```json
{
  "bank-001": "оплата через ерип",
  "bank-002": "подключить м банкинг"
}
```

Missing transcripts count as incorrect. Unknown or duplicate IDs fail the
benchmark to prevent comparing different samples.

### Run

From the repository root:

```powershell
.\backend\.venv\Scripts\python.exe .\benchmarks\suites\asr_hotword.py `
  --without-boost .\path\without_boost.json `
  --with-boost .\path\with_boost.json `
  --output .\benchmarks\results\asr_hotword.json
```

The report contains accuracy for both modes, improvement in percentage points,
missing transcript IDs, and per-term recognition details. It is the
machine-readable input for the ASR evaluation report.

### Verification

```powershell
.\backend\.venv\Scripts\python.exe -m pytest `
  .\tests\benchmarks\test_asr_hotword.py -v
```
