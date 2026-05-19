import os
import utils
import json
import sys

def process_data(focal_file_path, dic, full_dataset, complete_path_to_json_before):
    print(focal_file_path)

    # if focal_file_path != "/bernard/dataset_construction/prep/repos/lambda/src/main/java/com/jnape/palatable/lambda/functor/builtin/Identity.java":
    #     return
    # keys of dic
    # ['class_content', 'test_content', 
    # 'method_lines_dic', 'test_method_lines_dic', 
    # 'reverse_method_lines_dic', 'test_reverse_method_lines_dic', 
    # 'tests']

    complete_path_to_json = complete_path_to_json_before.replace('labelled_data', 'postprocessed_2')
    path_to_dir = '/'.join(complete_path_to_json.split('/')[:-1])

    tests = dic['tests']
    class_content = dic['class_content']
    test_reverse_method_lines_dic = dic['test_reverse_method_lines_dic']
    foc_method_lines_dic = dic['method_lines_dic']
    test_method_lines_dic = dic['test_method_lines_dic']

    test_content = dic['test_content']

    class_path = focal_file_path
    test_path = focal_file_path.replace('src/main/java', 'src/test/java')[:-5] + 'Test.java'

    foc_calls_map = utils.get_method_calls_map(class_path)
    test_calls_map = utils.get_method_calls_map(test_path)

    if foc_calls_map == {} or test_calls_map == {}:
        return

    unused_classes_lines = utils.get_unused_classes_lines(class_path)
    unused_classes_test_lines = utils.get_unused_classes_lines(test_path)
    
    # for each test in tests
    for test in tests:
        # keys of test
        # ['test_lines', 'covered_lines', 'label']
        if 'label' not in test:
            continue

        label = test['label']
        if label.startswith("<<"):
            continue

        test_lines = test['test_lines']

        test_method_name_full = test_reverse_method_lines_dic[str(test_lines[0])]

        cov_lines = test['covered_lines']
        class_content_copy = class_content.copy()

        # tag all covered lines with <COVER>
        for line in cov_lines:
            if class_content_copy[line - 1].strip() != '}':
                class_content_copy[line - 1] = "<COVER>" + class_content_copy[line - 1]

        focal_method_full = label

        irrelevant_methods = utils.get_irrelevant_methods(foc_calls_map, focal_method_full)

        comment_lines = utils.get_comment_lines(class_path)
        unused_classes_lines_specific = unused_classes_lines[focal_method_full]

        sanitised_class_content = utils.annotate_deleted_classes(class_content, unused_classes_lines_specific)
        sanitised_class_content = utils.delete_irrelevant_methods_and_comments(sanitised_class_content, irrelevant_methods, foc_method_lines_dic, comment_lines)
        sanitised_class_content = utils.delete_consecutive_empty_lines(sanitised_class_content)

        irrelevant_methods_test = utils.get_irrelevant_methods(test_calls_map, test_method_name_full)

        comment_lines_test = utils.get_comment_lines(test_path)
        unused_classes_lines_specific_test = unused_classes_test_lines[test_method_name_full] if test_method_name_full in unused_classes_test_lines else []

        sanitised_test_content = utils.annotate_deleted_classes(test_content, unused_classes_lines_specific_test)
        sanitised_test_content = utils.delete_irrelevant_methods_and_comments(sanitised_test_content, irrelevant_methods_test, test_method_lines_dic, comment_lines_test, True)
        sanitised_test_content = utils.delete_consecutive_empty_lines(sanitised_test_content)

        focal_start, focal_end = foc_method_lines_dic[focal_method_full]
        
        focal_method_annotated_full = class_content_copy[focal_start - 1:focal_end]

        print(''.join(sanitised_class_content))
        print('-------')
        print(''.join(sanitised_test_content))
        print('--------')
        print(''.join(focal_method_annotated_full))
        print('--------')

        if class_path not in full_dataset:
            full_dataset[class_path] = {}

        if focal_method_full not in full_dataset[class_path]:
            full_dataset[class_path][focal_method_full] = []

        full_dataset[class_path][focal_method_full].append([
            test_method_name_full,
            sanitised_test_content,
            focal_method_annotated_full,
            sanitised_class_content
        ])

        # if path_to_json does not exist, create it first
        if not os.path.exists(path_to_dir):
            os.makedirs(path_to_dir)
        with open(complete_path_to_json, 'w') as f:
            json.dump(full_dataset, f)

# for all jsons inside /bernard/dataset_construction/human_written_tests/v3/labelled_data
for root, dirs, files in os.walk('/bernard/dataset_construction/human_written_tests/v3/labelled_data'):
    for file in files:
        print("Currently processing: " + file)
        if not file.endswith('.json'):
            continue

        json_file_path = root + '/' + file

        if json_file_path != "/bernard/dataset_construction/human_written_tests/v3/labelled_data/after_files_w_coverage_full.json":
            continue

        with open(json_file_path) as f:
            data = json.load(f)

        full_dataset = {}

        complete_path_to_json = json_file_path.replace('labelled_data', 'postprocessed_2')
        
        for focal_file_path, dic in data.items():
            process_data(focal_file_path, dic, full_dataset, json_file_path)