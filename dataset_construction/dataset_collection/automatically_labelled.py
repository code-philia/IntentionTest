import os
import utils
import json
import sys

# Example usage:
# path = "/bernard/dataset_construction/prep/repos/blade/blade-kit"
# org_name = "com"
# test_suffix = "Test"

path = sys.argv[1]
org_name = sys.argv[2]
test_suffix = sys.argv[3]

repo_name = path.split("/")[-1]

full_dataset = {}

# use os.walk to walk through the files in path + /src/main/java
for root, dirs, files in os.walk(path + '/src/main/java'):
    # before_src = root[:-1 * len('src/main/java') - 1]
    before_src = path
    path_to_json = '/'.join(before_src.split('/')[:-1]).replace('prep/repos', 'human_written_tests/v2/dataset_reorganised')
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
        old_foc_method_lines_dic, old_foc_reverse_method_lines_dic = utils.get_method_lines(class_path, False)

        foc_calls_map = utils.get_method_calls_map(class_path)
        test_calls_map = utils.get_method_calls_map(test_path)
        cross_calls_map = utils.get_method_calls_cross_map(test_path)

        # Get all methods within the focal class
        possible_focal_methods = list(old_foc_method_lines_dic.keys())

        # sort possible_focal_methods from the longest to the shortest
        possible_focal_methods.sort(key=lambda x: len(x), reverse=True)

        unused_classes_lines = utils.get_unused_classes_lines(class_path)
        unused_classes_test_lines = utils.get_unused_classes_lines(test_path)

        for test_method_name_full, (starting_line, ending_line) in test_method_lines_dic.items():
            if test_method_name_full not in cross_calls_map:
                continue
            test_method_name = test_method_name_full.split("(")[0]

            expected_focal_method_name = utils.get_expected_focal_method_name(test_method_name, possible_focal_methods)

            if expected_focal_method_name == "":
                continue

            jacoco_path = utils.get_jacoco_report(path, test_class_name_formatted, test_method_name[test_method_name.index("::::") + 4:], org_name, test_suffix)

            if not os.path.exists(jacoco_path):
                continue

            cov_lines, uncov_lines = utils.get_lines_coverage(jacoco_path)
            print(cov_lines, uncov_lines)

            # make a copy of class_content
            class_content_copy = class_content.copy()
            # tag all covered lines with <COVER>
            for line in cov_lines:
                if class_content_copy[line - 1].strip() != '}':
                    class_content_copy[line - 1] = "<COVER>" + class_content_copy[line - 1]

            called_methods = cross_calls_map[test_method_name_full]
            focal_method_full = ""
            for called_method in called_methods:
                if called_method.split("(")[0] == expected_focal_method_name:
                    foc_start, foc_end = foc_method_lines_dic[called_method]
                    for i in range(foc_start, foc_end + 1):
                        if i in cov_lines:
                            focal_method_full = called_method
                            break

            if focal_method_full == "":
                continue

            if focal_method_full not in foc_calls_map or test_method_name_full not in test_calls_map:
                continue

            irrelevant_methods = utils.get_irrelevant_methods(foc_calls_map, focal_method_full)

            comment_lines = utils.get_comment_lines(class_path)
            unused_classes_lines_specific = unused_classes_lines[focal_method_full]

            sanitised_class_content = utils.annotate_deleted_classes(class_content, unused_classes_lines_specific)
            sanitised_class_content = utils.delete_irrelevant_methods_and_comments(sanitised_class_content, irrelevant_methods, foc_method_lines_dic, comment_lines)
            sanitised_class_content = utils.delete_consecutive_empty_lines(sanitised_class_content)

            irrelevant_methods_test = utils.get_irrelevant_methods(test_calls_map, test_method_name_full)

            comment_lines_test = utils.get_comment_lines(test_path)
            unused_classes_lines_specific_test = unused_classes_test_lines[test_method_name_full]

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
                sanitised_test_content,
                focal_method_annotated_full,
                sanitised_class_content
            ])

            # if path_to_json does not exist, create it first
            if not os.path.exists(path_to_json):
                os.makedirs(path_to_json)

            print(complete_path_to_json)

            with open(complete_path_to_json, 'w') as f:
                json.dump(full_dataset, f)


