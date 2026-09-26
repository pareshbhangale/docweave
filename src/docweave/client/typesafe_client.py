"""
Multi-Provider LLM & System One Client for docweave.
Supports:
1. TypeSafe System One (Jev / Laya) native API
2. OpenAI-compatible local/remote endpoints (Ollama, vLLM, LM Studio, llama.cpp, OpenAI, OpenRouter)
"""

import os
import json
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Config fallback paths
_PKG_DIR = Path(__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_PATHS = [
    Path.cwd() / "config.json",
    _REPO_ROOT / "config.json",
    _REPO_ROOT / "config.template.json",
    Path.home() / ".docweave" / "config.json"
]


def load_config() -> Dict[str, Any]:
    """Loads configuration from environment or config.json files."""
    for cfg_path in _CONFIG_PATHS:
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                if "providers" in data:
                    return data
                # Legacy root config fallback
                ts_cfg = data.get("text_models", {}).get("typesafe", {})
                if ts_cfg:
                    return {
                        "active_provider": "typesafe",
                        "providers": {
                            "typesafe": {
                                "endpoint": ts_cfg.get("endpoint", "https://api.typesafe.ai/v1/systemone"),
                                "api_key": ts_cfg.get("api_key", ""),
                                "model": ts_cfg.get("model", "jev-latest"),
                                "timeout": 12.0
                            }
                        }
                    }
            except Exception:
                continue

    return {
        "active_provider": "typesafe",
        "providers": {
            "typesafe": {
                "endpoint": "https://api.typesafe.ai/v1/systemone",
                "api_key": "",
                "model": "jev-latest",
                "timeout": 12.0
            }
        }
    }


def get_typesafe_credentials() -> Dict[str, Any]:
    """Retrieves active provider credentials and configuration."""
    cfg = load_config()
    active_key = os.environ.get("DOCWEAVE_PROVIDER", cfg.get("active_provider", "typesafe"))
    provider = cfg.get("providers", {}).get(active_key, {})

    # Environment variable overrides
    api_key = os.environ.get("TYPESAFE_API_KEY") or os.environ.get("OPENAI_API_KEY") or provider.get("api_key", "")
    model = os.environ.get("TYPESAFE_MODEL") or os.environ.get("OPENAI_MODEL") or provider.get("model", "jev-latest")
    endpoint = os.environ.get("TYPESAFE_ENDPOINT") or os.environ.get("OPENAI_BASE_URL") or provider.get("endpoint", "https://api.typesafe.ai/v1/systemone")
    timeout = float(provider.get("timeout", 15.0))

    is_openai_compat = "/chat/completions" in endpoint or active_key in ("local_ollama", "local_vllm", "openai")

    return {
        "provider": active_key,
        "api_key": api_key.strip(),
        "model": model,
        "endpoint": endpoint,
        "timeout": timeout,
        "is_openai_compat": is_openai_compat
    }


class TypeSafePDFClient:
    """Supervisory decision client for ambiguous page routing and table QA auditing."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        is_openai_compat: Optional[bool] = None
    ):
        creds = get_typesafe_credentials()
        self.api_key = api_key if api_key is not None else creds["api_key"]
        self.model = model or creds["model"]
        self.endpoint = endpoint or creds["endpoint"]
        self.timeout = creds["timeout"]
        self.is_openai_compat = is_openai_compat if is_openai_compat is not None else creds["is_openai_compat"]

        if not self.is_openai_compat and not self.api_key:
            raise ValueError(
                "TypeSafe API key missing. Set TYPESAFE_API_KEY environment variable or "
                "configure 'providers.typesafe.api_key' in config.json."
            )

    @property
    def headers(self) -> Dict[str, str]:
        hdrs = {"Content-Type": "application/json"}
        if self.api_key:
            hdrs["Authorization"] = f"Bearer {self.api_key}"
        return hdrs

    def _call_openai_compat(self, prompt: str, schema_instruction: str) -> str:
        """Invokes OpenAI-compatible endpoint (Ollama / vLLM / LocalAI / OpenAI)."""
        messages = [
            {"role": "system", "content": schema_instruction},
            {"role": "user", "content": prompt}
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0
        }
        resp = requests.post(self.endpoint, headers=self.headers, json=payload, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"OpenAI-compatible API error {resp.status_code}: {resp.text}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def evaluate_typesafe(
        self,
        state: Union[str, Dict, List],
        questions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Submits typed questions over state to TypeSafe System One API (Jev / Laya)."""
        payload = {
            "state": state,
            "model": self.model,
            "questions": questions
        }
        resp = requests.post(self.endpoint, headers=self.headers, json=payload, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"TypeSafe API error {resp.status_code}: {resp.text}")
        return resp.json()

    def route_ambiguous_batch(self, candidate_pages: List[Dict[str, Any]]) -> Dict[int, str]:
        """Classifies ALL ambiguous pages simultaneously in ONE batch request."""
        if not candidate_pages:
            return {}

        if not self.is_openai_compat:
            # Native TypeSafe System One (Jev / Laya)
            state = {}
            questions = {}
            for p in candidate_pages:
                idx = p["page_idx"]
                k = f"p_{idx}"
                state[k] = {
                    "page": idx + 1,
                    "chars": p["char_count"],
                    "drawings": p["drawings"],
                    "tables_detected": p["tables"],
                    "text_snippet": p["text_sample"][:800]
                }
                questions[f"route_{idx}"] = {
                    "type": "choice",
                    "instructions": f"Determine whether page `{k}` contains a real financial/tabular dataset or narrative text.",
                    "criteria": {
                        "TABLE": "Real structured financial data, balance sheet, P&L, multi-column metrics, or tabular SEBI schedule.",
                        "TEXT": "Notice, prose, resolution, disclaimer, or letter (even if it has letterhead lines or borders).",
                        "OCR": "Scanned document or illegible bitmap."
                    }
                }

            res = self.evaluate_typesafe(state=state, questions=questions)
            answers = res.get("answers", {})

            results = {}
            for p in candidate_pages:
                idx = p["page_idx"]
                choice_val = answers.get(f"route_{idx}", {}).get("choice", "TEXT")
                if choice_val == "TABLE":
                    results[idx] = "TABLE"
                elif choice_val == "OCR":
                    results[idx] = "OCR"
                else:
                    results[idx] = "TEXT_SIMPLE"
            return results

        # OpenAI / Local Model (Ollama / vLLM) compatible fallback
        pages_summary = []
        for p in candidate_pages:
            pages_summary.append({
                "page_idx": p["page_idx"],
                "chars": p["char_count"],
                "tables_hint": p["tables"],
                "snippet": p["text_sample"][:300].replace("\n", " ")
            })

        system_prompt = (
            "You are a strict document layout classifier. Classify each candidate page as either "
            "'TABLE' (structured financial tables, balance sheets, schedules) or 'TEXT_SIMPLE' (prose, letters, notices). "
            "Respond ONLY with a valid JSON object mapping integer page_idx string to classification, e.g. {\"0\": \"TABLE\", \"1\": \"TEXT_SIMPLE\"}."
        )
        user_prompt = f"Candidate pages:\n{json.dumps(pages_summary, indent=2)}"

        try:
            raw_text = self._call_openai_compat(user_prompt, system_prompt)
            clean_json = raw_text.strip()
            if clean_json.startswith("```"):
                clean_json = clean_json.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(clean_json)
            return {int(k): v.upper() for k, v in parsed.items()}
        except Exception:
            # Fallback
            return {p["page_idx"]: ("TABLE" if p["tables"] > 0 else "TEXT_SIMPLE") for p in candidate_pages}

    def audit_tables_batch(self, table_pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Audits converted table pages in ONE batch request."""
        if not table_pages:
            return []

        if not self.is_openai_compat:
            state = {}
            questions = {}
            for tp in table_pages:
                p_num = tp["page_num"]
                k = f"table_p_{p_num}"
                state[k] = tp["markdown"][:1800]
                questions[f"corrupt_{p_num}"] = {
                    "type": "noul",
                    "instructions": f"Is the markdown table in `{k}` corrupted or scrambled?"
                }
                questions[f"fidelity_{p_num}"] = {
                    "type": "score",
                    "instructions": f"Rate table structural preservation in `{k}`.",
                    "criteria": ["Corrupted", "Acceptable", "High Fidelity"]
                }

            res = self.evaluate_typesafe(state=state, questions=questions)
            answers = res.get("answers", {})

            audits = []
            for tp in table_pages:
                p_num = tp["page_num"]
                p_corrupt = answers.get(f"corrupt_{p_num}", {}).get("noul", 0.0)
                score_fid = answers.get(f"fidelity_{p_num}", {}).get("score", 2.0)
                audits.append({
                    "page_number": p_num,
                    "is_corrupted_prob": round(p_corrupt, 3),
                    "fidelity_score": round(score_fid, 2),
                    "needs_escalation": p_corrupt > 0.5 or score_fid < 0.8
                })
            return audits

        # Local model audit
        system_prompt = (
            "You are a strict financial markdown table QA inspector. Evaluate whether each table markdown has garbled rows or broken columns. "
            "Respond ONLY with a JSON list: [{\"page_number\": int, \"is_corrupted_prob\": float, \"fidelity_score\": float, \"needs_escalation\": bool}]."
        )
        sample_tables = [{"page_number": tp["page_num"], "markdown": tp["markdown"][:600]} for tp in table_pages]
        try:
            raw_text = self._call_openai_compat(json.dumps(sample_tables), system_prompt)
            clean_json = raw_text.strip()
            if clean_json.startswith("```"):
                clean_json = clean_json.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(clean_json)
        except Exception:
            return [{"page_number": tp["page_num"], "is_corrupted_prob": 0.0, "fidelity_score": 2.0, "needs_escalation": False} for tp in table_pages]
