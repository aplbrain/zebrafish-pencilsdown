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
uv run python manage.py changelog subsample --step-size 5000 --shuffle-count 2 --shuffle-seed 42
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

[Resulting channels (neuroglancer)](https://neuroglancer.bossdb.io/#!%7B%22dimensions%22:%7B%22x%22:%5B9e-9%2C%22m%22%5D%2C%22y%22:%5B9e-9%2C%22m%22%5D%2C%22z%22:%5B2.1e-8%2C%22m%22%5D%7D%2C%22position%22:%5B3339.91552734375%2C4407.447265625%2C6048.2451171875%5D%2C%22crossSectionScale%22:2.150931887074575%2C%22projectionOrientation%22:%5B0.559953510761261%2C-0.19673286378383636%2C-0.6504355072975159%2C0.47400620579719543%5D%2C%22projectionScale%22:20367.57777423346%2C%22layers%22:%5B%7B%22type%22:%22image%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/em%22%2C%22tab%22:%22source%22%2C%22name%22:%22em%22%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%22%212%22%5D%2C%22name%22:%22synapses%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses_relabeled%22%2C%22tab%22:%22source%22%2C%22crossSectionRenderScale%22:19.248400577313852%2C%22segments%22:%5B%22%212%22%5D%2C%22name%22:%22synapses_relabeled%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/supervoxels%22%2C%22tab%22:%22rendering%22%2C%22crossSectionRenderScale%22:0.1088188204120155%2C%22segments%22:%5B%5D%2C%22name%22:%22supervoxels%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_5000%22%2C%22tab%22:%22source%22%2C%22notSelectedAlpha%22:0.36%2C%22crossSectionRenderScale%22:0.0625%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_5000%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_10000%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_10000%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_15000%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_15000%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_20000%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_20000%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_25000%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_25000%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_30000%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_30000%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_35000%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_35000%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_40000/%7Cneuroglancer-precomputed:%22%2C%22tab%22:%22rendering%22%2C%22crossSectionRenderScale%22:0.0625%2C%22segments%22:%5B%22%2116457933%22%2C%22%2121859317%22%5D%2C%22segmentQuery%22:%2221859317%22%2C%22name%22:%22agglomeration_checkpoint_40000%22%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration%22%2C%22visible%22:false%7D%5D%2C%22selectedLayer%22:%7B%22visible%22:true%2C%22layer%22:%22agglomeration_checkpoint_40000%22%7D%2C%22layout%22:%22xy%22%2C%22layerListPanel%22:%7B%22size%22:425%2C%22visible%22:true%7D%7D)

[Just latest agglomeration (neuroglancer)](https://neuroglancer.bossdb.io/#!%7B%22dimensions%22:%7B%22x%22:%5B9e-9%2C%22m%22%5D%2C%22y%22:%5B9e-9%2C%22m%22%5D%2C%22z%22:%5B2.1e-8%2C%22m%22%5D%7D%2C%22position%22:%5B3339.91552734375%2C4407.447265625%2C6048.2451171875%5D%2C%22crossSectionScale%22:2.150931887074575%2C%22projectionOrientation%22:%5B0.559953510761261%2C-0.19673286378383636%2C-0.6504355072975159%2C0.47400620579719543%5D%2C%22projectionScale%22:20367.57777423346%2C%22layers%22:%5B%7B%22type%22:%22image%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/em%22%2C%22tab%22:%22source%22%2C%22name%22:%22em%22%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%22%212%22%5D%2C%22name%22:%22synapses%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses_relabeled%22%2C%22tab%22:%22source%22%2C%22crossSectionRenderScale%22:19.248400577313852%2C%22segments%22:%5B%22%212%22%5D%2C%22name%22:%22synapses_relabeled%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_40000/%7Cneuroglancer-precomputed:%22%2C%22tab%22:%22rendering%22%2C%22crossSectionRenderScale%22:0.0625%2C%22segments%22:%5B%22%2116457933%22%2C%22%2121859317%22%5D%2C%22segmentQuery%22:%2221859317%22%2C%22name%22:%22agglomeration_checkpoint_40000%22%7D%5D%2C%22selectedLayer%22:%7B%22visible%22:true%2C%22layer%22:%22agglomeration_checkpoint_40000%22%7D%2C%22layout%22:%22xy%22%2C%22layerListPanel%22:%7B%22size%22:425%2C%22visible%22:true%7D%7D)

### Downsample channels

```bash
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_5000 --mip 0 --num-mips 1 --fill-missing  --queue q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_10000 --mip 0 --num-mips 1 --fill-missing --queue q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_15000 --mip 0 --num-mips 1 --fill-missing --queue q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_20000 --mip 0 --num-mips 1 --fill-missing --queue q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_25000 --mip 0 --num-mips 1 --fill-missing --queue q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_30000 --mip 0 --num-mips 1 --fill-missing --queue q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_35000 --mip 0 --num-mips 1 --fill-missing --queue q-downsample


uv run igneous --parallel 8 execute -x q-downsample

uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_5000 --mip 1 --num-mips 3 --fill-missing --volumetric --queue q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_10000 --mip 1 --num-mips 3 --fill-missing --volumetric --queue q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_15000 --mip 1 --num-mips 3 --fill-missing --volumetric --queue q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_20000 --mip 1 --num-mips 3 --fill-missing --volumetric --queue q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_25000 --mip 1 --num-mips 3 --fill-missing --volumetric --queue q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_30000 --mip 1 --num-mips 3 --fill-missing --volumetric --queue q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_35000 --mip 1 --num-mips 3 --fill-missing --volumetric --queue q-downsample
uv run igneous image downsample s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration --mip 1 --num-mips 3 --fill-missing --volumetric --queue q-downsample

uv run igneous --parallel 8 execute -x q-downsample
```

### Create meshes

```bash
uv run igneous mesh forge s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_5000 --mip 2 --queue ./q-mesh --sharded
uv run igneous mesh forge s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_10000 --mip 2 --queue ./q-mesh --sharded
uv run igneous mesh forge s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_15000 --mip 2 --queue ./q-mesh --sharded
uv run igneous mesh forge s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_20000 --mip 2 --queue ./q-mesh --sharded
uv run igneous mesh forge s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_25000 --mip 2 --queue ./q-mesh --sharded
uv run igneous mesh forge s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_30000 --mip 2 --queue ./q-mesh --sharded
uv run igneous mesh forge s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_35000 --mip 2 --queue ./q-mesh --sharded
uv run igneous mesh forge s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration --mip 2 --queue ./q-mesh --sharded

uv run igneous execute -x ./q-mesh
```

```bash
uv run igneous mesh merge-sharded s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_5000 --queue ./q-mesh-sharded --nlod 0
uv run igneous mesh merge-sharded s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_10000 --queue ./q-mesh-sharded --nlod 0
uv run igneous mesh merge-sharded s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_15000 --queue ./q-mesh-sharded --nlod 0
uv run igneous mesh merge-sharded s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_20000 --queue ./q-mesh-sharded --nlod 0
uv run igneous mesh merge-sharded s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_25000 --queue ./q-mesh-sharded --nlod 0
uv run igneous mesh merge-sharded s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_30000 --queue ./q-mesh-sharded --nlod 0
uv run igneous mesh merge-sharded s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_35000 --queue ./q-mesh-sharded --nlod 0
uv run igneous mesh merge-sharded s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration --queue ./q-mesh-sharded --nlod 0

uv run igneous execute -x ./q-mesh-sharded
```

## For new checkpoints

After re-running `wget` to get the latest changes, there may be new checkpoints to create. Run the three commands above in order, and then you can run the postprocessing steps:

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
