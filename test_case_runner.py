import os
import json
import shutil
import re
from tqdm import tqdm
from bs4 import BeautifulSoup
import subprocess


class TestCaseRunner():
    def __init__(self, configs, test_case_run_log_dir):
        self.configs = configs
        self.test_case_run_log_dir = test_case_run_log_dir
        self.cur_no_ref_log_name = None
        self.cur_human_ref_log_name = None
        self.cur_rag_ref_log_name = None

        self.focal_file_coverage = dict()  # e.g., {'Base64_1_no_ref': cov_no_ref, 'Base64_1_with_rag_ref': cov_with_rag_ref}

    def check_jacoco_in_pom(self, project_path):
        """Check if JaCoCo plugin is configured in pom.xml files."""
        pom_files = []
        
        # Find all pom.xml files in the project
        for root, dirs, files in os.walk(project_path):
            if 'pom.xml' in files:
                pom_files.append(os.path.join(root, 'pom.xml'))
        
        if not pom_files:
            print(f"[ERROR] No pom.xml found in {project_path}")
            return False
        
        # Check if any pom.xml contains jacoco
        jacoco_found = False
        for pom_file in pom_files:
            try:
                with open(pom_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'jacoco' in content.lower():
                        jacoco_found = True
                        break
            except Exception as e:
                print(f"[WARNING] Could not read {pom_file}: {e}")
        
        if not jacoco_found:
            print(f"[WARNING] JaCoCo plugin not found in any pom.xml files in {project_path}")
        
        return jacoco_found
    
    def add_jacoco_to_pom(self, project_path):
        """Automatically add JaCoCo plugin to the main pom.xml if missing."""
        main_pom = os.path.join(project_path, 'pom.xml')
        
        if not os.path.exists(main_pom):
            print(f"[ERROR] Main pom.xml not found at {main_pom}")
            return False
        
        try:
            with open(main_pom, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if jacoco already exists
            if 'jacoco' in content.lower():
                print(f"[INFO] JaCoCo already configured in {main_pom}")
                return True
            
            # JaCoCo plugin configuration
            jacoco_plugin = '''            <plugin>
                <groupId>org.jacoco</groupId>
                <artifactId>jacoco-maven-plugin</artifactId>
                <version>0.8.8</version>
                <executions>
                    <execution>
                        <goals>
                            <goal>prepare-agent</goal>
                        </goals>
                    </execution>
                    <execution>
                        <id>report</id>
                        <phase>prepare-package</phase>
                        <goals>
                            <goal>report</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>'''
            
            # Try to find <plugins> section and add JaCoCo
            if '<plugins>' in content:
                # Insert after <plugins> tag
                content = content.replace('<plugins>', f'<plugins>\n{jacoco_plugin}', 1)
                print(f"[INFO] Added JaCoCo plugin to {main_pom}")
            elif '<build>' in content:
                # Create <plugins> section if it doesn't exist
                plugins_section = f'''        <plugins>
{jacoco_plugin}
        </plugins>'''
                content = content.replace('<build>', f'<build>\n{plugins_section}', 1)
                print(f"[INFO] Created plugins section and added JaCoCo to {main_pom}")
            else:
                # Create <build> and <plugins> section
                build_section = f'''    <build>
        <plugins>
{jacoco_plugin}
        </plugins>
    </build>'''
                # Insert before </project>
                content = content.replace('</project>', f'{build_section}\n</project>', 1)
                print(f"[INFO] Created build section and added JaCoCo to {main_pom}")
            
            # Write back to file
            with open(main_pom, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"[SUCCESS] JaCoCo plugin added to {main_pom}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to add JaCoCo to {main_pom}: {e}")
            return False
    
    def ensure_jacoco_configured(self, project_path):
        """Ensure JaCoCo is configured in the project, add it if missing."""
        if not self.check_jacoco_in_pom(project_path):
            print(f"[INFO] JaCoCo not found, attempting to add it automatically...")
            if self.add_jacoco_to_pom(project_path):
                # Verify it was added successfully
                if self.check_jacoco_in_pom(project_path):
                    print(f"[SUCCESS] JaCoCo successfully configured")
                    return True
                else:
                    print(f"[ERROR] JaCoCo addition verification failed")
                    return False
            else:
                return False
        return True

    def backup_project_state(self, project_path):
        """Record git state before test execution and ensure JaCoCo is configured."""
        backup_info = {'path': project_path}
        
        # Ensure JaCoCo is configured (add if missing)
        backup_info['has_jacoco'] = self.ensure_jacoco_configured(project_path)
        
        return backup_info
    
    def restore_project_if_damaged(self, backup_info):
        """Restore project using git reset if damage detected."""
        project_path = backup_info['path']
        
        # Check if damage occurred
        src_path = os.path.join(project_path, 'src')
        if os.path.exists(src_path):
            # No damage, no need to restore
            return False
        
        print(f"\n\n[WARNING] Project damage detected at {project_path}\n\n")
        
        try:
            # Use git to restore (very fast)
            print(f"[INFO] Restoring project using git reset...")
            subprocess.run(['git', 'reset', '--hard', 'HEAD'], cwd=project_path, check=True, timeout=30)
            subprocess.run(['git', 'clean', '-fd'], cwd=project_path, check=True, timeout=30)
            print(f"[INFO] Project restored successfully")
            
            # Re-ensure JaCoCo is configured after restore
            if backup_info.get('has_jacoco'):
                if not self.ensure_jacoco_configured(project_path):
                    print(f"[ERROR] Failed to restore JaCoCo configuration!")
                else:
                    print(f"[INFO] JaCoCo configuration restored")
            
            return True
        except Exception as e:
            print(f"[ERROR] Git restore failed: {e}")
            return False
    
    def validate_project_structure(self, project_path):
        """Validate that critical project files still exist after test execution."""
        src_path = os.path.join(project_path, 'src')
        if not os.path.exists(src_path):
            print(f"[ERROR] Project source directory is missing: {src_path}")
            return False
        return True
    
    def run_test_with_protection(self, test_case_path, focal_file_path, is_ref):
        """Run test with automatic git restore if damage occurs."""
        project_path = test_case_path.split('/src/test/')[0]
        
        # Record project state
        backup_info = self.backup_project_state(project_path)
        
        # Run the test
        log_path = self.run_test_case(test_case_path, focal_file_path, is_ref)
        
        # Restore if damaged
        if self.restore_project_if_damaged(backup_info):
            print(f"[WARNING] Project was restored using git after test execution")
        
        return log_path

    def run_all_test_cases(self, test_cases, is_ref):
        test_case_with_log_coverage = []
        # run the generated test cases
        for each_test_case in tqdm(test_cases, ncols=80, desc='Running test cases'):
            focal_file_path = each_test_case['focal_file_path']

            generation_relative_path = each_test_case['test_case_path']
            tc_path = f"{self.configs.project_dir}/{generation_relative_path}"
            tc = each_test_case['generated_test_case']
            fm_name_param = each_test_case['focal_method_name'].split('::::')[1]

            log_path, focal_file_coverage, fm_cov_statistic_by_jacoco = self.run_test_case_and_get_coverage(tc, tc_path, focal_file_path, fm_name_param, is_ref=is_ref)
            each_test_case[f'log_path_{is_ref}'] = log_path
            each_test_case[f'coverage_focal_file'] = focal_file_coverage  # used for analyze_coverage_with_target_coverage()
            each_test_case[f'coverage_focal_method'] = fm_cov_statistic_by_jacoco  # used for analyze_coverage_with_target_focal_method()

            test_case_with_log_coverage.append(each_test_case)
        return test_case_with_log_coverage

    def save_log_coverage(self, log_coverage, save_path):
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'w') as f:
            json.dump(log_coverage, f, indent=4)
            print(f"Saved the generated test cases' log and coverage to {save_path}")

    def run_test_case(self, test_case_path, focal_file_path, is_ref):
        assert is_ref in ('no_ref', 'human_ref', 'rag_ref')
        test_case_relative_path = self.get_test_case_relative_path(test_case_path)

        focal_method_name = focal_file_path.split('/')[-1].split('.')[0]

        suffix = is_ref
        index = 1
        log_file_path = f'{self.test_case_run_log_dir}/{focal_method_name}_{index}_{suffix}.log'
        while os.path.exists(log_file_path):
            index += 1
            log_file_path = f'{self.test_case_run_log_dir}/{focal_method_name}_{index}_{suffix}.log'
        setattr(self, f'cur_{is_ref}_ref_log_name', f'{focal_method_name}_{index}_{suffix}')

        cwd_path = test_case_path.split('/src/test/')[0]

        cmd = f"cd {cwd_path} && mvn clean verify jacoco:report -Dtest={test_case_relative_path} -Dcheckstyle.skip=true -DskipTests=false > '{log_file_path}' 2>&1"

        print(cmd)
        os.system(cmd)
        return log_file_path

    def run_test_case_and_get_coverage(self, test_case, test_case_path, focal_file_path, focal_method_name_parameter, is_ref):
        print(f'Running the test case with = {is_ref} = reference...')
        # remove the folder of test cases
        tc_rel_path = test_case_path.split('/src/test/')[1]
        tc_base_dir = test_case_path.replace(tc_rel_path, '')
        os.makedirs(os.path.dirname(test_case_path), exist_ok=True)
        with open(test_case_path, 'w') as f:
            f.write(test_case)

        # tc_run_log_path = self.run_test_case(test_case_path, focal_file_path, is_ref)
        tc_run_log_path = self.run_test_with_protection(test_case_path, focal_file_path, is_ref)

        focal_file_coverage, fm_cov_statistic_by_jacoco = self.get_focal_file_coverage(focal_file_path, test_case_path, focal_method_name_parameter)  # used for analyze_coverage_with_target_coverage()
        focal_file_coverage = ''.join(focal_file_coverage) if focal_file_coverage is not None else None

        if os.path.exists(test_case_path):
            os.remove(test_case_path)

        return tc_run_log_path, focal_file_coverage, fm_cov_statistic_by_jacoco

    def get_coverage_jacoco(self, test_case_path, focal_file_path, focal_method_name_parameter):

        focal_file_coverage, fm_cov_statistic_by_jacoco = self.get_focal_file_coverage(focal_file_path, test_case_path, focal_method_name_parameter)  # used for analyze_coverage_with_target_coverage()
        focal_file_coverage = ''.join(focal_file_coverage) if focal_file_coverage is not None else None

        return focal_file_coverage, fm_cov_statistic_by_jacoco

    def compile_and_execute_test_case(self, test_case, test_case_path):
        compile_success, execute_success = False, False
        compile_log, test_log = '', ''

        tc_rel_path = test_case_path.split('/src/test/')[1]
        tc_base_dir = test_case_path.replace(tc_rel_path, '')
        os.makedirs(os.path.dirname(test_case_path), exist_ok=True)
        with open(test_case_path, 'w') as f:
            f.write(test_case)

        test_case_relative_path = self.get_test_case_relative_path(test_case_path)

        cwd_path = test_case_path.split('/src/test/')[0]
        
        # Add security properties to prevent directory traversal in tests
        mvn_compile_cmd = ['mvn', 'clean', f'-Dtest={test_case_relative_path}', 'test-compile', 
                          '-Dcheckstyle.skip=true', '-Djava.io.tmpdir=' + os.path.join(cwd_path, 'target', 'tmp')]
        compile_result = subprocess.run(mvn_compile_cmd, cwd=cwd_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        compile_log = f'{compile_result.stdout}\n\n{compile_result.stderr}\n\n'

        if "BUILD SUCCESS" in compile_log:
            compile_success = True

            # Add security properties to prevent directory traversal in tests  
            mvn_test_cmd = ['mvn', 'clean', 'verify', f'-Dtest={test_case_relative_path}', 
                           '-Dcheckstyle.skip=true', '-Djava.io.tmpdir=' + os.path.join(cwd_path, 'target', 'tmp')]
            test_result = subprocess.run(mvn_test_cmd, cwd=cwd_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            test_log = f'{test_result.stdout}\n\n{test_result.stderr}'
            if "BUILD SUCCESS" in test_log:
                execute_success = True
                
        if os.path.exists(test_case_path):
            os.remove(test_case_path)
        return compile_log, test_log, compile_success, execute_success

    def compile_and_execute_test_case_with_protection(self, test_case, test_case_path):
        """Compile and execute test case with automatic git restore if damage occurs."""
        project_path = test_case_path.split('/src/test/')[0]
        
        # Backup project state
        backup_info = self.backup_project_state(project_path)
        
        # Run the test
        compile_log, test_log, compile_success, execute_success = self.compile_and_execute_test_case(test_case, test_case_path)
        
        # Auto-restore if damaged
        if self.restore_project_if_damaged(backup_info):
            print(f"[INFO] Project was restored using git after test execution")
        
        return compile_log, test_log, compile_success, execute_success

    def get_test_case_relative_path(self, test_case_path):
        test_case_relative_path = test_case_path.split('/src/test/java/')[1]
        test_case_relative_path = test_case_relative_path.split('/')[1:]
        test_case_relative_path = '/'.join(test_case_relative_path)
        test_case_relative_path = test_case_relative_path.replace('.java', '')
        test_case_relative_path = test_case_relative_path.replace('/', '.')
        return test_case_relative_path

    def get_focal_file_coverage(self, focal_file_path, test_case_path, focal_method_name_parameter):
        # base_path = f'{self.configs.project_dir}/{self.configs.project_name}'
        base_path = test_case_path.split('/src/test/java/')[0]
        org_name = test_case_path.split('/src/test/java/')[1].split('/')[0]
        test_suffix = 'Test'
        test_case_relative_path = self.get_test_case_relative_path(test_case_path)

        # jacoco java.html report contains java code lines with tags.
        jacoco_java_html_report_path = self.get_jacoco_java_html_report_path(base_path, test_case_relative_path, org_name, test_suffix)

        if not os.path.exists(jacoco_java_html_report_path):
            print(f'[WARNING] Jacoco report not found: {jacoco_java_html_report_path}')
            return None, None

        # will be used for analyze_coverage_with_target_coverage(). will be used to count the target coverage's coverage
        cov_lines, uncov_lines = self.get_lines_coverage(jacoco_java_html_report_path)
        with open(f'{self.configs.project_dir}/{focal_file_path}', 'r') as f:
            focal_file = f.readlines()
        for line in cov_lines:
            if focal_file[line - 1].strip() != '}':
                focal_file[line - 1] = "<COVER>" + focal_file[line - 1]

        # will be used for analyze_coverage_with_target_focal_method(). directly use the focal method's coverage counted by jacoco
        jacoco_html_report_path = jacoco_java_html_report_path.replace('.java.html', '.html')

        if not os.path.exists(jacoco_html_report_path):
            print(f'[WARNING] Jacoco report not found: {jacoco_html_report_path}. But Jacoco java.html report is found: {jacoco_java_html_report_path}')
            return None, None
        #

        fm_cov_statistic_by_jacoco = self.get_focal_method_coverage_statistic_by_jacoco(focal_method_name_parameter, jacoco_html_report_path)

        return focal_file, fm_cov_statistic_by_jacoco

    def get_jacoco_java_html_report_path(self, base_path, test_class_name, org_name, test_suffix):
        # get jacoco report
        # append_path = "spark/" if '.' not in test_class_name else "spark." + '.'.join(test_class_name.split(".")[:-1]) + '/'
        append_path = org_name + "/" if '.' not in test_class_name else org_name + "." + '.'.join(test_class_name.split(".")[:-1]) + '/'
        suff_len = len(test_suffix)
        html_name = test_class_name.split(".")[-1][:suff_len * -1] + ".java.html" # changes from -4 to -5 depending on whether it's Test or Tests
        
        jacoco_path = base_path + "/target/site/jacoco/" + append_path + html_name
        return jacoco_path

    def get_lines_coverage(self, jacoco_java_html_report_path):
        with open(jacoco_java_html_report_path) as f:
            soup = BeautifulSoup(f, 'html.parser')
            # find all spans with class 'fc' or 'pc' or 'bpc', and extract the ID
            cov_lines = []
            uncov_lines = []
            for span in soup.find_all('span', class_=['fc', 'pc', 'bpc', 'nc']):
                if span['class'][0] == 'nc':
                    uncov_lines.append(int(span['id'][1:]))
                else:
                    cov_lines.append(int(span['id'][1:]))
        
        return cov_lines, uncov_lines
    

    def get_focal_method_coverage_statistic_by_jacoco(self, focal_method_name_param, jacoco_html_report_path):
        with open(jacoco_html_report_path) as f:
            soup = BeautifulSoup(f, 'html.parser')

        # example: focal_method_name_param is intersectionDistinct(java.util.Collection<T>,java.util.Collection<T>,java.util.Collection<T>[]). to match intersectionDistinct(Collection, Collection, Collection[])
        # example: valuesOfKeys(java.util.Map<K, V>,K[]) to match valuesOfKeys(Map, Object[])
        # example: groupingBy(java.util.function.Function<? super T, ? extends K>,java.util.function.Function<? super T, ? extends R>) to match groupingBy(Function, Function)
        # example: filter(java.util.Map<K, V>,cn.hutool.core.lang.Filter<java.util.Map.Entry<K, V>>) to match filter(Map, Filter)
        target_fm_name = focal_method_name_param.strip().split('(')[0]
        target_fm_params_str = focal_method_name_param.strip().split('(')[1][:-1]
        target_fm_params_str = self.remove_angle_brackets_substrings(target_fm_params_str)
        target_fm_params = [each_param.strip() for each_param in target_fm_params_str.split(',')]
        target_fm_params = [each_param.split('.')[-1] if '.' in each_param else each_param for each_param in target_fm_params]

        cov_stat = {}

        candidates = []
        table = soup.find('tbody')
        for each_tr in table.find_all('tr'):
            # check the method name
            candidate_all_column = each_tr.find_all('td')

            method_name = candidate_all_column[0].text
            candidate_fm_name = method_name.strip().split('(')[0]
            if candidate_fm_name != target_fm_name:
                continue
            
            candidates.append(candidate_all_column)

        if len(candidates) == 0:
            print('[WARNING] Cannot find the focal method in the jacoco report. Need manual check\n', f'focal_method_name: {focal_method_name_param}\n\n')
            cov_stat['raw_html'] = str(soup)
            return cov_stat        

        if len(candidates) > 1:
            all_column = self.select_focal_method_coverage_statistic_by_jacoco(target_fm_params, candidates)
        else:
            all_column = candidates[0]

        if all_column is not None:
            # parse the result
            cov_stat['number_of_lines'] = int(all_column[8].text.strip())
            cov_stat['number_of_branches'] = int(all_column[6].text.strip()) - 1
            cov_stat['line_coverage'] = float(all_column[2].text.strip()[:-1])  # remove the '%'
            branch_cov = all_column[4].text.strip()
            cov_stat['branch_coverage'] = float(branch_cov[:-1]) if branch_cov != 'n/a' else branch_cov
        else:
            print('[WARNING] Cannot find the focal method in the jacoco report. Need manual check\n', f'focal_method_name: {focal_method_name_param}\n\n')
            cov_stat['raw_html'] = str(soup)

        return cov_stat

    def select_focal_method_coverage_statistic_by_jacoco(self, target_fm_params, candidates):
        # filter according to the number of parameters
        filter_candidates = []
        for each_candidate in candidates:
            method_name = each_candidate[0].text

            candidate_fm_params = [each_param.strip() for each_param in method_name.strip().split('(')[1][:-1].split(',')]
            if len(target_fm_params) == len(candidate_fm_params):
                filter_candidates.append(each_candidate)
        
        if len(filter_candidates) == 1:
            all_column = filter_candidates[0]
            return all_column

        # filter according to the detailed parameters
        all_column = None

        for each_candidate in filter_candidates:
            method_name = each_candidate[0].text

            candidate_fm_params = [each_param.strip() for each_param in method_name.strip().split('(')[1][:-1].split(',')]
            is_match = True
            for idx in range(len(target_fm_params)):
                if target_fm_params[idx] != candidate_fm_params[idx]:
                    is_match = False
                    break

            if is_match:
                all_column = each_candidate
                return all_column

        # for corner case such as: valuesOfKeys(java.util.Map<K, V>,K[]) to match valuesOfKeys(Map, Object[]). need to transform K to Object
        if all_column is None:  
            for each_candidate in filter_candidates:
                method_name = each_candidate[0].text

                candidate_fm_params = [each_param.strip() for each_param in method_name.strip().split('(')[1][:-1].split(',')]
                is_match = True
                for idx in range(len(target_fm_params)): 
                    if target_fm_params[idx] != candidate_fm_params[idx]:
                        change_to_object = re.sub(r'[A-Za-z]', 'Object', target_fm_params[idx])
                        if change_to_object == candidate_fm_params[idx]:  # add this to check the corner case
                            continue
                        else:
                            is_match = False
                            break

                if is_match:
                    all_column = each_candidate
                    break

        return all_column

    def remove_angle_brackets_substrings(self, input_string):
        # Define the regular expression pattern to match substrings within angle brackets, including nested ones
        pattern = re.compile(r"<[^<>]*>")
        
        while True:
            # Remove all substrings that match the pattern
            input_string, count = pattern.subn('', input_string)
            if count == 0:
                break
        
        return input_string