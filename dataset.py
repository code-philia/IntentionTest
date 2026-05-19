import json
import os
import re
from utils import skeletonize_java_code
from collections import namedtuple
CoveragePair = namedtuple('CoveragePair', ['project_name', 'focal_file_path', 'focal_method_name', 'coverage', 'focal_method', 'context', 'focal_file_skeleton', 'test_case', 'test_case_name', 'test_case_path', 'references'])


class Dataset:
    def __init__(self, configs):
        self.configs = configs
        self.raw_data = None
        self.coverage_human_labeled = None

    def load_coverage_data_jacoco(self):
        path = os.path.join(self.configs.coverage_human_labeled_dir, f'{self.configs.project_name}.json')
        coverage_data = self._load_coverage_data_jacoco(path)
        return coverage_data

    def _load_coverage_data_jacoco(self, path: str):
        coverage_data = []
        with open(path, 'r') as f:
            data = json.load(f)
        for each_focal_file_path, coverages in data.items():
            for each_fm_name, tc_cov_pairs in coverages.items():
                for each_pair in tc_cov_pairs:
                    tc_name, tc, cov, context, focal_file_skeleton = each_pair

                    # check data, will be removed after standardising the format of dataset
                    tc = [self.add_newline_char(each_line) for each_line in tc]
                    cov = [self.add_newline_char(each_line) for each_line in cov]
                    context = [self.add_newline_char(each_line) for each_line in context]

                    if '::::' in tc_name:
                        tc_name = tc_name.split('::::')[1]
                        tc_name = tc_name.split('(')[0]
                    # 

                    fm = ''.join(cov).replace('<COVER>', '')

                    focal_case_dir = each_focal_file_path[:each_focal_file_path.rfind('/')]
                    test_case_dir = focal_case_dir.replace('/main/', '/test/')
                    
                    is_extend_clss = False
                    test_case_class_name = None
                    for each_line in tc:
                        tc_class_name = re.findall(r'public class (\w+)\s*{', each_line)
                        if len(tc_class_name) == 1:
                            test_case_class_name = tc_class_name[0]
                            break

                        tc_class_name = re.findall(r'public class (\w+) extends \w+\s*{', each_line)
                        if len(tc_class_name) == 1:
                            test_case_class_name = tc_class_name[0]
                            is_extend_clss = True
                            break
                        
                        tc_class_name = re.findall(r'class (\w+)\s*{', each_line)
                        if len(tc_class_name) == 1:
                            test_case_class_name = tc_class_name[0]
                            break

                        tc_class_name = re.findall(r'public class (\$\w+)\s*{', each_line)  # project lambda
                        if len(tc_class_name) == 1:
                            test_case_class_name = tc_class_name[0]
                            break
                    
                    # NOTE: for blade, we skip the test cases that extend other classes
                    
                    if self.configs.project_name == 'blade' and is_extend_clss:
                        continue    
                    
                    if test_case_class_name is None:
                        raise ValueError(f'Test case class name is not found.\nTest case:\n{tc}\n')

                    test_case_path = f'{self.configs.project_dir_no_test_file}/{test_case_dir}/{test_case_class_name}.java'
                    
                    # with open(f"{self.configs.project_dir_no_test_file}/{each_focal_file_path}", 'r') as f:
                    #     focal_file = f.read()
                    # focal_file_skeleton = skeletonize_java_code(focal_file)
                    if len(focal_file_skeleton) == 0:
                        raise ValueError(f'Focal file skeleton is empty.\nFocal file:\n{each_focal_file_path}\n')

                    coverage_pair = CoveragePair(
                        project_name=self.configs.project_name, 
                        focal_file_path=each_focal_file_path, 
                        focal_method=fm, 
                        coverage=''.join(cov), 
                        context=''.join(context), 
                        focal_file_skeleton=focal_file_skeleton,
                        test_case=''.join(tc), 
                        test_case_name = tc_name,
                        test_case_path = test_case_path,
                        focal_method_name=each_fm_name, 
                        references=None
                    )
                    coverage_data.append(coverage_pair)
        return coverage_data

    def add_newline_char(self, string):
        if not string.endswith('\n'):
            string += '\n'
        return string

    def load_test_desc(self, setting: str):
        with open(self.configs.test_desc_dataset_path, 'r') as f:
            test_desc_data = json.load(f)

        test_desc_data_reformat = []
        for each in test_desc_data:
            test_desc = each['test_desc']
            test_desc = test_desc[3:] if test_desc.startswith('```') else test_desc
            test_desc = test_desc[:-3] if test_desc.endswith('```') else test_desc
            test_desc = test_desc.strip()
            test_desc = divide_desc(test_desc)

            if setting == 'none':
                test_desc_under_setting = ''
            elif setting == 'obj':
                test_desc_under_setting = '# Objective\n' + test_desc['Objective']
            elif setting == 'obj_pre':
                test_desc_under_setting = '# Objective\n' + test_desc['Objective'] + '\n\n# Preconditions\n' + test_desc['Preconditions']
            elif setting == 'obj_exp':
                test_desc_under_setting = '# Objective\n' + test_desc['Objective'] + '\n\n# Expected Results\n' + test_desc['Expected Results']
            elif setting == 'full':
                test_desc_under_setting = '# Objective\n' + test_desc['Objective'] + '\n\n# Preconditions\n' + test_desc['Preconditions'] + '\n\n# Expected Results\n' + test_desc['Expected Results']
            else:
                raise ValueError(f'Unknown setting: {setting}')

            test_desc['under_setting'] = test_desc_under_setting
            each['test_desc'] = test_desc
            test_desc_data_reformat.append(each)
        return test_desc_data_reformat
        
    def load_offline_fact_ref_data(self, reference_setting, fact_setting, test_desc_setting, max_exploration_depth, retrieval_threshold):
        save_path = f'{self.configs.fact_set_dir}/ref_{reference_setting}_fact_{fact_setting}_desc_{test_desc_setting}_depth_{max_exploration_depth}_refThres_{retrieval_threshold}.json'
        with open(save_path, 'r') as f:
            fact_ref_data = json.load(f)
        return fact_ref_data
    
    def load_golden_fact_ref_data(self, reference_setting, fact_setting, 
    test_desc_setting, max_exploration_depth, retrieval_threshold):
        save_path = f'{self.configs.fact_set_dir}/ref_{reference_setting}_fact_golden_desc_{test_desc_setting}_depth_{max_exploration_depth}_refThres_{retrieval_threshold}.json'
        with open(save_path, 'r') as f:
            fact_ref_data = json.load(f)
        return fact_ref_data
    
def divide_desc(desc):
    """
    each desc data is like:
        # Objective
        To verify that the `parse` method correctly throws an `IllegalArgumentException` when given an empty cron expression.

        # Preconditions
        1. The `CronDefinition` mock returns an empty set when `getCronNicknames` is called.
        2. The `CronParser` instance is created with the mocked `CronDefinition`.
        3. The `parse` method is called with an empty string as input.

        # Expected Results
        1. The `parse` method throws an `IllegalArgumentException` with the message "Empty expression!".
    need to divide it into Objective, Preconditions, Expected Results
    """
    desc_lines = desc.split('\n')
    obj_line_idx, precondictions_line_idx, expected_results_line_idx = None, None, None
    for line_idx, each_line in enumerate(desc_lines):
        if each_line.strip().startswith('#'):
            if '# Obj' in each_line:
                obj_line_idx = line_idx
            elif '# Precondition' in each_line:
                precondictions_line_idx = line_idx
            elif '# Expected' in each_line:
                expected_results_line_idx = line_idx
            else:
                raise ValueError(f'Unknown desc line: {each_line}')
    assert None not in (obj_line_idx, precondictions_line_idx, expected_results_line_idx), f'Incompleted Test Desc:\n{desc}\n\n'
    assert obj_line_idx < precondictions_line_idx < expected_results_line_idx, f'Invalid order of desc:\n{desc}\n\n'
    obj = desc_lines[obj_line_idx+1:precondictions_line_idx]
    precondictions = desc_lines[precondictions_line_idx+1:expected_results_line_idx]
    expected_results = desc_lines[expected_results_line_idx+1:]

    desc_dict = {
        'Objective': '\n'.join(obj).strip(),
        'Preconditions': '\n'.join(precondictions).strip(),
        'Expected Results': '\n'.join(expected_results).strip()
    }

    # Check the total number of lines
    total_lines_origin = len([each_line for each_line in desc_lines if each_line.strip()])
    total_lines_divided = len([each_line for each_line in obj + precondictions + expected_results if each_line.strip()]) + 3
    if total_lines_origin != total_lines_divided:
        print(f'WARNING: The total number of lines is not equal after dividing the desc.\nOriginal:\n{desc}\n--------------------\nDivided three parts\n{obj + precondictions + expected_results}\n\n')

    return desc_dict