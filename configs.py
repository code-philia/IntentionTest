import os


class Configs:
    def __init__(self, project_name: str, llm_name: str):
        self.project_name = project_name
        self.root_dir = os.path.dirname(os.path.abspath(__file__))

        common_project_dir_no_test_file = f'{self.root_dir}/data/repos/repos_removing_test'
        self.common_project_path_no_test_file = f'{common_project_dir_no_test_file}/{project_name}'
        self.project_dir = f'{self.root_dir}/data/repos/repos_with_test'

        idx = 0
        while True:
            self.project_dir_no_test_file = f'{common_project_dir_no_test_file}/workspace_{idx}'
            self.project_path_no_test_file = f'{self.project_dir_no_test_file}/{project_name}'
            if not os.path.exists(self.project_path_no_test_file):
                os.makedirs(self.project_dir_no_test_file, exist_ok=True)
                os.system(f'cp -r {self.common_project_path_no_test_file} {self.project_path_no_test_file}')
                break
            idx += 1

        # model configs
        assert llm_name in ['gpt-5-mini', 'deepseek-v3.2', 'claude-haiku-4-5-20251001', 'o1-mini-2024-09-12']
        self.llm_name = llm_name
        
        # dataset relevant paths
        self.coverage_human_labeled_dir = f'{self.root_dir}/data/collected_coverages'
        self.test_desc_dataset_path = f'{self.root_dir}/data/test_desc_dataset/{project_name}.json'
        self.test_desc_from_fm_dataset_path = f'{self.root_dir}/data/test_desc_from_fm_dataset/raw_{project_name}.json'
        self.matched_test_desc_with_tc_dataset_path = f'{self.root_dir}/data/test_desc_from_fm_dataset/matched_{project_name}.json'
        self.fact_set_dir = f'{self.root_dir}/data/fact_set/{project_name}'
        self.test_timestamp_path = f'{self.root_dir}/data/test_timestamp/{project_name}.json'
        
        # temporal candidate collection paths
        self.temporal_clone_dir = f'{self.root_dir}/data/repos/temporal_clones'
        self.temporal_candidate_dataset_dir = f'{self.root_dir}/data/temporal_candidate_dataset'
        self.temporal_candidate_dataset_path = f'{self.temporal_candidate_dataset_dir}/{project_name}.json'

        # save paths
        self.generated_test_case_save_path = f'{self.root_dir}/data/generated_test_cases/{llm_name}/{project_name}.json'
        self.generation_message_log_save_path = f'{self.root_dir}/data/generation_message_log/{llm_name}/{project_name}.json'
        self.test_case_run_log_dir = f'{self.root_dir}/data/test_case_run_log/{llm_name}/{project_name}'
        self.test_case_log_and_coverage_save_path = f'{self.root_dir}/data/generated_test_cases_log_coverage/{llm_name}/{self.project_name}.json'

        # project url used for system prompt
        self.project_url = {
            "itext-java": 'https://github.com/itext/itext-java', 
            "hutool": 'https://github.com/chinabugotech/hutool', 
            "yavi": 'https://github.com/making/yavi', 
            "lambda": 'https://github.com/palatable/lambda', 
            "truth": 'https://github.com/google/truth', 
            "cron-utils": 'https://github.com/jmrozanec/cron-utils', 
            "imglib": 'https://github.com/nackily/imglib', 
            "ofdrw": 'https://github.com/ofdrw/ofdrw', 
            "RocketMQC": 'https://github.com/ProgrammerAnthony/RocketMQC', 
            "blade": 'https://github.com/lets-blade/blade', 
            "spark": 'https://github.com/perwendel/spark', 
            "awesome-algorithm": 'https://github.com/codeartx/awesome-algorithm',
            "jInstagram": 'https://github.com/sachin-handiekar/jInstagram'
        }[project_name]