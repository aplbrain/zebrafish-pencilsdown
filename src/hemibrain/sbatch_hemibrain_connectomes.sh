#!/bin/bash

# example usage
# sh sbatch_hemibrain_connectomes.sh

PARAMS=(
  28841c8277e044a7b187dda03e18da13
  305b514e13d0411c8fe6c789935e7030
  a0dfa4f260244946b7abbab4dcd2cc86
  0c6f54d9677f4d3181eedfb272b1c0b0
  dd7b7e43bd0d4054aeb554633dfc4857
  34d7acb0167d438baa85c47ea0a739d4
  52a13328874c4bb7b15dc4280da26576
  45bdcf98287347a39ee5eccb8a00e409
  54c2700f0e204c9ab2a64a245cf925b0
  e44b9e8ae63a4e3fa9e978e088348254
  ef000defa00c42b7b5be64b81663aa25
)

for p in "${PARAMS[@]}"; do
  sbatch run_hemibrain_connectome.sh "$p"
done