# Updating Checkpoints

## 1. Refresh the changelog input

```bash
wget https://taurus.agglomeration.ariadne.ai/api/changes.tsv -O data/raw/changes.tsv
```

## 2. Generate component-graph snapshots

```bash
uv run python manage.py changelog subsample --step-size 5000
```

This writes changelog excerpts, component graphs, and later remap JSONs under `data/generated/component-graphs/`.

## 3. Build remap dictionaries

```bash
uv run python manage.py remap generate
```

## 4. Upload checkpoint channels

```bash
uv run python manage.py checkpoint upload
```

Use repeated `--skip` flags if you only need to create new checkpoints.

## 5. Generate connectomes and contactomes

Run Cloudome on the uploaded checkpoints and place the ordered series under:

- `data/raw/connectomes/original_order/`
- `data/raw/contactomes/original_order/`

## 6. Run the analysis workflow

```bash
uv run snakemake --cores 1
```

The active analysis is now script- and Snakemake-driven. The old notebooks are retained only as legacy references in `docs/legacy-notebooks/`.
