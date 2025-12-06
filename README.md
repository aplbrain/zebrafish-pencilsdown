# Zebrafish "Pencils-Down" Paper

Repository point of contact: [Jordan Matelsky](@j6k4m8)

This repository contains code for the preprocessing and analysis of the "Pencils down" paper exploring the relationship between proofreading effort and connectome/contactome quality.

## Preprocessing

### Create connected-components labels of synapses

```python
uv run igneous -p 4 image ccl auto s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses_relabeled --mip 1 --fill-missing --dust 6 --threshold-gte 2 --threshold-lte 2 --queue q-syn-ccl


uv run igneous image ccl faces s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses --mip 1 --fill-missing --dust 6 --threshold-gte 2 --threshold-lte 2 --queue q-syn-ccl
uv run igneous execute -x q-syn-ccl
uv run igneous image ccl links s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses --mip 1 --fill-missing --dust 6 --threshold-gte 2 --threshold-lte 2 --queue q-syn-ccl
uv run igneous execute -x q-syn-ccl
uv run igneous image ccl calc-labels s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses --mip 1
uv run igneous image ccl relabel s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses_relabeled --mip 1 --fill-missing --dust 6 --threshold-gte 2 --threshold-lte 2 --queue q-syn-ccl --encoding compresso
uv run igneous execute -x q-syn-ccl
uv run igneous image ccl clean s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses # removes intermediate files
```

### Create timeseries of changes

```bash
wget https://taurus.agglomeration.ariadne.ai/api/changes.tsv -O changes.tsv
```

Because this file is checked into version control, you should see new lines added in the diff of this file.

You can now run the orchestration CLI (instead of the individual notebooks) using the project manage script:

```bash
uv run python manage.py changelog subsample --step-size 5000
uv run python manage.py remap generate
uv run python manage.py checkpoint upload
```

-   `manage.py changelog subsample` converts the Ariadne changelog into incremental NetworkX snapshots (stored in `component-graphs/`). The `--step-size` flag controls the cadence of snapshots, and you can disable writing intermediate changelog exports with `--skip-change-logs`.
-   `manage.py remap generate` walks the component graphs to produce remap dictionaries (`*.remap.json`) for each milestone.
-   `manage.py checkpoint upload` constructs CloudVolume checkpoints for each remap dictionary. You can adjust the mip level for reading/writing (`--mip`), override destination chunk sizes (`--chunk-size`), parallelism (`--jobs`), chunk traversal (`--block-size`), source/destination paths, and skip already uploaded edit counts via repeated `--skip` flags.

For example, to make the 50K checkpoint when 0-45 already exist:

```bash
uv run python manage.py checkpoint upload --skip 5000 --skip 10000 --skip 15000 --skip 20000 --skip 25000 --skip 30000 --skip 35000 --skip 40000 --skip 45000
```

This workflow results in the creation of several `agglomeration_checkpoint_####` channels, where each `####` is a checkpoint number corresponding to the number of edits performed to reach this agglomeration threshold.

### Generating shuffled controls

To build control checkpoints with fully permuted edit histories, request one or more shuffles when subsampling:

```bash
uv run python manage.py changelog subsample --step-size 5000 --shuffle-count 2 --shuffle-seed 42 --shuffle-mode default
```

This command writes the canonical snapshots to `component-graphs/` and adds complete random permutations to `component-graphs/shuffle_1/`, `component-graphs/shuffle_2/`, etc. Produce the associated remap dictionaries for a specific shuffle with:

```bash
uv run python manage.py remap generate --shuffle-id 1
```

Upload shuffled checkpoints by selecting the same shuffle identifier (the destination stem defaults to `.../shuffle_1_checkpoint_` when not overridden):

```bash
uv run python manage.py checkpoint upload --shuffle-id 1
```

Repeat for `shuffle_2`, `shuffle_3`, etc., to create `shuffle_X_checkpoint_5000`, `shuffle_X_checkpoint_10000`, and so on.

Shuffle strategy: By default shuffles preserve per-pair merge/split ordering so a split never precedes its merge. Use `--shuffle=naive` on the `changelog subsample` command to revert to the legacy fully random permutation if needed.

See [Neuroglancer Links](docs/Neuroglancer-Links.md) for visuals.

## For new checkpoints

After re-running `wget` to get the latest changes, there may be new checkpoints to create. Run the three commands above in order, and then you can run these postprocessing steps:

```bash
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_40000 --mip 0 --num-mips 1 --fill-missing --queue q-downsample
uv run igneous --parallel 8 execute -x q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_40000 --mip 1 --num-mips 3 --fill-missing --volumetric --queue q-downsample
uv run igneous --parallel 8 execute -x q-downsample

uv run igneous mesh forge s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_40000 --mip 2 --queue ./q-mesh --sharded
uv run igneous execute -x ./q-mesh

uv run igneous mesh merge-sharded s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_40000 --queue ./q-mesh-sharded --nlod 0
uv run igneous execute -x ./q-mesh-sharded
```
