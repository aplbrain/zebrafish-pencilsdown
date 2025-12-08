# Zebrafish "Pencils-Down" Paper

This repository contains code for the preprocessing and analysis of the "Pencils down" paper exploring the relationship between proofreading effort and connectome/contactome quality.

Before the raw data can be analyzed, the raw data must be preprocessed. For details on synaptic connected component relabeling, see [Preprocessing](docs/Preprocessing.md).

## Create timeseries of changes

```bash
wget https://taurus.agglomeration.ariadne.ai/api/changes.tsv -O changes.tsv
```

Because this file is checked into version control, you should see new lines added in the diff of this file.

You can now run these three commands:

### Construct checkpoint changelogs

Convert the Ariadne changelog into incremental NetworkX snapshots (stored in `component-graphs/`). The `--step-size` flag controls the cadence of snapshots, and you can disable writing intermediate changelog exports with `--skip-change-logs`:

```bash
uv run python manage.py changelog subsample --step-size 5000
```

For example, to make the 50K checkpoint when 0-45 already exist:

```bash
uv run python manage.py checkpoint upload --skip 5000 --skip 10000 --skip 15000 --skip 20000 --skip 25000 --skip 30000 --skip 35000 --skip 40000 --skip 45000
```

This command will produce `changes.tsv.#####` files inside of `component-graphs/` where each `#####` is a multiple of `step-size` up to the maximum number of edits in `changes.tsv`. For example, with a `step-size` of `5000` this will generate `changes.tsv.5000`, `changes.tsv.10000`, ..., `changes.tsv.N` where `N` is the largest multiple of `5000` less than or equal to the total number of edits.

This will also generate a final `changes.tsv.#####` file that contains all edits in the original `changes.tsv` and is named with the length of the original file. For example, if `changes.tsv` contains `123456` edits, then a final `changes.tsv.123456` file will be created. This file will not be used for checkpoint generation, but is useful for record-keeping.

### Generate remap dictionaries and upload checkpoints

```bash
uv run python manage.py remap generate
```

This command will read the changelog snapshots created in the previous step and generate remap dictionaries (`*.remap.json` files) that map supervoxel IDs to agglomerated segment IDs at each checkpoint. These are stored in the same `component-graphs/` directory.

As a byproduct, this will also generate `component-graphs/change_nx.#####.gexf` files that contain NetworkX-compatible representations of the component graphs at each checkpoint. The connected components of these graphs correspond to the segments present at each checkpoint.

By convention, the _smallest_ ID in each connected component is chosen as the segment ID for that component. Thus, the remap dictionaries map supervoxel IDs to the smallest supervoxel ID in their connected component at each checkpoint.

### Upload checkpoints

```bash
uv run python manage.py checkpoint upload
```

This workflow results in the creation of several `agglomeration_checkpoint_####` channels, where each `####` is a checkpoint number corresponding to the number of edits performed to reach this agglomeration threshold.

You can adjust the mip level for reading/writing (`--mip`), override destination chunk sizes (`--chunk-size`), parallelism (`--jobs`), chunk traversal (`--block-size`), source/destination paths (`--supervoxels-path`, `--checkpoint-prefix`, `--checkpoint-stem`), and skip already uploaded edit counts via repeated `--skip` flags.

## For new checkpoints

After re-running `wget` to get the latest changes, there may be new checkpoints to create. Run the three commands above in order, and then you can run these postprocessing steps:

```bash
CHECKPOINT=50000
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_${CHECKPOINT} --mip 0 --num-mips 1 --fill-missing --queue q-downsample
uv run igneous --parallel 8 execute -x q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_${CHECKPOINT} --mip 1 --num-mips 6 --fill-missing --volumetric --queue q-downsample
uv run igneous --parallel 8 execute -x q-downsample

uv run igneous mesh forge s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_${CHECKPOINT} --mip 2 --queue ./q-mesh --sharded
uv run igneous execute -x ./q-mesh

uv run igneous mesh merge-sharded s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_${CHECKPOINT} --queue ./q-mesh-sharded --nlod 0
uv run igneous execute -x ./q-mesh-sharded
```

## Neuroglancer Links

See [Neuroglancer Links](docs/Neuroglancer-Links.md) for visuals.

---

## Shuffles

To serve as a control for edit ordering effects, we generate shuffled versions of the agglomeration checkpoints with permuted edit histories.

These permutations cannot be naively random, as that would allow splits to occur before their corresponding merges. For example, if two supervoxels A and B are merged into segment C and then split again later, a naive shuffle could place a nonsensical split of C back into A and B at a prior edit to the merge.

Instead, shuffles are generated as a DAG, where each merge/split operation is a node and edges represent ordering constraints (e.g., a split must occur after its corresponding merge). Any topological sort of this DAG produces a valid edit ordering that respects these constraints, so the default shuffle behavior is to randomly permute the order of operations while preserving these constraints.

### Generating shuffled controls

To build control checkpoints with fully permuted edit histories, request one or more shuffles when subsampling:

```bash
uv run python manage.py changelog subsample --step-size 5000 --shuffle-count 4 --shuffle-seed 42 --shuffle-mode default
```

This command writes the canonical snapshots to `component-graphs/` and adds complete random permutations to `component-graphs/shuffle_1/`, `component-graphs/shuffle_2/`, etc. Produce the associated remap dictionaries for a specific shuffle with:

```bash
uv run python manage.py remap generate --shuffle-id 1
```

The above command should be run, say, four times with `--shuffle-id` values of `1`, `2`, `3`, and `4` to generate remap dictionaries for each shuffle if the original subsample command was run with `--shuffle-count 4`.

Upload shuffled checkpoints by selecting the same shuffle identifier (the destination stem defaults to `.../shuffle_1_checkpoint_` when not overridden):

```bash
uv run python manage.py checkpoint upload \
  --shuffle-id 1 \
  --mip 2 \
  --supervoxels-path precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/supervoxels/ \
  --checkpoint-prefix precomputed://s3://cvdb-bossdb-boss/martinez2026/zebrafish/
```

Each execution of this command uploads a full set of checkpoints for the specified shuffle (i.e., `shuffle_1_checkpoint_5000`, `shuffle_1_checkpoint_10000`, etc.) all uploaded sequentially.

Repeat for `shuffle_2`, etc., to create `shuffle_X_checkpoint_5000`, `shuffle_X_checkpoint_10000`, and so on.

Use `--shuffle=naive` on the `changelog subsample` command to revert to fully random permutation (not recommended).
