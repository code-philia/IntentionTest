import json
import os
import subprocess
import pandas as pd
import re
import utils

from tqdm import tqdm

gpt_4o_release_date = "2024-05-13"

repo_path = "/bernard/dataset_construction/prep/up_to_date_repos/itext-java"

def get_changes_date(test_path, start_line, end_line):
    blame_output = subprocess.run(["git", "blame", "-L", f"{start_line},{end_line}", test_path], stdout=subprocess.PIPE, cwd=repo_path)
    blame_output = blame_output.stdout.decode("utf-8")

    commit_dates = re.findall(r"\d{4}-\d{2}-\d{2}", blame_output)
    commit_dates.sort()

    return commit_dates[0], commit_dates[-1]

total_files = sum(len(files) for _, _, files in os.walk(repo_path))

test_files = []

with tqdm(total=total_files, desc="Processing files") as pbar:
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            pbar.update(1)
            
            if not file.endswith("Test.java") or not "src/test/java" in root:
                continue
            
            full_test_path = os.path.join(root, file)

            src_file_path = full_test_path.replace("src/test/java", "src/main/java").replace("Test.java", ".java")

            # check both src and test files exist
            if not os.path.exists(src_file_path):
                continue

            # Get the content of the test file
            with open(full_test_path, "r") as f:
                full_test_content = f.readlines()

            method_lines, _ = utils.get_method_lines(full_test_path, False)

            for method_name, (start_line, end_line) in method_lines.items():
                if "@Test" not in full_test_content[start_line] and "@Test" not in full_test_content[start_line - 1]:
                    continue
                # Get the commit dates for the test method
                earliest_commit_date, latest_commit_date = get_changes_date(full_test_path, start_line, end_line)

                classification = "partial" if latest_commit_date > gpt_4o_release_date and earliest_commit_date < gpt_4o_release_date else (
                    "after" if latest_commit_date > gpt_4o_release_date and earliest_commit_date > gpt_4o_release_date else "before"
                )

                if classification != "before":
                    test_files.append({
                        "full_test_path": full_test_path,
                        "src_file_path": src_file_path,
                        "method_name": method_name,
                        "earliest_commit_date": earliest_commit_date,
                        "latest_commit_date": latest_commit_date,
                        "classification": classification
                    })

# Save the test files as a json
with open("test_files.json", "w") as f:
    json.dump(test_files, f, indent=4)
        
        