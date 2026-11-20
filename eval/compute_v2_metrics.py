"""Compute deterministic metrics from the real pipeline capture."""
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    return round(values[min(len(values) - 1, math.ceil(len(values) * p / 100) - 1)], 3)


def rankdata(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        rank = (i + j + 2) / 2
        for n in range(i, j + 1):
            ranks[order[n]] = rank
        i = j + 1
    return ranks


def spearman(xs, ys):
    if len(xs) < 2:
        return None
    rx, ry = rankdata(xs), rankdata(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    numerator = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denominator = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return round(numerator / denominator, 6) if denominator else 0.0


def relevance(label):
    return {"STRONG_FIT": 2, "PARTIAL_FIT": 1, "NOT_FIT": 0}[label]


def ndcg(rows, k):
    rels = [relevance(row["label"]) for row in rows[:k]]
    ideal = sorted((relevance(row["label"]) for row in rows), reverse=True)[:k]
    dcg = sum((2**rel - 1) / math.log2(i + 2) for i, rel in enumerate(rels))
    idcg = sum((2**rel - 1) / math.log2(i + 2) for i, rel in enumerate(ideal))
    return round(dcg / idcg, 6) if idcg else 0.0


def strong_precision(rows, k):
    return round(sum(row["label"] == "STRONG_FIT" for row in rows[:k]) / k, 6) if len(rows) >= k else None


def strong_recall(rows, k):
    total = sum(row["label"] == "STRONG_FIT" for row in rows)
    return round(sum(row["label"] == "STRONG_FIT" for row in rows[:k]) / total, 6) if total else None


def metrics_for(rows, ranking_key):
    ranked = sorted(rows, key=lambda row: row[ranking_key], reverse=True)
    first_strong = next((i + 1 for i, row in enumerate(ranked) if row["label"] == "STRONG_FIT"), None)
    return {
        "nDCG@5": ndcg(ranked, 5),
        "nDCG@10": ndcg(ranked, 10),
        "Precision@5_STRONG_FIT": strong_precision(ranked, 5),
        "Recall@5_STRONG_FIT": strong_recall(ranked, 5),
        "MRR_first_STRONG_FIT": round(1 / first_strong, 6) if first_strong else 0.0,
    }, ranked


def main():
    pipeline = json.loads((RESULTS / "pipeline_v2.json").read_text(encoding="utf-8"))
    rows = pipeline["screening_results"]
    semantic_metrics = {}
    final_rows = []
    for row in rows:
        semantic = dict(row)
        semantic["semantic_score"] = semantic["semantic_score"] or -1
        semantic_metrics.setdefault(row["job"], []).append(semantic)
        final = dict(row)
        final["final_score"] = row["score"] if row["score"] is not None else -1
        final_rows.append(final)

    ranking = {}
    retrieval = {}
    gate = {}
    confusion = {label: {"SHORTLIST": 0, "REVIEW": 0, "REJECT": 0} for label in ("STRONG_FIT", "PARTIAL_FIT", "NOT_FIT")}
    for job, job_rows in semantic_metrics.items():
        final_job = [row for row in final_rows if row["job"] == job]
        ranking[job], _ = metrics_for(final_job, "final_score")
        retrieval[job], semantic_ranked = metrics_for(job_rows, "semantic_score")
        survivors = [row for row in job_rows if row["decision"] != "PRE_SCREENED_OUT"]
        top10 = semantic_ranked[:10]
        total_strong = sum(row["label"] == "STRONG_FIT" for row in job_rows)
        gate[job] = {
            "strong_fit_total": total_strong,
            "strong_fit_survived_adaptive_gate": sum(row["label"] == "STRONG_FIT" for row in survivors),
            "adaptive_gate_recall": round(sum(row["label"] == "STRONG_FIT" for row in survivors) / total_strong, 6),
            "fixed_top10_strong_fit_recall": round(sum(row["label"] == "STRONG_FIT" for row in top10) / total_strong, 6),
            "candidates_sent_to_llm": sum(row["score"] is not None for row in job_rows),
        }
    for row in rows:
        decision = "REJECT" if row["decision"] == "PRE_SCREENED_OUT" else row["decision"]
        confusion[row["label"]][decision] += 1

    scored = [row for row in rows if row["score"] is not None]
    score_separation = {}
    for label in ("STRONG_FIT", "PARTIAL_FIT", "NOT_FIT"):
        values = [row["score"] for row in scored if row["label"] == label]
        score_separation[label] = {
            "count": len(values),
            "mean": round(statistics.mean(values), 6) if values else None,
            "p50": percentile(values, 50),
        }
    strong_total = sum(row["label"] == "STRONG_FIT" for row in rows)
    false_shortlist = sum(row["label"] == "NOT_FIT" and row["decision"] == "SHORTLIST" for row in rows)
    false_reject = sum(row["label"] == "STRONG_FIT" and row["decision"] in ("REJECT", "PRE_SCREENED_OUT") for row in rows)
    consistency = pipeline.get("consistency", [])
    attempts = pipeline.get("llm_attempts", [])
    latency = {}
    for stage, values in pipeline["latencies_ms"].items():
        latency[stage] = {"count": len(values), "p50_ms": percentile(values, 50), "p95_ms": percentile(values, 95)}
    successful = sum(row["status"] == "processed" for row in pipeline["files"])
    total_seconds = sum(row["total_ms"] for row in pipeline["files"]) / 1000
    output = {
        "dataset": {
            "files": len(rows),
            "jobs": len(set(row["job"] for row in rows)),
            "labels": {label: sum(row["label"] == label for row in rows) for label in ("STRONG_FIT", "PARTIAL_FIT", "NOT_FIT")},
        },
        "ranking_by_job": ranking,
        "retrieval_by_job": retrieval,
        "adaptive_gate_by_job": gate,
        "average_candidates_sent_to_llm": round(sum(item["candidates_sent_to_llm"] for item in gate.values()) / len(gate), 3),
        "decision_confusion_matrix": confusion,
        "false_shortlist_rate_not_fit": round(false_shortlist / sum(row["label"] == "NOT_FIT" for row in rows), 6),
        "false_reject_rate_strong_fit": round(false_reject / strong_total, 6),
        "score_separation": score_separation,
        "spearman_llm_score_vs_ground_truth": spearman(
            [row["score"] for row in scored],
            [relevance(row["label"]) for row in scored],
        ),
        "consistency": {
            "resumes": len(consistency),
            "runs_per_resume": 3,
            "mean_score_stddev": round(statistics.mean([row["score_stddev"] for row in consistency if row["score_stddev"] is not None]), 6) if consistency else None,
            "decision_agreement_rate": round(sum(row["decision_agreement"] for row in consistency) / len(consistency), 6) if consistency else None,
        },
        "llm_reliability": {
            "provider_attempts": len(attempts),
            "successful_valid_json_attempts": sum(bool(row.get("success")) for row in attempts),
            "valid_json_rate": round(sum(bool(row.get("success")) for row in attempts) / len(attempts), 6) if attempts else None,
            "providers_used": sorted(set(row.get("provider") for row in attempts)),
            "fallback_provider_usage": 0 if len(set(row.get("provider") for row in attempts)) <= 1 else "measured per-call in pipeline_v2.json",
        },
        "latency_ms": latency,
        "processed_resumes_per_minute": round(successful / total_seconds * 60, 6) if total_seconds else None,
    }
    (RESULTS / "metrics_v2.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
