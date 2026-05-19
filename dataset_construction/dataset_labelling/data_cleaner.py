import os
import json

# For all jsons in ./api/dataset_reorganised
for root, dirs, files in os.walk("./api/dataset_reorganised"):
  for file in files:
    if not file.endswith(".json"):
      continue

    complete_path = os.path.join(root, file)

    # read json
    json_content = json.load(open(complete_path))

    ls_no_tests = []

    for key, value in json_content.items():
      if "tests" in value:
        continue

      # add key to list if no tests
      ls_no_tests.append(key)

    for key in ls_no_tests:
      # delete key if no tests
      del json_content[key]

    print(f"Deleted {len(ls_no_tests)} entries from {complete_path}")
    # write json
    with open(complete_path, "w") as f:
      json.dump(json_content, f, indent=2)