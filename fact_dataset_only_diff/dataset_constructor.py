"""
Extract the golden facts.
Given the retrieved referable test and the target test, extract the crucial facts that are present in the target test but not in the referable test.
"""

import sys
import os
import json
import javalang
from transformers import AutoModel, AutoTokenizer

sys.path.append('..')
from parser.java_code_parser import JavaCodeParser
from LSPs.java_lsp import JavaLanguageServer
from configs import Configs
from dataset import Dataset
from tqdm import tqdm
from retriever import Retriever


IMPLEMENTATION_FILTER = ('thenReturn', 'assertThrows', 'mock', 'when', 'assertEquals', 'assertNotNull', 'assertTrue', 'assertFalse', 'verify', 'initMocks')


def extract_signature_from_implementation(lsp_server, path: str, position_line: int, position_column: int, method_name: str):
    implementation = get_implementation(lsp_server, path, position_line, position_column)
    if implementation is None and method_name not in IMPLEMENTATION_FILTER:
        print(f"- Extract signature ({method_name}): No implementation found.")
        print(f"- Path: {path}\nposition: {position_line}, {position_column}\n\n")
        return None

    enclose_class = f"public class TempClass {{\n{implementation}\n}}"

    try:
        tree = javalang.parse.parse(enclose_class)
    except:
        if method_name not in IMPLEMENTATION_FILTER:
            print(f"- Extract signature ({method_name}): failed to parse the implementation.")
            print(f"- Path: {path}\nposition: {position_line}, {position_column}")
            print(implementation, "\n\n")
        return None

    # Traverse the tree to find method declarations
    for _, node in tree:
        if isinstance(node, javalang.tree.MethodDeclaration):
            visibility = ' '.join(node.modifiers)
            return_type = node.return_type.name if node.return_type else ''
            method_name = node.name
            parameters = ', '.join(f"{p.type.name} {p.name}" for p in node.parameters)
            exceptions = ', '.join(node.throws) if node.throws else ''
            
            # Construct the method signature
            method_signature = f"{visibility} {return_type} {method_name}({parameters})"
            if exceptions:
                method_signature += f" throws {exceptions}"
            return method_signature
        
        elif isinstance(node, javalang.tree.ConstructorDeclaration):  # Constructors
            visibility = ' '.join(node.modifiers)
            constructor_name = node.name
            parameters = ', '.join(f"{p.type.name} {p.name}" for p in node.parameters)
            
            # Construct the constructor signature
            constructor_signature = f"{visibility} {constructor_name}({parameters})"
            # print("Constructor:", constructor_signature, "\n\n")
            return constructor_signature
            
    print(f"- Extract signature ({method_name}): failed to find the method declaration in the implementation.")
    print(f"- Path: {path}\nposition: {position_line}, {position_column}")
    print(f'{implementation}\n\n')
    return None


def get_implementation(lsp_server, path: str, position_line: int, position_column: int):
    message = lsp_server.implementation(
        path,
        {"line": position_line, "character": position_column}
    )

    if len(message) == 0:
        return None

    if 'result' not in message[0]:
        return None

    results = message[0]['result']
    if len(results) == 0:
        return None

    impl_file_path = results[0]['uri'].replace('file://', '')
    impl_start_line = results[0]['range']['start']['line']

    if '.class' in impl_file_path:  # TODO: support parse .class file in the jar.
        return None

    java_code_parser = JavaCodeParser()
    java_code_parser.parse_java_file(impl_file_path)
    impl = java_code_parser.get_implementation_given_name_line(impl_start_line)
    return impl


def get_definition(lsp_server, path: str, position_line: int, position_column: int):
    message = lsp_server.definition(
        path,
        {"line": position_line, "character": position_column}
    )

    if len(message) == 0:
        return None

    if 'result' not in message[0]:
        return None

    results = message[0]['result']
    if len(results) == 0:
        return None

    def_file_path = results[0]['uri'].replace('file://', '')
    def_start_line = results[0]['range']['start']['line']

    if '.class' in def_file_path:  # TODO: support parse .class file in the jar.
        return None

    with open(def_file_path, 'r') as f:
        lines = f.readlines()
        definition = lines[def_start_line].strip()

    return definition


def get_type_definition(lsp_server, path: str, position_line: int, position_column: int):
    message = lsp_server.type_definition(
        path,
        {"line": position_line, "character": position_column}
    )

    if len(message) == 0:
        return None
    
    if 'result' not in message[0]:
        return None
    
    results = message[0]['result']
    if len(results) == 0:
        return None
    
    type_def_file_path = results[0]['uri'].replace('file://', '')
    type_def_start_line = results[0]['range']['start']['line']
    type_def_start_column = results[0]['range']['start']['character']
    type_def_end_column = results[0]['range']['end']['character']

    if '.class' in type_def_file_path:  # TODO: support parse .class file in the jar.
        return None

    with open(type_def_file_path, 'r') as f:
        lines = f.readlines()
        type_definition = lines[type_def_start_line][type_def_start_column: type_def_end_column].strip()
    return type_definition


def extract_api_field_invocations(java_code: str):
    java_parser = JavaCodeParser()
    java_parser.parse_java_code(java_code)

    api_invocations = java_parser.get_all_invocation()
    field_access_standard, field_access_other = java_parser.get_all_field_access()
    return api_invocations, field_access_standard, field_access_other


def extract_signatures_and_fields(java_code: str, java_code_save_path: str, lsp_server: JavaLanguageServer):
    with open(java_code_save_path, 'w') as f:
        f.write(java_code)

    signatures, fields = [], []
    api_invocations, field_access_standard, field_access_other = extract_api_field_invocations(java_code)

    for each_invoc in api_invocations:
        each_invoc_position = each_invoc[0]
        each_invoc_name = each_invoc[1]
        sign = extract_signature_from_implementation(lsp_server, java_code_save_path, each_invoc_position[0], each_invoc_position[1], each_invoc_name)

        if sign and sign not in [each[0] for each in signatures]:
            signatures.append(sign)

    # such as CronFieldName.DAY_OF_MONTH
    for each_field in field_access_standard:
        each_field_position = each_field[0]
        each_field_name = each_field[1]

        qualifier_name, field_name = each_field_name.split('.')
        qualifier_type = get_type_definition(lsp_server, java_code_save_path, each_field_position[0], each_field_position[1])  # considering such cases like input.closed where input is a valiable of MockInputStream

        column = each_field_position[1] + len(qualifier_name) + 1
        field = get_definition(lsp_server, java_code_save_path, each_field_position[0], column)  # TODO: fix a bug. some field access (e.g., CronType.QUARTZ) cannot be found using field (e.g., QUARTZ in CronType.QUARTZ) but can be found using the identifier (e.g., CronType in CronType.QUARTZ) 
        # TODO: fix a bug. the current implementation assumes that all fields are in one line. However, for some cases, the fields could be in multiple lines, such as the fields in a class. So, can extract all fields after getting the type definition.

        if field is None:
            continue
        
        if (each_field_name, qualifier_type, field) not in fields:
            fields.append((each_field_name, qualifier_type, field))

    # Field access such as AlwaysFieldValueGenerator.class
    # TODO: consider parsing such field access

    os.remove(java_code_save_path)
    lsp_server.did_close(java_code_save_path)
    return set(signatures), set(fields)


def extract_facts(lsp_server, tar_tc: str, tar_fm_name: str, tar_context: str, tar_path: str, ref_tc: str, ref_path: str):
    signatures_in_tar_tc, field_in_tar_tc = extract_signatures_and_fields(tar_tc, tar_path, lsp_server)
    
    if ref_tc is None:
        signatures_in_ref_tc, field_in_ref_tc = set(), set()
    else:
        signatures_in_ref_tc, field_in_ref_tc = extract_signatures_and_fields(ref_tc, ref_path, lsp_server)
    
    fact_signatures = signatures_in_tar_tc - signatures_in_ref_tc

    ###
    # filter out the facts that is the focal method itself or have appear in the class skeleton.
    ###
    fact_signatures_filter = []
    for each in fact_signatures:
        method_name = each.split('(')[0].split(' ')[-1]
        if method_name == tar_fm_name:
            continue
        
        # find the name token
        # TODO: some inconsistency in the formats of signatures from skeleton and the signatures extrated here. Such as `protected  loadIfNot() throws IOException` vs `protected void loadIfNot()`, and `public Every(FieldExpression expression, IntegerFieldValue period)` vs `public Every(final FieldExpression expression, final IntegerFieldValue period)`
        # TODO: for now, only compare the method name and the parameters. In the future, consider comparing the return type and the exceptions.
        each_signature_tokens = each.split()
        for idx, each_token in enumerate(each_signature_tokens):
            if '(' in each_token:
                each_signature_name_with_parameters = ' '.join(each_signature_tokens[idx:])
                break
        if each_signature_name_with_parameters in tar_context:
            continue
        
        fact_signatures_filter.append(each)
    fact_signatures = set(fact_signatures_filter)

    fact_fields = field_in_tar_tc - field_in_ref_tc
    fact_fields = set([f'Fields in {each[1]}: {each[2]}' for each in fact_fields])
    
    facts = fact_signatures.union(fact_fields)
    return list(facts)


def main():
    crucial_dataset = []

    # prepare the save path
    save_path = f'{configs.fact_set_dir}/ref_retrieve_fact_golden_desc_full_depth_5_refThres_0.2.json'

    if resume_generation_at > 0:
        save_path = save_path.replace('.json', f'_resume_{resume_generation_at}.json')

    ###
    # prepare the lsp server for the reference and target test cases, which are used to extract the method signature given the method invocation.
    ###
    lsp_workspace = f'{configs.project_path_no_test_file}'
    lsp_server = JavaLanguageServer(lsp_workspace, log=False)
    lsp_server.initialize(lsp_workspace)
    file_paths = lsp_server.get_all_file_paths(lsp_workspace)
    lsp_server.open_in_batch(file_paths)

    for target_pair_idx, each_target_pair in tqdm(enumerate(coverage_data), total=len(coverage_data), ncols=80, desc='Extracting Crucial Facts'):
        if target_pair_idx < resume_generation_at:
            continue

        tar_tc = each_target_pair.test_case
        tar_fm_name = each_target_pair.focal_method_name
        tar_tc_name = each_target_pair.test_case_name
        tar_context = each_target_pair.focal_file_skeleton
        target_test_case_path = each_target_pair.test_case_path
        tar_path = target_test_case_path[:-5] + '_tar' + '.java'  # modified the test case path to avoid the conflict with the reference test case path.

        tar_fm_name_pure = tar_fm_name.split('::::')[1].split('(')[0]
        ###
        # load reference
        ###
        offline_fact_info = offline_fact_ref_data[target_pair_idx]
        assert offline_fact_info['target_coverage_idx'] == target_pair_idx
        assert offline_fact_info['focal_method_name'] == each_target_pair.focal_method_name

        if len(offline_fact_info['rag_references']) > 0:
            ref_score, ref_fm, ref_tc = offline_fact_info['rag_references'][0]
            for each_cov in coverage_data:
                if ref_tc == each_cov.test_case:
                    ref_path = each_cov.test_case_path
                    ref_path_modified = ref_path[:-5] + '_ref' + '.java'  # modified the test case path to avoid the conflict with the target test case path.
                    break
            assert ref_path_modified is not None
        else:
            ref_tc, ref_path_modified = None, None

        ###
        # extract crucial facts
        ###
        facts = extract_facts(lsp_server, tar_tc, tar_fm_name_pure, tar_context, tar_path, ref_tc, ref_path_modified)

        data = {
            'target_coverage_idx': target_pair_idx,
            'focal_file_path': each_target_pair.focal_file_path,
            'focal_method_name': each_target_pair.focal_method_name,
            'test_desc': offline_fact_info['test_desc'],
            'rag_references': [[ref_score, ref_fm, ref_tc]] if ref_tc is not None else [],
            'target_test_case': tar_tc,
            'golden_facts': facts,
            'target_coverage': each_target_pair.coverage,
        }

        crucial_dataset.append(data)

        with open(save_path, 'w') as f:
            f.write(json.dumps(crucial_dataset, indent=4))

    os.system(f'rm -rf {configs.project_path_no_test_file}')
    # close the lsp server
    lsp_server.close()


if __name__ == '__main__':
    project_name_list = [('spark', 0)]

    for project_name, resume_generation_at in project_name_list:
        print(f'\n\n\nProject: {project_name}')
        configs = Configs(project_name, llm_name='deepseek-32B')

        print('Loading jacoco labelled coverages...')
        dataset = Dataset(configs)
        coverage_data = dataset.load_coverage_data_jacoco()

        offline_fact_ref_data = dataset.load_offline_fact_ref_data('retrieve', 'disc', 'full', 5, 0.2)  # contains the retrieved reference.

        main()