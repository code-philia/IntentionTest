import os
import utils_v3 as utils
import json
import sys

json_path = "after_files_copy.json"

json_w_coverage = "after_files_w_coverage.json"

full_dataset = {}

if os.path.exists(json_w_coverage):
    with open(json_w_coverage, "r") as f:
        full_dataset = json.load(f)

with open(json_path, "r") as f:
    after_files = json.load(f)

file_specific_cache = {}

org_name = "com"
test_suffix = "Test"

start_from = 0

for i, after_file in enumerate(after_files):
    if i < start_from:
        continue
    print(f"Processing file {i + 1}/{len(after_files)}")

    full_test_path = after_file["full_test_path"]
    src_file_path = after_file["src_file_path"]

    if "itext-java/sign" in src_file_path:
        print("Skipping due to weird errors")
        continue

    test_method_name_target = after_file["method_name"]

    class_name = src_file_path.split("/")[-1][:-5]
    class_path = src_file_path

    # path is class_path before src/main/java
    path = class_path.split("/src/main/java")[0]

    if class_path not in file_specific_cache:
        file_specific_cache[class_path] = {}
    
    if "class_content" not in file_specific_cache[class_path]:
        with open(class_path) as f:
            file_specific_cache[class_path]["class_content"] = f.readlines()
    
    class_content = file_specific_cache[class_path]["class_content"]

    test_class_name = full_test_path.split("/")[-1][:-5]
    test_path = full_test_path

    if "test_content" not in file_specific_cache[class_path]:
        with open(test_path) as f:
            file_specific_cache[class_path]["test_content"] = f.readlines()

    test_content = file_specific_cache[class_path]["test_content"]

    test_class_name_formatted = class_path.split('/src/main/java/' + org_name + '/')[1][:-5].replace("/", ".") + test_suffix

    str_method_tuples = [
        ("test_method_lines_dic", lambda : utils.get_method_lines(test_path)[0]),
        ("test_reverse_method_lines_dic", lambda : utils.get_method_lines(test_path)[1]),
        ("foc_method_lines_dic", lambda : utils.get_method_lines(class_path)[0]),
        ("foc_reverse_method_lines_dic", lambda : utils.get_method_lines(class_path)[1]),
        ("foc_calls_map", lambda : utils.get_method_calls_map(class_path)),
        ("test_calls_map", lambda : utils.get_method_calls_map(test_path)),
        ("cross_calls_map", lambda : utils.get_method_calls_cross_map(test_path)),
        ("unused_classes_lines", lambda : utils.get_unused_classes_lines(class_path)),
        ("unused_classes_test_lines", lambda : utils.get_unused_classes_lines(test_path))
    ]

    for method_name, method in str_method_tuples:
        if method_name not in file_specific_cache[class_path]:
            file_specific_cache[class_path][method_name] = method()
    
    test_method_lines_dic = file_specific_cache[class_path]["test_method_lines_dic"]
    test_reverse_method_lines_dic = file_specific_cache[class_path]["test_reverse_method_lines_dic"]
    foc_method_lines_dic = file_specific_cache[class_path]["foc_method_lines_dic"]
    foc_reverse_method_lines_dic = file_specific_cache[class_path]["foc_reverse_method_lines_dic"]
    foc_calls_map = file_specific_cache[class_path]["foc_calls_map"]
    test_calls_map = file_specific_cache[class_path]["test_calls_map"]
    cross_calls_map = file_specific_cache[class_path]["cross_calls_map"]
    unused_classes_lines = file_specific_cache[class_path]["unused_classes_lines"]
    unused_classes_test_lines = file_specific_cache[class_path]["unused_classes_test_lines"]

    for test_method_name_full, (starting_line, ending_line) in test_method_lines_dic.items():
        if test_method_name_target not in test_method_name_full:
            continue
        test_method_name = test_method_name_full.split("(")[0]

        jacoco_path = utils.get_jacoco_report(path, test_class_name_formatted, test_method_name[test_method_name.index("::::") + 4:], org_name, test_suffix)
        print(jacoco_path)

        if not os.path.exists(jacoco_path):
            print("Jacoco path does not exist")
            exit()
            continue

        cov_lines, uncov_lines = utils.get_lines_coverage(jacoco_path)
        print(cov_lines, uncov_lines)

        if class_path not in full_dataset:
            full_dataset[class_path] = {}

        '''
        Structure of the json
        {
            class_path: {
                "class_content": [],
                "test_content": [],
                "method_lines_dic": foc_method_lines_dic,
                "test_method_lines_dic": test_method_lines_dic,
                "reverse_method_lines_dic": foc_reverse_method_lines_dic,
                "test_reverse_method_lines_dic": test_reverse_method_lines_dic,
                "tests": [
                    {
                        "line": [starting_line, ending_line],
                        "covered_lines": [],
                        "test_method_name": test_method_name_full
                    },
                    ...
                ]
            }
        }
        '''

        if len(cov_lines) == 0:
            continue
        
        if "class_content" not in full_dataset[class_path]:
            full_dataset[class_path]["class_content"] = class_content

        if "test_content" not in full_dataset[class_path]:
            full_dataset[class_path]["test_content"] = test_content

        if "method_lines_dic" not in full_dataset[class_path]:
            full_dataset[class_path]["method_lines_dic"] = foc_method_lines_dic
        
        if "test_method_lines_dic" not in full_dataset[class_path]:
            full_dataset[class_path]["test_method_lines_dic"] = test_method_lines_dic
        
        if "reverse_method_lines_dic" not in full_dataset[class_path]:
            full_dataset[class_path]["reverse_method_lines_dic"] = foc_reverse_method_lines_dic

        if "test_reverse_method_lines_dic" not in full_dataset[class_path]:
            full_dataset[class_path]["test_reverse_method_lines_dic"] = test_reverse_method_lines_dic

        if "tests" not in full_dataset[class_path]:
            full_dataset[class_path]["tests"] = []

        full_dataset[class_path]["tests"].append({
            "test_lines": [starting_line, ending_line],
            "covered_lines": cov_lines
        })

        # print(full_dataset)

        with open(json_w_coverage, 'w') as f:
            json.dump(full_dataset, f)
