import os
import re
from configs import Configs
from agents import TestGenAgent, TestRefineAgent
from test_case_runner import TestCaseRunner


class IntentionTest:
    def __init__(self, configs: Configs, lsp_server, max_round=3, skip_deepseek_think: bool = False):
        self.configs = configs
        self.max_round = max_round
        self.max_line_error_msg = 20

        self.lsp_server = lsp_server
        self.test_gen_agent = TestGenAgent(configs.llm_name, configs.project_name, configs.project_url, n_responses=1, skip_deepseek_think=skip_deepseek_think)
        self.test_refine_agent = TestRefineAgent(configs.llm_name, configs.project_name, configs.project_url, n_responses=1, skip_deepseek_think=skip_deepseek_think)
        self.test_runner = TestCaseRunner(configs, configs.test_case_run_log_dir)
        self.generation_with_refine_log = []  # [(test_status, prompt, test_case)]
        
    def generate_test_case_with_refine(self, 
                                       target_focal_method, target_context, target_test_case_desc, target_test_case_path,
                                       referable_test_case, facts, junit_version,
                                       prohibit_fact: bool = False):
        self.generation_with_refine_log = []

        target_test_class_name = target_test_case_path.split('/')[-1].replace('.java', '')
        gen_test_case, prompt = self.generate_test_case(target_focal_method, target_context, target_test_class_name, target_test_case_desc, referable_test_case, facts, junit_version, prohibit_fact)
        error_msg, test_status = self.run_test_case(gen_test_case, target_test_case_path)
        self.generation_with_refine_log.append((test_status, prompt, gen_test_case))

        if test_status == 'success':
            return gen_test_case, test_status

        for round in range(self.max_round):
            gen_test_case, prompt = self.refine(gen_test_case, error_msg, target_focal_method, target_context, target_test_case_desc, target_test_case_path, referable_test_case, facts, prohibit_fact)
            error_msg, test_status = self.run_test_case(gen_test_case, target_test_case_path)
            self.generation_with_refine_log.append((test_status, prompt, gen_test_case))

            if test_status == 'success':
                break

        return gen_test_case, test_status

    def generate_test_case(self, target_focal_method, target_context, target_test_class_name, target_test_case_desc, referable_test_case, facts, junit_version, prohibit_fact):
        gen_test_case, prompt = self.test_gen_agent.generate_test_case(target_focal_method, target_context, target_test_class_name, target_test_case_desc, referable_test_case, facts, junit_version, prohibit_fact)
        return gen_test_case[0], prompt
    
    def refine(self, gen_test_case, error_msg, target_focal_method, target_context, target_test_case_desc, target_test_case_path, referable_test_case, facts: list, prohibit_fact):
        error_msg_lines = error_msg.split('\n')
        error_msg_cut = '\n'.join(error_msg_lines[:self.max_line_error_msg])

        if self.configs.fact_setting != 'none':
            import_stat_fix_suggestions = self.get_import_stat_fix_suggestions(gen_test_case, target_test_case_path)
            facts = facts + import_stat_fix_suggestions

        refined_tc_list, prompt = self.test_refine_agent.refine(gen_test_case, error_msg_cut, target_focal_method, target_context, target_test_case_desc, referable_test_case, facts, prohibit_fact)
        return refined_tc_list[0], prompt
    
    def get_import_stat_fix_suggestions(self, test_case, test_case_path):
        os.makedirs(os.path.dirname(test_case_path), exist_ok=True)
        with open(test_case_path, 'w') as f:
            f.write(test_case)
        
        suggestions = self.lsp_server.get_import_stat_fix_suggestions(test_case_path)
        os.remove(test_case_path)

        candidate_suggested_import_stats = []
        for uri, edits in suggestions.items():
            file_path = uri.replace("file://", "")
            # compare the file path with the original test case path, but at the beginning of project name
            file_path_rel = file_path.replace(file_path.split(self.configs.project_name)[0], '')
            test_case_path_rel = test_case_path.replace(test_case_path.split(self.configs.project_name)[0], '')
            if file_path_rel != test_case_path_rel:
                # print(f'WARNING: in fix_import_stat(), edited file path is different from the original test case path. {file_path} != {test_case_path}. So retain the original test case.')
                # print(f'Edited files:\n{suggestions}\n\n')
                continue
            
            for each_edit in edits:
                candidate_suggested_import_stats += each_edit["newText"].split('\n')
            
        # filter the suggestions
        suggested_import_stats = []
        for each_suggest in candidate_suggested_import_stats:
            if len(each_suggest) == 0 or each_suggest in test_case:
                continue
            suggested_import_stats.append(each_suggest)

        return suggested_import_stats

    def run_test_case(self, test_case, test_case_path):
        def _extract_error_msg(log):
            error_msg = []
            stop_flag = False
            for each_line in log.split('\n'):
                if each_line.strip().startswith('[INFO]'):
                    continue
                if each_line.strip().startswith('[main]'):
                    continue
                if each_line.strip().startswith('[WARNING]'):
                    continue
                
                if each_line.strip().startswith('[ERROR] Tests run:'):
                    if stop_flag:
                        break
                    else:
                        stop_flag = True
                
                if each_line.strip().startswith('[ERROR] To see the full stack trace'):
                    break

                error_msg.append(each_line)

            error_msg = '\n'.join(error_msg)
            return error_msg

        compile_log, test_log, compile_success, execute_success = self.test_runner.compile_and_execute_test_case(test_case, test_case_path) 

        if not compile_success:
            error_msg = _extract_error_msg(compile_log)
            test_status = 'fail_compile'
        elif not execute_success:
            error_msg = _extract_error_msg(test_log)
            test_status = 'fail_execute'

            test_run_info = re.search(r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)', test_log)
            if test_run_info is not None:
                test_run_info = test_run_info.groups()

                if int(test_run_info[0]) > 1:
                    print(f'[INFO] Multiple test methods in a single test case: {test_case_path}')

                success = int(test_run_info[0]) - int(test_run_info[1]) - int(test_run_info[2]) - int(test_run_info[3])
                if success > 0:
                    test_status = 'success'
                    error_msg = ""
                elif int(test_run_info[1]) > 0:
                    test_status = 'fail_pass'
                else:
                    test_status = 'fail_execute'

        else:
            error_msg = ""
            test_status = 'success'

        return error_msg, test_status