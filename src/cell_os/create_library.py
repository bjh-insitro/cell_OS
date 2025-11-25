import argparse
import logging
import multiprocessing
from collections import defaultdict
from typing import Callable, List, Dict, Any, Tuple

import numpy as np
import pandas as pd
from ortools.sat.python import cp_model
from tqdm.auto import tqdm

from cell_os.config_utils import load_yaml
from cell_os.barcode_trie import Trie
from cell_os.guide_utils import format_library


logging.basicConfig(level=logging.INFO)

_processing_helper: Callable[[str], List[str]]


def _add_hamming_distance_constraints(
    guide_repository: pd.DataFrame,
    design_config: Dict[str, Any],
    model: cp_model.CpModel,
    model_vars: List[cp_model.IntVar],
    verbose: bool,
) -> None:
    posh_barcode_hamming_distance = design_config["posh_barcode_hamming_distance"]
    posh_barcode_length = design_config["posh_barcode_length"]

    if verbose:
        logging.info(
            f"""Adding Hamming distance conflicts. Guides are considered to
            conflict if their barcodes have Hamming distance <= {posh_barcode_hamming_distance}."""
        )

    guide_repository.loc[:, "barcode"] = guide_repository["sgRNA"].map(
        lambda x: x[0:posh_barcode_length]
    )

    if verbose:
        logging.info("Initializing trie with barcodes.")
    trie = Trie()
    for barcode in tqdm(guide_repository["barcode"], disable=not verbose):
        trie.insert(barcode)

    if verbose:
        logging.info("Computing Hamming conflicts via trie search.")

    # The global declaration here is a hack so that our helper function can be passed to
    # multiprocessing, which cannot normally accept local functions
    global _processing_helper

    def _processing_helper(x: str) -> List[str]:
        return trie.find_all_hamming_conflicts(x, distance=posh_barcode_hamming_distance)

    # Maps each barcode in our library dataframe to a list of conflicting sequences
    with multiprocessing.Pool() as p:
        r = list(
            tqdm(
                p.imap(_processing_helper, guide_repository["barcode"]),
                total=guide_repository.shape[0],
                disable=not verbose,
            )
        )
    del _processing_helper

    # Our trie based conflict search returns conflicting barcodes (not indices).
    # Here we map these barcodes back to corresponding indices in the repository dataframe
    if verbose:
        logging.info("Mapping barcodes to guide repository indices.")
    barcode_to_indices = defaultdict(list)
    for i, barcode in tqdm(
        enumerate(guide_repository["barcode"]),
        total=guide_repository.shape[0],
        disable=not verbose,
    ):
        barcode_to_indices[barcode].append(i)

    # For each guide in the dataframe, we retrieve its conflicting indices and add
    # corresponding constraints to our ILP solver.
    if verbose:
        logging.info("Adding constraints to ILP solver.")
    previously_seen_conflicts = set()
    for i, barcode in tqdm(
        enumerate(guide_repository["barcode"]),
        total=guide_repository.shape[0],
        disable=not verbose,
    ):
        for conflicting_barcode in r[i]:
            for j in barcode_to_indices[conflicting_barcode]:
                if i == j:  # Do not consider own index as a conflict
                    continue

                pair = frozenset([i, j])  # Do not add redundant constraints
                if pair not in previously_seen_conflicts:
                    previously_seen_conflicts.add(pair)
                    model.add(cp_model.LinearExpr.Sum([model_vars[i], model_vars[j]]) <= 1)


def _load_guide_repository(
    repositories_config: Dict[str, str],
    design_config: Dict[str, Any],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    # Targeting repositories: prefer explicit targeting_repositories, else fall back to repositories
    targeting_sources = design_config.get("targeting_repositories")
    if targeting_sources is None:
        targeting_sources = design_config.get("repositories")

    if not targeting_sources:
        raise ValueError(
            "No targeting repositories specified. "
            "Expected 'targeting_repositories' or 'repositories' in design config."
        )

    logging.info(f"Loading targeting guides from {list(targeting_sources)} repositories.")

    targeting_repository_dfs = []
    for source in targeting_sources:
        path = repositories_config[source]
        targeting_repository_dfs.append(
            format_library(pd.read_csv(path), str(source))
        )

    targeting_df = pd.concat(targeting_repository_dfs, ignore_index=True)

    gene_list = pd.read_csv(design_config["gene_list"])[
        design_config["gene_identifier_column"]
    ].values

    genes_with_guides = set(targeting_df[design_config["gene_identifier_column"]].unique())
    genes_without_guides = [x for x in gene_list if x not in genes_with_guides]
    if genes_without_guides:
        raise ValueError(
            f"No guides found for {genes_without_guides} in provided guide repositories"
        )

    targeting_df = targeting_df[
        targeting_df[design_config["gene_identifier_column"]].isin(gene_list)
    ].reset_index(drop=True)

    # Nontargeting repositories are optional
    control_sources = design_config.get("nontargeting_repositories", [])
    logging.info(f"Loading nontargeting guides from {list(control_sources)} repositories.")

    nontargeting_repository_dfs = []
    for source in control_sources:
        path = repositories_config[source]
        nontargeting_repository_dfs.append(
            format_library(pd.read_csv(path), str(source))
        )

    if nontargeting_repository_dfs:
        nontargeting_df = pd.concat(nontargeting_repository_dfs, ignore_index=True)
    else:
        # Empty controls dataframe is fine. The caller can decide what to do.
        nontargeting_df = pd.DataFrame(columns=targeting_df.columns)

    return targeting_df, nontargeting_df


def _add_guide_number_constraints(
    guide_repository: pd.DataFrame,
    design_config: Dict[str, Any],
    model: cp_model.CpModel,
    model_vars: List[cp_model.IntVar],
    verbose: bool,
) -> None:
    min_guides_per_gene = design_config["min_guides_per_gene"]
    max_guides_per_gene = design_config["max_guides_per_gene"]

    if verbose:
        logging.info(
            f"""Adding guide number constraints. For each gene we will select between
            {min_guides_per_gene} and {max_guides_per_gene} guides."""
        )

    for gene in tqdm(
        guide_repository[design_config["gene_identifier_column"]].unique(), disable=not verbose
    ):
        indices = guide_repository[
            guide_repository[design_config["gene_identifier_column"]] == gene
        ].index
        model.add(cp_model.LinearExpr.Sum([model_vars[i] for i in indices]) <= max_guides_per_gene)
        model.add(cp_model.LinearExpr.Sum([model_vars[i] for i in indices]) >= min_guides_per_gene)


def _add_location_constraints(
    guide_repository: pd.DataFrame,
    design_config: Dict[str, Any],
    model: cp_model.CpModel,
    model_vars: List[cp_model.IntVar],
    verbose: bool,
) -> None:
    # We consider guides targeting the same gene to conflict if their
    # (start, end) intervals overlap by more than `overlap_threshold` base pairs
    overlap_threshold = design_config["overlap_threshold"]

    if verbose:
        logging.info(
            f"""Adding guide location conflicts. Guides are considered to conflict if
            their (start, end) intervals overlap by > {overlap_threshold} bases."""
        )

    location_conflicts = defaultdict(list)
    for gene in tqdm(
        guide_repository[design_config["gene_identifier_column"]].unique(), disable=not verbose
    ):
        gene_dataframe = guide_repository[
            guide_repository[design_config["gene_identifier_column"]] == gene
        ]
        starts, ends = gene_dataframe["Start"], gene_dataframe["End"]

        # This block computes an n x n matrix `mask`, where `mask[i, j]` is a
        # binary variable indicating whether the (start, end) intervals of guides `i`
        # and `j` conflict
        start_a, end_a = starts.to_numpy(), ends.to_numpy()
        start_b, end_b = start_a[:, None], end_a[:, None]
        mask = ((start_a < start_b) & (end_a - start_b > overlap_threshold)) | (
            (start_b < start_a) & (end_b - start_a > overlap_threshold)
        )

        # Overlaps contains two lists: the first list contains the first coordinate of each
        # conflict, and the second list contains the second coordinate
        overlaps = np.triu(mask, k=1).nonzero()

        # The indices in `overlaps` always go from [0, ..., gene_dataframe.shape[0]]
        # Here we retrieve the corresponding original indices from the full dataframe
        for k in range(len(overlaps[0])):
            idx1, idx2 = overlaps[0][k], overlaps[1][k]
            original_idx1, original_idx2 = (
                gene_dataframe.iloc[idx1].name,
                gene_dataframe.iloc[idx2].name,
            )
            location_conflicts[original_idx1].append(original_idx2)

    # Add location conflicts to solver
    for i in location_conflicts:
        for j in location_conflicts[i]:
            model.add(cp_model.LinearExpr.Sum([model_vars[i], model_vars[j]]) <= 1)


def run(
    config_yaml: str,
    repositories_yaml: str,
    use_scores: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Pipeline to create sgRNA library for POSH.

    Parameters
    ----------
    config_yaml : str
        Library design configuration.
    repositories_yaml : str
        Mapping of repository name to CSV path.
    use_scores : bool
        If True, maximize score weighted sum. If False, just maximize count.
    verbose : bool
        If True, prints ILP search solver progress.

    Returns
    -------
    pd.DataFrame
        Designed library dataframe.
    """

    design_config = load_yaml(config_yaml)
    repositories_config = load_yaml(repositories_yaml)

    # Step 1: Load sgRNA libraries
    sgRNA_repository, nt_sgRNA_repository = _load_guide_repository(
        repositories_config, design_config
    )

    # Step 2: Set up ILP solver
    logging.info("Setting up ILP solver to select targeting guides")
    num_guides = sgRNA_repository.shape[0]
    model = cp_model.CpModel()
    model_vars = [model.new_bool_var(f"x_{i}") for i in range(num_guides)]

    # Step 2a: Add guide number constraints
    _add_guide_number_constraints(
        guide_repository=sgRNA_repository,
        design_config=design_config,
        model=model,
        model_vars=model_vars,
        verbose=verbose,
    )

    # Step 2b: Add guide target location constraints
    _add_location_constraints(
        guide_repository=sgRNA_repository,
        design_config=design_config,
        model=model,
        model_vars=model_vars,
        verbose=verbose,
    )

    # Step 2c: Add Hamming distance constraints
    _add_hamming_distance_constraints(
        guide_repository=sgRNA_repository,
        design_config=design_config,
        model=model,
        model_vars=model_vars,
        verbose=verbose,
    )

    # Step 3: Run the solver to select targeting guides
    logging.info("Running first round of ILP solver to select targeting guides")

    if use_scores:
        model.maximize(
            cp_model.LinearExpr.weighted_sum(
                model_vars, sgRNA_repository[design_config["score_name"]]
            )
        )
    else:
        model.maximize(sum(model_vars))

    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = verbose
    solver.parameters.max_time_in_seconds = design_config["solver_time_limit_seconds"]
    status = solver.solve(model)

    if status == cp_model.OPTIMAL:
        logging.info("Optimal set of guides found")
    elif status == cp_model.FEASIBLE:
        logging.info("Feasible guide selection found, but could not prove optimality of solution")
    else:
        raise RuntimeError("Solution not found")

    sgRNA_repository["selected"] = [solver.value(model_vars[i]) for i in sgRNA_repository.index]
    targeting_library = sgRNA_repository[sgRNA_repository["selected"] == 1]

    # If we have no nontargeting repositories configured, stop here
    if not design_config.get("nontargeting_repositories"):
        logging.info(
            "No 'nontargeting_repositories' specified in design config. "
            "Returning targeting library only."
        )
        return targeting_library

    # Step 4: Set up ILP solver for a second round to select control guides
    logging.info("Setting up ILP solver to select nontargeting guides")
    second_round_repository = pd.concat([targeting_library, nt_sgRNA_repository], axis=0)
    second_round_repository = second_round_repository.reset_index(drop=True)

    num_guides = second_round_repository.shape[0]
    model = cp_model.CpModel()
    model_vars = [model.new_bool_var(f"x_{i}") for i in range(num_guides)]

    # Step 4a: Force previously selected targeting guides to be selected in 2nd round
    for i in range(targeting_library.shape[0]):
        model.add(model_vars[i] == 1)

    # Step 4b: Add Hamming distance constraints
    _add_hamming_distance_constraints(
        guide_repository=second_round_repository,
        design_config=design_config,
        model=model,
        model_vars=model_vars,
        verbose=verbose,
    )

    # Step 5: Run second round of ILP optimization
    logging.info("Running second round of ILP solver to select nontargeting guides")
    solver = cp_model.CpSolver()
    model.maximize(sum(model_vars))
    solver.parameters.log_search_progress = verbose
    solver.parameters.max_time_in_seconds = design_config["solver_time_limit_seconds"]
    status = solver.solve(model)

    second_round_repository["selected"] = [
        solver.value(model_vars[i]) for i in second_round_repository.index
    ]

    return second_round_repository[second_round_repository["selected"] == 1]


def main(config_yaml: str, repositories_yaml: str, output_path: str, verbose: bool) -> None:
    library_df = run(
        config_yaml=config_yaml,
        repositories_yaml=repositories_yaml,
        verbose=verbose,
    )
    library_df.to_csv(output_path, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_yaml", type=str, required=True)
    parser.add_argument("--repositories_yaml", type=str, required=True)
    parser.add_argument("--output-path", type=str, required=True)
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    main(
        config_yaml=args.config_yaml,
        repositories_yaml=args.repositories_yaml,
        verbose=args.verbose,
        output_path=args.output_path,
    )
