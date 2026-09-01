# Pencils Down Paper

This repository contains the checkpoint-generation and graph-analysis code for the zebrafish proofreading study, published in [Connectome quality converges predictably to reveal optimal stopping points during proofreading](https://doi.org/10.64898/2026.06.30.735414). The active workflow now follows a science-repo layout:

- `data/raw/`: external inputs such as `changes.tsv`, connectome CSVs, and contactome CSVs
- `data/provided/`: stable project-supplied inputs
- `data/generated/`: derived intermediates such as component-graph snapshots and invariant JSONs
- `analysis/`: workflow entrypoints
- `notebooks/`: legacy notebooks that are useful to keep around
- `src/zfish/`: shared Python package
- `src/hemibrain/`: standalone slurm scripts for Hemibrain analysis
- `results/data/`: final summary tables
- `results/figures/`: final figures
- `Snakefile`: reproducible workflow wiring

`data/` remains ignored in git. Code and `results/` are the tracked outputs.

## Setup

```bash
uv sync --group dev
```

## Checkpoint Workflow

This workflow converts an Ariadne proofreading changelog into a series of segmentation checkpoints that can be visualized or analyzed. The process consists of four stages:

1. Download the proofreading changelog
2. Reconstruct intermediate agglomeration graphs
3. Generate supervoxel remapping tables
4. Apply each remapping to the original supervoxel segmentation to create checkpoint volumes

The default directory structure is

```text
data/
├── raw/
│   └── changes.tsv
└── generated/
    ├── component-graphs/
    └── remaps/
```

Each stage uses the output of the previous stage.


### 1. Download the Ariadne changelog

Download the proofreading edit history from your Ariadne deployment.

```bash
wget https://<ariadne-domain>/api/changes.tsv \
    -O data/raw/changes.tsv
```

This file records every merge and split operation performed during proofreading.

### 2. Generate component graph snapshots

Reconstruct the agglomeration state after every *N* proofreading edits.

```bash
uv run python manage.py changelog subsample
```

| Argument | Default | Description |
|-----------|---------|-------------|
| `--changes-file` | `data/raw/changes.tsv` | Input Ariadne changelog |
| `--output-dir` | `data/generated/component-graphs` | Directory for graph snapshots |
| `--step-size` | `5000` | Number of proofreading edits between checkpoints |
| `--max-changes` | Process entire changelog | Stop after *N* edits |
| `--shuffle-count` | `0` | Generate randomized proofreading orders |


### 3. Generate remapping dictionaries

Create lookup tables mapping every supervoxel ID to its agglomerated object ID for each checkpoint.

```bash
uv run python manage.py remap generate
```

| Argument | Default |
|-----------|---------|
| `--component-graph-dir` | `data/generated/component-graphs` |
| `--output-dir` | `data/generated/remaps` |

### 4. Generate checkpoint segmentations

Apply each remapping dictionary to the original supervoxel segmentation.

```bash
uv run python manage.py checkpoint upload \
    --supervoxels-path precomputed://<path-to-supervoxels> \
    --checkpoint-prefix precomputed://<output-prefix>
```

The result is a sequence of segmentation checkpoints representing the dataset at different stages of proofreading.

| Argument | Default |
|-----------|-------------|
| `--supervoxels-path` | (required) CloudVolume containing the original supervoxel segmentation |
| `--checkpoint-prefix` | (required) Prefix used when writing checkpoint segmentations |
| `--component-graph-dir` | `data/generated/component-graphs` |
| `--remap-dir` | `data/generated/remaps` |
| `--mip` | `0` |
| `--jobs` | `1` |
| `--block-size` | `(512, 512, 64)` |
| `--chunk-size` | `(512, 512, 64)` |
| `--skip` | `0` |
| `--shuffle-id` | `None` |
| `--randomize` | Enabled (disable with `--no-randomize`) |
| `--progress` | Enabled (disable with `--no-progress`) |


## Analysis Workflow

Put one ordered connectome series under `data/raw/connectomes/original_order/` and one ordered contactome series under `data/raw/contactomes/original_order/`. The loaders also accept the legacy `data/connectomes` and `data/contactomes` paths for one migration cycle.

Run the full analysis with Snakemake:

```bash
uv run snakemake --cores 1
```

This produces:

- `data/generated/connectome/invariants.json`
- `data/generated/contactome/invariants.json`
- `results/data/*-convergence-summary.md`
- `results/data/*-convergence-summary.tex`
- `results/data/*-convergence-stats.json`
- `results/figures/*-convergence/`
- `results/data/*-projection-summary.md`
- `results/data/*-projection-summary.tex`
- `results/data/*-projection-summary.csv`
- `results/data/*-projection-stats.json`
- `results/figures/*-projection-milestones/`

The default metric profile is `fast`. It prefers scalable or approximate graph metrics and avoids exhaustive computations such as exact diameter in routine runs.

You can run workflow steps directly while developing:

```bash
uv run python analysis/invariants/run.py \
  --dataset connectome \
  --input-dir data/raw/connectomes/original_order \
  --output-json data/generated/connectome/invariants.json \
  --metric-profile fast

uv run python analysis/convergence/run.py \
  --dataset connectome \
  --input-json data/generated/connectome/invariants.json \
  --summary-md results/data/connectome-convergence-summary.md \
  --summary-tex results/data/connectome-convergence-summary.tex \
  --stats-json results/data/connectome-convergence-stats.json \
  --figure-dir results/figures/connectome-convergence

uv run python analysis/projections/run.py \
  --dataset connectome \
  --input-json data/generated/connectome/invariants.json \
  --convergence-stats results/data/connectome-convergence-stats.json \
  --summary-md results/data/connectome-projection-summary.md \
  --summary-tex results/data/connectome-projection-summary.tex \
  --summary-csv results/data/connectome-projection-summary.csv \
  --stats-json results/data/connectome-projection-stats.json \
  --figure-dir results/figures/connectome-projection-milestones
```

## Attribution

For questions or collaboration inquiries, please email hannah.martinez@jhuapl.edu or jordan.matelsky@jhuapl.edu.

This software was created by the Johns Hopkins University Applied Physics Laboratory, with funding supported by the NIH BRAIN Initiative under grant no. R24MH114785.

The views, opinions, and/or findings expressed are those of the author(s) and should not be interpreted as representing the official views or policies of the NIH.

© 2026 The Johns Hopkins University Applied Physics Laboratory LLC
