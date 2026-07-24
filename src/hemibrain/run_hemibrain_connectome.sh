#!/bin/bash

# example usage
# sbatch run_hemibrain_connectome.sh 305b514e13d0411c8fe6c789935e7030

#SBATCH --job-name=
#SBATCH --partition=
#SBATCH --time=
#SBATCH --output=
#SBATCH --error=
#SBATCH --mem=
#SBATCH --cpus-per-task=

uv run run_rustworkx.py $1
