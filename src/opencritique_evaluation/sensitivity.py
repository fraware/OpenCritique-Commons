from __future__ import annotations

from pathlib import Path

from .engine import evaluate
from .models import (
    BenchmarkManifest,
    EvaluationSubmission,
    MatcherConfig,
    MatcherSensitivityReport,
    SensitivityRun,
)


def default_sensitivity_grid() -> list[MatcherConfig]:
    return [
        MatcherConfig(config_id="baseline", threshold=0.55),
        MatcherConfig(config_id="threshold-low", threshold=0.45),
        MatcherConfig(config_id="threshold-high", threshold=0.65),
        MatcherConfig(
            config_id="anchor-heavy",
            anchor_weight=0.65,
            type_weight=0.20,
            lexical_weight=0.15,
            threshold=0.55,
        ),
        MatcherConfig(
            config_id="type-heavy",
            anchor_weight=0.35,
            type_weight=0.45,
            lexical_weight=0.20,
            threshold=0.55,
        ),
        MatcherConfig(
            config_id="lexical-heavy",
            anchor_weight=0.35,
            type_weight=0.20,
            lexical_weight=0.45,
            threshold=0.55,
        ),
    ]


def _pairs(result) -> set[tuple[str, str, str, str]]:
    return {
        (case.case_id, case.case_version, match.submitted_local_id, match.reference_concern_id)
        for case in result.case_evaluations
        for match in case.matches
    }


def analyze_sensitivity(
    *,
    benchmark: BenchmarkManifest,
    benchmark_root: Path,
    submission: EvaluationSubmission,
    configs: list[MatcherConfig] | None = None,
) -> MatcherSensitivityReport:
    configs = configs or default_sensitivity_grid()
    if len(configs) < 2:
        raise ValueError("sensitivity analysis requires at least two matcher configurations")
    if len({item.config_id for item in configs}) != len(configs):
        raise ValueError("matcher config_id values must be unique")

    runs: list[SensitivityRun] = []
    pair_sets: list[set[tuple[str, str, str, str]]] = []
    for config in configs:
        result = evaluate(
            benchmark=benchmark,
            benchmark_root=benchmark_root,
            submission=submission,
            matcher_config=config,
        )
        pairs = _pairs(result)
        pair_sets.append(pairs)
        runs.append(
            SensitivityRun(
                config=config,
                matched_pairs=sorted(pairs),
                matched_count=len(pairs),
                precision=(
                    float(result.metrics.precision.value)
                    if result.metrics.precision.value is not None
                    else None
                ),
                recall=(
                    float(result.metrics.recall.value)
                    if result.metrics.recall.value is not None
                    else None
                ),
            )
        )

    stable = set.intersection(*pair_sets)
    union = set.union(*pair_sets)
    baseline = pair_sets[0]
    retention = 1.0 if not baseline else len(stable & baseline) / len(baseline)
    precision_values = [item.precision for item in runs if item.precision is not None]
    recall_values = [item.recall for item in runs if item.recall is not None]
    return MatcherSensitivityReport(
        benchmark_id=benchmark.benchmark_id,
        benchmark_version=benchmark.version,
        submission_id=submission.submission_id,
        baseline_config=configs[0],
        runs=runs,
        stable_pairs=sorted(stable),
        unstable_pairs=sorted(union - stable),
        baseline_retention_rate=round(retention, 6),
        match_count_min=min(item.matched_count for item in runs),
        match_count_max=max(item.matched_count for item in runs),
        precision_min=min(precision_values) if precision_values else None,
        precision_max=max(precision_values) if precision_values else None,
        recall_min=min(recall_values) if recall_values else None,
        recall_max=max(recall_values) if recall_values else None,
    )
