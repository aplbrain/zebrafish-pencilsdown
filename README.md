# Zebrafish "Pencils-Down" Paper

Repository point of contact: [Jordan Matelsky](@j6k4m8)

## Usage

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
