import json
import os
import subprocess
import pandas as pd
import utils
import javalang
import move_resources

# Successful tests are stored in successful_tests.csv with no header
set_successful = set() if not os.path.exists("successful_tests.csv") else set(pd.read_csv("successful_tests.csv", header=None)[0])

blacklisted_files = set() if not os.path.exists("blacklisted_files.csv") else set(pd.read_csv("blacklisted_files.csv", header=None)[0])

def try_adding_before_each(ori_test_path, test_path, test_content):
    # read ori content as ls of lines
    with open(ori_test_path, 'r') as f:
        ori_content = f.readlines()

    method_lines_dic, reverse_method_lines_dic = utils.get_method_lines(ori_test_path)

    added_lines = []

    for method_name, lines in method_lines_dic.items():
        start, end = lines
        if "@BeforeEach" in ori_content[start - 1] or "@Before" in ori_content[start - 1]:
            added_lines = ori_content[start - 1 : end]
            break
    
    if added_lines == []:
        return 1

    # insert the added lines to the test_content on lines before the @Test or @ParameterizedTest
    for i, line in enumerate(test_content):
        if "@Test" in line or "@ParameterizedTest" in line:
            test_content = test_content[:i] + added_lines + ["\n"] + test_content[i:]

    with open(test_path, 'w') as f:
        f.write(''.join(test_content))
    
    return 0

def try_adding_specific_lines(test_path, test_content, added_lines):
    # insert the added lines right before the last }
    # this necessitates traversal from the end of the file
    i = len(test_content) - 1
    while i >= 0:
        if "}" in test_content[i]:
            test_content = test_content[:i] + added_lines + ["\n"] + test_content[i:]
            break
        i -= 1
    
    if i == -1:
        return 1
    
    with open(test_path, 'w') as f:
        f.write(''.join(test_content)
    )
        
    return 0

def process_json(json_file):
    data = utils.get_json(json_file)
    # take the first focal_file
    first_focal_file = list(data.keys())[0]
    # generate the test_root
    test_path = utils.generate_test_location(first_focal_file)
    ori_test_path = test_path.replace("/bernard/dataset_construction/human_written_tests/test_analysis/repos/", "/bernard/dataset_construction/prep/repos/")
    test_location = '/'.join(test_path.split("/")[:-1])
    repo_root = test_location.split("/src/test/java")[0]
    test_root_wo_java = repo_root + "/src/test/"

    move_resources.move_resources(test_root_wo_java)

    print(test_root_wo_java)

    for focal_file, temp in data.items():
        if focal_file in blacklisted_files:
            print("Skipping focal file: ", focal_file)
            continue
        test_path = utils.generate_test_location(focal_file)
        ori_test_path = test_path.replace("/bernard/dataset_construction/human_written_tests/test_analysis/repos/", "/bernard/dataset_construction/prep/repos/")
        test_location = '/'.join(test_path.split("/")[:-1])
        repo_root = test_location.split("/src/test/java")[0]
        test_root = repo_root + "/src/test/java"

        for focal_method, tests in temp.items():
            for test_details in tests:
                name, test, coverage, context = test_details

                if focal_file + "####" + focal_method + "####" + name in set_successful or focal_file in blacklisted_files:
                    print("Skipping test: ", focal_file + "####" + focal_method + "####" + name)
                    # if test_path exists, delete it
                    if os.path.exists(test_path):
                        os.remove(test_path)
                    utils.clean_test_folder(test_root)
                    continue

                # delete the whole test_location first
                utils.clean_test_folder(test_root)

                if not os.path.exists(test_location):
                    os.makedirs(test_location)

                with open(test_path, 'w') as f:
                    f.write(''.join(test))
                
                # Run the test using mvn clean test
                # mvn_args = ["mvn", "clean", "test"]
                mvn_args = ["mvn", "test"]

                print(mvn_args, " in ", repo_root)

                # Run the test
                result = subprocess.run(mvn_args, cwd=repo_root)

                # Get the status (whether it is successful or not)
                status = result.returncode

                if status == 0:
                    add_to_set = focal_file + "####" + focal_method + "####" + name
                    set_successful.add(add_to_set)
                    print("Successful test: ", add_to_set)
                    pd.DataFrame(list(set_successful)).to_csv("successful_tests.csv", header=None, index=None)
                    # if test_path exists, delete it
                    if os.path.exists(test_path):
                        os.remove(test_path)

                    utils.clean_test_folder(test_root)    
                else:
                    # print("Failed test:")
                    # print("Focal file: ", focal_file)
                    # print("Focal method: ", focal_method)
                    # print("Test name: ", name)
                    # args = ["code", "-r", ori_test_path]
                    # subprocess.run(args)
                    # args = ["code", "-r", test_path]
                    # subprocess.run(args)
                    # exit()

                    print("Trying to add @BeforeEach")
                    
                    ret_code = try_adding_before_each(ori_test_path, test_path, test)

                    if ret_code == 1:
                        print(len(tests))
                        print("Failed test:")
                        print("Focal file: ", focal_file)
                        print("Focal method: ", focal_method)
                        print("Test name: ", name)

                        args = ["code", "-r", ori_test_path]
                        subprocess.run(args)
                        args = ["code", "-r", test_path]
                        subprocess.run(args)

                        exit()
                    
                    args = ["python", "update_dataset.py", json_file]

                    res = subprocess.run(args)

                    if res.returncode == 0:
                        add_to_set = focal_file + "####" + focal_method + "####" + name
                        set_successful.add(add_to_set)

                        # if test_path exists, delete it
                        if os.path.exists(test_path):
                            os.remove(test_path)

                        utils.clean_test_folder(test_root)  
                    else:
                        print(len(tests))
                        print("Failed test:")
                        print("Focal file: ", focal_file)
                        print("Focal method: ", focal_method)
                        print("Test name: ", name)

                        args = ["code", "-r", ori_test_path]
                        subprocess.run(args)
                        args = ["code", "-r", test_path]
                        subprocess.run(args)

                        exit()

                        # print("Failed test:")
                        # print("Focal file: ", focal_file)
                        # print("Focal method: ", focal_method)
                        # print("Test name: ", name)

                        # args = ["code", "-r", ori_test_path]
                        # subprocess.run(args)
                        # args = ["code", "-r", test_path]
                        # subprocess.run(args)

                        # exit()

# process_json("/bernard/dataset_construction/human_written_tests/test_analysis/dataset/blade/imglib.json")

dataset_repo_root = "/bernard/dataset_construction/human_written_tests/test_analysis/dataset/ofdrw"

for json_file in os.listdir(dataset_repo_root):
    if json_file.endswith(".json"):
        process_json(os.path.join(dataset_repo_root, json_file))