# README
- add_test_name.py post-extracts the test name and add it to the dataset (it could have incorporated at
  the start but when we were working on DTester, this was a late addition
- automatically_labelled.py will come up with the automatically-labelled dataset (i.e., the focal method is determined based on
  the name of the test)
- manually_labelled.py will come up with the raw dataset that still needs to be manually labelled (the application needed to manually label
  the dataset can be found in ../dataset_labelling)
- postprocess.py postprocesses the dataset (after manual labelling) so that it adheres to our dataset format
- utils.py contains a lot of different necessary utils to do various different things
- xml_utils.py will add the jacoco plugin automatically to repositories. It's not 100% fool-proof; sometimes you might still need to
  do some debugging to figure out why the jacoco report is not generated

after_gpt_4o contains the scripts to get tests that were written after gpt-4o were released.
