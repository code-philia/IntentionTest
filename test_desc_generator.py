import json
import os
from agents import TestDescAgent
from configs import Configs
from dataset import Dataset
from tqdm import tqdm
from utils import remove_import_statements


def main():
    test_desc_agent = TestDescAgent(llm_name)

    save_path = configs.test_desc_dataset_path
    if resume_generation_at > 0:
        save_path = save_path.replace('.json', f'_resume_{resume_generation_at}.json')

    test_desc_dataset = []
    for target_pair_idx, each_target_pair in tqdm(enumerate(coverage_data), total=len(coverage_data), ncols=80, desc='Generating test descriptions'):
        if target_pair_idx < resume_generation_at:
            continue

        tar_fm = each_target_pair.focal_method
        tar_tc = each_target_pair.test_case
        tar_tc_no_import_stat = remove_import_statements(tar_tc)

        test_desc = test_desc_agent.generate_test_desc(tar_tc_no_import_stat.strip(), tar_fm)

        data = {
            'coverage_idx': target_pair_idx,
            'target_test_case': tar_tc,
            'target_focal_method': tar_fm,
            'test_desc': test_desc
        }

        test_desc_dataset.append(data)

        if not os.path.exists(os.path.dirname(save_path)):
            os.makedirs(os.path.dirname(save_path))

        with open(save_path, 'w') as f:
            json.dump(test_desc_dataset, f, indent=4)
            

if __name__ == '__main__':
    llm_name = 'gpt-5-mini'
    project_name_list = [('itext-java', 0), ('yavi', 0), ('jInstagram', 0), ('hutool', 0), ('truth', 0), ('lambda', 0), ('imglib', 0)]

    for project_name, resume_generation_at in project_name_list:
        print(f'\n\n\nProject: {project_name}')
        configs = Configs(project_name, llm_name=llm_name)

        print('Loading jacoco labelled coverages...')
        coverage_dataset = Dataset(configs)
        coverage_data = coverage_dataset.load_coverage_data_jacoco()

        main()