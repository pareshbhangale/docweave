# docweave: AI-Supervised PDF-to-Markdown Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![TypeSafe System One](https://img.shields.io/badge/TypeSafe-Jev%20%2F%20Laya-purple.svg)](https://typesafe.ai)
[![Local CLM System One](https://img.shields.io/badge/Contrastive--LM-CLM--8B-orange.svg)](https://github.com/Contrastive-LM/CLM)
[![Local LLM Compatible](https://img.shields.io/badge/Local%20LLM-Ollama%20%7C%20vLLM%20%7C%20LM%20Studio-green.svg)](https://ollama.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI-Supervised PDF-to-Markdown with TypeSafe (Jev / Laya), Local Contrastive Language Models (CLM-8B), and OpenAI-compatible local models (Ollama, vLLM, LM Studio) for semantic layout routing and financial table QA auditing.**

While standard pipelines rely solely on local geometry heuristics, `docweave` adds an intelligent AI supervision layer designed specifically for complex financial filings (SEBI/SEC notices, annual reports, debt circulars):

1. **Batched Ambiguity Routing**: High-confidence pages (pure prose or dense balance sheets) take the instant local fast-path ($<0.5\,\text{ms}$). Borderline pages (decorative letterheads, border boxes, schedules) are resolved collectively in **one single batched request** using TypeSafe (Jev/Laya), Local CLM-8B, or any local OpenAI-compatible model (Ollama, vLLM, LM Studio).
2. **In-Flight Financial Table QA Audit**: Converted financial tables are audited in-flight with Jev / CLM Noul (corruption probability) & Score (structural fidelity), immediately flagging mangled columns or lost decimal alignments for human escalation.

---

## 🏛️ Architecture

<p align="center">
  <img src="assets/architecture.jpg" alt="docweave AI-Supervised Architecture Diagram" width="100%">
</p>

```mermaid
flowchart TD
    PDF["📄 Input PDF Document"] --> FastInspect["⚡ Fast Geometry Pre-Filter (<0.5ms/page)<br/>(C-level PyMuPDF Char/Image/Line Counter)"]

    FastInspect -->|"Clear Prose (no borders/tables)"| FastText["⚡ Native Vector Parser (PyMuPDF4LLM)<br/>(<10ms/page, Zero Network)"]
    FastInspect -->|"Obvious Dense Grid / Balance Sheet"| DoclingTable["🧠 Docling TableFormer Stream<br/>(In-Memory Sub-PDF, Zero Disk I/O)"]
    FastInspect -->|"Borderline / Ambiguous Pages"| BatchRouter["🔍 Single-Pass Batch AI Classifier<br/>(1 HTTP Call for All Ambiguous Pages)"]

    subgraph AISupervision ["AI Supervision Providers (Pluggable)"]
        BatchRouter --> TypeSafe["☁️ TypeSafe System One (Jev / Laya)"]
        BatchRouter --> CLM["⚡ Local CLM (Contrastive-LM / Apple Silicon)"]
        BatchRouter --> LocalOllama["💻 Local Ollama / vLLM (Air-Gapped)"]
        BatchRouter --> CloudLLM["🌐 OpenAI / OpenRouter Compatible"]
    end

    BatchRouter -->|"Prose / Notice"| FastText
    BatchRouter -->|"Financial Table / Schedule"| DoclingTable

    FastText --> Stitcher["📑 Continuous Document Stitcher"]
    DoclingTable --> Stitcher

    DoclingTable --> TableQA["🛡️ Targeted Table QA Audit<br/>(Noul Corruption Prob + Fidelity Score)"]
    TableQA -->|"Score < 0.8 or Corrupt > 0.5"| FlagEscalate["⚠️ Flag Page for Human Review"]
    TableQA -->|"Clean Table"| Stitcher

    Stitcher --> OutputMD["📝 Unified Clean Markdown (.md)"]
```

---

## 📊 Benchmark: TypeSafe Jev vs. Local Contrastive-LM (CLM-8B)

We evaluated **TypeSafe Jev** (Cloud System One) against **Local CLM-8B** (Contrastive Language Model running on Apple Silicon via MPS) across real-world Indian regulatory filings (SEBI disclosures, audited balance sheets, AGM circulars, and financial table conversions).

### ⚡ Speed Comparison

| Metric | TypeSafe Jev (Cloud) | Local CLM-8B (Apple Silicon) | Advantage |
| :--- | :---: | :---: | :---: |
| **Total Test Suite Time** | `4,687.8 ms` | **`940.2 ms`** | **CLM is 4.99× faster** |
| **Average Query Latency** | `781.3 ms` | **`156.7 ms`** | **~5× lower latency** |
| **Fastest Single Decision** | `340.8 ms` | **`40.7 ms`** | **8.4× lower latency** |
| **Network & Privacy** | Cloud API (Subject to TLS/RTT) | 100% Local / Air-Gapped | Complete data privacy |

### 🎯 Semantic Routing & Table QA Accuracy

| Benchmark Case | Description | Ground Truth | TypeSafe Jev | Local CLM-8B (Zero-Shot) |
| :--- | :--- | :---: | :---: | :---: |
| **`case_1_balance_sheet`** | Standalone Audited Balance Sheet | `TABLE` | **`TABLE`** (100% conf) ✓ | `TEXT` (48.7% vs 7.4%) ✗ |
| **`case_2_agm_notice`** | AGM Notice with decorative lines | `TEXT` | **`TEXT`** (100% conf) ✓ | **`TEXT`** (50.9% vs 6.8%) ✓ |
| **`case_3_shareholding_pattern`** | Tabular SEBI Reg 31 Breakdown | `TABLE` | **`TABLE`** (87% conf) ✓ | `TEXT` (55.9% vs 6.4%) ✗ |
| **`case_4_director_report_prose`**| Narrative Management Discussion | `TEXT` | **`TEXT`** (100% conf) ✓ | **`TEXT`** (55.7% vs 6.1%) ✓ |
| **`case_5_table_qa_clean`** | High-Fidelity Clean Markdown Table | `Clean` | **`p=0.05`** (Clean) ✓ | `p=0.57` (Borderline) ✗ |
| **`case_6_table_qa_corrupted`** | Scrambled Table (Missing columns) | `Corrupted` | **`p=0.94`** (Corrupt) ✓ | **`p=0.62`** (Corrupt) ✓ |
| **Decision Accuracy** | — | — | **6 / 6 (100%)** | **3 / 6 (50.0%)** |

> **Key Takeaway**:
> - **Speed**: Local CLM-8B runs **5× faster** than cloud-based Jev, dropping to **~40ms** once candidate embeddings are cached.
> - **Accuracy**: **TypeSafe Jev** provides **100% accuracy** out of the box because it was specifically pre-trained on structured document and table schemas.
> - **Fine-tuning**: For maximum speed and air-gapped security, CLM's projection heads can be fine-tuned (`python train/finetune.py --task choice`) with domain-specific financial prompts to achieve Jev's 100% accuracy while keeping CLM's sub-100ms local execution speed.

To reproduce this benchmark:
```bash
python run_benchmark.py
```

---

## ⚙️ Configuration & Model Providers

`docweave` supports multiple providers configured via `config.json` (copy from `config.template.json`) or environment variables. It works seamlessly with **cloud APIs** as well as **100% offline local models**:

### 1. Copy Config Template
```bash
cp config.template.json config.json
```

### 2. Available Providers in `config.json`:

```json
{
  "active_provider": "clm",
  "providers": {
    "clm": {
      "name": "Local Contrastive Language Model (CLM-8B System One)",
      "endpoint": "http://127.0.0.1:8700/v1/systemone",
      "api_key": "local",
      "model": "clm-latest",
      "timeout": 10.0
    },
    "typesafe": {
      "name": "TypeSafe System One (Jev / Laya)",
      "endpoint": "https://api.typesafe.ai/v1/systemone",
      "api_key": "your-typesafe-key",
      "model": "jev-latest",
      "timeout": 12.0
    },
    "local_ollama": {
      "name": "Local Ollama (Air-Gapped / Privacy)",
      "endpoint": "http://localhost:11434/v1/chat/completions",
      "api_key": "ollama",
      "model": "llama3.2:latest",
      "timeout": 30.0
    },
    "local_vllm": {
      "name": "Local vLLM / LM Studio",
      "endpoint": "http://localhost:8000/v1/chat/completions",
      "api_key": "not-needed",
      "model": "meta-llama/Llama-3.2-3B-Instruct",
      "timeout": 30.0
    },
    "openai": {
      "name": "OpenAI / OpenRouter",
      "endpoint": "https://api.openai.com/v1/chat/completions",
      "api_key": "your-openai-key",
      "model": "gpt-4o-mini",
      "timeout": 15.0
    }
  }
}
```

### 3. Quick Switch via Environment Variables
```bash
# Use Local CLM (Apple Silicon / Air-Gapped)
export DOCWEAVE_PROVIDER="clm"

# Use TypeSafe (Jev / Laya Cloud)
export DOCWEAVE_PROVIDER="typesafe"
export TYPESAFE_API_KEY="your-api-key"

# Use Local Ollama (Free & Offline)
export DOCWEAVE_PROVIDER="local_ollama"

# Use Local vLLM / LM Studio
export DOCWEAVE_PROVIDER="local_vllm"
```

---

## 🚀 Installation & Usage

### Installation
```bash
pip install -e .
```

### CLI
```bash
# Convert with active AI supervision and table auditing
docweave input.pdf -o output.md

# Convert with table auditing disabled
docweave input.pdf --no-qa -o output.md

# Custom hardware acceleration
docweave input.pdf --threads 10 --batch-size 16
```

### Python API
```python
from pathlib import Path
import docweave

result = docweave.convert(
    pdf_path=Path("input/annual_report.pdf"),
    output_path=Path("output/annual_report.md"),
    audit_quality=True
)

print(f"Total Pages: {result['total_pages']}")
print(f"Ambiguous Pages Routed by AI: {result['ambiguous_routed_by_jev']}")
print(f"Tables Audited: {result['table_qa_audited']}")
```

---

## 📜 License
MIT License.
