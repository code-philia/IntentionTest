import os
import json
import subprocess
import utils
import re

from tqdm import tqdm

dataset_path = "/home/binhang/Documents/softlink/DTester/rescovery/result_backup_20241021/DTester/generated_test_cases_w_date"
repos_path = "/home/binhang/Documents/softlink/DTester/data/raw_data/repos_with_test"

gpt_4o_release_date = "2024-05-13"

cached_method_lines = {}

for file in os.listdir(dataset_path):
# for file in ["truth_gpt-4o_init_gen.json"]:
    if not file.endswith("init_gen.json"):
        continue

    print(f"Processing file: {file}")

    file_path = os.path.join(dataset_path, file)

    with open(file_path, "r") as f:
        data = json.load(f)

    after_gpt_4o = []
    after_gpt_4o_partial = []

    for d in tqdm(data):
        focal_file_path = d["focal_file_path"]
        target_test_case_name = d["target_test_case_name"]
        project_name = d["project_name"]

        project_path = os.path.join(repos_path, project_name)

        # Test path changes src/main/java to src/test/java and .java to Test.java. join it with project path
        test_path = os.path.join(repos_path, focal_file_path.replace("src/main/java", "src/test/java").replace(".java", "Test.java"))

        if test_path in cached_method_lines:
            method_lines = cached_method_lines[test_path]
        else:
            method_lines, _ = utils.get_method_lines(test_path, False)
            if method_lines == {}:
                continue
            cached_method_lines[test_path] = method_lines

        start_line, end_line = method_lines[target_test_case_name]

        # Get git blame for the test file from the start line to the end line
        blame_output = subprocess.run(["git", "blame", "-L", f"{start_line},{end_line}", test_path], stdout=subprocess.PIPE, cwd=project_path)
        blame_output = blame_output.stdout.decode("utf-8")

        # Get the commit dates from the blame output using regex
        commit_dates = re.findall(r"\d{4}-\d{2}-\d{2}", blame_output)

        # sort it in ascending order
        commit_dates.sort()

        # Get the latest commit date
        latest_commit_date = commit_dates[-1]

        # Get the earliest commit date
        earliest_commit_date = commit_dates[0]

        if latest_commit_date > gpt_4o_release_date and earliest_commit_date < gpt_4o_release_date:
            after_gpt_4o_partial.append(d)
        elif latest_commit_date > gpt_4o_release_date and earliest_commit_date > gpt_4o_release_date:
            after_gpt_4o.append(d)
        
    print(f"File: {file}")
    print(f"Total test cases: {len(data)}")
    print(f"Test cases after GPT-4o: {len(after_gpt_4o)}")
    print(f"Test cases after GPT-4o partial: {len(after_gpt_4o_partial)}")

    with open(file_path.replace("init_gen.json", "after_gpt_4o.json"), "w") as f:
        json.dump(after_gpt_4o, f, indent=4)
    
    with open(file_path.replace("init_gen.json", "after_gpt_4o_partial.json"), "w") as f:
        json.dump(after_gpt_4o_partial, f, indent=4)
        