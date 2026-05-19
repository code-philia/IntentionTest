import csv
import os


def _root_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_csv(file_path):
    with open(file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        return list(reader)


def write_csv(file_path, data):
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerows(data)


def calculate_project_cms(project_name, llm_name):
    root_dir = _root_dir()
    ground_truth_pit_dir = f"{root_dir}/data/mutation_data/ground-truth/{project_name}"
    generated_pit_dir = f"{root_dir}/data/mutation_data/{llm_name}/{project_name}"

    if not os.path.exists(generated_pit_dir):
        print(f"generated pit dir not found: {generated_pit_dir}")
        return

    score_report = [["idx", "class name", "test case name", "tool killed cnt", "ground-truth killed cnt", "shared killed cnt", "total killed cnt", "score"]]

    for class_name in os.listdir(generated_pit_dir):
        ground_truth_csv_dir = f"{ground_truth_pit_dir}/{class_name}"

        if os.path.exists(ground_truth_csv_dir):
            generated_csv_dir = f"{generated_pit_dir}/{class_name}"

            for test_case in os.listdir(generated_csv_dir):
                ground_truth_csv_path = f"{ground_truth_csv_dir}/{test_case}"
                if os.path.exists(ground_truth_csv_path):
                    ground_truth_pit_data = read_csv(ground_truth_csv_path)
                    generated_pit_data = read_csv(f'{generated_csv_dir}/{test_case}')
                    if len(ground_truth_pit_data) != len(generated_pit_data):
                        continue
                    tool_killed_cnt, ground_truth_killed_cnt, shared_killed_cnt, total_killed_cnt, score = calculate_cms(ground_truth_pit_data, generated_pit_data)
                    score_report.append([test_case.split('_')[0], class_name.replace('_', '.'), test_case.split('.')[0].split('_')[-1], tool_killed_cnt, ground_truth_killed_cnt, shared_killed_cnt, total_killed_cnt, score])
                else:
                    print(f"no ground truth data {test_case}")
        else:
            print(f"no ground truth data for class {class_name}")

    scores_dir = f"{root_dir}/data/collected_mutation_scores/{llm_name}"
    os.makedirs(scores_dir, exist_ok=True)
    write_csv(f'{scores_dir}/{project_name}.csv', score_report)


def calculate_cms(ground_truth_data, generated_data):
    tool_killed_cnt = 0
    ground_truth_killed_cnt = 0
    shared_killed_cnt = 0
    total_killed_cnt = 0

    for i in range(0, len(generated_data)):
        ground_truth_result = ground_truth_data[i][5]
        generated_result = generated_data[i][5]

        if generated_result == 'KILLED':
            tool_killed_cnt += 1
            total_killed_cnt += 1
            if ground_truth_result == 'KILLED':
                shared_killed_cnt += 1
                ground_truth_killed_cnt += 1
        elif ground_truth_result == 'KILLED':
            ground_truth_killed_cnt += 1
            total_killed_cnt += 1

    if ground_truth_killed_cnt == 0:
        score = "NaN"
    else:
        score = round(shared_killed_cnt / total_killed_cnt, 2)
    return tool_killed_cnt, ground_truth_killed_cnt, shared_killed_cnt, total_killed_cnt, score


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--project_name', type=str, required=True)
    parser.add_argument('--llm_name', type=str, required=True)
    args = parser.parse_args()
    calculate_project_cms(args.project_name, args.llm_name)
