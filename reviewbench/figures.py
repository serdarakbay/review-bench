"""README figures: the writer x reviewer matrix, the persona effect and the samples_v3 rates.

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
from reviewbench.scoring import Rate, catch_rate, false_alarm_rate, paired_counts, paired_difference  # noqa: E402

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
    fig, axes = plt.subplots(2, 2, figsize=(9.6, 6.9), facecolor=SURFACE,
                             gridspec_kw={"width_ratios": [3.6, 1.6], "hspace": 0.42, "wspace": 0.06})
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
        ax_fa.set_xlim(-5, 100)  # a 0% dot is drawn whole, not cut by the axis
        ax_fa.set_xticks([0, 25, 50, 75, 100])
        ax_fa.spines["bottom"].set_bounds(0, 100)
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
    fig.subplots_adjust(left=0.19, right=0.98, top=0.84, bottom=0.075)
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
    """Persona minus neutral, in percentage points, on the same samples (paired difference, 95% CI)."""
    panels = [(t, r, v) for t, r, v in _persona_panels() if "neutral" in v and len(v) > 1]
    label = dict(VARIANTS)
    rows = []  # (panel index, reviewer, persona, {metric: (diff, lo, hi, b, c)})
    for i, (title, rev, variants) in enumerate(panels):
        for prompt in variants:
            if prompt == "neutral":
                continue
            stats = {}
            for metric, buggy in (("catch", True), ("false_alarm", False)):
                n, b, c = paired_counts(variants["neutral"], variants[prompt], buggy)
                stats[metric] = (*paired_difference(n, b, c), b, c)
            rows.append((i, rev, prompt, stats))
    span = max(abs(v) for *_, st in rows for m in st.values() for v in m[:3]) * 100
    lim = 25 if span < 22 else 50  # wider intervals are cut at the axis edge
    counts = [sum(1 for r in rows if r[0] == i) for i in range(len(panels))]
    top, bottom, gap, row_h = 1.6, 0.6, 0.62, 0.34  # inches
    height = top + bottom + row_h * sum(counts) + gap * (len(panels) - 1)
    fig, axes = plt.subplots(len(panels), 2, figsize=(9.6, height), facecolor=SURFACE, squeeze=False,
                             gridspec_kw={"height_ratios": counts, "wspace": 0.12,
                                          "hspace": gap / (row_h * sum(counts) / len(panels))})
    fig.subplots_adjust(left=0.2, right=0.97, top=1 - top / height, bottom=bottom / height)
    plotted = {}
    for i, (title, rev, variants) in enumerate(panels):
        mine = [r for r in rows if r[0] == i]
        color = reviewer_color(rev)
        for col, metric in enumerate(("catch", "false_alarm")):
            ax = axes[i][col]
            _style(ax)
            ax.axvline(0, color=INK_2, linewidth=1.2, zorder=1)
            for y, (_, _, prompt, st) in enumerate(mine):
                diff, lo, hi, b, c = st[metric]
                lo, hi = max(lo, -lim / 100), min(hi, lim / 100)
                ax.plot([lo * 100, hi * 100], [y, y], color=color, linewidth=2.2, solid_capstyle="round",
                        zorder=2)
                ax.plot(diff * 100, y, "o", color=color, markersize=8.5, markeredgecolor=SURFACE,
                        markeredgewidth=1.5, zorder=3)
                ax.text(hi * 100 + lim * 0.04, y, f"{diff * 100:+.0f} pp", va="center", ha="left",
                        color=INK_2, fontsize=8.5)
                plotted[(title, prompt, metric)] = f"+{c} / -{b}"
            ax.set_ylim(len(mine) - 0.5, -0.5)
            ax.set_xlim(-lim, lim)
            ticks = [-lim, -lim // 2, 0, lim // 2, lim]
            ax.set_xticks(ticks, [f"{t:+d}" if t else "0" for t in ticks])
            ax.tick_params(labelsize=8.5)
            if col == 0:
                ax.set_yticks(range(len(mine)), [label[r[2]] for r in mine], color=INK, fontsize=9.5)
                ax.set_title(title, color=INK, fontsize=10.5, loc="left", fontweight="bold")
            else:
                ax.set_yticks(range(len(mine)), [""] * len(mine))
    heads = (("Catch rate: persona minus neutral", "← fewer bugs caught      more bugs caught →"),
             ("False alarms: persona minus neutral", "← fewer false alarms      more false alarms →"))
    for col, (head, hint) in enumerate(heads):
        box = axes[0][col].get_position()
        fig.text(box.x0, 1 - 1.0 / height, head, color=INK, fontsize=11.5, ha="left", fontweight="bold")
        fig.text((box.x0 + box.x1) / 2, 1 - 1.25 / height, hint, color=INK_2, fontsize=8.5, ha="center")
        axes[-1][col].set_xlabel("percentage points (line: 95% CI of the paired difference)", color=INK_2,
                                 fontsize=8.5)
    fig.text(0.01, 1 - 0.3 / height, "Do role prompts (personas) help a reviewer?", ha="left", va="center",
             color=INK, fontsize=14, fontweight="bold")
    fig.text(0.01, 1 - 0.62 / height, "Each dot: the same reviewer with a persona system prompt minus without "
             "one, on the same samples. A line crossing 0 = no clear effect.", va="center", color=INK_2,
             fontsize=9)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return plotted


# --- figure 3: samples_v3 rates --------------------------------------------------------------


def plot_v3_rates(path: Path) -> dict:
    calls = load_run("samples-v3")
    stats = []
    for rev in REVIEWERS:
        group = select(calls, rev, "neutral")
        if group:
            stats.append((rev, catch_rate(group), false_alarm_rate(group)))
    stats.sort(key=lambda row: row[2].value)
    height = 1.6 + 0.52 * len(stats)
    fig, (ax_c, ax_f) = plt.subplots(1, 2, figsize=(9.6, height), facecolor=SURFACE,
                                     gridspec_kw={"width_ratios": [1.3, 2.7], "wspace": 0.2})
    plotted = {}
    for ax, idx, lim, ticks in ((ax_c, 1, (85, 101), [85, 90, 95, 100]),
                                (ax_f, 2, (-3, 103), [0, 25, 50, 75, 100])):
        _style(ax)
        for y, row in enumerate(stats):
            rate, color = row[idx], reviewer_color(row[0])
            lo, hi = rate.ci
            ax.plot([lo * 100, hi * 100], [y, y], color=color, linewidth=2.2, solid_capstyle="round", zorder=2)
            ax.plot(rate.value * 100, y, "o", color=color, markersize=9, markeredgecolor=SURFACE,
                    markeredgewidth=1.5, zorder=3)
            if idx == 2:
                ax.text(hi * 100 + 2, y, f"{rate.value * 100:.0f}%  ({rate.k}/{rate.n})", va="center",
                        color=INK_2, fontsize=8.5)
            plotted[(row[0], idx)] = f"{rate.k}/{rate.n}"
        ax.set_xlim(*lim)
        ax.set_xticks(ticks)
        ax.spines["bottom"].set_bounds(ticks[0], ticks[-1])
        ax.set_ylim(len(stats) - 0.5, -0.5)
        ax.tick_params(labelsize=8.5)
        ax.set_xlabel("%  (line: Wilson 95% CI)", color=INK_2, fontsize=8.5)
    ax_c.set_yticks(range(len(stats)), [REVIEWER_LABEL[r[0]] for r in stats], color=INK, fontsize=9.5)
    ax_f.set_yticks(range(len(stats)), [""] * len(stats))
    ax_c.set_title("Catch rate (axis from 85%)", color=INK, fontsize=10.5, loc="left", fontweight="bold")
    ax_f.set_title("False-alarm rate on correct code", color=INK, fontsize=10.5, loc="left", fontweight="bold")
    n = stats[0][1].n if stats else 0
    fig.text(0.01, 1 - 0.28 / height, "Harder code (BigCodeBench): bugs are still caught, false alarms "
             "separate the reviewers", ha="left", va="center", color=INK, fontsize=12.5, fontweight="bold")
    fig.text(0.01, 1 - 0.58 / height, f"samples_v3: {n} injected bugs + {n} correct solutions, neutral prompt. "
             "Sorted by false-alarm rate.", color=INK_2, fontsize=9, va="center")
    fig.subplots_adjust(left=0.19, right=0.97, top=1 - 1.05 / height, bottom=0.55 / height)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return plotted


def build_figures(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / "writer_reviewer_matrix.png", out_dir / "persona_effect.png",
             out_dir / "samples_v3_rates.png"]
    plot_writer_reviewer(paths[0])
    plot_persona_effect(paths[1])
    plot_v3_rates(paths[2])
    return paths
