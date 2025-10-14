# Updating checkpoint channels after new edits are made

# 1. Download the latest changes.tsv file from the Taurus API

```bash
wget https://taurus.agglomeration.ariadne.ai/api/changes.tsv -O changes.tsv
```

Because this file is checked into version control, you should see new lines added in the diff of this file.

# 2. Update the checkpoint channels

In `2-Create-Checkpoint-Channels.ipynb` you can add previously existing checkpoints to the "Ignore" list on the line,

```python
if editcount in [5000, 10000, 35000, 25000, 15000, 20000, 30000, 35000, 40000]:
```

to avoid re-creating those checkpoints.

You can now run these three notebooks in order:

-   0-Subsample-Changelog.ipynb
-   1-Create-Remap-Dicts.ipynb
-   2-Create-Checkpoint-Channels.ipynb

This will result in the creation of several `agglomeration_checkpoint_####` channels, where each `####` is a checkpoint number corresponding to the number of edits performed to reach this agglomeration threshold.
