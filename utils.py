import javalang
import json
import re

def extract_import_statements(java_code: str):
    try:
        tree = javalang.parse.parse(java_code)
    except Exception as e:
        print(f"WARNING: Failed to parse java code. {e}\n{java_code}\n\n")
        return []

    import_statements = []
    for _, node in tree:
        if isinstance(node, javalang.tree.Import):
            import_statements.append(f'import {node.path};')

    return import_statements


def insert_import_statements(init_java_code: str, import_statements: list):
    lines = init_java_code.split('\n')
    insert_index = 0

    # Find the index to insert import statements after the package declaration
    for i, line in enumerate(lines):
        if line.startswith('package '):
            insert_index = i + 1
            break

    # Insert import statements
    for statement in import_statements:
        lines.insert(insert_index, statement)
        insert_index += 1

    return '\n'.join(lines)


def remove_import_statements(java_code: str):
    lines = java_code.split('\n')
    new_lines = []
    for line in lines:
        if line.startswith('import ') or line.startswith('package '):
            continue
        
        new_lines.append(line)

    return '\n'.join(new_lines)


def type_to_str(t):
    """
    Convert a javalang type node into its Java source code representation.
    Supports both BasicType and ReferenceType, including type arguments and dimensions.
    """
    if t is None:
        return ""
    if isinstance(t, javalang.tree.BasicType):
        type_str = t.name
    elif isinstance(t, javalang.tree.ReferenceType):
        type_str = t.name
        if t.arguments:
            args_str = ", ".join(type_argument_to_str(arg) for arg in t.arguments)
            type_str += f"<{args_str}>"
    else:
        type_str = str(t)
    if hasattr(t, 'dimensions') and t.dimensions:
        type_str += "[]" * len(t.dimensions)
    return type_str


def type_argument_to_str(arg):
    """
    Convert a TypeArgument node to its source code representation.
    If the argument represents a wildcard (i.e. its type is None), simply return "?".
    Otherwise, if a bound is specified, include it.
    """
    if isinstance(arg, javalang.tree.TypeArgument):
        # Wildcard with no bound, e.g. <?>
        if arg.type is None:
            return "?"
        # Wildcard with a bound, e.g. <? extends Number>
        if arg.pattern_type:
            return f"? {arg.pattern_type} {type_to_str(arg.type)}"
        else:
            return type_to_str(arg.type)
    else:
        return type_to_str(arg)


def format_parameter(param):
    """
    Format a method or constructor parameter, including modifiers such as 'final'.
    """
    mods = ""
    if param.modifiers and "final" in param.modifiers:
        mods = "final "
    type_str = type_to_str(param.type)
    return f"{mods}{type_str} {param.name}"


def expr_to_str(expr):
    """
    Convert an expression node back into Java source code.
    This function handles literals, member references, method invocations,
    array initializers/creators, class creators, class references, binary
    and ternary expressions.
    """
    if expr is None:
        return ""
    if isinstance(expr, javalang.tree.Literal):
        return expr.value
    elif isinstance(expr, javalang.tree.MemberReference):
        qualifier = f"{expr.qualifier}." if expr.qualifier else ""
        return f"{qualifier}{expr.member}"
    elif isinstance(expr, javalang.tree.MethodInvocation):
        qualifier = f"{expr.qualifier}." if expr.qualifier else ""
        args = ", ".join(expr_to_str(arg) for arg in expr.arguments)
        return f"{qualifier}{expr.member}({args})"
    elif isinstance(expr, javalang.tree.ArrayInitializer):
        elements = ", ".join(expr_to_str(e) for e in expr.initializers)
        return f"{{ {elements} }}"
    elif isinstance(expr, javalang.tree.ArrayCreator):
        type_str = type_to_str(expr.type)
        dims = "[]" * len(expr.dimensions) if expr.dimensions else ""
        initializer = ""
        if expr.initializer is not None:
            initializer = " " + expr_to_str(expr.initializer)
        return f"new {type_str}{dims}{initializer}"
    elif isinstance(expr, javalang.tree.ClassCreator):
        type_str = type_to_str(expr.type)
        args = ", ".join(expr_to_str(arg) for arg in expr.arguments)
        return f"new {type_str}({args})"
    elif isinstance(expr, javalang.tree.ClassReference):
        # Handle class literals like CronConverter.class
        return f"{type_to_str(expr.type)}.class"
    elif isinstance(expr, javalang.tree.BinaryOperation):
        left = expr_to_str(expr.operandl)
        right = expr_to_str(expr.operandr)
        return f"{left} {expr.operator} {right}"
    elif isinstance(expr, javalang.tree.TernaryExpression):
        cond = expr_to_str(expr.condition)
        if_true = expr_to_str(expr.if_true)
        if_false = expr_to_str(expr.if_false)
        return f"{cond} ? {if_true} : {if_false}"
    else:
        return str(expr)
    

def order_modifiers(modifiers):
    """
    Order modifiers according to conventional Java ordering.
    """
    order = ['public', 'protected', 'private', 'abstract', 'static', 'final',
             'transient', 'volatile', 'synchronized', 'native', 'strictfp']
    sorted_mods = sorted(modifiers, key=lambda x: order.index(x) if x in order else 100)
    return " ".join(sorted_mods)


def process_type(type_decl, indent=""):
    """
    Process a class or interface declaration (including inner types) and return its skeleton as a list of lines.
    """
    lines = []
    # Build the header line with modifiers, type keyword, name, type parameters,
    # and extends/implements clauses.
    modifiers = order_modifiers(type_decl.modifiers) + " " if type_decl.modifiers else ""
    type_keyword = "class" if isinstance(type_decl, javalang.tree.ClassDeclaration) else "interface"
    header = f"{indent}{modifiers}{type_keyword} {type_decl.name}"
    if hasattr(type_decl, 'type_parameters') and type_decl.type_parameters:
        tparams = ", ".join(tp.name for tp in type_decl.type_parameters)
        header += f"<{tparams}>"
    if isinstance(type_decl, javalang.tree.ClassDeclaration):
        if type_decl.extends is not None:
            header += " extends " + type_to_str(type_decl.extends)
        if type_decl.implements:
            header += " implements " + ", ".join(type_to_str(t) for t in type_decl.implements)
    elif isinstance(type_decl, javalang.tree.InterfaceDeclaration):
        if type_decl.extends:
            header += " extends " + ", ".join(type_to_str(t) for t in type_decl.extends)
    header += " {"
    lines.append(header)

    # Process fields
    for field in type_decl.fields:
        mod_field = order_modifiers(field.modifiers) + " " if field.modifiers else ""
        field_type = type_to_str(field.type)
        declarators = []
        for declarator in field.declarators:
            decl = declarator.name
            if declarator.initializer is not None:
                decl += " = " + expr_to_str(declarator.initializer)
            declarators.append(decl)
        decls_str = ", ".join(declarators)
        lines.append(f"{indent}    {mod_field}{field_type} {decls_str};")
    if type_decl.fields:
        lines.append("")

    # Process constructors (only for classes)
    if isinstance(type_decl, javalang.tree.ClassDeclaration):
        for constructor in type_decl.constructors:
            mod_ctor = order_modifiers(constructor.modifiers) + " " if constructor.modifiers else ""
            params = ", ".join(format_parameter(param) for param in constructor.parameters)
            lines.append(f"{indent}    {mod_ctor}{type_decl.name}({params})")

    # Process methods
    for method in type_decl.methods:
        mod_method = order_modifiers(method.modifiers) + " " if method.modifiers else ""
        return_type = type_to_str(method.return_type) if method.return_type else "void"
        params = ", ".join(format_parameter(param) for param in method.parameters)
        end_char = ";" if isinstance(type_decl, javalang.tree.InterfaceDeclaration) else ""
        lines.append(f"{indent}    {mod_method}{return_type} {method.name}({params}){end_char}")

    # Process inner types (if any) found in the body.
    if hasattr(type_decl, 'body'):
        for element in type_decl.body:
            if isinstance(element, (javalang.tree.ClassDeclaration, javalang.tree.InterfaceDeclaration)):
                lines.append("")  # add a blank line before inner type
                inner_lines = process_type(element, indent + "    ")
                lines.extend(inner_lines)

    lines.append(f"{indent}}}")
    return lines


# TODO: to fix a small bug in the case of "private final Map<Integer, List<CronParserField>> expressions = new HashMap<>();" where the function results in a wrong output "...new HashMap()"
def skeletonize_java_code(java_code):
    tree = javalang.parse.parse(java_code)
    lines = []
    # Package declaration
    if tree.package:
        lines.append(f"package {tree.package.name};\n")
    # Import declarations
    for imp in tree.imports:
        line = "import "
        if imp.static:
            line += "static "
        line += imp.path
        if imp.wildcard:
            line += ".*"
        line += ";"
        lines.append(line)
    if tree.imports:
        lines.append("")

    # Process each top-level type
    for type_decl in tree.types:
        type_lines = process_type(type_decl)
        lines.extend(type_lines)
        lines.append("")  # blank line between top-level types

    return "\n".join(lines)


def dataset_statistics(project_name):
    from dataset import Dataset
    from configs import Configs
    configs = Configs(project_name, 'deepseek-32B')
    dataset = Dataset(configs)
    print('Loading datasets...')
    coverage_data = dataset.load_coverage_data_jacoco()
    
    # test case length
    test_case_lengths = []
    for each_target_pair in coverage_data:
        full_test_case = each_target_pair.test_case
        test_case = remove_import_statements(full_test_case)
        test_case_lengths.append(len(test_case.split('\n')))

    # focal method length
    focal_method_lengths = []
    for each_target_pair in coverage_data:
        full_focal_method = each_target_pair.focal_method
        focal_method = remove_import_statements(full_focal_method)
        focal_method_lengths.append(len(focal_method.strip().split('\n')))
        if len(focal_method.split('\n')) == 3:
            print
    
    # show min, max, avg
    print(f"Project: {project_name}")
    print(f"Test case length: min={min(test_case_lengths)}, max={max(test_case_lengths)}, avg={sum(test_case_lengths)/len(test_case_lengths):.2f}")
    print(f"Focal method length: min={min(focal_method_lengths)}, max={max(focal_method_lengths)}, avg={sum(focal_method_lengths)/len(focal_method_lengths):.2f}")
    print()


def concatanate_generated_test_cases(paths: list):
    all_test_cases = []
    for path in paths:
        with open(path, 'r') as f:
            test_cases = json.load(f)
        all_test_cases.extend(test_cases)
    
    # check
    for idx, each in enumerate(all_test_cases):
        assert idx == each['target_coverage_idx']
    
    print(f"Total {len(all_test_cases)} test cases.")
    with open(paths[0] + '_Cat', 'w') as f:
        json.dump(all_test_cases, f, indent=4)
    return all_test_cases


def test_desc_len_statistic(project_name):
    from dataset import Dataset
    from configs import Configs

    configs = Configs(project_name, 'deepseek-32B')
    dataset = Dataset(configs)
    try:
        test_desc_data = dataset.load_test_desc(setting='full')
    except Exception as e:
        print(f"Failed to load test desc data. {e}")
        return
    
    ###
    # statistics for length
    ###
    obj_part, precondition_part, expected_result_part, pre_exp_sum_part, full_part = [], [], [], [], []  # for each part, record the length.
    for each_data in test_desc_data:
        each = each_data['test_desc']
        obj_part.append(len(each['Objective'].split()))
        precondition_part.append(len(each['Preconditions'].split()))
        expected_result_part.append(len(each['Expected Results'].split()))
        pre_exp_sum_part.append(len(each['Preconditions'].split()) + len(each['Expected Results'].split()))
        full_part.append(len(each['under_setting'].split()))

        if len(each['Preconditions'].split()) + len(each['Expected Results'].split()) > 200:
            print(f'Pre & Expected: {len(each['Preconditions'].split()) + len(each['Expected Results'].split())}')
            print(f"{project_name} sCoverage idx: {each_data['coverage_idx']}\n\n")
    
    print(f"====== Project: {project_name}: total {len(test_desc_data)} test cases ======")

    # for each part, show min, max, avg
    print(f"Objective part: min={min(obj_part)}, max={max(obj_part)}, avg={sum(obj_part)/len(obj_part):.2f}")
    print(f"Precondition part: min={min(precondition_part)}, max={max(precondition_part)}, avg={sum(precondition_part)/len(precondition_part):.2f}")
    print(f"Expected result part: min={min(expected_result_part)}, max={max(expected_result_part)}, avg={sum(expected_result_part)/len(expected_result_part):.2f}")
    print(f"Pre & Expected parts: min={min(pre_exp_sum_part)}, max={max(pre_exp_sum_part)}, avg={sum(pre_exp_sum_part)/len(pre_exp_sum_part):.2f}")
    print(f"Full part: min={min(full_part)}, max={max(full_part)}, avg={sum(full_part)/len(full_part):.2f}")    
    print()

    obj_info = [min(obj_part), max(obj_part), sum(obj_part)/len(obj_part)]
    pre_info = [min(precondition_part), max(precondition_part), sum(precondition_part)/len(precondition_part)]
    exp_info = [min(expected_result_part), max(expected_result_part), sum(expected_result_part)/len(expected_result_part)]
    pre_exp_info = [min(pre_exp_sum_part), max(pre_exp_sum_part), sum(pre_exp_sum_part)/len(pre_exp_sum_part)]
    full_info = [min(full_part), max(full_part), sum(full_part)/len(full_part)]

    return obj_info, pre_info, exp_info, pre_exp_info, full_info


def count_program_elements_ratio(test_desc, test_case):
    filter_list = ['The', 'Test', 'There', 'Tests', 'When', 'Not', 'This', 'Java', 'All', 'Both', 'Ensure', 'JUnit', 'String', 'Class', 'Verifies', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten']
        
    # extract the camel words in the test desc
    test_desc = test_desc.replace('# Objective', '').replace('# Preconditions', '').replace('# Expected Results', '')
    # process the first word of each line
    processed_test_desc = []
    test_desc_lines = test_desc.split('\n')
    for line in test_desc_lines:
        if len(line.strip()) == 0:
            processed_test_desc.append(line)
            continue

        words = line.split()
        if len(words[0]) > 1 and words[0][1] == '.':  # for the index i.e., 1. xxxx
            words[1] = words[1].lower()
        else:
            words[0] = words[0].lower()
        processed_test_desc.append(' '.join(words))
    test_desc = '\n'.join(processed_test_desc)


    element_test_desc = set(re.findall(r'\b(?=[A-Za-z]*[a-z])(?=[A-Za-z]*[A-Z])[A-Za-z]+\b', test_desc))
    element_test_desc = set(filter(lambda x: x not in filter_list, element_test_desc))
    # element_test_case_2 = set(re.findall(r'\b[A-Z]+\b', test_case))
    # element_test_desc = element_test_desc_1.union(element_test_case_2)


    # extract the camel words in the test case
    element_test_case = set(re.findall(r'\w+', test_case))

    # calculate the ratio of program elements in the test desc
    ratio = len(element_test_desc.intersection(element_test_case)) / len(element_test_case)
    return ratio, element_test_desc


def test_desc_program_ratio_statistic(project_name):
    from dataset import Dataset
    from configs import Configs

    configs = Configs(project_name, 'deepseek-32B')
    dataset = Dataset(configs)
    try:
        test_desc_data = dataset.load_test_desc(setting='full')
    except Exception as e:
        print(f"Failed to load test desc data. {e}")
        return
    
    ###
    # statistics for ratio of program elements
    ###
    obj_ratio_list, pre_ratio_list, exp_ratio_list, pre_exp_ratio_list, full_ratio_list = [], [], [], [], []
    for each in test_desc_data:
        test_case = each['target_test_case']

        obj_ratio, obj_element_test_desc = count_program_elements_ratio(each['test_desc']['Objective'], test_case)
        if obj_ratio > 0.1 and len(obj_element_test_desc) > 3:
            print(f'Ratio: {obj_ratio:.2f}')
            print(f'Coverage idx: {each['coverage_idx']}')

        pre_ratio, pre_element_test_desc = count_program_elements_ratio(each['test_desc']['Preconditions'], test_case)
        if pre_ratio > 0.1 and len(pre_element_test_desc) > 3:
            print(f'Ratio: {pre_ratio:.2f}')
            print(f'Coverage idx: {each['coverage_idx']}')

        exp_ratio, exp_element_test_desc = count_program_elements_ratio(each['test_desc']['Expected Results'], test_case)
        if exp_ratio > 0.1 and len(exp_element_test_desc) > 3:
            print(f'Ratio: {exp_ratio:.2f}')
            print(f'Coverage idx: {each['coverage_idx']}')

        pre_exp_ratio, pre_exp_element_test_desc = count_program_elements_ratio(each['test_desc']['Preconditions'] + '\n' + each['test_desc']['Expected Results'], test_case)
        if pre_exp_ratio > 0.1 and len(pre_exp_element_test_desc) > 3:
            print(f'Ratio: {pre_exp_ratio:.2f}')
            print(f'Coverage idx: {each['coverage_idx']}')

        full_ratio, full_element_test_desc = count_program_elements_ratio(each['test_desc']['under_setting'], test_case)
        if full_ratio > 0.1 and len(full_element_test_desc) > 3:
            print(f'Ratio: {full_ratio:.2f}')
            print(f'Coverage idx: {each['coverage_idx']}')

        obj_ratio_list.append(obj_ratio)
        pre_ratio_list.append(pre_ratio)
        exp_ratio_list.append(exp_ratio)
        pre_exp_ratio_list.append(pre_exp_ratio)
        full_ratio_list.append(full_ratio)
        
    obj_ratio_info = [min(obj_ratio_list), max(obj_ratio_list), sum(obj_ratio_list)/len(obj_ratio_list)]
    pre_ratio_info = [min(pre_ratio_list), max(pre_ratio_list), sum(pre_ratio_list)/len(pre_ratio_list)]
    exp_ratio_info = [min(exp_ratio_list), max(exp_ratio_list), sum(exp_ratio_list)/len(exp_ratio_list)]
    pre_exp_ratio_list = [min(pre_exp_ratio_list), max(pre_exp_ratio_list), sum(pre_exp_ratio_list)/len(pre_exp_ratio_list)]
    full_ratio_info = [min(full_ratio_list), max(full_ratio_list), sum(full_ratio_list)/len(full_ratio_list)]
    return obj_ratio_info, pre_ratio_info, exp_ratio_info, pre_exp_ratio_list, full_ratio_info


def analyze_facts(project_name):
    from dataset import Dataset
    from configs import Configs

    configs = Configs(project_name, 'deepseek-32B')
    dataset = Dataset(configs)

    max_depth = 3 if project_name == 'lambda' else 5
    golden_fact_path = ''  # Please specify the path to the golden fact file
    disc_fact_path = '' # Please specify the path to the discovered fact file
    all_test_case_info = dataset.load_coverage_data_jacoco()

    with open(golden_fact_path, 'r') as f:
        golden_facts = json.load(f)

    with open(disc_fact_path, 'r') as f:
        disc_facts = json.load(f)

    # count recall
    total_golden_facts_method, total_matched_facts_method, total_mismatched_facts_method = [], [], []
    total_recall_for_a_sample = []

    total_golden_facts_field, total_matched_facts_field, total_mismatched_facts_field = [], [], []  # TODO: this should be optimized, as the field facts in golden facts have different format compared to the field facts in disc facts.
    sample_idx_to_missing_facts_method = []
    sample_idx_to_matched_facts_method = []
    total_n_samples_have_facts = 0
    
    # golden fact from context
    sample_idx_to_golden_facts_context = []
    sample_idx_to_golden_facts_non_context = []

    for each_golden_info in golden_facts:
        coverage_idx = each_golden_info['target_coverage_idx']
        golden_facts = each_golden_info['golden_facts']

        if len(golden_facts) == 0:
            continue

        total_n_samples_have_facts += 1
        
        test_info = all_test_case_info[coverage_idx]
        assert test_info.focal_method_name == each_golden_info['focal_method_name']
        target_context = test_info.focal_file_skeleton

        ###
        # validate the golden facts, see whether the golden fact appear in the target_context
        ###
        focal_class_name = each_golden_info['focal_method_name'].split('::::')[0]
        golden_facts_context = []
        golden_facts_non_context = []
        for each_golden_fact in golden_facts:
            if 'Fields in' in each_golden_fact:
                field_class_name = each_golden_fact.split(':')[0].split()[-1]
                if field_class_name == focal_class_name:
                    golden_facts_context.append(each_golden_fact)
                    continue
            else:
                each_golden_fact_tokens = each_golden_fact.split()
                # find the test name token
                for idx, each_token in enumerate(each_golden_fact_tokens):
                    if '(' in each_token:
                        each_golden_fact_method_name_with_parameters = ' '.join(each_golden_fact_tokens[idx:])
                        break
                if each_golden_fact_method_name_with_parameters in target_context:
                    golden_facts_context.append(each_golden_fact)
                    continue
            
            golden_facts_non_context.append(each_golden_fact)
        
        if len(golden_facts_context) > 0:
            sample_idx_to_golden_facts_context.append((coverage_idx, golden_facts_context))
        
        if len(golden_facts_non_context) > 0:
            sample_idx_to_golden_facts_non_context.append((coverage_idx, golden_facts_non_context))

                
        ###
        # compare golden facts with disc facts
        ###
        disc_info = disc_facts[coverage_idx]
        assert disc_info['target_coverage_idx'] == coverage_idx
        assert each_golden_info['focal_method_name'] == disc_info['focal_method_name']

        disc_candidate_facts = []
        for each_candidate_fact_info in disc_info['candidate_facts']:
            disc_candidate_facts.append(each_candidate_fact_info[1].strip())
        disc_candidate_facts += disc_info['top_usages']

        disc_candidate_facts = disc_info['top_usages']
        
        each_golden_facts_method, each_golden_facts_field = [], []
        each_sample_missing_facts_method_total = []
        each_sample_missing_facts_method_context = []
        each_sample_missing_facts_method_non_context = []
        each_sample_matched_facts_method = []
        for each_golden_fact in golden_facts:
            if 'Fields in' in each_golden_fact:
                each_golden_facts_field.append(each_golden_fact)
                continue  # TODO consider fields
            
            each_golden_facts_method.append(each_golden_fact)
            each_golden_fact_name = each_golden_fact.split('(')[0].split()[-1].strip()
            for each_candidate_fact in disc_candidate_facts:
                if each_golden_fact_name in each_candidate_fact.strip():
                    each_sample_matched_facts_method.append(each_golden_fact)
                    break
            else:
                each_sample_missing_facts_method_total.append(each_golden_fact)
                if each_golden_fact in golden_facts_context:
                    each_sample_missing_facts_method_context.append(each_golden_fact)
                else:
                    each_sample_missing_facts_method_non_context.append(each_golden_fact)

        if len(each_sample_matched_facts_method) > 0:
            sample_idx_to_matched_facts_method.append((coverage_idx, each_sample_matched_facts_method))
            total_recall_for_a_sample.append(len(each_sample_matched_facts_method) / len(each_golden_facts_method))
        else:
            total_recall_for_a_sample.append(0)

        if len(each_sample_missing_facts_method_total) > 0:
            sample_idx_to_missing_facts_method.append((coverage_idx, each_sample_missing_facts_method_total, each_sample_missing_facts_method_context, each_sample_missing_facts_method_non_context))

        total_golden_facts_field.extend(each_golden_facts_field)
        total_golden_facts_method.extend(each_golden_facts_method)
        total_matched_facts_method.extend(each_sample_matched_facts_method)
        total_mismatched_facts_method.extend(each_sample_missing_facts_method_total)
    
    print(f'project: {project_name} | total samples: {len(all_test_case_info)}')
    print(f'Total golden facts (field): {len(set(total_golden_facts_field))}')
    print(f'Total golden facts (method): {len(set(total_golden_facts_method))}')
    print(f'Total matched facts (method): {len(set(total_matched_facts_method))}')
    print(f'Total mismatched facts (method): {len(set(total_mismatched_facts_method))}')
    print(f'{len(sample_idx_to_matched_facts_method)}/{total_n_samples_have_facts} samples have matched facts')
    print(f'{len(sample_idx_to_missing_facts_method)}/{total_n_samples_have_facts} samples have missing facts')
    print(f'{len(sample_idx_to_golden_facts_context)}/{total_n_samples_have_facts} samples have golden facts in context')
    print(f'{len(sample_idx_to_golden_facts_non_context)}/{total_n_samples_have_facts} samples have golden facts not in context')
    print(f'Total recall: {sum(total_recall_for_a_sample)/len(total_recall_for_a_sample):.2f}')
    print()
    
    return len(set(total_matched_facts_method)), len(sample_idx_to_golden_facts_non_context), total_recall_for_a_sample


def main():
    project_list = ["itext-java", "hutool", "yavi", "lambda", "truth", "jInstagram", "cron-utils", "imglib", "ofdrw", "RocketMQC", "blade", "spark", "awesome-algorithm"]
    # project_list = ["lambda",]

    # for project_name in project_list:
        # dataset_statistics(project_name)

    n_samples_have_matched_facts, n_samples_have_golden_facts_non_context = 0, 0
    recall_project_level_list = []
    recall_sample_level_list = []
    for project_name in project_list:
        ###
        n_matched_facts, n_golden_facts_non_context, total_recall_for_a_sample = analyze_facts(project_name)
        n_samples_have_matched_facts += n_matched_facts
        n_samples_have_golden_facts_non_context += n_golden_facts_non_context
        recall_project_level_list.append(sum(total_recall_for_a_sample)/len(total_recall_for_a_sample))
        recall_sample_level_list.extend(total_recall_for_a_sample)
        ###
    print(f"Total samples have matched facts / total samples have non-context facts: {n_samples_have_matched_facts}/{n_samples_have_golden_facts_non_context}")
    print(f"Project level recall: {sum(recall_project_level_list)/len(recall_project_level_list):.2f}")
    print(f"Sample level recall: {sum(recall_sample_level_list)/len(recall_sample_level_list):.2f}")

    ### Length statistics
    # obj_min, obj_max, obj_avg = [], [], []
    # pre_min, pre_max, pre_avg = [], [], []
    # exp_min, exp_max, exp_avg = [], [], []
    # pre_exp_min, pre_exp_max, pre_exp_avg = [], [], []
    # full_min, full_max, full_avg = [], [], []
    # ratio_min, ratio_max, ratio_avg = [], [], []
    # for project_name in project_list:
    #     obj_info, pre_info, exp_info, pre_exp_info, full_info = test_desc_len_statistic(project_name)
    #     obj_min.extend([obj_info[0]])
    #     obj_max.extend([obj_info[1]])
    #     obj_avg.extend([obj_info[2]])
    #     pre_min.extend([pre_info[0]])
    #     pre_max.extend([pre_info[1]])
    #     pre_avg.extend([pre_info[2]])
    #     exp_min.extend([exp_info[0]])
    #     exp_max.extend([exp_info[1]])
    #     exp_avg.extend([exp_info[2]])
    #     pre_exp_min.extend([pre_exp_info[0]])
    #     pre_exp_max.extend([pre_exp_info[1]])
    #     pre_exp_avg.extend([pre_exp_info[2]])
    #     full_min.extend([full_info[0]])
    #     full_max.extend([full_info[1]])
    #     full_avg.extend([full_info[2]])
        
    # print(f"Objective part: min={min(obj_min)}, max={max(obj_max)}, avg={sum(obj_avg)/len(obj_avg):.2f}")
    # print(f"Precondition part: min={min(pre_min)}, max={max(pre_max)}, avg={sum(pre_avg)/len(pre_avg):.2f}")
    # print(f"Expected result part: min={min(exp_min)}, max={max(exp_max)}, avg={sum(exp_avg)/len(exp_avg):.2f}")
    # print(f"Pre & Expected parts: min={min(pre_exp_min)}, max={max(pre_exp_max)}, avg={sum(pre_exp_avg)/len(pre_exp_avg):.2f}")
    # print(f"Full part: min={min(full_min)}, max={max(full_max)}, avg={sum(full_avg)/len(full_avg):.2f}")

    ### Ratio statistics
    obj_ratio_min, obj_ratio_max, obj_ratio_avg = [], [], []
    pre_ratio_min, pre_ratio_max, pre_ratio_avg = [], [], []
    exp_ratio_min, exp_ratio_max, exp_ratio_avg = [], [], []
    pre_exp_ratio_min, pre_exp_ratio_max, pre_exp_ratio_avg = [], [], []
    full_ratio_min, full_ratio_max, full_ratio_avg = [], [], []

    for project_name in project_list:
        obj_ratio_info, pre_ratio_info, exp_ratio_info, pre_exp_ratio_list, full_ratio_info = test_desc_program_ratio_statistic(project_name)
        obj_ratio_min.extend([obj_ratio_info[0]])
        obj_ratio_max.extend([obj_ratio_info[1]])
        obj_ratio_avg.extend([obj_ratio_info[2]])
        pre_ratio_min.extend([pre_ratio_info[0]])
        pre_ratio_max.extend([pre_ratio_info[1]])
        pre_ratio_avg.extend([pre_ratio_info[2]])
        exp_ratio_min.extend([exp_ratio_info[0]])
        exp_ratio_max.extend([exp_ratio_info[1]])
        exp_ratio_avg.extend([exp_ratio_info[2]])
        pre_exp_ratio_min.append(pre_exp_ratio_list[0])
        pre_exp_ratio_max.append(pre_exp_ratio_list[1])
        pre_exp_ratio_avg.append(pre_exp_ratio_list[2])
        full_ratio_min.extend([full_ratio_info[0]])
        full_ratio_max.extend([full_ratio_info[1]])
        full_ratio_avg.extend([full_ratio_info[2]])

    print(f"Objective part: min={min(obj_ratio_min)}, max={max(obj_ratio_max)}, avg={sum(obj_ratio_avg)/len(obj_ratio_avg):.2f}")
    print(f"Precondition part: min={min(pre_ratio_min)}, max={max(pre_ratio_max)}, avg={sum(pre_ratio_avg)/len(pre_ratio_avg):.2f}")
    print(f"Expected result part: min={min(exp_ratio_min)}, max={max(exp_ratio_max)}, avg={sum(exp_ratio_avg)/len(exp_ratio_avg):.2f}")
    print(f"Pre & Expected parts: min={min(pre_exp_ratio_list)}, max={max(pre_exp_ratio_list)}, avg={sum(pre_exp_ratio_list)/len(pre_exp_ratio_list):.2f}")
    print(f"Full part: min={min(full_ratio_min)}, max={max(full_ratio_max)}, avg={sum(full_ratio_avg)/len(full_ratio_avg):.2f}")

if __name__ == "__main__":
    main()
