import json
import os
import argparse
from tqdm import tqdm
import subprocess
from transformers import AutoModel, AutoTokenizer

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from LSPs.java_lsp import JavaLanguageServer
from fact_discriminator.discriminator import FactDiscriminator
from statistic_gpt4 import StatisticKG
from test_case_runner import TestCaseRunner
from generator import IntentionTest
from configs import Configs
from retriever import Retriever
from graph_explorer import GraphExplorer
from dataset import Dataset, divide_desc


def apply_test_desc_setting(raw_desc: str, setting: str) -> str:
    """Apply test_desc_setting to a raw description string."""
    if setting == 'none':
        return ''

    parsed = divide_desc(raw_desc)

    if setting == 'obj':
        return '# Objective\n' + parsed['Objective']
    elif setting == 'obj_pre':
        return '# Objective\n' + parsed['Objective'] + '\n\n# Preconditions\n' + parsed['Preconditions']
    elif setting == 'obj_exp':
        return '# Objective\n' + parsed['Objective'] + '\n\n# Expected Results\n' + parsed['Expected Results']
    elif setting == 'full':
        return '# Objective\n' + parsed['Objective'] + '\n\n# Preconditions\n' + parsed['Preconditions'] + '\n\n# Expected Results\n' + parsed['Expected Results']
    else:
        raise ValueError(f'Unknown setting: {setting}')


def generation_pipeline():
    # prepare the datasets
    dataset = Dataset(configs)
    print('Loading datasets...')
    coverage_data = dataset.load_coverage_data_jacoco()
    # historical test use the test descriptions from the test
    test_desc_data = dataset.load_test_desc(setting=args.test_desc_setting)
    
    # target focal method should use the test descriptions written by humans
    with open(manual_desc_path, 'r') as f:
        test_desc_manual_data = json.load(f)
    cov_id2manual_desc = dict()
    for each in test_desc_manual_data:
        assert each['target_test_case'] == coverage_data[each['coverage_idx']].test_case
        cov_id2manual_desc[each['coverage_idx']] = each


    test_timestamp_data = load_test_timestamp()
    test2lastmod_timestamp_tmp = {f"{each['test_case_path']}::::{each['test_case_name']}": each['last_modified_timestamp'] for each in test_timestamp_data}
    test2firstmod_timestamp_tmp = {f"{each['test_case_path']}::::{each['test_case_name']}": each['first_committed_timestamp'] for each in test_timestamp_data}

    test2lastmod_timestamp = dict()
    test2firstmod_timestamp = dict()
    for idx in range(len(coverage_data)):
        each1 = coverage_data[idx]
        key = f"{args.project_name}{each1.test_case_path.split(args.project_name, 1)[1]}::::{each1.test_case_name}"
        if key not in test2lastmod_timestamp_tmp:
            print(f'[WARNING] Missing last modification timestamp for {key}. Using -1\n')
            test2lastmod_timestamp[each1.test_case] = -1
        else:
            test2lastmod_timestamp[each1.test_case] = test2lastmod_timestamp_tmp[key]

        if key not in test2firstmod_timestamp_tmp:
            print(f'[WARNING] Missing first committed timestamp for {key}. Using -1\n')
            test2firstmod_timestamp[each1.test_case] = -1
        else:
            test2firstmod_timestamp[each1.test_case] = test2firstmod_timestamp_tmp[key]

    if args.offline_fact_ref:
        if args.fact_setting == 'none' or args.test_desc_setting != 'full'  or args.reference_setting == 'none':
            offline_fact_ref_data = dataset.load_offline_fact_ref_data('retrieve', 'disc', 'full', args.max_exploration_depth, args.retrieval_threshold)
        else:
            offline_fact_ref_data = dataset.load_offline_fact_ref_data(args.reference_setting, args.fact_setting, args.test_desc_setting, args.max_exploration_depth, args.retrieval_threshold)

    # clean test cases in repos_removing_test folder
    test_case_paths = [each_target_pair.test_case_path for each_target_pair in coverage_data]
    clean_test_cases(test_case_paths)

    # # check the environment
    # check_environment([(each_target_pair.test_case, each_target_pair.test_case_path) for each_target_pair in coverage_data])

    # prepare LSP server
    lsp_workspace = f'{configs.project_path_no_test_file}'
    lsp_server = JavaLanguageServer(lsp_workspace, log=False)
    lsp_server.initialize(lsp_workspace)
    file_paths = lsp_server.get_all_file_paths(lsp_workspace)
    lsp_server.open_in_batch(file_paths)

    if args.offline_fact_ref:
        embedding_model, embedding_model_tokenizer = None, None
    else:
        # prepare embedding model and tokenizer used by retriever
        embedding_model = AutoModel.from_pretrained("Salesforce/codet5p-110m-embedding", trust_remote_code=True).eval().to('cuda')
        embedding_model_tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5p-110m-embedding", trust_remote_code=True)

    # prepare the fact discriminator
    if args.fact_setting == 'golden':
        if args.reference_setting == 'none' or args.test_desc_setting != 'full':
            golden_fact_set = dataset.load_golden_fact_ref_data('retrieve', 'golden', 'full', args.max_exploration_depth, args.retrieval_threshold)
        else:
            golden_fact_set = dataset.load_golden_fact_ref_data(args.reference_setting, args.fact_setting, args.test_desc_setting, args.max_exploration_depth, args.retrieval_threshold)
        fact_discriminator = FactDiscriminator(configs, embedding_model=None, tokenizer=None, is_golden=True)
        fact_discriminator.golden_fact_set = golden_fact_set
    elif args.fact_setting == 'disc':
        fact_discriminator = FactDiscriminator(configs, embedding_model=embedding_model, tokenizer=embedding_model_tokenizer, is_golden=False)
        graph_explorer = GraphExplorer(lsp_server, max_depth=args.max_exploration_depth)
    elif args.fact_setting == 'none':
        pass
    else:
        raise ValueError
    
    if args.prohibit_fact:
        golden_fact_set = dataset.load_golden_fact_ref_data('retrieve', 'golden', 'full', args.max_exploration_depth, args.retrieval_threshold)

    # prepare test generator
    intentiontest = IntentionTest(configs, lsp_server, max_round=args.n_refinement, skip_deepseek_think=args.skip_deepseek_think)

    # prepare the save path
    gen_save_path, messages_log_save_path = prepare_save_path()

    # start generating test case
    total_generated_test_cases = []
    total_generation_log = []

    for target_pair_idx, each_target_pair in tqdm(enumerate(coverage_data), total=len(coverage_data), ncols=80, desc='Generating test cases'):
        if target_pair_idx >= args.early_stop_at:
            print(f'[INFO] Early stop at {target_pair_idx}\n')
            break

        if target_pair_idx < args.resume_generation_at:
            continue
            
        if args.specify_test_cov_idx and target_pair_idx not in args.specify_test_cov_idx:
            continue
        
        print(f'\n\n[INFO] Coverage index: {target_pair_idx}\n\n')

        project_name = each_target_pair.project_name
        focal_file_path = each_target_pair.focal_file_path
        focal_method_name = each_target_pair.focal_method_name
        target_focal_method = each_target_pair.focal_method
        target_coverage = each_target_pair.coverage
        context = each_target_pair.focal_file_skeleton
        target_test_case = each_target_pair.test_case
        target_test_case_name = each_target_pair.test_case_name
        target_test_case_path = each_target_pair.test_case_path
        
        focal_method_pure_name = focal_method_name.split('::::')[1].split('(')[0]

        # assert test_desc_data[target_pair_idx]['target_test_case'] == target_test_case
        # target_test_case_desc = test_desc_data[target_pair_idx]['test_desc']['under_setting']

        if target_pair_idx not in cov_id2manual_desc:
            print(f'[INFO] Missing manual test description for {target_pair_idx}. Skip this sample.\n')
            continue
        
        target_test_case_desc = apply_test_desc_setting(cov_id2manual_desc[target_pair_idx]['test_desc'], args.test_desc_setting)

        # assert test_timestamp_data[target_pair_idx]['target_test_case'] == target_test_case
        target_test_case_first_committed_timestamp = test2firstmod_timestamp[target_test_case]

        if args.reference_setting == 'none':
            references_tc_rag, references_fm_rag, references_score = [], [], []
        else:
            if args.offline_fact_ref:
                if args.skip_missing_samples:
                    for info in offline_fact_ref_data:
                        if info['target_coverage_idx'] == target_pair_idx and focal_method_name in info['focal_method_name']:
                            ref_score, ref_focal_method, ref_test_case = info['rag_references'][0] if len(info['rag_references']) > 0 else [], [], []
                            break
                    else:
                        print(f'[INFO] Missing offline reference for {target_pair_idx}. Skip.\n')
                        continue
                else:
                    ref_score, ref_focal_method, ref_test_case = retrieve_reference_offline(target_pair_idx, offline_fact_ref_data, focal_method_name)
                references_tc_rag = [ref_test_case]
                references_fm_rag = [ref_focal_method]
                references_score = [ref_score]
            else:
                # prepare retriever and retrieve the reference
                # prepare corpus. remove the target pair from the corpus
                corpus_coverage_data = coverage_data[:target_pair_idx] + coverage_data[target_pair_idx+1:]
                corpus_desc_data = test_desc_data[:target_pair_idx] + test_desc_data[target_pair_idx+1:]

                references_cov_rag, references_fm_rag, references_fm_name_rag, references_tc_rag, reference_tc_desc_rag, references_score, references_tc_path =  retrieve_reference(
                    corpus_coverage_data, corpus_desc_data, target_focal_method, target_test_case, target_test_case_desc, args.retrieval_threshold, embedding_model_tokenizer, embedding_model, args.reference_setting,
                    top_k=1000
                    )
        
        top_1_reference_tc_rag = None
        rag_references = []
        if len(references_tc_rag) > 0:
            # find if there is a historical test
            for i, each_ref_tc in enumerate(references_tc_rag):
                ref_lastmod_timestamp = test2lastmod_timestamp[each_ref_tc]
                if ref_lastmod_timestamp <= target_test_case_first_committed_timestamp:
                    top_1_reference_tc_rag = each_ref_tc
                    rag_references = [(references_score[i], references_fm_rag[i], references_tc_rag[i])]

                    break
            if top_1_reference_tc_rag is None:
                print(f'[INFO] No suitable historical test case found for {target_pair_idx}.\n\n')
        
        if not rag_references and args.reference_setting == 'low_sim':
            print('[INFO] Since using low similarity reference setting, skip this sample\n')
            continue

        # collect facts
        if args.fact_setting == 'golden':
            if args.skip_missing_samples:
                facts = fact_discriminator.get_golden_facts_traversal(target_pair_idx, focal_method_name)
                if facts is None:
                    print(f'[INFO] Missing golden facts for {target_pair_idx}. Skip.\n')
                    continue

                facts_sim = [1.0] * len(facts)
            else:
                facts = fact_discriminator.get_golden_facts(target_pair_idx, focal_method_name)
                facts_sim = [1.0] * len(facts)
        elif args.fact_setting == 'none':
            if args.prohibit_fact:
                if args.skip_missing_samples:
                    facts = None
                    for info in golden_fact_set:
                        if info['target_coverage_idx'] == target_pair_idx and focal_method_name in info['focal_method_name']:
                            facts = info['golden_facts']
                            break
                    if facts is None:
                        print(f'[INFO] Missing golden facts for {target_pair_idx}. Skip.\n')
                        continue

                    facts_sim = [1.0] * len(facts)
                else:
                    facts = golden_fact_set[target_pair_idx]['golden_facts']
                    facts_sim = [1.0] * len(facts)
            else:
                facts = []
        elif args.fact_setting == 'disc':
            if args.offline_fact_ref:
                facts, facts_sim, usages, usages_sim = get_crucial_facts_offline(target_pair_idx, offline_fact_ref_data, focal_method_name, threshold=args.disc_threshold, top_k=args.disc_top_k)
            else:
                facts, facts_sim, usages, usages_sim = discriminate_cruical_facts(graph_explorer, fact_discriminator, focal_file_path, target_focal_method, target_test_case_desc, focal_method_pure_name, threshold=args.disc_threshold, top_k=args.disc_top_k)
            facts += usages
            facts_sim += usages_sim
        else:
            raise ValueError

        # generate the test case
        generated_test_case, test_status = intentiontest.generate_test_case_with_refine(
            target_focal_method=target_focal_method,
            target_context=context,
            target_test_case_desc=target_test_case_desc,
            target_test_case_path=target_test_case_path,
            referable_test_case=top_1_reference_tc_rag,
            facts=facts,
            junit_version=args.junit_version,
            prohibit_fact=args.prohibit_fact
            )
        generation_log = intentiontest.generation_with_refine_log
        refinement_times = len(generation_log) - 1

        # save results
        start_idx = target_test_case_path.index(project_name)
        target_test_case_rel_path = target_test_case_path[start_idx:]

        total_generation_log.append({
            'target_coverage_idx': target_pair_idx,
            'running_result': test_status,
            'refinement_times': refinement_times,
            'focal_file_path': focal_file_path, 
            'focal_method_name': focal_method_name,
            'target_test_case_name': target_test_case_name,
            'test_case_path': target_test_case_rel_path,
            'messages': [{
                'test_status': each_round[0],
                'prompt': each_round[1],
                'generated_test_case': each_round[2]
            } for each_round in generation_log]
        })

        if test_status == 'success':
            focal_method_name_parameter = focal_method_name.split('::::')[1]
            focal_file_coverage, fm_cov_statistic_by_jacoco = get_coverage_info(configs, target_test_case_rel_path, focal_method_name_parameter, focal_file_path)
        else:
            focal_file_coverage, fm_cov_statistic_by_jacoco = None, None

        total_generated_test_cases.append({
            'project_name': project_name,
            'target_coverage_idx': target_pair_idx,
            'running_result': test_status,
            'refinement_times': refinement_times,
            'focal_file_path': focal_file_path, 
            'focal_method_name': focal_method_name,
            'target_test_case_name': target_test_case_name,
            'test_case_path': target_test_case_rel_path,
            'test_desc': target_test_case_desc,
            'generated_test_case': generated_test_case,
            'rag_references': rag_references,
            'facts': list(zip(facts, facts_sim)) if args.fact_setting == 'disc' else facts,
            'target_coverage': target_coverage,
            'target_context': context,
            'target_test_case': target_test_case,
            'coverage_focal_file': focal_file_coverage,
            'coverage_focal_method': fm_cov_statistic_by_jacoco
        })

        with open(gen_save_path, 'w') as f:
            json.dump(total_generated_test_cases, f, indent=4)

        with open(messages_log_save_path, 'w') as f:
            json.dump(total_generation_log, f, indent=4)
    
    os.system(f'rm -rf {configs.project_path_no_test_file}')
    lsp_server.cleanup()
    lsp_server.close()


def retrieve_reference_offline(coverage_idx, offline_ref_data, focal_method_name, top_k=1):
    info = offline_ref_data[coverage_idx]
    assert info['target_coverage_idx'] == coverage_idx
    assert focal_method_name == info['focal_method_name']
    assert top_k == 1  # for now, only consider the top 1

    if len(info['rag_references']) == 0:
        return [], [], []
    else:
        ref_score, ref_focal_method, ref_test_case  = info['rag_references'][0]
        return ref_score, ref_focal_method, ref_test_case


def retrieve_reference(corpus_code, corpus_desc, target_focal_method, target_test_case, target_test_desc, threshold, retriever_tokenizer, retriever_embedding_model, setting, top_k=1):
    corpus_cov, corpus_fm, corpus_fm_name, corpus_tc, corpus_tc_desc, corpus_test_case_path = [], [], [], [], [], []
    for idx, each_pair_cor in enumerate(corpus_code):
        corpus_cov.append(each_pair_cor.coverage)
        corpus_fm.append(each_pair_cor.focal_method)
        corpus_fm_name.append(each_pair_cor.focal_method_name)
        corpus_tc.append(each_pair_cor.test_case)
        corpus_test_case_path.append(each_pair_cor.test_case_path)

        assert corpus_desc[idx]['target_test_case'] == each_pair_cor.test_case
        corpus_tc_desc.append(corpus_desc[idx]['test_desc']['under_setting'])
    
    retriever = Retriever(corpus_cov, corpus_fm, corpus_fm_name, corpus_tc, corpus_tc_desc, corpus_test_case_path, retriever_embedding_model, retriever_tokenizer)

    if setting == 'golden':
        assert top_k == 1  # for now, only consider the top 1
        references_cov_rag, references_fm_rag, references_fm_name_rag, references_tc_rag, reference_tc_desc_rag, references_score, references_tc_path = retriever.ideal_retrieve(
            target_tc=target_test_case, 
            threshold=threshold,
            top_k=top_k
            )
    elif setting == 'retrieve':
        references_cov_rag, references_fm_rag, references_fm_name_rag, references_tc_rag, reference_tc_desc_rag, references_score, references_tc_path = retriever.retrieve_with_threshold(
            target_fm=target_focal_method, 
            target_tc_desc=target_test_desc, 
            threshold=threshold,
            top_k=top_k
            )
    elif setting == 'low_sim':
        references_cov_rag, references_fm_rag, references_fm_name_rag, references_tc_rag, reference_tc_desc_rag, references_score, references_tc_path = retriever.retrieve_low_similarity(
            target_tc=target_test_case,
            target_fm=target_focal_method,
            percentile=0.2,
            top_k=top_k
            )
    else:
        raise ValueError
    return references_cov_rag, references_fm_rag, references_fm_name_rag, references_tc_rag, reference_tc_desc_rag, references_score, references_tc_path


def get_crucial_facts_offline(coverage_idx: int, offline_facts, focal_method_name: str, threshold: float, top_k: int):
    info = offline_facts[coverage_idx]
    assert info['target_coverage_idx'] == coverage_idx, f'Inconsistent coverage_idx: {coverage_idx} vs {info["target_coverage_idx"]}'
    assert focal_method_name == info['focal_method_name'], f'Inconsistent focal_method_name: {focal_method_name} vs {info["focal_method_name"]}'

    disc_facts = info['disc_facts']
    disc_facts_sim = info['disc_facts_sim']
    top_usages = info['top_usages']
    top_usages_sim = info['top_usages_sim']

    top_disc_facts, top_disc_facts_sim = [], []
    for i, each_disc_fact in enumerate(disc_facts):
        if disc_facts_sim[i] >= threshold:
            top_disc_facts.append(each_disc_fact)
            top_disc_facts_sim.append(disc_facts_sim[i])
    top_disc_facts = top_disc_facts[:top_k]
    top_disc_facts_sim = top_disc_facts_sim[:top_k]

    # provide signature rather the full body
    # TODO: should also modify the online version
    top_disc_facts_sig = []
    for each_fact in top_disc_facts:
        class_name, signature = each_fact.split('{')[0], each_fact.split('{')[1].strip()
        top_disc_facts_sig.append(class_name + '{\n' + signature + '\n}')
    top_disc_facts = top_disc_facts_sig

    return top_disc_facts, top_disc_facts_sim, top_usages, top_usages_sim


def discriminate_cruical_facts(graph_explorer, fact_discriminator, focal_file_path, target_focal_method, target_test_case_desc, focal_method_name, threshold=0.3, top_k=3):
    candidate_facts, focal_method_usages = graph_explorer.explore(f'{configs.project_dir_no_test_file}/{focal_file_path}', target_focal_method, focal_method_name)

    if len(candidate_facts) == 0:
        facts_string, facts_sim, usages_string, usages_sim = [], [], [], []
    else:
        # preprocess the candidate_facts and focal_method_usages
        candidate_facts_proc = [(each[0], each[1], each[2]) for each in candidate_facts if len(each[2]) > 0]  # [(class_name, signature, body)]
        candidate_facts_proc = list(set(candidate_facts_proc))

        usage_proc = []  # [(usage_body, [(fact_class_name, fact_signature)])]
        for each_usage in focal_method_usages:
            usage_proc.append(
                (
                    each_usage[2], 
                    set([(each_fact_in_usage[0], each_fact_in_usage[1]) for each_fact_in_usage in each_usage[3]])
                    )
                )

        facts, facts_sim, usages, usages_sim = fact_discriminator.get_crucial_facts_v2(candidate_facts_proc, usage_proc, target_test_case_desc, threshold=threshold, top_k=top_k)
        facts_string = [each[0] + '{\n' + each[1] + each[2] + '\n}' for each in facts]
        usages_string = [each[0] for each in usages]
    return facts_string, facts_sim, usages_string, usages_sim

def prepare_save_path():
    os.makedirs(os.path.dirname(configs.generated_test_case_save_path), exist_ok=True)
    os.makedirs(os.path.dirname(configs.generation_message_log_save_path), exist_ok=True)

    gen_save_path = f'{configs.generated_test_case_save_path[:-5]}'
    messages_log_save_path = f'{configs.generation_message_log_save_path[:-5]}'
    
    suffix = f'_{args.reference_setting}_ref_{args.fact_setting}_fact'
    suffix += f'_{args.disc_threshold}_{args.disc_top_k}' if args.fact_setting == 'disc' else ''
    suffix += f'_{args.test_desc_setting}_desc'
    suffix += f'_manual'

    if args.resume_generation_at > 0:
        suffix += f'_start_{args.resume_generation_at}'

    if args.specify_test_cov_idx:
        specify_test_cov_idx_str = ''.join([str(idx) for idx in args.specify_test_cov_idx])
        if len(specify_test_cov_idx_str) > 40:
            specify_test_cov_idx_str = specify_test_cov_idx_str[:40] + '_omitted'
        suffix += f'_specify_{specify_test_cov_idx_str}'

    suffix += '.json'

    gen_save_path = gen_save_path + suffix
    messages_log_save_path = messages_log_save_path + suffix

    return gen_save_path, messages_log_save_path


def check_environment(test_case_and_paths):
    for tc, tc_path in test_case_and_paths:
        print(f'[INFO] Checking the environment for {tc_path}...')
        os.makedirs(os.path.dirname(tc_path), exist_ok=True)
        with open(tc_path, 'w') as f:
            f.write(tc)

        cwd_path = tc_path.split('/src/test/')[0]
        mvn_compile_cmd = ['mvn', 'clean', 'test-compile']
        compile_result = subprocess.run(mvn_compile_cmd, cwd=cwd_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        os.remove(tc_path)

        if 'BUILD SUCCESS' not in compile_result.stdout:
            print(f'[ERROR] {tc_path} cannot be compiled.')
            print(compile_result.stdout)
            print(compile_result.stderr)
            exit(1)


def clean_test_cases(test_case_paths):
    for test_case_path in test_case_paths:
        if os.path.exists(test_case_path):
            os.system(f'rm {test_case_path}')


def get_coverage_info(configs, target_test_case_rel_path, focal_method_name_parameter, focal_file_path):
    test_runner = TestCaseRunner(configs, configs.test_case_run_log_dir)
    test_case_path = f"{configs.project_dir_no_test_file}/{target_test_case_rel_path}"
    focal_file_coverage, fm_cov_statistic_by_jacoco = test_runner.get_coverage_jacoco(test_case_path, focal_file_path, focal_method_name_parameter)
    return focal_file_coverage, fm_cov_statistic_by_jacoco


def run_all_test_cases(test_case_runner):
    # run the generated test cases
    with open(configs.generated_test_case_save_path, 'r') as f:
        test_cases = json.load(f)

    rag_ref_log_coverage = test_case_runner.run_all_test_cases(test_cases, is_ref='rag_ref')  # although set is_ref='rag_ref', it acutally execute both rag_ref and no_ref test cases. Will be modified in the future.
            
    test_case_runner.save_log_coverage(rag_ref_log_coverage, configs.test_case_log_and_coverage_save_path)


def get_statistics(statistic):
    def _analyze_coverage_with_target_coverage():
        print('- All coverages:')

        statistic.analyze_coverage_with_target_coverage(is_ref='all', n_cover_line_threshold=1)
        statistic.analyze_coverage_with_target_coverage(is_ref='all', n_cover_line_threshold=2)
        statistic.analyze_coverage_with_target_coverage(is_ref='all', n_cover_line_threshold=3)

    statistic.count_test_case_pass()

    # statistic.cal_bleu_for_test_cases(is_pass=False, is_common=False)
    # statistic.cal_bleu_for_test_cases(is_pass=True, is_common=False)

    statistic.cal_codebleu_for_test_cases(is_pass=False, is_common=False)
    # statistic.cal_codebleu_for_test_cases(is_pass=True, is_common=False)

    print('Coverage analysis...')
    _analyze_coverage_with_target_coverage()


def load_test_timestamp():
    from datetime import datetime

    with open(configs.test_timestamp_path, 'r') as f:
        test_timestamp_raw_data = json.load(f)
    test_timestamp_data = []
    for each in test_timestamp_raw_data:
        dt = datetime.strptime(each['timeline']['first_commit']['date'], "%Y-%m-%d %H:%M:%S %z")
        first_commit_timestamp = dt.timestamp()
        dt = datetime.strptime(each['timeline']['last_modification']['date'], "%Y-%m-%d %H:%M:%S %z")
        last_modification_timestamp = dt.timestamp()
        assert last_modification_timestamp == each['timeline']['last_modification']['timestamp']

        test_timestamp_data.append({
            'target_coverage_idx': each['target_coverage_idx'],
            'test_case_name': each['target_test_case_name'],
            'test_case_path': each['test_case_path'],
            'target_test_case': each['target_test_case'],
            'first_committed_timestamp': first_commit_timestamp,
            'last_modified_timestamp': last_modification_timestamp
        })
    return test_timestamp_data


def main():
    if not args.eval:
        # generate all test cases with rag (BM25)
        generation_pipeline()
    
        if args.resume_generation_at > 0 or args.specify_test_cov_idx:
            return

    # run all test cases
    if os.path.exists(configs.test_case_run_log_dir):
        os.system(f'rm -r {configs.test_case_run_log_dir}')
    os.makedirs(configs.test_case_run_log_dir)
    
    gen_save_path, _ = prepare_save_path()
    configs.generated_test_case_save_path = gen_save_path

    test_case_runner = TestCaseRunner(configs, configs.test_case_run_log_dir)
    run_all_test_cases(test_case_runner)

    # statistics of test case execution
    statistic = StatisticKG(configs.test_case_log_and_coverage_save_path)
    get_statistics(statistic)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project_name', type=str)
    parser.add_argument('--llm_name', type=str, default='gpt-5-mini', choices=['gpt-5-mini', 'deepseek-v3.2'])
    parser.add_argument('--retrieval_threshold', type=float, default=0.2)
    parser.add_argument('--resume_generation_at', type=int, default=0)
    parser.add_argument('--early_stop_at', type=int, default=999999)
    parser.add_argument('--specify_test_cov_idx', type=lambda s: [int(x) for x in s.split(',')], default=[])
    parser.add_argument('--junit_version', type=str, required=True, choices=['4', '5'])
    parser.add_argument('--eval', action='store_true')
    parser.add_argument('--fact_setting', type=str, default='disc', choices=['none', 'disc', 'golden'])
    parser.add_argument('--test_desc_setting', type=str, default='full', choices=['none', 'obj', 'obj_pre', 'obj_exp', 'full'])
    parser.add_argument('--reference_setting', type=str, default='retrieve', choices=['none', 'retrieve', 'golden', 'low_sim'])
    parser.add_argument('--max_exploration_depth', type=int, default=5)
    parser.add_argument('--offline_fact_ref', action='store_true')
    parser.add_argument('--disc_threshold', type=float, default=0.4)
    parser.add_argument('--disc_top_k', type=int, default=3)
    parser.add_argument('--skip_deepseek_think', action='store_true')
    parser.add_argument('--prohibit_fact', action='store_true')
    parser.add_argument('--n_refinement', type=int, default=3)
    parser.add_argument('--skip_missing_samples', action='store_true')

    args = parser.parse_args()

    configs = Configs(args.project_name, args.llm_name)
    setattr(configs, 'fact_setting', args.fact_setting)

    print(f'Args:\n{args}\n\n')
    print(f'Configs:\n{configs.__dict__}\n\n')

    print(f"Processing {configs.project_name}...\n\n")

    manual_desc_path = f'{configs.root_dir}/data/test_desc_from_human_dataset/{configs.project_name}.json'

    main()