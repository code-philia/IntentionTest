import utils
import os
import pandas as pd
import subprocess
import json
import sys

# Successful tests are stored in successful_tests.csv with no header
set_successful = set() if not os.path.exists("successful_tests.csv") else set(pd.read_csv("successful_tests.csv", header=None)[0])

blacklisted_files = set() if not os.path.exists("blacklisted_files.csv") else set(pd.read_csv("blacklisted_files.csv", header=None)[0])

def process_json(json_file):
    data = utils.get_json(json_file)
    for focal_file, temp in data.items():
        test_path = utils.generate_test_location(focal_file)
        ori_test_path = test_path.replace("/bernard/dataset_construction/human_written_tests/test_analysis/repos/", "/bernard/dataset_construction/prep/repos/")
        test_location = '/'.join(test_path.split("/")[:-1])
        repo_root = test_location.split("/src/test/java")[0]
        test_root = repo_root + "/src/test/java"

        for focal_method, tests in temp.items():
            for i, test_details in enumerate(tests):
                name, test, coverage, context = test_details

                if focal_file + "####" + focal_method + "####" + name in set_successful or focal_file in blacklisted_files:
                    # print("Skipping test: ", focal_file + "####" + focal_method + "####" + name)
                    continue
                
                # read the content of test_path as list of lines
                with open(test_path) as f:
                    test_content = f.readlines()

                # verify that it's different from test
                if test_content != test:
                    # Run the test using mvn clean test
                    mvn_args = ["mvn", "test"]

                    # Run the test
                    result = subprocess.run(mvn_args, cwd=repo_root)

                    # Get the status (whether it is successful or not)
                    status = result.returncode

                    if status == 0:
                        # test content is the new test. update the json file
                        temp[focal_method][i] = [name, test_content, coverage, context]
                        with open(json_file, 'w') as f:
                            json.dump(data, f, indent=4)

                        add_to_set = focal_file + "####" + focal_method + "####" + name
                        set_successful.add(add_to_set)
                        print("Successful test: ", add_to_set)
                        pd.DataFrame(list(set_successful)).to_csv("successful_tests.csv", header=None, index=None)
                        exit(0)
                    else:
                        print("Test still fails")
                        # exit with exitcode 1
                        exit(1)
                else:
                    print("Test hasn't changed")
                    # exit with exitcode 1
                    exit(1)

                # verify that it's different from test
                # if content != ''.join(test):
                #     with open(test_path, 'w') as f:
                #         f.write(''.join(test))
                #     print("Updated test: ", focal_file + "####" + focal_method + "####" + name)
                #     # if test_path exists, delete it
                #     if os.path.exists(test_path):
                #         os.remove(test_path)
                #     main.clean_test_folder(test_root)
                #     continue


if __name__ == "__main__":
    path = sys.argv[1]
    process_json(path)