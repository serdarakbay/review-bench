"""README figures: the writer x reviewer matrix and the persona effect.

Every number comes from logged calls in results/ plus the manual right-reason
counts in docs/right_reason_counts.json. Missing runs or rows are left out of
the figure, never estimated, so the figures can be rebuilt as runs land.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from reviewbench.config import ROOT  # noqa: E402
from reviewbench.report import GRID, INK, INK_2, SURFACE, _style, reviewer_color  # noqa: E402
from reviewbench.scoring import Rate, catch_rate, false_alarm_rate  # noqa: E402

REVIEWERS = ["claude", "gemini", "gemini-argon", "gemini-lite", "ollama"]
REVIEWER_LABEL = {
    "claude": "Claude Sonnet 5.5",
    "gemini": "Gemini 3.8 Flash",
    "gemini-argon": "Gemini 4 Argon",
    "gemini-lite": "Gemini 3.5 Flash-Lite",
    "ollama": "Qwen 3.5 9B",
}
# Writers of the natural MBPP+ sets: (key in right_reason_counts.json, label, run, adjudication, real-bug class).
WRITERS = [
    ("claude", "Claude Sonnet 5.5", "natural-mbpp-v1", "natural_mbpp_v1_adjudication.json", "claude_bug"),
    ("gemini", "Gemini 3.8 Flash", "natural-mbpp-gemini-v1", "natural_mbpp_gemini_v1_adjudication.json",
     "gemini_bug"),
]
VARIANTS = [
    ("neutral", "neutral"),
    ("persona-agency-code-reviewer", "agency reviewer"),
    ("persona-wshobson-security-auditor", "wshobson security"),
    ("persona-voltagent-qa-expert", "voltagent QA"),
]
MUTED = "#8a8984"
SHADE = "#efeeea"  # background band for the same-model row


def load_run(run: str) -> list[dict]:
    """Scored calls (no `error`) of results/<run>/calls.jsonl; [] if the run does not exist."""
    path = ROOT / "results" / run / "calls.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [r for r in rows if r.get("error") is None]


def select(calls: list[dict], reviewer: str, prompt: str) -> list[dict]:
    return [c for c in calls if c["reviewer"] == reviewer and c["prompt_name"] == prompt]


def real_bug_flags(calls: list[dict], adjudication: dict, real_class: str) -> Rate:
    """BUG verdicts on the samples adjudicated as real bugs of class `real_class` / those samples."""
    real = [c for c in calls if c["is_buggy"] and adjudication.get(c["sample_id"]) == real_class]
    return Rate(sum(c["verdict"] == "BUG" for c in real), len(real))


def _same_model(writer: str, reviewer: str) -> bool:
    return writer == reviewer  # claude reviews claude, gemini (Flash) reviews gemini (Flash)


def _ci_err(rate: Rate) -> list[list[float]]:
    lo, hi = rate.ci
    return [[max(0.0, rate.value - lo) * 100], [max(0.0, hi - rate.value) * 100]]


def _yticks(ax, labels: list[str], bold: list[bool]) -> None:
    ax.set_yticks(range(len(labels)), labels, color=INK, fontsize=9.5)
    for tick, b in zip(ax.get_yticklabels(), bold):
        tick.set_fontweight("bold" if b else "normal")
    ax.set_ylim(len(labels) - 0.5, -0.5)


# --- figure 1: writer x reviewer --------------------------------------------------------


def plot_writer_reviewer(path: Path) -> dict:
    counts = json.loads((ROOT / "docs" / "right_reason_counts.json").read_text(encoding="utf-8"))
    fig, axes = plt.subplots(2, 2, figsize=(9.6, 7.4), facecolor=SURFACE,
                             gridspec_kw={"width_ratios": [3.6, 1.6], "hspace": 0.55, "wspace": 0.06})
    plotted = {}
    for row, (wkey, wlabel, run, adj_file, real_class) in enumerate(WRITERS):
        calls = load_run(run)
        adj = json.loads((ROOT / "docs" / adj_file).read_text(encoding="utf-8"))
        ax_bug, ax_fa = axes[row]
        for ax in (ax_bug, ax_fa):
            _style(ax)
        labels, bold = [], []
        n_real = n_correct = 0
        for y, rev in enumerate(REVIEWERS):
            same = _same_model(wkey, rev)
            labels.append(REVIEWER_LABEL[rev] + ("\n(same model)" if same else ""))
            bold.append(same)
            group = select(calls, rev, "neutral")
            if not group:
                ax_bug.text(0.15, y, "no run yet", va="center", color=MUTED, fontsize=8.5, style="italic")
                continue
            color = reviewer_color(rev)
            flags = real_bug_flags(group, adj, real_class)
            fa = false_alarm_rate(group)
            n_real, n_correct = max(n_real, flags.n), max(n_correct, fa.n)
            graded = counts.get(wkey, {}).get(rev)
            ax_bug.barh(y, flags.k, height=0.62, color=color, alpha=0.25, linewidth=0)
            text = f"{flags.k} flagged"
            if graded:
                right, partial = graded["right"], graded["partial"]
                ax_bug.barh(y, right, height=0.62, color=color, linewidth=0)
                if partial:
                    ax_bug.barh(y, partial, left=right, height=0.62, color="none", edgecolor=color,
                                hatch="////", linewidth=0)
                text += f"  ·  {right} right" + (f" + {partial} partial" if partial else "")
            else:
                text += "  ·  reasons not graded yet"
            ax_bug.text(flags.k + 0.15, y, text, va="center", color=INK_2, fontsize=8.5)
            if fa.n:
                ax_fa.errorbar(fa.value * 100, y, xerr=_ci_err(fa), fmt="o", color=color, markersize=8,
                               elinewidth=2, capsize=0, markeredgecolor=SURFACE, markeredgewidth=1.5)
                ax_fa.text(fa.ci[1] * 100 + 2, y, f"{fa.k}/{fa.n}", va="center", color=INK_2, fontsize=8.5)
            plotted[(wkey, rev)] = {"flagged": f"{flags.k}/{flags.n}", "right_partial": graded,
                                    "false_alarm": f"{fa.k}/{fa.n}"}
            if same:  # shade the same-model row in both panels
                for ax in (ax_bug, ax_fa):
                    ax.axhspan(y - 0.5, y + 0.5, color=SHADE, zorder=0, linewidth=0)
        _yticks(ax_bug, labels, bold)
        ax_fa.set_yticks(range(len(labels)), [""] * len(labels))
        ax_fa.set_ylim(len(labels) - 0.5, -0.5)
        ax_bug.set_xlim(0, 13.2)  # room for the bar labels; the axis itself stops at 10
        ax_bug.set_xticks(range(0, 11, 2))
        ax_bug.spines["bottom"].set_bounds(0, 10)
        ax_fa.set_xlim(0, 100)
        ax_fa.set_xticks([0, 25, 50, 75, 100])
        ax_bug.set_title(f"Code written by {wlabel}", color=INK, fontsize=11, loc="left", fontweight="bold")
        ax_bug.set_xlabel(f"real bugs flagged (of {n_real or 10})", color=INK_2, fontsize=9)
        ax_fa.set_title(f"False alarms ({n_correct} correct)", color=INK, fontsize=10,
                        loc="left")
        ax_fa.set_xlabel("%  (bars: Wilson 95% CI)", color=INK_2, fontsize=9)
    legend = [Patch(color=INK_2, alpha=0.25, label="flagged BUG"),
              Patch(color=INK_2, label="right reason (manual)"),
              Patch(facecolor="none", edgecolor=INK_2, hatch="////", label="partial reason")]
    fig.legend(handles=legend, loc="upper left", bbox_to_anchor=(0.01, 0.925), ncol=3, frameon=False,
               labelcolor=INK_2, fontsize=9)
    fig.suptitle("Is a model a better reviewer of its own code?", x=0.01, y=0.995, ha="left", color=INK,
                 fontsize=14, fontweight="bold")
    fig.text(0.01, 0.945, "Natural bugs in MBPP+ solutions, neutral prompt. Real bugs = manually adjudicated "
             "test failures. Shaded row = the reviewer is the writer's model.", color=INK_2, fontsize=9)
    fig.subplots_adjust(left=0.19, right=0.98, top=0.85, bottom=0.07)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return plotted


# --- figure 2: persona effect -------------------------------------------------------------


def _persona_panels() -> list[tuple[str, str, dict[str, list[dict]]]]:
    """(title, reviewer, {variant: calls}) per panel row; variants without calls are left out."""
    synth, v2, gem_code = load_run("personas-v2-synth"), load_run("samples-v2"), load_run("natural-mbpp-gemini-v1")
    panels = []
    for rev in ("claude", "gemini", "gemini-argon", "gemini-lite", "ollama"):
        variants = {}
        for prompt, _ in VARIANTS:
            source = v2 if prompt == "neutral" and rev != "ollama" else synth
            calls = [c for c in select(source, rev, prompt) if c.get("error") is None]
            if calls:
                variants[prompt] = calls
        full = len(variants.get("neutral", []))
        # a variant stopped early (API spending cap) covers other samples than neutral: leave it out
        variants = {p: v for p, v in variants.items() if len(v) >= full}
        if variants:
            panels.append((f"{REVIEWER_LABEL[rev]}  (samples_v2)", rev, variants))
    adj = json.loads((ROOT / "docs" / "natural_mbpp_gemini_v1_adjudication.json").read_text(encoding="utf-8"))
    variants = {}
    for prompt, _ in VARIANTS:
        calls = select(gem_code, "claude", prompt)
        if calls:  # buggy side = the adjudicated real Gemini bugs only
            variants[prompt] = [c for c in calls if not c["is_buggy"] or adj.get(c["sample_id"]) == "gemini_bug"]
    if variants:
        panels.append(("Claude Sonnet 5.5 on Gemini 3.8 Flash's code  (natural MBPP+, real bugs only)",
                       "claude", variants))
    return panels


def plot_persona_effect(path: Path) -> dict:
    panels = _persona_panels()
    ratios = [len(v) for _, _, v in panels]
    top, bottom, gap, row_h = 1.45, 0.55, 0.55, 0.36  # inches
    height = top + bottom + row_h * sum(ratios) + gap * (len(panels) - 1)
    fig, axes = plt.subplots(len(panels), 2, figsize=(9.6, height), facecolor=SURFACE, sharex="col",
                             squeeze=False, gridspec_kw={"height_ratios": ratios, "wspace": 0.1,
                                                         "hspace": gap / (row_h * sum(ratios) / len(panels))})
    fig.subplots_adjust(left=0.17, right=0.98, top=1 - top / height, bottom=bottom / height)
    plotted = {}
    label = dict(VARIANTS)
    for row, (title, rev, variants) in enumerate(panels):
        color = reviewer_color(rev)
        names = list(variants)
        for col, metric in enumerate((catch_rate, false_alarm_rate)):
            ax = axes[row][col]
            _style(ax)
            base = metric(variants["neutral"]) if "neutral" in variants else None
            if base and base.n:
                ax.axvline(base.value * 100, color=MUTED, linewidth=1, linestyle=(0, (3, 2)), zorder=1)
            for y, prompt in enumerate(names):
                rate = metric(variants[prompt])
                if not rate.n:
                    continue
                neutral = prompt == "neutral"
                ax.errorbar(rate.value * 100, y, xerr=_ci_err(rate), fmt="o", color=color, markersize=8,
                            elinewidth=2, capsize=0, zorder=3, markeredgewidth=2 if neutral else 1.5,
                            markerfacecolor=SURFACE if neutral else color,
                            markeredgecolor=color if neutral else SURFACE)
                plotted.setdefault((title, prompt), {})[metric.__name__] = f"{rate.k}/{rate.n}"
            ax.set_ylim(len(names) - 0.5, -0.5)
            ax.set_xlim(0, 100)
            ax.set_xticks([0, 25, 50, 75, 100])
            if col == 0:
                ax.set_yticks(range(len(names)), [label[p] for p in names], color=INK, fontsize=9.5)
                ax.set_title(title, color=INK, fontsize=10.5, loc="left", fontweight="bold")
            else:
                ax.set_yticks(range(len(names)), [""] * len(names))
    for col, head in enumerate(("Catch rate (buggy samples)", "False-alarm rate (correct samples)")):
        box = axes[0][col].get_position()
        fig.text(box.x0, 1 - 0.95 / height, head, color=INK, fontsize=11.5, ha="left", fontweight="bold")
        fig.add_artist(plt.Line2D([box.x0, box.x1], [1 - 1.03 / height] * 2, color=GRID, linewidth=1))
        axes[-1][col].set_xlabel("%  (bars: Wilson 95% CI)", color=INK_2, fontsize=9)
    fig.text(0.01, 1 - 0.3 / height, "Do role prompts (personas) help a reviewer?", ha="left", va="center",
             color=INK, fontsize=14, fontweight="bold")
    fig.text(0.01, 1 - 0.6 / height, "Persona text as system prompt, same neutral user prompt. Hollow dot and "
             "dashed line = neutral (no persona).", va="center", color=INK_2, fontsize=9)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return plotted


def build_figures(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / "writer_reviewer_matrix.png", out_dir / "persona_effect.png"]
    plot_writer_reviewer(paths[0])
    plot_persona_effect(paths[1])
    return paths
