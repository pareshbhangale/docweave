#!/usr/bin/env python3
"""
Benchmark comparison: CLM (Local Contrastive LM) vs TypeSafe Jev (Cloud System One)
Evaluating semantic routing accuracy, table audit latency, and decision consistency in docweave.
"""

import sys
import time
import json
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_APP_DIR / "src"))

import requests

JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
JEV_API_KEY = "apikey_293a2c9abe9855c4301a2951be1864ab82a_fc3d57e2cc85d21cf049bb7c3714202dc16012df6e09a0e93c967c406c9ac662"

# Test states derived from real SEBI filings, balance sheets, and narrative disclosures
BENCHMARK_CASES = [
    {
        "id": "case_1_balance_sheet",
        "description": "Dense audited balance sheet with multiple columns of figures",
        "state": {
            "page": 4,
            "chars": 2840,
            "drawings": 82,
            "tables_detected": 1,
            "text_snippet": "Standalone Balance Sheet as at March 31, 2026. Non-current assets: Property, Plant and Equipment 4,521.8 Cr vs 3,890.1 Cr. Current liabilities: Trade payables 1,230.4 Cr. Total equity and liabilities 12,450.9 Cr."
        },
        "expected_route": "TABLE",
        "question": {
            "type": "choice",
            "instructions": "Determine whether this page contains a real financial/tabular dataset or narrative text.",
            "criteria": {
                "TABLE": "Real structured financial data, balance sheet, P&L, multi-column metrics, or tabular SEBI schedule.",
                "TEXT": "Notice, prose, resolution, disclaimer, or letter (even if it has letterhead lines or borders).",
                "OCR": "Scanned document or illegible bitmap."
            }
        }
    },
    {
        "id": "case_2_agm_notice",
        "description": "Notice of Annual General Meeting with decorative borders and letterhead",
        "state": {
            "page": 1,
            "chars": 1920,
            "drawings": 14,
            "tables_detected": 0,
            "text_snippet": "NOTICE IS HEREBY GIVEN THAT the 28th Annual General Meeting of the Members of the Company will be held on Friday, September 25, 2026 at 11:00 AM IST through Video Conferencing to transact Ordinary Business and Special Resolutions."
        },
        "expected_route": "TEXT",
        "question": {
            "type": "choice",
            "instructions": "Determine whether this page contains a real financial/tabular dataset or narrative text.",
            "criteria": {
                "TABLE": "Real structured financial data, balance sheet, P&L, multi-column metrics, or tabular SEBI schedule.",
                "TEXT": "Notice, prose, resolution, disclaimer, or letter (even if it has letterhead lines or borders).",
                "OCR": "Scanned document or illegible bitmap."
            }
        }
    },
    {
        "id": "case_3_shareholding_pattern",
        "description": "SEBI Regulation 31 tabular shareholding breakdown",
        "state": {
            "page": 12,
            "chars": 3120,
            "drawings": 120,
            "tables_detected": 1,
            "text_snippet": "Statement showing shareholding pattern of the Promoter and Promoter Group: Indian Promoters 54.21% (124,500,000 shares), Foreign Institutional Investors 22.18% (50,900,000 shares), Public 23.61%."
        },
        "expected_route": "TABLE",
        "question": {
            "type": "choice",
            "instructions": "Determine whether this page contains a real financial/tabular dataset or narrative text.",
            "criteria": {
                "TABLE": "Real structured financial data, balance sheet, P&L, multi-column metrics, or tabular SEBI schedule.",
                "TEXT": "Notice, prose, resolution, disclaimer, or letter (even if it has letterhead lines or borders).",
                "OCR": "Scanned document or illegible bitmap."
            }
        }
    },
    {
        "id": "case_4_director_report_prose",
        "description": "Directors' report narrative paragraph discussing business operations",
        "state": {
            "page": 8,
            "chars": 2650,
            "drawings": 2,
            "tables_detected": 0,
            "text_snippet": "Management Discussion & Analysis: During the fiscal year under review, the global supply chain experienced stabilization. Your Company achieved record revenues in the specialty rail transport segment driven by modernization orders from Indian Railways."
        },
        "expected_route": "TEXT",
        "question": {
            "type": "choice",
            "instructions": "Determine whether this page contains a real financial/tabular dataset or narrative text.",
            "criteria": {
                "TABLE": "Real structured financial data, balance sheet, P&L, multi-column metrics, or tabular SEBI schedule.",
                "TEXT": "Notice, prose, resolution, disclaimer, or letter (even if it has letterhead lines or borders).",
                "OCR": "Scanned document or illegible bitmap."
            }
        }
    },
    {
        "id": "case_5_table_qa_clean",
        "description": "Clean markdown table audit for structural corruption",
        "state": "| Quarter Ended | Jun 30, 2026 | Mar 31, 2026 | Jun 30, 2025 |\n|---|---|---|---|\n| Revenue from Operations | 1,450.2 | 1,320.5 | 1,180.0 |\n| Operating Profit | 320.1 | 290.4 | 240.5 |\n| Net Profit | 210.5 | 185.2 | 150.3 |",
        "expected_corrupted": False,
        "question": {
            "type": "noul",
            "instructions": "Is the markdown table corrupted, scrambled, or broken?"
        }
    },
    {
        "id": "case_6_table_qa_corrupted",
        "description": "Garbled table markdown with collapsed columns and misaligned values",
        "state": "Revenue from Operations Jun 30 1,450.2 | Mar 31 1,320.5 -- 1,180.0\nOperating Profit ||| Net Profit 210.5 185.2 150.3 ??? missing cols",
        "expected_corrupted": True,
        "question": {
            "type": "noul",
            "instructions": "Is the markdown table corrupted, scrambled, or broken?"
        }
    }
]


def test_typesafe_jev():
    print("\n--- [1] Testing TypeSafe Jev (Cloud) ---")
    headers = {
        "Authorization": f"Bearer {JEV_API_KEY}",
        "Content-Type": "application/json"
    }
    results = []
    total_time = 0.0

    for case in BENCHMARK_CASES:
        payload = {
            "state": case["state"],
            "model": "jev-latest",
            "questions": {"q1": case["question"]}
        }
        t0 = time.perf_counter()
        try:
            resp = requests.post(JEV_ENDPOINT, headers=headers, json=payload, timeout=15)
            dt = (time.perf_counter() - t0) * 1000
            total_time += dt
            if resp.status_code == 200:
                data = resp.json()
                ans = data["answers"]["q1"]
                results.append({
                    "id": case["id"],
                    "latency_ms": round(dt, 1),
                    "answer": ans,
                    "success": True
                })
                print(f"  ✓ {case['id']}: {dt:.1f}ms -> {ans.get('choice') or ans.get('noul')}")
            else:
                print(f"  ✗ {case['id']}: Status {resp.status_code} - {resp.text}")
                results.append({"id": case["id"], "latency_ms": round(dt, 1), "success": False, "error": resp.text})
        except Exception as e:
            print(f"  ✗ {case['id']}: Exception {e}")
            results.append({"id": case["id"], "latency_ms": None, "success": False, "error": str(e)})

    return results, total_time


CLM_ENDPOINT = "http://127.0.0.1:8700/v1/systemone"


def test_clm():
    print("\n--- [2] Testing Local CLM (Contrastive LM on Apple Silicon) ---")
    headers = {"Content-Type": "application/json"}
    results = []
    total_time = 0.0

    for case in BENCHMARK_CASES:
        payload = {
            "state": case["state"],
            "model": "clm-latest",
            "questions": {"q1": case["question"]}
        }
        t0 = time.perf_counter()
        try:
            resp = requests.post(CLM_ENDPOINT, headers=headers, json=payload, timeout=10)
            dt = (time.perf_counter() - t0) * 1000
            total_time += dt
            if resp.status_code == 200:
                data = resp.json()
                ans = data["answers"]["q1"]
                results.append({
                    "id": case["id"],
                    "latency_ms": round(dt, 1),
                    "answer": ans,
                    "success": True
                })
                print(f"  ✓ {case['id']}: {dt:.1f}ms -> {ans.get('choice') or ans.get('noul')}")
            else:
                print(f"  ✗ {case['id']}: Status {resp.status_code} - {resp.text}")
                results.append({"id": case["id"], "latency_ms": round(dt, 1), "success": False, "error": resp.text})
        except Exception as e:
            print(f"  ✗ {case['id']}: Exception {e}")
            results.append({"id": case["id"], "latency_ms": None, "success": False, "error": str(e)})

    return results, total_time


def main():
    print("=" * 65)
    print("📊 DOCWEAVE SUPERVISION BENCHMARK: JEV vs CLM")
    print("=" * 65)

    jev_results, jev_total_ms = test_typesafe_jev()
    clm_results, clm_total_ms = test_clm()

    print("\n" + "=" * 65)
    print("🏁 COMPARATIVE BENCHMARK SUMMARY")
    print("=" * 65)

    print(f"\n⚡ SPEED COMPARISON:")
    print(f"  • TypeSafe Jev (Cloud) : Total {jev_total_ms:.1f}ms | Avg {jev_total_ms/len(BENCHMARK_CASES):.1f}ms / query")
    print(f"  • Local CLM (Apple Silicon): Total {clm_total_ms:.1f}ms | Avg {clm_total_ms/len(BENCHMARK_CASES):.1f}ms / query")
    if clm_total_ms > 0:
        speedup = jev_total_ms / clm_total_ms
        print(f"  🚀 Speed Difference: CLM is {speedup:.2f}x faster per query" if speedup >= 1 else f"  Jev is {1/speedup:.2f}x faster")

    print(f"\n🎯 DECISION ACCURACY / ALIGNMENT:")
    matches = 0
    total = len(BENCHMARK_CASES)
    for j_res, c_res, case in zip(jev_results, clm_results, BENCHMARK_CASES):
        j_ans = j_res.get("answer", {})
        c_ans = c_res.get("answer", {})
        cid = case["id"]

        j_val = j_ans.get("choice") if "choice" in j_ans else j_ans.get("noul")
        c_val = c_ans.get("choice") if "choice" in c_ans else c_ans.get("noul")

        # Check alignment
        if "expected_route" in case:
            exp = case["expected_route"]
            j_acc = "✓" if j_val == exp else "✗"
            c_acc = "✓" if c_val == exp else "✗"
            print(f"  [{cid}] Target: {exp} | Jev: {j_val} ({j_acc}, {j_res.get('latency_ms')}ms) | CLM: {c_val} ({c_acc}, {c_res.get('latency_ms')}ms)")
            if c_val == exp:
                matches += 1
        elif "expected_corrupted" in case:
            exp_corrupt = case["expected_corrupted"]
            j_flag = (j_val > 0.5) if isinstance(j_val, (int, float)) else False
            c_flag = (c_val > 0.5) if isinstance(c_val, (int, float)) else False
            j_acc = "✓" if j_flag == exp_corrupt else "✗"
            c_acc = "✓" if c_flag == exp_corrupt else "✗"
            print(f"  [{cid}] Target Corrupted={exp_corrupt} | Jev: {j_val:.2f} ({j_acc}) | CLM: {c_val:.2f} ({c_acc})")
            if c_flag == exp_corrupt:
                matches += 1

    print(f"\nAccuracy Score: {matches}/{total} ({matches/total*100:.1f}%)")

    # Save summary report
    out_path = _APP_DIR / "output" / "benchmark_comparison.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "jev_total_ms": jev_total_ms,
        "clm_total_ms": clm_total_ms,
        "jev_avg_ms": jev_total_ms / len(BENCHMARK_CASES),
        "clm_avg_ms": clm_total_ms / len(BENCHMARK_CASES),
        "accuracy_matches": matches,
        "total_cases": total,
        "jev_results": jev_results,
        "clm_results": clm_results
    }, indent=2), encoding="utf-8")
    print(f"\nDetailed JSON report saved to {out_path}")


if __name__ == "__main__":
    main()
