"""Rebuild evals/cases.md, the easy-to-read page of test cases, from cases.json.

    python -m evals.render_cases
"""

import json
from collections import Counter
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent


def main() -> None:
    cases = json.loads((EVAL_DIR / "cases.json").read_text(encoding="utf-8"))

    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "two cases share an id"
    bodies = [c["email"]["body"] for c in cases]
    assert len(bodies) == len(set(bodies)), "two cases have the same email"
    for c in cases:
        assert set(c) == {"id", "tags", "email", "must", "must_not"}, f"{c['id']}: unexpected fields"
        assert c["must"] or c["must_not"], f"{c['id']}: has no checklist"

    groups = Counter(c["tags"][0] for c in cases)
    lines = [
        "# Eval cases",
        "",
        "This page is generated from `cases.json` so the cases are easy to read. Edit `cases.json`, not this file.",
        "",
        f"{len(cases)} test emails. " + ", ".join(f"{n} {g}" for g, n in groups.items()) + ".",
        "",
        "| # | id | group | subject | must | must not |",
        "|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(cases, 1):
        lines.append(
            f"| {i} | {c['id']} | {c['tags'][0]} | {c['email']['subject']} | {len(c['must'])} | {len(c['must_not'])} |"
        )
    for i, c in enumerate(cases, 1):
        e = c["email"]
        lines += [
            "", f"## {i}. {c['id']}", "", f"Group: {', '.join(c['tags'])}", "",
            f"From: {e['from_name']} <{e['from_address']}>  ", f"Subject: {e['subject']}", "",
            "````text", e["body"], "````", "",
            "A good reply must:",
        ]
        lines += [f"- {m}" for m in c["must"]] or ["- (nothing required)"]
        lines += ["", "A good reply must not:"]
        lines += [f"- {m}" for m in c["must_not"]] or ["- (nothing forbidden)"]

    (EVAL_DIR / "cases.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote cases.md: {len(cases)} cases, {dict(groups)}")


if __name__ == "__main__":
    main()
