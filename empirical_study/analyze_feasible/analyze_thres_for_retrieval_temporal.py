"""
Analyze Reference Availability (RA) and Reference Level (RL) using temporal candidate dataset.

This script calculates two simple metrics based on test-to-test similarity:
1. Reference Availability (RA): What fraction of tests have at least one reference
   (candidate with similarity >= threshold)?
2. Reference Level (RL): On average, how many references does each test have
   (candidates with similarity >= threshold)?

Usage:
    python analyze_thres_for_retrieval_temporal.py --project_name truth
"""

import argparse
import sys
import numpy as np
import os
import json
import re
from tqdm import tqdm

sys.path.append('../..')
from configs import Configs
from test_only_retriever import TestOnlyRetriever
from parser.java_code_parser import JavaCodeParser


def load_temporal_candidate_dataset(configs):
    """Load the precomputed temporal candidate dataset."""
    with open(configs.temporal_candidate_dataset_path, 'r') as f:
        data = json.load(f)
    return data


def extract_target_method_body(full_class_code: str, target_method_name: str) -> str:
    """
    Extract the test method body from a full test class code.
    This ensures the target test code format matches the candidate format
    (method body only, not full class).
    
    Args:
        full_class_code: The complete test class code with package, imports, etc.
        target_method_name: The name of the target test method
        
    Returns:
        The method body with annotations, or the original code if extraction fails
    """
    try:
        parser = JavaCodeParser()
        parser.parse_java_code(full_class_code)
        method_pairs = parser.get_all_method_definition()
        
        lines = full_class_code.split('\n')
        
        for method_pair in method_pairs:
            name_node = method_pair['name']
            body_node = method_pair['body']
            
            method_name = name_node.text.decode('utf-8')
            if method_name != target_method_name:
                continue
            
            start_line = name_node.start_point[0]  # 0-indexed
            end_line = body_node.end_point[0]  # 0-indexed
            
            # Find annotation block start
            annotation_start = start_line
            for i in range(start_line - 1, max(-1, start_line - 20), -1):
                line = lines[i].strip()
                if line.endswith('}') or line.endswith(';') or (line and not line.startswith('@') and not line.startswith('//') and not line.startswith('/*') and not line.startswith('*') and line != ''):
                    break
                annotation_start = i
            
            method_code = '\n'.join(lines[annotation_start:end_line + 1])
            return method_code
        
        # If method not found, return original (shouldn't happen)
        return full_class_code
    except Exception as e:
        # If parsing fails, return original
        return full_class_code


def statistics_similarity():
    # Load temporal candidate dataset
    print('Loading temporal candidate dataset...')
    temporal_data = load_temporal_candidate_dataset(configs)
    print(f'Loaded {len(temporal_data)} target tests with candidates\n')
    
    ra_list = []  # Reference Availability per test
    rl_list = []  # Reference Level per test
    
    # Statistics
    total_candidates = 0
    tests_skipped_error = 0
    tests_skipped_empty_corpus = 0
    tests_skipped_no_creation_version = 0
    tests_processed = 0

    for target_entry in tqdm(temporal_data, ncols=80, desc='Analyzing Similarity'):
        # Skip if there was an error during collection
        if target_entry.get('error') is not None:
            tests_skipped_error += 1
            continue
        
        # Use creation version if available, otherwise fall back to current version
        target_code_at_creation = target_entry.get('target_test_code_at_creation')
        if target_code_at_creation is None:
            # No creation version collected - skip for temporal consistency
            tests_skipped_no_creation_version += 1
            continue
        
        # The creation version is already in method-only format from collection
        target_test_code = target_code_at_creation
        
        candidates = target_entry['candidates']
        
        # Skip if corpus is empty
        if len(candidates) == 0:
            tests_skipped_empty_corpus += 1
            continue
        
        total_candidates += len(candidates)
        tests_processed += 1
        
        # Build corpus from candidates
        corpus_tc = [c['test_case_code'] for c in candidates]
        corpus_tc_name = [c['test_case_name'] for c in candidates]
        corpus_tc_path = [c['test_case_path'] for c in candidates]
        
        # Create retriever and compute similarities
        retriever = TestOnlyRetriever(corpus_tc, corpus_tc_name, corpus_tc_path)
        tc_self_sim_score, tc_ref_sim_scores = retriever.get_score_self_and_ref_tc(target_test_code)
        
        if tc_self_sim_score == 0:
            # Avoid division by zero
            tc_ratio_self_ref = np.zeros_like(tc_ref_sim_scores)
        else:
            tc_ratio_self_ref = tc_ref_sim_scores / tc_self_sim_score

        # Calculate Reference Availability (binary: has at least 1 reference?)
        ra = calculate_reference_availability(tc_ratio_self_ref)
        ra_list.append(ra)

        # Calculate Reference Level (count: how many references?)
        rl = calculate_reference_level(tc_ratio_self_ref)
        rl_list.append(rl)

    # Calculate averages across all tests
    avg_ra = np.mean(ra_list, axis=0) if ra_list else np.array([])
    avg_rl = np.mean(rl_list, axis=0) if rl_list else np.array([])
    
    # Print statistics
    print('\n' + '='*80)
    print('TEMPORAL CANDIDATE ANALYSIS STATISTICS')
    print('='*80)
    print(f'Total targets in dataset: {len(temporal_data)}')
    print(f'Tests skipped (collection error): {tests_skipped_error}')
    print(f'Tests skipped (no creation version): {tests_skipped_no_creation_version}')
    print(f'Tests skipped (empty corpus): {tests_skipped_empty_corpus}')
    print(f'Tests processed: {tests_processed}')
    print(f'Total candidates: {total_candidates}')
    if tests_processed > 0:
        print(f'Average candidates per target: {total_candidates/tests_processed:.2f}')
    print('='*80 + '\n')
    
    # Print RA and RL metrics table
    if len(avg_ra) > 0 and len(avg_rl) > 0:
        print('REFERENCE AVAILABILITY (RA) AND REFERENCE LEVEL (RL) METRICS')
        print('='*80)
        print(f'{"Threshold":<12} | {"RA (%)":<12} | {"RL (avg)":<12}')
        print('-' * 80)
        thresholds = [i / 10 for i in range(1, 10)]  # 0.1 to 0.9
        for i, threshold in enumerate(thresholds):
            ra_val = avg_ra[i] * 100 if i < len(avg_ra) else 0
            rl_val = avg_rl[i] if i < len(avg_rl) else 0
            print(f'{threshold:<12.1f} | {ra_val:<12.1f} | {rl_val:<12.2f}')
        print('='*80 + '\n')
    
    return avg_ra, avg_rl


def calculate_reference_availability(tc_ratio_self_ref):
    """
    Calculate Reference Availability: for each threshold, check if the test
    has at least one reference (candidate with similarity >= threshold).
    
    Args:
        tc_ratio_self_ref: Array of similarity ratios between target and candidates
        
    Returns:
        1D list of RA values (0 or 1) for each threshold
    """
    tc_thres_list = [i / 10 for i in range(1, 10)]  # 0.1 to 0.9 with step 0.1
    ra = []
    
    for each_tc_thres in tc_thres_list:
        # Check if any candidate has similarity >= threshold
        has_reference = 1.0 if np.any(tc_ratio_self_ref >= each_tc_thres) else 0.0
        ra.append(has_reference)
    
    return ra


def calculate_reference_level(tc_ratio_self_ref):
    """
    Calculate Reference Level: count of candidates with similarity >= threshold.
    
    Args:
        tc_ratio_self_ref: Array of similarity ratios between target and candidates
        
    Returns:
        1D list of RL counts for each threshold
    """
    tc_thres_list = [i / 10 for i in range(1, 10)]  # 0.1 to 0.9 with step 0.1
    rl = []
    
    for each_tc_thres in tc_thres_list:
        # Count how many candidates exceed this threshold
        count = np.sum(tc_ratio_self_ref >= each_tc_thres)
        rl.append(count)
    
    return rl


def main():
    avg_ra, avg_rl = statistics_similarity()

    save_dir = 'data/temporal_candidate_analysis'
    os.makedirs(save_dir, exist_ok=True)

    np.save(f'{save_dir}/{args.project_name}_ra.npy', avg_ra)
    np.save(f'{save_dir}/{args.project_name}_rl.npy', avg_rl)
    
    print(f'Results saved to {save_dir}/{args.project_name}_*.npy')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project_name', type=str, required=True, help='Project name')

    args = parser.parse_args()

    configs = Configs(args.project_name, 'gpt-o1-mini')

    print(f'Configs:\n{configs.__dict__}\n\n')
    print(f"Processing {configs.project_name}...\n\n")

    main()
