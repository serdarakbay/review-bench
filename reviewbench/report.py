"""Build report.md + plots from one or more runs' calls.jsonl.

Every number comes from logged calls; nothing is estimated. Rates carry Wilson
95% CIs. Reviewer differences on the same samples are tested with the exact
McNemar test, Holm-adjusted across all comparisons in the report.
"""

from datetime import datetime
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from reviewbench.dataset import read_jsonl  # noqa: E402
from reviewbench.scoring import (  # noqa: E402
    GROUP_KEYS, by_bug_type, group_by, holm, mcnemar_exact, paired_counts, summarize,
)

# Reference palette (light mode): categorical slots in fixed order, text inks, surface.
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
# Color follows the entity: a reviewer keeps its color in every chart and report.
REVIEWER_ORDER = ["ollama", "gemini", "claude", "codex"]
PROMPT_STYLE = {"neutral": ("o", SLOTS[0]), "adversarial": ("^", SLOTS[1])}
BLUES = LinearSegmentedColormap.from_list("blues", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab"])


def reviewer_color(name: str) -> str:
    i = REVIEWER_ORDER.index(name) if name in REVIEWER_ORDER else len(REVIEWER_ORDER)
    return SLOTS[min(i, len(SLOTS) - 1)]


def load_calls(run_dirs: list[Path]) -> list[dict]:
    calls = []
    for d in run_dirs:
        calls += read_jsonl(d / "calls.jsonl")
    return calls


def label(key: tuple) -> str:
    reviewer, model, prompt_name, prompt_version = key
    return f"{model} / {prompt_name}_{prompt_version}"


def pct(rate) -> str:
    if rate.value is None:
        return "-"
    lo, hi = rate.ci
    return f"{rate.value:.1%} [{lo:.0%}–{hi:.0%}] ({rate.k}/{rate.n})"


# --- comparisons --------------------------------------------------------------


def comparisons(groups: dict[tuple, list[dict]]) -> list[dict]:
    """Prompt effect within each reviewer, and reviewer vs reviewer within each prompt."""
    pairs = []
    for ka, kb in combinations(groups, 2):
        same_reviewer = ka[:2] == kb[:2]
        same_prompt = ka[2:] == kb[2:]
        if same_reviewer != same_prompt:  # exactly one of the two differs
            pairs.append((ka, kb))
    rows = []
    for ka, kb in pairs:
        for metric, buggy in (("catch", True), ("false alarm", False)):
            n, only_a, only_b = paired_counts(groups[ka], groups[kb], buggy)
            if n:
                rows.append({"a": label(ka), "b": label(kb), "metric": metric, "n": n,
                             "only_a": only_a, "only_b": only_b, "p": mcnemar_exact(only_a, only_b)})
    for row, adjusted in zip(rows, holm([r["p"] for r in rows])):
        row["p_holm"] = adjusted
    return rows


# --- plots --------------------------------------------------------------------


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_rates(groups: dict[tuple, list[dict]], path: Path) -> None:
    """Catch rate and false-alarm rate with 95% CI, one row per reviewer, one marker per prompt."""
    reviewers = sorted({k[:2] for k in groups}, key=lambda k: (reviewer_color(k[0]), k[1]))
    fig, axes = plt.subplots(1, 2, figsize=(10, 1.2 + 0.7 * len(reviewers)), sharey=True, facecolor=SURFACE)
    for ax, (title, metric) in zip(axes, (("Catch rate (buggy samples)", "catch_rate"),
                                          ("False-alarm rate (correct samples)", "false_alarm_rate"))):
        _style(ax)
        for key, calls in groups.items():
            rate = summarize(calls)[metric]
            if rate.value is None:
                continue
            marker, color = PROMPT_STYLE.get(key[2], ("s", SLOTS[2]))
            y = reviewers.index(key[:2]) + (-0.15 if key[2] == "neutral" else 0.15)
            lo, hi = rate.ci
            err = [[max(0.0, rate.value - lo) * 100], [max(0.0, hi - rate.value) * 100]]
            ax.errorbar(rate.value * 100, y, xerr=err,
                        fmt=marker, color=color, markersize=8, elinewidth=2, capsize=0,
                        markeredgecolor=SURFACE, markeredgewidth=1.5)
        ax.set_xlim(0, 100)
        ax.set_title(title, color=INK, fontsize=11, loc="left")
        ax.set_xlabel("%  (bars: Wilson 95% CI)", color=INK_2, fontsize=9)
    axes[0].set_yticks(range(len(reviewers)), [m for _, m in reviewers], color=INK)
    axes[0].invert_yaxis()
    handles = [plt.Line2D([], [], marker=m, color=c, linestyle="", markersize=8, label=f"{p} prompt")
               for p, (m, c) in PROMPT_STYLE.items()]
    fig.legend(handles=handles, loc="upper right", frameon=False, labelcolor=INK_2, ncol=2)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def plot_bug_types(groups: dict[tuple, list[dict]], path: Path) -> None:
    """Heatmap: catch rate per bug type (columns) for each reviewer/prompt (rows)."""
    keys = list(groups)
    per = {k: by_bug_type(groups[k]) for k in keys}
    bug_types = sorted({bt for k in keys for bt in per[k]})
    fig, ax = plt.subplots(figsize=(1.5 + 1.25 * len(bug_types), 0.9 + 0.5 * len(keys)), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    values = [[(per[k][bt]["catch_rate"].value if bt in per[k] else float("nan")) for bt in bug_types] for k in keys]
    ax.imshow([[v * 100 for v in row] for row in values], cmap=BLUES, vmin=0, vmax=100, aspect="auto")
    for i, k in enumerate(keys):
        for j, bt in enumerate(bug_types):
            if bt not in per[k]:
                continue
            r = per[k][bt]["catch_rate"]
            ax.text(j, i, f"{r.value:.0%}\n{r.k}/{r.n}", ha="center", va="center", fontsize=8,
                    color=SURFACE if r.value >= 0.6 else INK)
    ax.set_xticks(range(len(bug_types)), bug_types, rotation=30, ha="right", color=INK, fontsize=9)
    ax.set_yticks(range(len(keys)), [label(k) for k in keys], color=INK, fontsize=9)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Catch rate by bug type", color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def plot_cost_f1(groups: dict[tuple, list[dict]], path: Path) -> None:
    """F1 against cost per 100 reviews (API list-price equivalent)."""
    fig, ax = plt.subplots(figsize=(7, 4.2), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    reviewers = {}
    for key, calls in groups.items():
        s = summarize(calls)
        n_scored = s["n_calls"] - s["n_errors"]
        if s["f1"] is None or not n_scored:
            continue
        cost100 = 100 * s["cost_usd"] / n_scored
        marker = PROMPT_STYLE.get(key[2], ("s", None))[0]
        ax.scatter(cost100, s["f1"], s=70, marker=marker, color=reviewer_color(key[0]),
                   edgecolors=SURFACE, linewidths=1.5, zorder=3)
        reviewers[key[1]] = reviewer_color(key[0])
    # Color = reviewer, shape = prompt: two small legends instead of per-point labels.
    color_handles = [plt.Line2D([], [], marker="o", color=c, linestyle="", markersize=8, label=m)
                     for m, c in reviewers.items()]
    shape_handles = [plt.Line2D([], [], marker=m, color=INK_2, linestyle="", markersize=7, label=f"{p} prompt")
                     for p, (m, _) in PROMPT_STYLE.items()]
    first = ax.legend(handles=color_handles, frameon=False, labelcolor=INK_2, fontsize=9, loc="lower right")
    ax.add_artist(first)
    ax.legend(handles=shape_handles, frameon=False, labelcolor=INK_2, fontsize=9, loc="lower left")
    ax.set_xlabel("USD per 100 reviews (API list price; Ollama = local, $0)", color=INK_2, fontsize=9)
    ax.set_ylabel("F1", color=INK_2, fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_xlim(left=-0.02)
    ax.set_title("Quality vs cost", color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


# --- report.md ----------------------------------------------------------------


def build_markdown(calls: list[dict], groups: dict[tuple, list[dict]], comps: list[dict],
                   sources: list[str], plots: list[str]) -> str:
    lines = [
        "# review-bench report",
        "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M} from {len(calls)} logged calls in: "
        + ", ".join(f"`{s}`" for s in sources),
        "",
        "Conventions: rates are shown with Wilson 95% CIs. API errors are excluded. PARSE_ERROR counts as "
        "\"not flagged\" and stays in the denominators. Localization = reported line within ±1 of the real "
        "bug line, among caught bugs with a known line. Cost = API list-price equivalent (Ollama is "
        "local, Claude runs on a subscription, Gemini was billed at list price).",
        "",
        "## Headline metrics",
        "",
        "| reviewer / prompt | catch rate | localization | false alarm | precision | F1 | parse fail "
        "| errors | thinking | mean latency | cost |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for key, g in groups.items():
        s = summarize(g)
        scored = [c for c in g if c.get("error") is None]
        thinking = sum(bool(c.get("thinking")) for c in scored) / len(scored) if scored else 0
        f1_text = "-" if s["f1"] is None else f"{s['f1']:.3f}"
        latency = "-" if s["mean_latency_s"] is None else f"{s['mean_latency_s']:.1f}s"
        lines.append(
            f"| {label(key)} | {pct(s['catch_rate'])} | {pct(s['localization'])} | {pct(s['false_alarm_rate'])} "
            f"| {pct(s['precision'])} | {f1_text} | {pct(s['parse_failure_rate'])} | {s['n_errors']} "
            f"| {thinking:.0%} | {latency} | ${s['cost_usd']:.2f} |"
        )
    lines += ["", *[f"![{p}]({p})" for p in plots], "", "## Catch rate by bug type", ""]
    bug_types = sorted({bt for g in groups.values() for bt in by_bug_type(g)})
    lines += ["| reviewer / prompt | " + " | ".join(bug_types) + " |",
              "|---|" + "---|" * len(bug_types)]
    for key, g in groups.items():
        bt = by_bug_type(g)
        cells = [pct(bt[t]["catch_rate"]) if t in bt else "-" for t in bug_types]
        lines.append(f"| {label(key)} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## Paired comparisons (exact McNemar, same samples)",
        "",
        "`A only` / `B only` = samples where only A / only B flagged BUG. For *catch*, more is better; "
        "for *false alarm*, fewer is better. p-values are Holm-adjusted across all "
        f"{len(comps)} tests in this table.",
        "",
        "| A | B | metric | n pairs | A only | B only | p | p (Holm) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in comps:
        flag = " **\\***" if r["p_holm"] < 0.05 else ""
        lines.append(f"| {r['a']} | {r['b']} | {r['metric']} | {r['n']} | {r['only_a']} | {r['only_b']} "
                     f"| {r['p']:.3g} | {r['p_holm']:.3g}{flag} |")
    lines += ["", "\\* = significant at 0.05 after Holm adjustment.", ""]
    return "\n".join(lines)


def write_report(run_dirs: list[Path], out_dir: Path) -> Path:
    calls = load_calls(run_dirs)
    groups = group_by(calls, GROUP_KEYS)
    out_dir.mkdir(parents=True, exist_ok=True)
    plots = ["rates.png", "bug_types.png", "cost_f1.png"]
    plot_rates(groups, out_dir / plots[0])
    plot_bug_types(groups, out_dir / plots[1])
    plot_cost_f1(groups, out_dir / plots[2])
    md = build_markdown(calls, groups, comparisons(groups), [d.name for d in run_dirs], plots)
    path = out_dir / "report.md"
    path.write_text(md, encoding="utf-8")
    return path
