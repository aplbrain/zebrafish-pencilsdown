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

```
wget https://taurus.agglomeration.ariadne.ai/api/changes.tsv
```

You can now run these three notebooks in order:

-   0-Subsample-Changelog.ipynb
-   1-Create-Remap-Dicts.ipynb
-   2-Create-Checkpoint-Channels.ipynb

This will result in the creation of several `agglomeration_checkpoint_####` channels, where each `####` is a checkpoint number corresponding to the number of edits performed to reach this agglomeration threshold.

[Resulting channels (neuroglancer)](https://neuroglancer.bossdb.io/#!%7B%22dimensions%22:%7B%22x%22:%5B9e-9%2C%22m%22%5D%2C%22y%22:%5B9e-9%2C%22m%22%5D%2C%22z%22:%5B2.1e-8%2C%22m%22%5D%7D%2C%22position%22:%5B6979.3701171875%2C5383.56005859375%2C4954.5%5D%2C%22crossSectionScale%22:1.0936111132518467%2C%22projectionOrientation%22:%5B-0.0283577311784029%2C0.002180782612413168%2C0.0000618670746916905%2C0.9995954632759094%5D%2C%22projectionScale%22:30384.85555473088%2C%22layers%22:%5B%7B%22type%22:%22image%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/em%22%2C%22tab%22:%22source%22%2C%22name%22:%22em%22%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%22%212%22%5D%2C%22name%22:%22synapses%22%2C%22archived%22:true%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/synapses_relabeled%22%2C%22tab%22:%22source%22%2C%22crossSectionRenderScale%22:19.248400577313852%2C%22segments%22:%5B%22%212%22%5D%2C%22name%22:%22synapses_relabeled%22%2C%22archived%22:true%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/supervoxels%22%2C%22tab%22:%22rendering%22%2C%22crossSectionRenderScale%22:0.1088188204120155%2C%22segments%22:%5B%5D%2C%22name%22:%22supervoxels%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_5000%22%2C%22tab%22:%22source%22%2C%22notSelectedAlpha%22:0.36%2C%22crossSectionRenderScale%22:0.0625%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_5000%22%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_10000%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_10000%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_15000%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_15000%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_20000%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_20000%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_25000%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_25000%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_30000%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_30000%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_35000%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration_checkpoint_35000%22%2C%22visible%22:false%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%5D%2C%22name%22:%22agglomeration%22%2C%22visible%22:false%7D%5D%2C%22selectedLayer%22:%7B%22visible%22:true%2C%22layer%22:%22agglomeration_checkpoint_35000%22%7D%2C%22layout%22:%22xy%22%7D)
