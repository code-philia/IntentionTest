import os
from statistic_new import StatisticKG


def get_statistics_new(statistic):
    def _analyze_coverage_with_target_coverage():
        print('- All coverages:')

        statistic.analyze_coverage_with_target_coverage(is_ref='all', n_cover_line_threshold=1)
        statistic.analyze_coverage_with_target_coverage(is_ref='all', n_cover_line_threshold=2)
        statistic.analyze_coverage_with_target_coverage(is_ref='all', n_cover_line_threshold=3)

    statistic.cal_codebleu_for_test_cases(is_pass=False, is_common=False)

    print('Coverage analysis...')
    _analyze_coverage_with_target_coverage()


if __name__ == '__main__':
    root_dir = os.path.dirname(os.path.abspath(__file__))
    path = f'{root_dir}/generated_test_cases/retrieve_ref_disc_fact_0.4_3_full_desc/gpt-o1-mini'
    projects = os.listdir(path)
    for project in projects:
        print(f'Processing {project}')
        statistic = StatisticKG(os.path.join(path, project))
        get_statistics_new(statistic)