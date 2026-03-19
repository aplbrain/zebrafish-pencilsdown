CONNECTOME_INPUT_DIR = "data/raw/connectomes/original_order"
CONTACTOME_INPUT_DIR = "data/raw/contactomes/original_order"
# Hemibrain invariants are calculated separately since they need HPC

CONNECTOME_INVARIANTS = "data/generated/connectome/invariants.json"
CONTACTOME_INVARIANTS = "data/generated/contactome/invariants.json"
HEMIBRAIN_INVARIANTS = "src/hemibrain/invariants.json"

CONNECTOME_SUMMARY_MD = "results/data/connectome-convergence-summary.md"
CONNECTOME_SUMMARY_TEX = "results/data/connectome-convergence-summary.tex"
CONNECTOME_STATS_JSON = "results/data/connectome-convergence-stats.json"
CONNECTOME_FIGURE_DIR = "results/figures/connectome-convergence"
CONNECTOME_PROJECTION_MD = "results/data/connectome-projection-summary.md"
CONNECTOME_PROJECTION_TEX = "results/data/connectome-projection-summary.tex"
CONNECTOME_PROJECTION_CSV = "results/data/connectome-projection-summary.csv"
CONNECTOME_PROJECTION_STATS_JSON = "results/data/connectome-projection-stats.json"
CONNECTOME_PROJECTION_FIGURE_DIR = "results/figures/connectome-projection-milestones"

CONTACTOME_SUMMARY_MD = "results/data/contactome-convergence-summary.md"
CONTACTOME_SUMMARY_TEX = "results/data/contactome-convergence-summary.tex"
CONTACTOME_STATS_JSON = "results/data/contactome-convergence-stats.json"
CONTACTOME_FIGURE_DIR = "results/figures/contactome-convergence"
CONTACTOME_PROJECTION_MD = "results/data/contactome-projection-summary.md"
CONTACTOME_PROJECTION_TEX = "results/data/contactome-projection-summary.tex"
CONTACTOME_PROJECTION_CSV = "results/data/contactome-projection-summary.csv"
CONTACTOME_PROJECTION_STATS_JSON = "results/data/contactome-projection-stats.json"
CONTACTOME_PROJECTION_FIGURE_DIR = "results/figures/contactome-projection-milestones"

HEMIBRAIN_SUMMARY_MD = "results/data/hemibrain-convergence-summary.md"
HEMIBRAIN_SUMMARY_TEX = "results/data/hemibrain-convergence-summary.tex"
HEMIBRAIN_STATS_JSON = "results/data/hemibrain-convergence-stats.json"
HEMIBRAIN_FIGURE_DIR = "results/figures/hemibrain-convergence"
HEMIBRAIN_PROJECTION_MD = "results/data/hemibrain-projection-summary.md"
HEMIBRAIN_PROJECTION_TEX = "results/data/hemibrain-projection-summary.tex"
HEMIBRAIN_PROJECTION_CSV = "results/data/hemibrain-projection-summary.csv"
HEMIBRAIN_PROJECTION_STATS_JSON = "results/data/hemibrain-projection-stats.json"
HEMIBRAIN_PROJECTION_FIGURE_DIR = "results/figures/hemibrain-projection-milestones"



rule all:
    input:
        CONNECTOME_INVARIANTS,
        CONTACTOME_INVARIANTS,
        CONNECTOME_SUMMARY_MD,
        CONNECTOME_SUMMARY_TEX,
        CONNECTOME_STATS_JSON,
        CONNECTOME_FIGURE_DIR,
        CONNECTOME_PROJECTION_MD,
        CONNECTOME_PROJECTION_TEX,
        CONNECTOME_PROJECTION_CSV,
        CONNECTOME_PROJECTION_STATS_JSON,
        CONNECTOME_PROJECTION_FIGURE_DIR,
        # CONTACTOME_SUMMARY_MD,
        # CONTACTOME_SUMMARY_TEX,
        # CONTACTOME_STATS_JSON,
        # CONTACTOME_FIGURE_DIR,
        # CONTACTOME_PROJECTION_MD,
        # CONTACTOME_PROJECTION_TEX,
        # CONTACTOME_PROJECTION_CSV,
        # CONTACTOME_PROJECTION_STATS_JSON,
        # CONTACTOME_PROJECTION_FIGURE_DIR,
        HEMIBRAIN_SUMMARY_MD,
        HEMIBRAIN_SUMMARY_TEX,
        HEMIBRAIN_STATS_JSON,
        HEMIBRAIN_FIGURE_DIR,
        HEMIBRAIN_PROJECTION_MD,
        HEMIBRAIN_PROJECTION_TEX,
        HEMIBRAIN_PROJECTION_CSV,
        HEMIBRAIN_PROJECTION_STATS_JSON,
        HEMIBRAIN_PROJECTION_FIGURE_DIR


rule connectome_invariants:
    input:
        CONNECTOME_INPUT_DIR,
    output:
        CONNECTOME_INVARIANTS,
    shell:
        "uv run python analysis/invariants/run.py "
        "--dataset connectome "
        "--input-dir {input} "
        "--output-json {output} "
        "--metric-profile fast"


# rule contactome_invariants:
#     input:
#         CONTACTOME_INPUT_DIR,
#     output:
#         CONTACTOME_INVARIANTS,
#     shell:
#         "uv run python analysis/invariants/run.py "
#         "--dataset contactome "
#         "--input-dir {input} "
#         "--output-json {output} "
#         "--metric-profile fast"


rule connectome_convergence:
    input:
        CONNECTOME_INVARIANTS,
    output:
        md=CONNECTOME_SUMMARY_MD,
        tex=CONNECTOME_SUMMARY_TEX,
        stats=CONNECTOME_STATS_JSON,
        figures=directory(CONNECTOME_FIGURE_DIR),
    shell:
        "uv run python analysis/convergence/run.py "
        "--dataset connectome "
        "--input-json {input} "
        "--summary-md {output.md} "
        "--summary-tex {output.tex} "
        "--stats-json {output.stats} "
        "--figure-dir {output.figures}"


# rule contactome_convergence:
#     input:
#         CONTACTOME_INVARIANTS,
#     output:
#         md=CONTACTOME_SUMMARY_MD,
#         tex=CONTACTOME_SUMMARY_TEX,
#         stats=CONTACTOME_STATS_JSON,
#         figures=directory(CONTACTOME_FIGURE_DIR),
#     shell:
#         "uv run python analysis/convergence/run.py "
#         "--dataset contactome "
#         "--input-json {input} "
#         "--summary-md {output.md} "
#         "--summary-tex {output.tex} "
#         "--stats-json {output.stats} "
#         "--figure-dir {output.figures}"


rule hemibrain_convergence:
    input:
        HEMIBRAIN_INVARIANTS,
    output:
        md=HEMIBRAIN_SUMMARY_MD,
        tex=HEMIBRAIN_SUMMARY_TEX,
        stats=HEMIBRAIN_STATS_JSON,
        figures=directory(HEMIBRAIN_FIGURE_DIR),
    shell:
        "uv run python analysis/convergence/run.py "
        "--dataset hemibrain "
        "--input-json {input} "
        "--summary-md {output.md} "
        "--summary-tex {output.tex} "
        "--stats-json {output.stats} "
        "--figure-dir {output.figures}"

rule connectome_projection_summary:
    input:
        invariants=CONNECTOME_INVARIANTS,
        convergence=CONNECTOME_STATS_JSON,
    output:
        md=CONNECTOME_PROJECTION_MD,
        tex=CONNECTOME_PROJECTION_TEX,
        csv=CONNECTOME_PROJECTION_CSV,
        stats=CONNECTOME_PROJECTION_STATS_JSON,
        figures=directory(CONNECTOME_PROJECTION_FIGURE_DIR),
    shell:
        "uv run python analysis/projections/run.py "
        "--dataset connectome "
        "--input-json {input.invariants} "
        "--convergence-stats {input.convergence} "
        "--summary-md {output.md} "
        "--summary-tex {output.tex} "
        "--summary-csv {output.csv} "
        "--stats-json {output.stats} "
        "--figure-dir {output.figures} "


# rule contactome_projection_summary:
#     input:
#         invariants=CONTACTOME_INVARIANTS,
#         convergence=CONTACTOME_STATS_JSON,
#     output:
#         md=CONTACTOME_PROJECTION_MD,
#         tex=CONTACTOME_PROJECTION_TEX,
#         csv=CONTACTOME_PROJECTION_CSV,
#         stats=CONTACTOME_PROJECTION_STATS_JSON,
#         figures=directory(CONTACTOME_PROJECTION_FIGURE_DIR),
#     shell:
#         "uv run python analysis/projections/run.py "
#         "--dataset contactome "
#         "--input-json {input.invariants} "
#         "--convergence-stats {input.convergence} "
#         "--summary-md {output.md} "
#         "--summary-tex {output.tex} "
#         "--summary-csv {output.csv} "
#         "--stats-json {output.stats} "
#         "--figure-dir {output.figures} "


rule hemibrain_projection_summary:
    input:
        invariants=HEMIBRAIN_INVARIANTS,
        convergence=HEMIBRAIN_STATS_JSON,
    output:
        md=HEMIBRAIN_PROJECTION_MD,
        tex=HEMIBRAIN_PROJECTION_TEX,
        csv=HEMIBRAIN_PROJECTION_CSV,
        stats=HEMIBRAIN_PROJECTION_STATS_JSON,
        figures=directory(HEMIBRAIN_PROJECTION_FIGURE_DIR),
    shell:
        "uv run python analysis/projections/run.py "
        "--dataset hemibrain "
        "--input-json {input.invariants} "
        "--convergence-stats {input.convergence} "
        "--summary-md {output.md} "
        "--summary-tex {output.tex} "
        "--summary-csv {output.csv} "
        "--stats-json {output.stats} "
        "--figure-dir {output.figures} "

