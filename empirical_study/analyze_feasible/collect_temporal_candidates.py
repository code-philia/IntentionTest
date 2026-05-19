"""
Collect temporal candidates for accurate retrieval analysis.

For each target test, this script:
1. Checks out the project to the commit before the target test's first commit
2. Collects all @Test annotated methods as candidates
3. Stores the candidates in a dataset for later analysis

Usage:
    python collect_temporal_candidates.py --project_name truth --num_workers 4
    python collect_temporal_candidates.py --project_name truth --num_workers 4 --cleanup
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from multiprocessing import Pool, Manager
from glob import glob
from tqdm import tqdm

sys.path.append('../..')
from configs import Configs
from parser.java_code_parser import JavaCodeParser


def clone_repos(source_repo_path: str, clone_dir: str, project_name: str, num_workers: int) -> list:
    """Clone the repository N times for parallel processing."""
    clone_paths = []
    for i in range(num_workers):
        clone_path = os.path.join(clone_dir, f'{project_name}_{i}')
        if os.path.exists(clone_path):
            print(f'Clone {i} already exists at {clone_path}, skipping...')
        else:
            print(f'Cloning repo to {clone_path}...')
            shutil.copytree(source_repo_path, clone_path)
        clone_paths.append(clone_path)
    return clone_paths


def cleanup_clones(clone_dir: str, project_name: str, num_workers: int):
    """Remove all cloned repositories."""
    for i in range(num_workers):
        clone_path = os.path.join(clone_dir, f'{project_name}_{i}')
        if os.path.exists(clone_path):
            print(f'Removing clone {i} at {clone_path}...')
            shutil.rmtree(clone_path)


def get_parent_commit(repo_path: str, commit_hash: str) -> tuple:
    """
    Get the parent commit of the given commit.
    Returns (parent_hash, is_first_commit).
    If the commit has no parent (first commit), returns (commit_hash, True).
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', f'{commit_hash}^'],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip(), False
        else:
            # No parent exists, this is the first commit
            return commit_hash, True
    except Exception as e:
        print(f'[ERROR] Failed to get parent commit for {commit_hash}: {e}')
        return commit_hash, True


def checkout_commit(repo_path: str, commit_hash: str) -> bool:
    """Checkout the repository to a specific commit."""
    try:
        # First, reset any local changes
        subprocess.run(
            ['git', 'reset', '--hard', 'HEAD'],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        subprocess.run(
            ['git', 'clean', '-fd'],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        # Checkout the commit
        result = subprocess.run(
            ['git', 'checkout', commit_hash],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f'[ERROR] Failed to checkout {commit_hash}: {e}')
        return False


def restore_repo(repo_path: str, original_branch: str = 'HEAD'):
    """Restore the repository to the original branch/commit."""
    try:
        subprocess.run(
            ['git', 'checkout', '-'],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
    except Exception:
        pass


def find_test_files(repo_path: str) -> list:
    """Find all *Test*.java files in the repository."""
    pattern = os.path.join(repo_path, '**', '*Test*.java')
    test_files = glob(pattern, recursive=True)
    return test_files


def extract_test_methods(file_path: str, parser: JavaCodeParser) -> list:
    """
    Extract all @Test annotated methods from a Java file.
    Returns list of (test_case_name, test_case_code, start_line, end_line).
    
    Only extracts methods with @Test annotation, excluding lifecycle methods
    like @Before, @After, @BeforeClass, @AfterClass, @BeforeEach, @AfterEach, etc.
    """
    test_methods = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f'[ERROR] Failed to read {file_path}: {e}')
        return test_methods
    
    try:
        parser.parse_java_code(content)
    except Exception as e:
        print(f'[ERROR] Failed to parse {file_path}: {e}')
        return test_methods
    
    # Get all method definitions
    try:
        method_pairs = parser.get_all_method_definition()
    except Exception as e:
        print(f'[ERROR] Failed to get methods from {file_path}: {e}')
        return test_methods
    
    lines = content.split('\n')
    
    # Lifecycle annotations to exclude
    lifecycle_annotations = [
        r'@\s*Before\b', r'@\s*After\b',
        r'@\s*BeforeClass\b', r'@\s*AfterClass\b',
        r'@\s*BeforeEach\b', r'@\s*AfterEach\b',
        r'@\s*BeforeAll\b', r'@\s*AfterAll\b',
        r'@\s*org\.junit\.Before\b', r'@\s*org\.junit\.After\b',
        r'@\s*org\.junit\.BeforeClass\b', r'@\s*org\.junit\.AfterClass\b',
        r'@\s*org\.junit\.jupiter\.api\.BeforeEach\b', r'@\s*org\.junit\.jupiter\.api\.AfterEach\b',
        r'@\s*org\.junit\.jupiter\.api\.BeforeAll\b', r'@\s*org\.junit\.jupiter\.api\.AfterAll\b',
    ]
    lifecycle_pattern = '|'.join(lifecycle_annotations)
    
    for method_pair in method_pairs:
        try:
            name_node = method_pair['name']
            body_node = method_pair['body']
            
            method_name = name_node.text.decode('utf-8')
            start_line = name_node.start_point[0]  # 0-indexed
            end_line = body_node.end_point[0]  # 0-indexed
            
            # Find the annotation block that directly precedes this method
            # Start from the line before method declaration and go backwards
            # Stop when we hit a non-annotation, non-comment, non-empty line (previous method body)
            annotation_start = start_line
            for i in range(start_line - 1, max(-1, start_line - 20), -1):
                line = lines[i].strip()
                # Stop at closing brace (end of previous method) or other code
                if line.endswith('}') or line.endswith(';') or (line and not line.startswith('@') and not line.startswith('//') and not line.startswith('/*') and not line.startswith('*') and line != ''):
                    break
                annotation_start = i
            
            # Get only the annotation block for THIS method
            annotation_lines = lines[annotation_start:start_line + 1]
            annotation_text = '\n'.join(annotation_lines)
            
            # Check for lifecycle annotations - skip if found
            if re.search(lifecycle_pattern, annotation_text):
                continue
            
            # Check for @Test annotation (handles @Test, @Test(...), @org.junit.Test, etc.)
            if not re.search(r'@\s*(org\.junit\.)?(jupiter\.api\.)?Test\b', annotation_text):
                continue
            
            # Extract the full method code including annotations
            method_code = '\n'.join(lines[annotation_start:end_line + 1])
            
            test_methods.append({
                'test_case_name': method_name,
                'test_case_code': method_code,
                'start_line': annotation_start,
                'end_line': end_line
            })
        except Exception as e:
            continue
    
    return test_methods


def collect_tests_at_commit(repo_path: str, project_name: str) -> list:
    """Collect all @Test methods from the repository at current commit."""
    parser = JavaCodeParser()
    all_tests = []
    
    test_files = find_test_files(repo_path)
    
    for file_path in test_files:
        test_methods = extract_test_methods(file_path, parser)
        
        # Make path relative to repo
        relative_path = file_path.replace(repo_path, '').lstrip('/')
        # Prepend project name to match the format in coverage_data
        full_path = f'{project_name}/{relative_path}'
        
        for method in test_methods:
            all_tests.append({
                'test_case_path': full_path,
                'test_case_name': method['test_case_name'],
                'test_case_code': method['test_case_code']
            })
    
    return all_tests


def process_target(args_tuple):
    """
    Process a single target test.
    This function is called by each worker in the pool.
    """
    (target_data, clone_path, project_name, worker_id) = args_tuple
    
    target_key = f"{target_data['test_case_path']}::::{target_data['target_test_case_name']}"
    first_commit_hash = target_data['timeline']['first_commit']['hash']
    
    result = {
        'target_test_key': target_key,
        'target_coverage_idx': target_data['target_coverage_idx'],
        'target_test_code': target_data['target_test_case'],
        'target_test_name': target_data['target_test_case_name'],
        'target_test_path': target_data['test_case_path'],
        'target_test_code_at_creation': None,  # Will be populated below
        'first_commit_hash': first_commit_hash,
        'checked_out_commit': first_commit_hash,  # Now checking out creation commit
        'candidates': [],
        'error': None
    }
    
    # Checkout to first commit (where target test was created)
    if not checkout_commit(clone_path, first_commit_hash):
        result['error'] = f'Failed to checkout {first_commit_hash}'
        return result
    
    # Collect all tests at creation commit
    try:
        all_tests = collect_tests_at_commit(clone_path, project_name)
    except Exception as e:
        result['error'] = f'Failed to collect tests: {e}'
        return result
    
    # Separate target test and candidates from all tests at creation commit
    target_at_creation = None
    candidates = []
    
    for test in all_tests:
        if (test['test_case_path'] == target_data['test_case_path'] and 
            test['test_case_name'] == target_data['target_test_case_name']):
            # This is the target test itself at creation
            target_at_creation = test['test_case_code']
        else:
            # This is a candidate (all other tests in same commit)
            candidates.append(test)
    
    result['target_test_code_at_creation'] = target_at_creation
    result['candidates'] = candidates
    return result


def worker_process(worker_args):
    """
    Worker function that processes a batch of targets.
    Each worker has its own clone of the repository.
    """
    worker_id, targets, clone_path, project_name = worker_args
    
    results = []
    for target in tqdm(targets, desc=f'Worker {worker_id}', position=worker_id, leave=False):
        result = process_target((target, clone_path, project_name, worker_id))
        results.append(result)
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Collect temporal candidates for retrieval analysis')
    parser.add_argument('--project_name', type=str, required=True, help='Project name')
    parser.add_argument('--num_workers', type=int, default=4, help='Number of parallel workers')
    parser.add_argument('--cleanup', action='store_true', help='Remove cloned repos after completion')
    
    args = parser.parse_args()
    
    # Initialize configs
    configs = Configs(args.project_name, 'gpt-o1-mini')
    
    # Define paths
    source_repo_path = f'{configs.project_dir}/{args.project_name}'
    clone_dir = f'{configs.root_dir}/data/repos/temporal_clones'
    output_dir = f'{configs.root_dir}/data/temporal_candidate_dataset'
    output_path = f'{output_dir}/{args.project_name}.json'
    
    os.makedirs(clone_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f'Project: {args.project_name}')
    print(f'Source repo: {source_repo_path}')
    print(f'Clone dir: {clone_dir}')
    print(f'Output: {output_path}')
    print(f'Num workers: {args.num_workers}')
    print()
    
    # Load test timestamp data
    print('Loading test timestamp data...')
    with open(configs.test_timestamp_path, 'r') as f:
        test_timestamp_data = json.load(f)
    print(f'Loaded {len(test_timestamp_data)} target tests')
    
    # Clone repos for parallel processing
    print('\nCloning repositories...')
    clone_paths = clone_repos(source_repo_path, clone_dir, args.project_name, args.num_workers)
    
    # Partition targets across workers
    targets_per_worker = [[] for _ in range(args.num_workers)]
    for i, target in enumerate(test_timestamp_data):
        worker_id = i % args.num_workers
        targets_per_worker[worker_id].append(target)
    
    print(f'\nTargets per worker: {[len(t) for t in targets_per_worker]}')
    
    # Prepare worker arguments
    worker_args_list = [
        (worker_id, targets_per_worker[worker_id], clone_paths[worker_id], args.project_name)
        for worker_id in range(args.num_workers)
    ]
    
    # Process targets in parallel
    print('\nCollecting temporal candidates...')
    all_results = []
    
    with Pool(processes=args.num_workers) as pool:
        worker_results = pool.map(worker_process, worker_args_list)
        for results in worker_results:
            all_results.extend(results)
    
    # Sort results by target_coverage_idx
    all_results.sort(key=lambda x: x['target_coverage_idx'])
    
    # Print statistics
    successful = sum(1 for r in all_results if r['error'] is None)
    failed = sum(1 for r in all_results if r['error'] is not None)
    total_candidates = sum(len(r['candidates']) for r in all_results)
    avg_candidates = total_candidates / successful if successful > 0 else 0
    
    print(f'\n{"="*60}')
    print('COLLECTION STATISTICS')
    print('='*60)
    print(f'Total targets: {len(all_results)}')
    print(f'Successful: {successful}')
    print(f'Failed: {failed}')
    print(f'Total candidates collected: {total_candidates}')
    print(f'Average candidates per target: {avg_candidates:.2f}')
    
    if failed > 0:
        print(f'\nFailed targets:')
        for r in all_results:
            if r['error']:
                print(f"  - {r['target_test_key']}: {r['error']}")
    
    print('='*60)
    
    # Save results
    print(f'\nSaving results to {output_path}...')
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print('Done!')
    
    # Cleanup if requested
    if args.cleanup:
        print('\nCleaning up cloned repositories...')
        cleanup_clones(clone_dir, args.project_name, args.num_workers)
        print('Cleanup complete!')


if __name__ == '__main__':
    main()
