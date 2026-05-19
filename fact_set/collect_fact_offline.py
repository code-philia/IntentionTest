import json
import os
import argparse
from tqdm import tqdm
import subprocess
from transformers import AutoModel, AutoTokenizer
import sys
sys.path.append('..')

from LSPs.java_lsp import JavaLanguageServer
from fact_discriminator.discriminator import FactDiscriminator
from configs import Configs
from retriever import Retriever, retrieve_reference
from graph_explorer import GraphExplorer
from dataset import Dataset


def collect_facts():
    # prepare the datasets
    dataset = Dataset(configs)
    print('Loading datasets...')
    coverage_data = dataset.load_coverage_data_jacoco()
    test_desc_data = dataset.load_test_desc(setting=args.test_desc_setting)

    # prepare LSP server
    lsp_workspace = f'{configs.project_path_no_test_file}'
    lsp_server = JavaLanguageServer(lsp_workspace, log=False)
    lsp_server.initialize(lsp_workspace)
    file_paths = lsp_server.get_all_file_paths(lsp_workspace)
    lsp_server.open_in_batch(file_paths)

    # prepare embedding model and tokenizer used by retriever
    embedding_model = AutoModel.from_pretrained("Salesforce/codet5p-110m-embedding", trust_remote_code=True).eval().to('cuda')
    embedding_model_tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5p-110m-embedding", trust_remote_code=True)

    # prepare the fact discriminator
    if args.fact_setting == 'golden':
        fact_discriminator = FactDiscriminator(configs, embedding_model=None, tokenizer=None, is_golden=True)
    elif args.fact_setting == 'disc':
        fact_discriminator = FactDiscriminator(configs, embedding_model=embedding_model, tokenizer=embedding_model_tokenizer, is_golden=False)
        graph_explorer = GraphExplorer(lsp_server, max_depth=args.max_exploration_depth, efficieny_mode=True if args.project_name == 'lambda' else False)
    elif args.fact_setting == 'none':
        pass
    else:
        raise ValueError
    
    # prepare the save path
    os.makedirs(configs.fact_set_dir, exist_ok=True)
    save_path = f'{configs.fact_set_dir}/ref_{args.reference_setting}_fact_{args.fact_setting}_desc_{args.test_desc_setting}_depth_{args.max_exploration_depth}_refThres_{args.retrieval_threshold}.json'

    if args.resume_generation_at > 0:
        save_path = save_path.replace('.json', f'_resume_{args.resume_generation_at}.json')

    collected_facts = []
    # start collection
    for target_pair_idx, each_target_pair in tqdm(enumerate(coverage_data), total=len(coverage_data), ncols=80, desc='Generating test cases'):
        if target_pair_idx < args.resume_generation_at:
            continue
            
        if args.specify_test_cov_idx and target_pair_idx not in args.specify_test_cov_idx:
            continue
        
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

        assert test_desc_data[target_pair_idx]['target_test_case'] == target_test_case
        target_test_case_desc = test_desc_data[target_pair_idx]['test_desc']['under_setting']

        if args.reference_setting == 'none':
            references_tc_rag, references_fm_rag, references_score = [], [], []
        else:
            # prepare retriever and retrieve the reference
            # prepare corpus. remove the target pair from the corpus
            corpus_coverage_data = coverage_data[:target_pair_idx] + coverage_data[target_pair_idx+1:]
            corpus_desc_data = test_desc_data[:target_pair_idx] + test_desc_data[target_pair_idx+1:]

            references_cov_rag, references_fm_rag, references_fm_name_rag, references_tc_rag, reference_tc_desc_rag, references_score, references_tc_path = retrieve_reference(
                corpus_coverage_data, corpus_desc_data, target_focal_method, target_test_case, target_test_case_desc, args.retrieval_threshold, embedding_model_tokenizer, embedding_model, args.reference_setting
                )
        
        if len(references_tc_rag) > 0:
            top_1_reference_tc_rag = references_tc_rag[0]
        else:
            top_1_reference_tc_rag = None
            
        # collect facts
        if args.fact_setting == 'golden':
            facts, target_tc_for_verify = fact_discriminator.get_golden_facts(target_pair_idx)
            if target_tc_for_verify is not None and target_tc_for_verify != target_test_case:
                print(f'WARNING: The target test case for verification is different from the target test case for generation.')
                print(f'# Target test case from coverage dataset:\n{target_test_case}')
                print(f'# Target test case from fact dataset:\n{target_tc_for_verify}')
                raise ValueError
        elif args.fact_setting == 'none':
            raise ValueError
        elif args.fact_setting == 'disc':
            all_candidate_facts, facts, facts_sim, all_usages, usages, usages_sim = discriminate_cruical_facts(graph_explorer, fact_discriminator, focal_file_path, target_focal_method, target_test_case_desc, focal_method_pure_name)
        else:
            raise ValueError

        rag_references = [(references_score[i], references_fm_rag[i], references_tc_rag[i]) for i in range(len(references_fm_rag))]

        collected_facts.append({
            'target_coverage_idx': target_pair_idx,
            'focal_file_path': focal_file_path,
            'focal_method_name': focal_method_name,
            'test_desc': target_test_case_desc,
            'rag_references': rag_references,
            'target_test_case': target_test_case,
            'candidate_facts': all_candidate_facts,
            'disc_facts': facts,
            'disc_facts_sim': facts_sim,
            'all_usages': all_usages,
            'top_usages': usages,
            'top_usages_sim': usages_sim,
            'target_coverage': target_coverage,
        })

        with open(save_path, 'w') as f:
            json.dump(collected_facts, f, indent=4)


def discriminate_cruical_facts(graph_explorer, fact_discriminator, focal_file_path, target_focal_method, target_test_case_desc, focal_method_name):
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

        facts, facts_sim, usages, usages_sim = fact_discriminator.get_crucial_facts_v2(candidate_facts_proc, usage_proc, target_test_case_desc, threshold=0.1, top_k=10)  # relax the threshold to returen more discriminated facts with similarity score
        facts_string = [each[0] + '{\n' + each[1] + each[2] + '\n}' for each in facts]
        usages_string = [each[0] for each in usages]
    return candidate_facts, facts_string, facts_sim, focal_method_usages, usages_string, usages_sim


def main():
    collect_facts()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project_name', type=str)
    parser.add_argument('--llm_name', type=str, default='deepseek-32B')
    parser.add_argument('--retrieval_threshold', type=float, default=0.2)
    parser.add_argument('--resume_generation_at', type=int, default=0)
    parser.add_argument('--specify_test_cov_idx', type=lambda s: [int(x) for x in s.split(',')], default=[])
    parser.add_argument('--fact_setting', type=str, default='disc', choices=['none', 'disc', 'golden'])
    parser.add_argument('--test_desc_setting', type=str, default='full', choices=['none', 'obj', 'obj_pre', 'obj_exp', 'full'])
    parser.add_argument('--reference_setting', type=str, default='retrieve', choices=['none', 'retrieve', 'golden'])
    parser.add_argument('--max_exploration_depth', type=int, default=5)

    args = parser.parse_args()

    # # project_list = ["itext-java", "hutool", "yavi", "lambda", "jInstagram", "truth", "cron-utils", "imglib", "ofdrw", "RocketMQC", "blade", "spark", "awesome-algorithm"]
    # project_list = ["hutool", ]

    # for each_project in project_list:
    #     args.project_name = each_project
    print(f'\n\n\n=======================Project: {args.project_name}=======================\n\n\n')

    configs = Configs(args.project_name, args.llm_name)
    setattr(configs, 'fact_setting', args.fact_setting)

    print(f'Args:\n{args}\n\n')
    print(f'Configs:\n{configs.__dict__}\n\n')

    print(f"Processing {configs.project_name}...\n\n")

    main()