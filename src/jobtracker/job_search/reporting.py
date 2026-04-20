from __future__ import annotations

import json

from jobtracker.job_search.models import InstantJobSearchRunSummary


def format_instant_job_search_summary(summary: InstantJobSearchRunSummary) -> str:
    lines = [
        "Instant Job Search",
        (
            f"Mode: {summary.source_mode} | Profile matching: "
            f"{'on' if summary.use_profile_matching else 'off'} | "
            f"Max age: {summary.max_age_days} days | Results: {len(summary.results)}"
        ),
    ]
    if summary.skipped_for_age or summary.skipped_for_relevance:
        lines.append(
            f"Skipped: age={summary.skipped_for_age}, relevance={summary.skipped_for_relevance}"
        )
    lines.append("")

    if not summary.results:
        lines.append("No matching jobs found.")
        return "\n".join(lines)

    for index, result in enumerate(summary.results, start=1):
        age_text = result.age_text or (
            f"{result.age_days} days old" if result.age_days is not None else "age unknown"
        )
        company = result.company or "Unknown company"
        location = result.location or result.workplace_type or "-"
        lines.append(
            f"{index}. {result.title} | {company} | {location} | {age_text} | score={result.score}"
        )
        lines.append(f"   {result.url}")
        if result.reasons:
            lines.append(f"   Why: {', '.join(result.reasons)}")
    return "\n".join(lines)


def format_instant_job_search_json(summary: InstantJobSearchRunSummary) -> str:
    return json.dumps(summary.model_dump(mode="json"), indent=2)


def format_instant_job_search_markdown(summary: InstantJobSearchRunSummary) -> str:
    lines = [
        "# Instant Job Search",
        "",
        f"Max age: {summary.max_age_days} days",
        f"Mode: {summary.source_mode}",
        f"Profile matching: {'on' if summary.use_profile_matching else 'off'}",
        f"Results: {len(summary.results)}",
        f"Skipped for age: {summary.skipped_for_age}",
        f"Skipped for relevance: {summary.skipped_for_relevance}",
        "",
    ]
    if not summary.results:
        lines.append("No matching jobs found.")
        return "\n".join(lines).rstrip() + "\n"

    lines.extend(
        [
            "| Rank | Title | Company | Location | Age | Score | Why | URL |",
            "| --- | --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for index, result in enumerate(summary.results, start=1):
        age_text = result.age_text or (
            f"{result.age_days} days old" if result.age_days is not None else "age unknown"
        )
        lines.append(
            " | ".join(
                [
                    f"| {index}",
                    _md(result.title),
                    _md(result.company or "Unknown company"),
                    _md(result.location or result.workplace_type or "-"),
                    _md(age_text),
                    str(result.score),
                    _md(", ".join(result.reasons) or "-"),
                    str(result.url),
                ]
            )
            + " |"
        )
    return "\n".join(lines).rstrip() + "\n"


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()
