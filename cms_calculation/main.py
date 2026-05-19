import argparse
import json
import logging
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

from configs import Configs


def modify_pom(project_path, class_name, is_junit5):
    pom_path = f'{project_path}/pom.xml'
    tree = ET.parse(pom_path)
    root = tree.getroot()

    namespace = {'': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {'': 'http://maven.apache.org/POM/4.0.0'}
    # logging.info(f"Detected namespace: {namespace}")

    build = root.find('build', namespace)
    if build is None:
        build = ET.Element('build')
        root.append(build)

    plugins = build.find('plugins', namespace)
    if plugins is None:
        plugins = ET.Element('plugins')
        build.append(plugins)

    pitest_plugin = None

    for plugin in plugins.findall('plugin', namespace):
        group_id = plugin.find('groupId', namespace)
        if group_id is not None and group_id.text == 'org.pitest':
            pitest_plugin = plugin
            break

    if pitest_plugin is None:
        pitest_plugin = ET.SubElement(plugins, 'plugin')

        group_id = ET.SubElement(pitest_plugin, 'groupId')
        group_id.text = 'org.pitest'

        artifact_id = ET.SubElement(pitest_plugin, 'artifactId')
        artifact_id.text = 'pitest-maven'

        version = ET.SubElement(pitest_plugin, 'version')
        version.text = configs.pit_version
        if configs.project_name == 'ofdrw':
            version.text = '1.3.2'

        if is_junit5: # junit5 plugin
            dependencies = ET.SubElement(pitest_plugin, 'dependencies')
            dependency = ET.SubElement(dependencies, 'dependency')
            group_id = ET.SubElement(dependency, 'groupId')
            group_id.text = 'org.pitest'
            artifact_id = ET.SubElement(dependency, 'artifactId')
            artifact_id.text = 'pitest-junit5-plugin'
            version = ET.SubElement(dependency, 'version')
            if configs.project_name == 'ofdrw':
                version.text = '0.4'
            else:
                version.text = configs.pit_junit5_plugin_version

    configuration = pitest_plugin.find('configuration', namespace)
    if configuration is None:
        configuration = ET.SubElement(pitest_plugin, 'configuration')

    def set_text_element(parent, tag, text):
        el = parent.find(tag, namespace)
        if el is None:
            el = ET.SubElement(parent, tag)
        el.text = text

    set_text_element(configuration, 'timeoutFactor', configs.pit_timeout)
    set_text_element(configuration, 'timestampedReports', 'false')

    # outputFormats needs a nested <param> element
    out_put_format = configuration.find('outputFormats', namespace)
    if out_put_format is None:
        out_put_format = ET.SubElement(configuration, 'outputFormats')
    param_el = out_put_format.find('param', namespace)
    if param_el is None:
        param_el = ET.SubElement(out_put_format, 'param')
    param_el.text = 'CSV'

    target_classes = configuration.find('targetClasses', namespace)
    if target_classes is None:
        target_classes = ET.SubElement(configuration, 'targetClasses')

    target_test = configuration.find('targetTests', namespace)
    if target_test is None:
        target_test = ET.SubElement(configuration, 'targetTests')


    param = target_classes.find('param', namespace)
    if param is None:
        param = ET.SubElement(target_classes, 'param')
    param.text = class_name

    param = target_test.find('param', namespace)
    if param is None:
        param = ET.SubElement(target_test, 'param')
    param.text = f'{class_name}Test'

    ET.register_namespace('', namespace[''])
    tree.write(pom_path, encoding='UTF-8', xml_declaration=True)

    logging.info("Pitest config modified")

def run_pitest(project_dir):
    maven_command = "mvn test-compile org.pitest:pitest-maven:mutationCoverage"

    try:
        result = subprocess.run(
            maven_command,
            cwd=project_dir,
            check=True,
            text=True,
            capture_output=True,
            shell = True,
            encoding='utf-8'
        )

        # logging.info("pitest result：")
        # logging.info(result.stdout)
        return 0, result.stdout

    except subprocess.CalledProcessError as e:
        # logging.error("failed to execute pitest：")
        # logging.error(f"error code: {e.returncode}")
        logging.error(f"error output: {e.stdout}")
        return e.returncode, e.stdout
    except FileNotFoundError:
        return 1, "no Maven available"


def extract_package_name_and_project_dir(file_path):
    try:
        split_marker = '/src/main/java/'
        if split_marker in file_path:
            project_dir, package_path = os.path.dirname(file_path).split(split_marker)
            package_name = package_path.replace('/', '.')
            return project_dir, package_name
        else:
            return None, None
    except Exception as e:
        logging.error(f"Error: {e}")
        return None, None

def extract_class_name(path):
    return os.path.basename(path).rsplit('.', 1)[0]


def check_test_case_name(test_case_name):
    split_marker = "::::"
    if split_marker in test_case_name:
        test_case_name = test_case_name.split(split_marker)[-1].strip("()")
    return test_case_name

def extract_test_case(generated_path, generation_key, include_all=False):
    with open(generated_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    test_cases_by_class = defaultdict(list)

    for test_case in data:
        if include_all or test_case.get('running_result') == 'success':
            idx = test_case.get('target_coverage_idx')
            focal_file_path = test_case.get('focal_file_path')
            target_test_case = test_case.get(generation_key)
            test_case_name = test_case.get('target_test_case_name').split("::::")[-1].split("(")[0]

            test_cases_by_class[focal_file_path].append((test_case_name, target_test_case, idx))

    return test_cases_by_class


def passed_test_case_cnt(generated_path):
    with open(generated_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    cnt = 0

    for test_case in data:
        if test_case.get('running_result') == 'success':
            cnt += 1

    return cnt

def prepare_generated_mutation_data(is_ground_truth=False):
    is_junit5 = False
    if configs.project_name in ['cron-utils', 'ofdrw', 'yavi']:
        is_junit5 = True

    if is_ground_truth:
        generated_pit_report_dir = configs.ground_truth_pit_report_dir
        generation_key = 'target_test_case'
    else:
        generated_pit_report_dir = configs.generated_pit_report_dir
        generation_key = 'generated_test_case'

    test_case_initial_gen_save_path = configs.test_case_initial_gen_save_path

    if os.path.exists(generated_pit_report_dir):
        shutil.rmtree(generated_pit_report_dir)
    os.makedirs(generated_pit_report_dir, exist_ok=True)

    generated_test_cases = extract_test_case(test_case_initial_gen_save_path, generation_key, include_all=is_ground_truth)

    for focal_file_path, test_cases in generated_test_cases.items():
        class_name = extract_class_name(focal_file_path)
        sub_project_dir, package_name = extract_package_name_and_project_dir(focal_file_path)

        test_case_path = f"{configs.project_dir}/{sub_project_dir}/src/test/java/{package_name.replace('.', '/')}"
        os.makedirs(test_case_path, exist_ok=True)

        output_file = f"{test_case_path}/{class_name}Test.java"

        sub_project_path = f"{configs.project_dir}/{sub_project_dir}"
        full_class_name = f"{package_name}.{class_name}"

        modify_pom(sub_project_path, full_class_name, is_junit5)
        print(f"execute pitest for generated Class {class_name}")

        for test_case_name, test_case, idx in test_cases:
            with open(output_file, 'w', encoding='utf-8') as java_file:
                java_file.write(test_case)

            logging.info(f"execute pitest for generated test {test_case_name}")
            ret, error_msg = run_pitest(sub_project_path)
            os.remove(output_file)
            if ret != 0:
                logging.error(f"{full_class_name}.{test_case_name} execute failed")
                print(f"{full_class_name}.{test_case_name} execute failed")
                continue

            generated_pit_report = f'{sub_project_path}/target/pit-reports/mutations.csv'
            prepared_data_dir = f"{generated_pit_report_dir}/{full_class_name.replace('.', '_')}"

            os.makedirs(prepared_data_dir, exist_ok=True)
            shutil.copy(generated_pit_report, f"{prepared_data_dir}/{idx}_{test_case_name}.csv")

            logging.info(f"pitest execute success")

    shutil.rmtree(configs.project_path_no_test_file)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project_name', type=str, required=True)
    parser.add_argument('--llm_name', type=str, required=True)
    parser.add_argument('--reference_setting', type=str, default='retrieve', choices=['none', 'retrieve', 'golden', 'low_sim'])
    parser.add_argument('--fact_setting', type=str, default='disc', choices=['none', 'disc', 'golden'])
    parser.add_argument('--disc_threshold', type=float, default=0.4)
    parser.add_argument('--disc_top_k', type=int, default=3)
    parser.add_argument('--test_desc_setting', type=str, default='full', choices=['none', 'obj', 'obj_pre', 'obj_exp', 'full'])
    parser.add_argument('--ground_truth', action='store_true',
                        help='Run pitest on ground-truth test cases (target_test_case) instead of generated ones')

    args = parser.parse_args()

    configs = Configs(args.project_name, args.llm_name)

    # Reconstruct the exact filename suffix used by generate_test.py
    suffix = f'_{args.reference_setting}_ref_{args.fact_setting}_fact'
    suffix += f'_{args.disc_threshold}_{args.disc_top_k}' if args.fact_setting == 'disc' else ''
    suffix += f'_{args.test_desc_setting}_desc'
    base = configs.test_case_initial_gen_save_path[:-5]  # strip .json
    configs.test_case_initial_gen_save_path = base + suffix + '.json'

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_filename = f'{configs.log_path}/pit_{args.project_name}_{timestamp}.log'

    logging.basicConfig(
        level=logging.INFO,
        filename=log_filename,
        filemode='a',
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    prepare_generated_mutation_data(is_ground_truth=args.ground_truth)


