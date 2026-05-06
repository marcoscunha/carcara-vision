"""Benchmark reporting utilities for per-stream inference metrics exports."""

from __future__ import annotations

import csv
import json
import platform
from dataclasses import asdict
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from ..api.models.benchmark import BenchmarkScenario
from .acceleration_policy import detect_capabilities


def _iso_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _run_id(prefix: str = "benchmark") -> str:
    return f"{prefix}_{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}"


def _hardware_snapshot() -> dict[str, Any]:
    mem_total_bytes = 0
    try:
        page_size = int(Path("/proc/meminfo").read_text().split("MemTotal:")[1].split("kB")[0].strip())
        mem_total_bytes = page_size * 1024
    except Exception:
        mem_total_bytes = 0

    caps = detect_capabilities(refresh=True)
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "memory_total_bytes": mem_total_bytes,
        "capabilities": asdict(caps),
    }


def _safe_stage_avg(stats: dict[str, Any], stage_name: str) -> float:
    stage = (stats.get("stage_timings_ms") or {}).get(stage_name, {})
    return float(stage.get("avg", 0.0) or 0.0)


def _safe_stage_percentile(stats: dict[str, Any], stage_name: str, metric: str) -> float:
    stage = (stats.get("stage_timings_ms") or {}).get(stage_name, {})
    return float(stage.get(metric, 0.0) or 0.0)


def _inference_parse_estimate(stats: dict[str, Any]) -> float:
    total_inf = _safe_stage_avg(stats, "inference_total")
    engine_inf = _safe_stage_avg(stats, "inference_engine")
    return max(total_inf - engine_inf, 0.0)


def _summary(worker_stats: list[dict[str, Any]]) -> dict[str, Any]:
    if not worker_stats:
        return {
            "streams": 0,
            "samples": 0,
            "fps_mean": 0.0,
            "inference_ms_p50": 0.0,
            "inference_ms_p95": 0.0,
            "inference_ms_p99": 0.0,
            "drop_ratio": 0.0,
        }

    fps_values = [float(s.get("fps", 0.0) or 0.0) for s in worker_stats]
    sample_values = [int(s.get("frames_processed", 0) or 0) for s in worker_stats]
    inf_p50 = [_safe_stage_percentile(s, "inference_engine", "p50") for s in worker_stats]
    inf_p95 = [_safe_stage_percentile(s, "inference_engine", "p95") for s in worker_stats]
    inf_p99 = [_safe_stage_percentile(s, "inference_engine", "p99") for s in worker_stats]

    dropped = sum(int(s.get("dropped_events_total", 0) or 0) for s in worker_stats)
    processed = sum(sample_values)
    drop_ratio = (dropped / processed) if processed > 0 else 0.0

    return {
        "streams": len(worker_stats),
        "samples": processed,
        "fps_mean": round(sum(fps_values) / max(len(fps_values), 1), 2),
        "inference_ms_p50": round(sum(inf_p50) / max(len(inf_p50), 1), 2),
        "inference_ms_p95": round(sum(inf_p95) / max(len(inf_p95), 1), 2),
        "inference_ms_p99": round(sum(inf_p99) / max(len(inf_p99), 1), 2),
        "drop_ratio": round(drop_ratio, 4),
    }


def _to_csv_rows(worker_stats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stats in worker_stats:
        rows.append(
            {
                "stream_id": int(stats.get("stream_id", 0) or 0),
                "model": stats.get("model"),
                "accelerator": stats.get("accelerator"),
                "runtime": stats.get("runtime"),
                "dtype": stats.get("dtype"),
                "frames_processed": int(stats.get("frames_processed", 0) or 0),
                "fps": round(float(stats.get("fps", 0.0) or 0.0), 2),
                "avg_inference_ms": round(float(stats.get("avg_inference_ms", 0.0) or 0.0), 2),
                "read_ms": round(_safe_stage_avg(stats, "read"), 2),
                "preprocess_ms": 0.0,
                "inference_ms": round(_safe_stage_avg(stats, "inference_engine"), 2),
                "parse_nms_ms": round(_inference_parse_estimate(stats), 2),
                "annotate_ms": round(_safe_stage_avg(stats, "annotate"), 2),
                "publish_ms": round(_safe_stage_avg(stats, "publish_annotated"), 2),
                "drop_events": int(stats.get("dropped_events_total", 0) or 0),
                "missed_slots": int(stats.get("missed_slots_total", 0) or 0),
            }
        )
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "stream_id",
        "model",
        "accelerator",
        "runtime",
        "dtype",
        "frames_processed",
        "fps",
        "avg_inference_ms",
        "read_ms",
        "preprocess_ms",
        "inference_ms",
        "parse_nms_ms",
        "annotate_ms",
        "publish_ms",
        "drop_events",
        "missed_slots",
    ]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_benchmark_report(
    *,
    scenario: BenchmarkScenario,
    worker_stats: list[dict[str, Any]],
    runtime_config: dict[str, Any],
    output_dir: str = "./benchmark_reports",
) -> dict[str, Any]:
    run_id = _run_id()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / f"{run_id}.json"
    csv_path = out / f"{run_id}.csv"

    payload = {
        "run_id": run_id,
        "created_at": _iso_now(),
        "scenario": scenario.model_dump(),
        "hardware": _hardware_snapshot(),
        "runtime": runtime_config,
        "summary": _summary(worker_stats),
        "per_stream": worker_stats,
    }

    _write_json(json_path, payload)
    _write_csv(csv_path, _to_csv_rows(worker_stats))

    return {
        "run_id": run_id,
        "json_report_path": str(json_path.resolve()),
        "csv_report_path": str(csv_path.resolve()),
        "scenario_name": scenario.scenario_name,
        "streams_count": len(worker_stats),
    }


def default_benchmark_scenario() -> BenchmarkScenario:
    return BenchmarkScenario()
