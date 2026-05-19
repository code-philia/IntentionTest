# README

Sometimes, when we do the postprocessing step, the extracted test might not be directly compilable/executable. This is so as there are
some limitations to the way we do our static/dynamic analysis at this point. Thus, sometimes, manual edits are necessary. These scripts
will make the manual edits much easier.

- main.py will try to run all tests in the dataset, and once there's an error, it will try to do the most common problem (adding
  @BeforeEach back). If it still fails, it will open both the reference (original test file) and the extracted test in our dataset
  side by side on VS Code.
- After manually editing the extracted test, run update_dataset.py to update the dataset.
- Continue the process with running main.py afterwards until the whole dataset is compilable and executable

move_resources.py adds the resources needed from the original test folder (non-{name}Test.java files)
