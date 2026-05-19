import os
import utils
import json
import sys

path = sys.argv[1]
org_name = sys.argv[2]
test_suffix = sys.argv[3]

repo_name = path.split("/")[-1]

full_dataset = {}

for root, dirs, files in os.walk(path + '/src/main/java'):
    before_src = path
    path_to_json = '/'.join(before_src.split('/')[:-1]).replace('prep/repos', 'human_written_tests/v3/dataset_reorganised')
    supposed_json_file_name = before_src.split('/')[-1] + '.json'

    complete_path_to_json = '/'.join([path_to_json] + [supposed_json_file_name])

    for k, file in enumerate(files):
        if not file.endswith('.java'):
            continue
            
        # class_name e.g.: CollectionUtils
        class_name = file[:-5]
        # class_path e.g.: /bernard/dataset_construction/prep/repos/spark/src/main/java/spark/utils/CollectionUtils.java
        class_path = root + '/' + file
        # read the content as list of lines
        # class_content e.g.: content of CollectionUtils.java
        with open(class_path) as f:
            class_content = f.readlines()

        # test_class_name e.g.: CollectionUtilsTest.java
        test_class_name = class_name + test_suffix + '.java'

        # test_path e.g.: /bernard/dataset_construction/prep/repos/spark/src/test/java/spark/utils/CollectionUtilsTest.java
        test_path = path + '/src/test/java/' + class_path.split('/src/main/java/')[1][:-5] + test_suffix + '.java'
        # read the content as list of lines
        # test_content e.g.: content of CollectionUtilsTest.java
        if not os.path.exists(test_path):
            continue
        with open(test_path) as f:
            test_content = f.readlines()

        # test_class_name_formatted e.g.: utils.CollectionUtilsTest
        test_class_name_formatted = class_path.split('/src/main/java/' + org_name + '/')[1][:-5].replace("/", ".") + test_suffix

        # get all methods within the test
        test_method_lines_dic, test_reverse_method_lines_dic = utils.get_method_lines(test_path)

        # get all methods within the focal class
        foc_method_lines_dic, foc_reverse_method_lines_dic = utils.get_method_lines(class_path)

        foc_calls_map = utils.get_method_calls_map(class_path)
        test_calls_map = utils.get_method_calls_map(test_path)

        unused_classes_lines = utils.get_unused_classes_lines(class_path)
        unused_classes_test_lines = utils.get_unused_classes_lines(test_path)

        for test_method_name_full, (starting_line, ending_line) in test_method_lines_dic.items():
            test_method_name = test_method_name_full.split("(")[0]

            jacoco_path = utils.get_jacoco_report(path, test_class_name_formatted, test_method_name[test_method_name.index("::::") + 4:], org_name, test_suffix)
            # print(jacoco_path)
            # exit()

            if not os.path.exists(jacoco_path):
                print("yeboi")
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

            # if path_to_json does not exist, create it first
            if not os.path.exists(path_to_json):
                os.makedirs(path_to_json)

            print(complete_path_to_json)

            with open(complete_path_to_json, 'w') as f:
                json.dump(full_dataset, f)


