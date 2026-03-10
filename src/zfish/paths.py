from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROVIDED_DATA_DIR = DATA_DIR / "provided"
GENERATED_DATA_DIR = DATA_DIR / "generated"
RESULTS_DIR = REPO_ROOT / "results"
RESULTS_DATA_DIR = RESULTS_DIR / "data"
RESULTS_FIGURES_DIR = RESULTS_DIR / "figures"


def ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_connectome_dir() -> Path:
    return RAW_DATA_DIR / "connectomes" / "original_order"


def default_contactome_dir() -> Path:
    return RAW_DATA_DIR / "contactomes" / "original_order"


def resolve_dataset_dir(dataset: str, override: Path | None = None) -> Path:
    if override is not None:
        return Path(override)

    candidates = []
    if dataset == "connectome":
        candidates = [
            default_connectome_dir(),
            RAW_DATA_DIR / "connectomes",
            DATA_DIR / "connectomes" / "original_order",
            DATA_DIR / "connectomes",
        ]
    elif dataset == "contactome":
        candidates = [
            default_contactome_dir(),
            RAW_DATA_DIR / "contactomes",
            DATA_DIR / "contactomes" / "original_order",
            DATA_DIR / "contactomes",
        ]
    else:
        raise ValueError(f"Unknown dataset: {dataset}")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def default_changes_path() -> Path:
    candidates = [
        RAW_DATA_DIR / "changes.tsv",
        REPO_ROOT / "changes.tsv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def default_component_graph_dir() -> Path:
    candidates = [
        GENERATED_DATA_DIR / "component-graphs",
        REPO_ROOT / "component-graphs",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def default_invariants_json(dataset: str) -> Path:
    return GENERATED_DATA_DIR / dataset / "invariants.json"


def default_convergence_summary_md(dataset: str) -> Path:
    return RESULTS_DATA_DIR / f"{dataset}-convergence-summary.md"


def default_convergence_summary_tex(dataset: str) -> Path:
    return RESULTS_DATA_DIR / f"{dataset}-convergence-summary.tex"


def default_convergence_stats_json(dataset: str) -> Path:
    return RESULTS_DATA_DIR / f"{dataset}-convergence-stats.json"


def default_convergence_figure_dir(dataset: str) -> Path:
    return RESULTS_FIGURES_DIR / f"{dataset}-convergence"


def default_projection_summary_md(dataset: str) -> Path:
    return RESULTS_DATA_DIR / f"{dataset}-projection-summary.md"


def default_projection_summary_tex(dataset: str) -> Path:
    return RESULTS_DATA_DIR / f"{dataset}-projection-summary.tex"


def default_projection_summary_csv(dataset: str) -> Path:
    return RESULTS_DATA_DIR / f"{dataset}-projection-summary.csv"


def default_projection_stats_json(dataset: str) -> Path:
    return RESULTS_DATA_DIR / f"{dataset}-projection-stats.json"


def default_projection_figure_dir(dataset: str) -> Path:
    return RESULTS_FIGURES_DIR / f"{dataset}-projection-milestones"
