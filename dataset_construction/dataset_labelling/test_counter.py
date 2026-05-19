import os 
import json

# For every dir in ./api/dataset_reorganised
for dir in os.listdir('./api/dataset_reorganised'):
    if not os.path.isdir('./api/dataset_reorganised/' + dir) and dir.endswith('json'):
        total_tests = 0
        labelled_tests = 0
        no_focal = 0
        unrecognised = 0

        file = dir
        json_content = json.load(open('./api/dataset_reorganised/' + file))

        for path in json_content:
            temp = json_content[path]
            if 'tests' not in temp:
                continue
            for test in temp['tests']:
                total_tests += 1
                if 'label' in test:
                    labelled_tests += 1
                    if test['label'] == "<<NO FOCAL METHOD>>":
                        no_focal += 1
                    elif test['label'] == "<<UNRECOGNISED_METHOD>>":
                        unrecognised += 1

        print(f"Total tests in {dir}: {total_tests}")
        print(f"Labelled tests in {dir}: {labelled_tests}")
        print(f"No focal method in {dir}: {no_focal}")
        print(f"Unrecognised method in {dir}: {unrecognised}")
        print("------------------")
    if os.path.isdir('./api/dataset_reorganised/' + dir):
        total_tests = 0
        labelled_tests = 0
        no_focal = 0
        unrecognised = 0
        # for every json inside the dir (use os.walk as it is recursive)
        for root, dirs, files in os.walk('./api/dataset_reorganised/' + dir):
            for file in files:
                if not file.endswith('.json'):
                    continue
                
                json_content = json.load(open(os.path.join(root, file)))

                for path in json_content:
                    temp = json_content[path]
                    if 'tests' not in temp:
                        continue
                    for test in temp['tests']:
                        total_tests += 1
                        if 'label' in test:
                            labelled_tests += 1
                            if test['label'] == "<<NO FOCAL METHOD>>":
                                no_focal += 1
                            elif test['label'] == "<<UNRECOGNISED_METHOD>>":
                                unrecognised += 1
        
        print(f"Total tests in {dir}: {total_tests}")
        print(f"Labelled tests in {dir}: {labelled_tests}")
        print(f"No focal method in {dir}: {no_focal}")
        print(f"Unrecognised method in {dir}: {unrecognised}")
        print("------------------")