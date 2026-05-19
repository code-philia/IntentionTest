import utils
import os
import json

# for every json file in /bernard/dataset_construction/human_written_tests/v2/dataset_reorganised_new
for root, dirs, files in os.walk('/bernard/dataset_construction/human_written_tests/v2/dataset_reorganised_new'):
    for file in files:
        json_file_path = root + '/' + file

        # print("Currently processing: " + json_file_path)
        if not file.endswith('.json'):
            continue

        # load the json file
        with open(json_file_path, 'r') as f:
            full_dataset = json.load(f)

        # for every class in the json
        for foc_file_path, temp_dic in full_dataset.items():
            for foc_method_name_raw, tests in temp_dic.items():
                for k, test_detail in enumerate(tests):
                    test, foc_method, context = test_detail

                    foc_method_name = ""

                    for line in foc_method:
                        if "(" in line:
                            foc_method_name = line.split("(")[0].split()[-1]
                            if not foc_method_name.startswith("@"):
                                break

                    test_method_name = ""

                    test_method_name_ls = []

                    i = 0
                    while i < len(test):
                        if "@Test" in test[i]:
                            while "(" not in test[i] or ("public" not in test[i] and "void" not in test[i]):
                                i += 1
                            test_method_name = test[i].split("(")[0].split()[-1]
                            test_method_name_ls.append(test_method_name)
                        i += 1
                    
                    if len(test_method_name) == 0:
                        i = 0
                        while i < len(test):
                            if "public void" in test[i]:
                                test_method_name = test[i].split("(")[0].split()[-1]
                                test_method_name_ls.append(test_method_name)
                                break
                            i += 1

                    final_test_method_name = ""

                    for test_method_name in test_method_name_ls:
                        if foc_method_name.lower() in test_method_name.lower():
                            final_test_method_name = test_method_name
                            break

                    if final_test_method_name == "":
                        print("ERRORRRRRRRRRRRRRRRRRR: " + foc_method_name + " " + test_method_name)
                        print(foc_file_path, foc_method_name_raw)
                        
                        exit()

                    new_test_detail = [final_test_method_name, test, foc_method, context]

                    tests[k] = new_test_detail

        # save the json file
        with open(json_file_path, 'w') as f:
            json.dump(full_dataset, f, indent=4)
                    