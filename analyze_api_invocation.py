import argparse
import json
import os
from tqdm import tqdm
from configs import Configs
from parser.java_code_parser import JavaCodeParser
from LSPs.java_lsp import JavaLanguageServer


def extract_project_api_invocations(java_code, java_code_path):
    os.makedirs(os.path.dirname(java_code_path), exist_ok=True)

    with open(java_code_path, 'w') as file:
        file.write(java_code)
    java_code_parser.parse_java_file(java_code_path)
    candidate_invocation_line_name_arg_tuples = java_code_parser.get_all_invocation()  # [((line, col), method_name, arguments), ...]

    # confirm the invoked API is defined in the project
    project_api_invocation_line_name_arg_tuples = []
    for invoc_node in candidate_invocation_line_name_arg_tuples:
        invoc_start_line, invoc_start_column = invoc_node[0]
        message = lsp_server.implementation(java_code_path, {"line": invoc_start_line, "character": invoc_start_column})
        impl_file_path, impl_start_line = extract_file_path_start_line_from_lsp_msg(message)
        
        if impl_file_path and impl_start_line:
            relative_impl_file_path = f'{args.project_name}/' + impl_file_path.split(f'/{args.project_name}/')[-1]
            invoc_info = list(invoc_node) + [relative_impl_file_path, impl_start_line]
            project_api_invocation_line_name_arg_tuples.append(invoc_info)

    return project_api_invocation_line_name_arg_tuples


def extract_file_path_start_line_from_lsp_msg(message):
    """
    check if the LSP message is valid.
    """
    if len(message) == 0:
        return None, None

    if 'result' not in message[0]:
        return None, None

    results = message[0]['result']
    if len(results) == 0:
        return None, None
    
    choice_idx = 0
    if len(results) > 1:
        for each_idx, each_result in enumerate(results):
            if each_result['uri'].endswith('.java'):
                choice_idx = each_idx
                break
    
    file_path = results[choice_idx]['uri'].replace('file://', '')
    start_line = results[choice_idx]['range']['start']['line']

    # TODO: support parse .class file in the jar.
    if ('.class' in file_path
        or '/src/test/' in file_path):  
        return None, None
    
    return file_path, start_line


def parse_invocation(invocations):
    parsed_invocations = dict()
    for each in invocations:
        idx = each['target_coverage_idx']

        invoc_list = []
        for each_invoc in each['invocations']:
            file_path, start_line = each_invoc[-2], each_invoc[-1]
            invoc_list.append((file_path, start_line))
        parsed_invocations[idx] = invoc_list
    return parsed_invocations


def calculate_invocation_ratio():
    generated_test_invocations_path = f'/home/binhang/binhang/DTester/data/project_api_invocation_stats/ours/{args.project_name}.json'
    target_test_invocations_path = f'/home/binhang/binhang/DTester/data/project_api_invocation_stats/target/{args.project_name}.json'
    chattester_test_invocations_path = f'/home/binhang/binhang/DTester/data/project_api_invocation_stats/chattester/{args.project_name}.json'
    
    with open(generated_test_invocations_path, 'r') as file:
        ours_gen_invocations = json.load(file)
    with open(target_test_invocations_path, 'r') as file:
        target_invocations = json.load(file)
    with open(chattester_test_invocations_path, 'r') as file:
        chattester_invocations = json.load(file)

    gen_idx_to_invoc_list = parse_invocation(ours_gen_invocations)
    tar_idx_to_invoc_list = parse_invocation(target_invocations)
    chat_idx_to_invoc_list = parse_invocation(chattester_invocations)

    gen_tar_list_ratio, gen_tar_set_ratio = [], []
    chat_tar_list_ratio, chat_tar_set_ratio = [], []
    for idx in tar_idx_to_invoc_list:
        if idx not in gen_idx_to_invoc_list:
            print(f'[WARNING] idx {idx} not in generated test invocations')
            continue
        
        if idx not in chat_idx_to_invoc_list:
            print(f'[WARNING] idx {idx} not in chattester test invocations')
            continue

        tar_invoc_list = tar_idx_to_invoc_list[idx]
        tar_invoc_set = set(tar_invoc_list)
        gen_invoc_list = gen_idx_to_invoc_list[idx]
        gen_invoc_set = set(gen_invoc_list)
        chat_invoc_list = chat_idx_to_invoc_list[idx]
        chat_invoc_set = set(chat_invoc_list)

        if len(tar_invoc_list) == 0:
            print(f'[INFO] idx {idx} has 0 target invocations. Skip.')
            continue

        # intersection between tar_invoc_list and gen_invoc_list
        gen_tar_inter_list = [each for each in gen_invoc_list if each in tar_invoc_list]
        gen_tar_list_ratio.append(len(gen_tar_inter_list) / len(tar_invoc_list))
        gen_tar_inter_set = gen_invoc_set.intersection(tar_invoc_set)
        gen_tar_set_ratio.append(len(gen_tar_inter_set) / len(tar_invoc_set))

        # intersection between tar_invoc_list and chat_invoc_list
        chat_tar_inter_list = [each for each in chat_invoc_list if each in tar_invoc_list]
        chat_tar_list_ratio.append(len(chat_tar_inter_list) / len(tar_invoc_list))
        chat_tar_inter_set = chat_invoc_set.intersection(tar_invoc_set)
        chat_tar_set_ratio.append(len(chat_tar_inter_set) / len(tar_invoc_set))

    print(f'\n\n{args.project_name}')
    print(f'[INFO] Total target common test cases with invocations: {len(chat_tar_set_ratio)}')
    print(f'[RESULT] Generated vs Target: List ratio: {sum(gen_tar_list_ratio) / len(gen_tar_list_ratio):.4f}, Set ratio: {sum(gen_tar_set_ratio) / len(gen_tar_set_ratio):.4f}')
    print(f'[RESULT] ChatTester vs Target: List ratio: {sum(chat_tar_list_ratio) / len(chat_tar_list_ratio):.4f}, Set ratio: {sum(chat_tar_set_ratio) / len(chat_tar_set_ratio):.4f}')


def main():
    if args.stage == 'collect_ours_gen_and_target':
        ours_gen_test_invocations = []
        target_test_invocations = []

        generated_tests_path = f'/home/binhang/binhang/DTester/data/backup_icse26/generated_test_cases/gpt-o1-mini/{args.project_name}_retrieve_ref_disc_fact_0.4_3_full_desc.json'

        generated_test_invocations_path = prepare_save_path(f'/home/binhang/binhang/DTester/data/project_api_invocation_stats/ours/{args.project_name}.json')
        target_test_invocations_path = prepare_save_path(f'/home/binhang/binhang/DTester/data/project_api_invocation_stats/target/{args.project_name}.json')
        os.makedirs(os.path.dirname(generated_test_invocations_path), exist_ok=True)
        os.makedirs(os.path.dirname(target_test_invocations_path), exist_ok=True)

        with open(generated_tests_path, 'r') as file:
            generated_tests = json.load(file)

        for idx, each_gen in tqdm(enumerate(generated_tests), total=len(generated_tests), ncols=80):
            if idx < args.start_at:
                continue
            if idx >= args.stop_at:
                break

            gen_test = each_gen['generated_test_case']
            tar_test = each_gen['target_test_case']

            project_path = configs.project_path_no_test_file.split(f'/{args.project_name}')[0]
            test_path = f"{project_path}/{each_gen['test_case_path']}"

            gen_test_invocations = extract_project_api_invocations(gen_test, test_path)
            tar_test_invocations = extract_project_api_invocations(tar_test, test_path)

            ours_gen_test_invocations.append({
                'target_coverage_idx': each_gen['target_coverage_idx'],
                'generated_test_case': gen_test,
                'invocations': gen_test_invocations
            })

            target_test_invocations.append({
                'target_coverage_idx': each_gen['target_coverage_idx'],
                'target_test_case': tar_test,
                'invocations': tar_test_invocations
            })

            with open(generated_test_invocations_path, 'w') as file:
                json.dump(ours_gen_test_invocations, file, indent=4)

            with open(target_test_invocations_path, 'w') as file:
                json.dump(target_test_invocations, file, indent=4)

    elif args.stage == 'collect_chattester':
        chattester_test_invocations = []

        chattester_tests_path = f'/home/binhang/binhang/DTester/data/backup_icse26/generated_test_cases/ChatTester/{args.project_name}.json'
        chattester_test_invocations_path = prepare_save_path(f'/home/binhang/binhang/DTester/data/project_api_invocation_stats/chattester/{args.project_name}.json')
        os.makedirs(os.path.dirname(chattester_test_invocations_path), exist_ok=True)

        with open(chattester_tests_path, 'r') as file:
            chattester_tests = json.load(file)

        for idx, each_gen in tqdm(enumerate(chattester_tests), total=len(chattester_tests), ncols=80):
            if idx < args.start_at:
                continue

            if idx >= args.stop_at:
                break

            test_code = each_gen['generation']
            project_path = configs.project_path_no_test_file.split(f'/{args.project_name}')[0]
            relative_path = each_gen['original_path'][len(each_gen['original_path'].split(f'/{args.project_name}/')[0])+1:]
            test_path = f"{project_path}/{relative_path}"

            test_invocations = extract_project_api_invocations(test_code, test_path)

            chattester_test_invocations.append({
                'target_coverage_idx': each_gen['target_coverage_idx'],
                'test_case': test_code,
                'invocations': test_invocations
            })

            with open(chattester_test_invocations_path, 'w') as file:
                json.dump(chattester_test_invocations, file, indent=4)
    elif args.stage == 'cal_ratio':
        calculate_invocation_ratio()
    else:
        raise NotImplementedError


def prepare_save_path(initial_path):
    updated_path = initial_path[:-5]

    suffix = ''
    if args.start_at > 0:
        suffix += f'_{args.start_at}'

    suffix += '.json'
    updated_path += suffix

    return updated_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--project_name', type=str)
    parser.add_argument('--stage', type=str, choices=['collect_ours_gen_and_target', 'collect_chattester', 'cal_ratio'])
    parser.add_argument('--start_at', type=int, default=0)
    parser.add_argument('--stop_at', type=int, default=9999999)

    args = parser.parse_args()
    configs = Configs(args.project_name, 'gpt-o1-mini')

    java_code_parser = JavaCodeParser()

    # prepare LSP server
    lsp_workspace = f'{configs.project_path_no_test_file}'
    lsp_server = JavaLanguageServer(lsp_workspace, log=False)
    lsp_server.initialize(lsp_workspace)
    file_paths = lsp_server.get_all_file_paths(lsp_workspace)
    lsp_server.open_in_batch(file_paths)

    main()