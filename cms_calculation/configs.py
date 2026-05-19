import os
import shutil


class Configs:

    def __init__(self, project_name, llm_name) -> None:

        self.project_name = project_name
        self.llm_name = llm_name

        # DTester root (parent of cms_calculation/)
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._module_dir = os.path.dirname(os.path.abspath(__file__))

        self.pit_version = '1.17.0'
        self.pit_junit5_plugin_version = '1.2.1'
        self.pit_timeout = '2'
        self.pit_output_format = 'csv'

        self.log_path = f'{self._module_dir}/logs'
        os.makedirs(self.log_path, exist_ok=True)

        self.pit_output_dir = f'{self.root_dir}/data/mutation_data'
        self.collected_mutation_scores_dir = f'{self.root_dir}/data/collected_mutation_scores'

        self.test_case_initial_gen_save_path = f'{self.root_dir}/data/generated_test_cases/{llm_name}/{project_name}.json'
        self.generated_pit_report_dir = f'{self.pit_output_dir}/{llm_name}/{project_name}'
        self.ground_truth_pit_report_dir = f'{self.pit_output_dir}/ground-truth/{project_name}'
        self.scores_dir = f'{self.collected_mutation_scores_dir}/{llm_name}'

        self.coverage_human_labeled_dir = f'{self.root_dir}/data/collected_coverages'

        common_project_dir_no_test_file = f'{self.root_dir}/data/repos/repos_removing_test'
        self.common_project_path_no_test_file = f'{common_project_dir_no_test_file}/{project_name}'

        idx = 0
        while True:
            self.project_dir = f'{common_project_dir_no_test_file}/workspace_{idx}'
            self.project_path_no_test_file = f'{self.project_dir}/{project_name}'
            if not os.path.exists(self.project_path_no_test_file):
                os.makedirs(self.project_dir, exist_ok=True)
                shutil.copytree(self.common_project_path_no_test_file, self.project_path_no_test_file)
                break
            idx += 1
