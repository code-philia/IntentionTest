import os
import shutil

def move_resources(test_root):
  ori_test_root = test_root.replace("/bernard/dataset_construction/human_written_tests/test_analysis/repos/", "/bernard/dataset_construction/prep/repos/")

  # For all file inside ori_test_root, if they don't end with Test.java, copy them to test_root
  for root, _, files in os.walk(ori_test_root):
    for file in files:
      if not file.endswith("Test.java"):
        dest_path = os.path.join(test_root, root.split(ori_test_root)[1], file)

        # if dest_path does not exist, create it
        if not os.path.exists(os.path.dirname(dest_path)):
          os.makedirs(os.path.dirname(dest_path))
        shutil.copy2(os.path.join(root, file), dest_path)

# /bernard/dataset_construction/human_written_tests/test_analysis/repos/blade
# for root, _, files in os.walk("/bernard/dataset_construction/human_written_tests/test_analysis/repos/blade"):
#   if root.endswith("src/main"):
#     test_root = root.replace("src/main", "src/test/")
#     print(test_root)
#     move_resources(test_root)
#     continue


# move_resources("/bernard/dataset_construction/human_written_tests/test_analysis/repos/blade")