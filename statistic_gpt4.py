import os
import re
import json
import evaluate

from codebleu import calc_codebleu


class StatisticKG():
    def __init__(self, test_case_log_and_coverage_save_path, specified_target_coverage_ids: list=None):
        self.specified_target_coverage_ids = specified_target_coverage_ids
        self.test_case_log_analysis = self.analyze_test_case_run_logs(test_case_log_and_coverage_save_path)

    def analyze_test_case_run_logs(self, test_case_log_and_coverage_save_path):
        with open(test_case_log_and_coverage_save_path, 'r') as f:
            test_case_log_and_cov = json.load(f)

        specified_test_case_log_and_cov = []
        if self.specified_target_coverage_ids is not None:
            self.specified_target_coverage_ids = [str(each_id) for each_id in self.specified_target_coverage_ids]
            for each_tc_log_cov in test_case_log_and_cov:
                if str(each_tc_log_cov['target_coverage_idx']) in self.specified_target_coverage_ids:
                    specified_test_case_log_and_cov.append(each_tc_log_cov)
            test_case_log_and_cov = specified_test_case_log_and_cov

        test_case_log_analysis = []
        for each_tc_log_cov in test_case_log_and_cov:
            log_path = each_tc_log_cov[f'log_path_rag_ref']
            if log_path is not None:
                result_type = self._analyze_tc_run_log(log_path)
                each_tc_log_cov[f'result'] = result_type
            else:
                each_tc_log_cov[f'result'] = None

            test_case_log_analysis.append(each_tc_log_cov)
        return test_case_log_analysis

    def _analyze_tc_run_log(self, log_path):
        # return: 'SUCCESS', 'FAIL_COMPILE', 'FAIL_EXECUTE', 'UNKNOWN'
        with open(log_path, 'r') as f:
            running_log = f.read()
        log_name = os.path.basename(log_path)

        # execution success
        test_run_info = re.search(r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)', running_log)
        if test_run_info is not None:
            test_run_info = test_run_info.groups()

            if int(test_run_info[0]) > 1:
                print(f'[INFO] Multiple test methods in a single test case: {log_name}')

            success = int(test_run_info[0]) - int(test_run_info[1]) - int(test_run_info[2]) - int(test_run_info[3])
            if success > 0:
                return 'SUCCESS'
            elif int(test_run_info[1]) > 0:
                return 'FAIL_PASS'
            else:
                return 'FAIL_EXECUTE'
        elif 'COMPILATION ERROR' in running_log:
            return 'FAIL_COMPILE'
        elif 'BUILD FAILURE' in running_log:
            return 'FAIL_EXECUTE'
        else:
            print(f'[WARNING] Unknown error type: {log_name}')
            return 'UNKNOWN'

    def count_test_case_pass(self):
        success_pass, fail_compile, fail_execute, fail_pass, unknown = self._count_test_case_pass()
        print(f'Fail Compile: {len(fail_compile)}, Fail Execute: {len(fail_execute)}, Fail Test: {len(fail_pass)}, Unknown: {len(unknown)}, Success Pass: {len(success_pass)}\n')

    def _count_test_case_pass(self):
        success_pass, fail_compile, fail_execute, fail_pass, unknown = [], [], [], [], []
        for each_tc_log_cov in self.test_case_log_analysis:
            result_type = each_tc_log_cov[f'result']
            if result_type == 'SUCCESS':
                # check whether consistent with the result obtained during generation.
                if each_tc_log_cov['running_result'] != 'success':
                    print(f'[WARNING] [TargetCoverageIdx: {each_tc_log_cov["target_coverage_idx"]}] In generation: {each_tc_log_cov["running_result"]}; In running: {result_type}')
                success_pass.append(each_tc_log_cov)
            elif result_type == 'FAIL_COMPILE':
                if each_tc_log_cov['running_result'] != 'fail_compile':
                    print(
                        f'[WARNING] [TargetCoverageIdx: {each_tc_log_cov["target_coverage_idx"]}] In generation: {each_tc_log_cov["running_result"]}; In running: {result_type}')
                fail_compile.append(each_tc_log_cov)
            elif result_type == 'FAIL_EXECUTE':
                if each_tc_log_cov['running_result'] != 'fail_execute':
                    print(f'[WARNING] [TargetCoverageIdx: {each_tc_log_cov["target_coverage_idx"]}] In generation: {each_tc_log_cov["running_result"]}; In running: {result_type}')
                fail_execute.append(each_tc_log_cov)
            elif result_type == 'FAIL_PASS':
                if each_tc_log_cov['running_result'] != 'fail_pass':
                    print(f'[WARNING] [TargetCoverageIdx: {each_tc_log_cov["target_coverage_idx"]}] In generation: {each_tc_log_cov["running_result"]}; In running: {result_type}')
                fail_pass.append(each_tc_log_cov)
            elif result_type == 'UNKNOWN':
                unknown.append(each_tc_log_cov)
            else:
                raise ValueError(f'Unknown result type: {result_type}')
        return success_pass, fail_compile, fail_execute, fail_pass, unknown
    
    def cal_bleu_for_test_cases(self, is_pass: bool=False, is_common: bool=False):
        test_case_rag_ref_target_pairs = self.load_test_cases(is_pass=is_pass)

        print(f'\n\nBLEU-4 Analysis: is_pass={is_pass}, is_common={is_common}')
        print(f'rag_ref: {len(test_case_rag_ref_target_pairs)}')

        bleu_with_rag_ref = self.cal_bleu(test_case_rag_ref_target_pairs)
        print(f'BLEU-4 with RAG reference: {bleu_with_rag_ref:.4f}\n')

        return bleu_with_rag_ref
    
    def cal_codebleu_for_test_cases(self, is_pass: bool=False, is_common: bool=False):
        test_case_rag_ref_target_pairs = self.load_test_cases(is_pass=is_pass)

        print(f'\n\nCodeBLEU Analysis: is_pass={is_pass}, is_common={is_common}')
        print(f'rag_ref: {len(test_case_rag_ref_target_pairs)}')

        bleu_with_rag_ref = self.cal_codebleu(test_case_rag_ref_target_pairs)
        print(f'CodeBLEU with RAG reference: {bleu_with_rag_ref:.4f}\n')

        return bleu_with_rag_ref
    
    def cal_codebleu(self, generated_target_pairs):
        generated_test_cases, target_test_cases = [], []
        for each_pair in generated_target_pairs:
            generated_test_cases.append(each_pair[0])
            target_test_cases.append(each_pair[1])

        codebleu_score = calc_codebleu(references=target_test_cases, predictions=generated_test_cases, lang='java')
        codebleu_score = codebleu_score['codebleu']
        return codebleu_score

    def load_test_cases(self, is_pass: bool=False, return_focal_method=False, is_ref = "all"):
        test_case_rag_ref_target_pairs = []
        for each_test_case in self.test_case_log_analysis:

            target_test_case = each_test_case['target_test_case']
            test_case_rag_ref = each_test_case['generated_test_case']
            fm_name = each_test_case['focal_method_name']
            
            if (not is_pass) or each_test_case['result'] == 'SUCCESS':
                rag_ref_pair = [test_case_rag_ref, target_test_case]
                if return_focal_method:
                    rag_ref_pair.append(fm_name)
                test_case_rag_ref_target_pairs.append(rag_ref_pair)
            
        return test_case_rag_ref_target_pairs

    def print_negative_rag_ref_pass(self):
        print('\n\nNegative RAG Reference: ')

        for each_tc_log_cov in self.test_case_log_analysis:
            if each_tc_log_cov['result_no_ref'] == 'SUCCESS' and each_tc_log_cov['result_rag_ref'] != 'SUCCESS':
                # print(f'- no_ref:\n{each_tc_log_cov["generation_no_ref"]}')
                print(f'- rag_ref:\n{each_tc_log_cov["generation_rag_ref"]}\n')
                for each_ref in each_tc_log_cov['rag_references']:
                    print(f'- rag_ref score: {each_ref[0]}\n')
                    print(f'- rag_ref coverage:\n{each_ref[1]}\n')
                    print(f'- rag_ref test case:\n{each_ref[2]}\n')
                    print('-'*50)
                print('='*50)
    
    def print_positive_rag_ref_pass(self):
        print('\n\nPositive RAG Reference: ')
        pos_tc_log_cov = self.get_positive_rag_ref_pass()
        for each_tc_log_cov in pos_tc_log_cov:
            print(f'- focal_method:\n{each_tc_log_cov["target_coverage"]}')
            print(f'- no_ref:\n{each_tc_log_cov["generation_no_ref"]}')
            print(f'- rag_ref:\n{each_tc_log_cov["generation_rag_ref"]}\n')
            for each_ref in each_tc_log_cov['rag_references']:
                print(f'- rag_ref score: {each_ref[0]}\n')
                print(f'- rag_ref coverage:\n{each_ref[1]}\n')
                print(f'- rag_ref test case:\n{each_ref[2]}\n')
                print('-'*50)
            print('='*50)

    def get_positive_rag_ref_pass(self):
        pos_tc_log_cov = []
        for each_tc_log_cov in self.test_case_log_analysis:
            if each_tc_log_cov['result_no_ref'] != 'SUCCESS' and each_tc_log_cov['result_rag_ref'] == 'SUCCESS':
                pos_tc_log_cov.append(each_tc_log_cov)
        return pos_tc_log_cov

    def get_negative_rag_ref_compilation(self):
        compilation_error_type = ['cannot find symbol',]
        unknow_types = []
        negative_rag_ref_compilation = []
        each_error_type_count = {error_type: 0 for error_type in compilation_error_type}

        print('\n\nRAG Fail Compilation but NoRAG Success Compilation: ')
        for each_tc_log_cov in self.test_case_log_analysis:
            if each_tc_log_cov['result_no_ref'] != 'FAIL_COMPILE' and each_tc_log_cov['result_rag_ref'] == 'FAIL_COMPILE':
                negative_rag_ref_compilation.append(each_tc_log_cov)
        
        # count the error types
        for each_tc_log_cov in negative_rag_ref_compilation:
            log_path = each_tc_log_cov['log_path_rag_ref']
            with open(log_path, 'r') as f:
                running_log = f.readlines()
            
            is_unknow_type = True
            for error_type in compilation_error_type:
                for each_line in running_log:
                    if error_type in each_line:
                        each_error_type_count[error_type] += 1
                        is_unknow_type = False
                        break
            if is_unknow_type:
                unknow_types.append(log_path)

        print(f'Negative RAG Ref Compilation in Total: {len(negative_rag_ref_compilation)}')
        print(f'Error Type Count:\n{each_error_type_count}\n\n')
        print(f'Unknown error types: {unknow_types}')

        # print the negative rag ref compilation
        for each_tc_log_cov in negative_rag_ref_compilation:
            print(f'- target_focal_method:\n{each_tc_log_cov["target_coverage"]}')
            print(f'- target_test_case:\n{each_tc_log_cov["target_test_case"]}')

            print(f'- no_ref log_path:\n{each_tc_log_cov["log_path_no_ref"]}')
            print(f'- no_ref generation:\n{each_tc_log_cov["generation_no_ref"]}\n')

            print(f'- rag_ref log_path:\n{each_tc_log_cov["log_path_rag_ref"]}')
            print(f'- rag_ref generation:\n{each_tc_log_cov["generation_rag_ref"]}\n')

            for each_ref in each_tc_log_cov['rag_references']:
                print('-'*50)
                print(f'+ rag_ref score: {each_ref[0]}\n')
                print(f'+ rag_ref coverage:\n{each_ref[1]}\n')
                print(f'+ rag_ref test case:\n{each_ref[2]}\n')
            print('='*50)


    def cal_bleu(self, generated_target_pairs):
        generated_test_cases, target_test_cases = [], []
        for each_pair in generated_target_pairs:
            generated_test_cases.append(each_pair[0])
            target_test_cases.append(each_pair[1])

        bleu = evaluate.load('bleu')
        bleu_score = bleu.compute(predictions=generated_test_cases, references=target_test_cases)
        bleu_4 = bleu_score['precisions'][3]

        return bleu_4
    
    def get_filtered_coverages(self, is_ref, n_cover_line_threshold: int=1, is_common: bool=False):
        assert n_cover_line_threshold > 0

        coverages = []
        for each_tc_cov in self.test_case_log_analysis:
            if each_tc_cov['coverage_focal_file'] is None:
                continue

            target_coverage = each_tc_cov['target_coverage']
            if target_coverage.count('<COVER>') < n_cover_line_threshold:
                continue

            coverages.append(each_tc_cov)

        return coverages
                
    def analyze_coverage_with_target_coverage(self, is_ref, n_cover_line_threshold: int=1, is_common: bool=False):
    # the test case is generated for a given target Coverage. thus this method how many specified lines in the target coverage are covered by the generated test case.
    # Args:
    #     is_ref: str, ['no_ref', 'human_ref', 'rag_ref']
    #     n_cover_line_threshold: int, the minimum number of covered lines in the target coverage.
    #     is_common: bool, whether to analyze the common coverage.
        assert is_ref in ['no_ref', 'rag_ref', 'all']
        assert n_cover_line_threshold > 0
        
        coverages = self.get_filtered_coverages(is_ref, n_cover_line_threshold, is_common=is_common)

        print(f'\n\nCoverage Analysis: Threshold={n_cover_line_threshold}\n')

        if len(coverages) == 0:
            print(f'No target coverages meet the requirements.')
            return
        
        is_ref_coverage = []
        for each_cov in coverages:
            target_coverage = each_cov['target_coverage']
            focal_file_coverage = each_cov['coverage_focal_file']
            focal_method_name = each_cov['focal_method_name']
            is_ref_coverage.append({'target_coverage': target_coverage, 'focal_file_coverage': focal_file_coverage, 'focal_method_name': focal_method_name})

        self._analyze_coverage(is_ref_coverage)
    
    def analyze_coverage_with_target_focal_method(self, is_ref, n_cover_line_threshold: int=1, is_common: bool=False):
        # the test case is generated for a given target Focal Method. thus this method how many lines in the focal method are covered by the generated test case.
        # Args:
        #     is_ref: str, ['no_ref', 'human_ref', 'rag_ref']
        #     n_cover_line_threshold: int, the minimum number of covered lines in the target focal method (all lines will be tagged <COVER>).
        #     is_common: bool, whether to analyze the common coverage.

        assert is_ref in ['no_ref', 'rag_ref']
        assert n_cover_line_threshold > 0
        print(f'\nCoverage Analysis: is_ref={is_ref}, Threshold={n_cover_line_threshold}, is_common={is_common}')  

        line_coverages = []        
        branch_coverages = []
        for each_cov in self.test_case_log_analysis:
            coverage_fm = each_cov[f'coverage_focal_method']
            if coverage_fm is None:
                continue
            
            if 'number_of_lines' not in coverage_fm:
                print(f'[WARNING] coverage_focal_method does not contain number_of_lines. maybe need manual identify from raw_html')
                continue

            number_of_lines = int(coverage_fm['number_of_lines'])
            if number_of_lines < n_cover_line_threshold:
                continue

            if is_common:
                if each_cov['result_no_ref'] != 'SUCCESS' or each_cov['result_rag_ref'] != 'SUCCESS':
                    continue

            line_coverages.append(coverage_fm['line_coverage'])
            if coverage_fm['number_of_branches'] > 0:
                branch_coverages.append(coverage_fm['branch_coverage'])
        
        if len(branch_coverages) > 0:
            print(f'Line Coverage ({len(line_coverages)} coverages): {sum(line_coverages)/len(line_coverages):.2f}%')
        else:
            print(f'Line Coverage: N/A')

        if len(branch_coverages) > 0:
            print(f'Branch Coverage ({len(branch_coverages)} coverages): {sum(branch_coverages)/len(branch_coverages):.2f}%')
        else:
            print(f'Branch Coverage: N/A')

    def _analyze_coverage(self, coverages):
        exact_match_cases, fully_cover_cases, cover_ratio_list = [], [], []
        for cov_info in coverages:
            target_focal_method_coverage = cov_info['target_coverage']
            focal_file_coverage = cov_info['focal_file_coverage']
            focal_method_name = cov_info['focal_method_name']
            focal_method_name = focal_method_name.split('::::')[1]

            is_exact_match, is_fully_cover, cover_ratio = self._analyze_cov(target_focal_method_coverage, focal_file_coverage, focal_method_name)

            exact_match_cases.append(is_exact_match)
            fully_cover_cases.append(is_fully_cover)
            cover_ratio_list.append(cover_ratio)

        avg_exact_match = sum(exact_match_cases) / len(exact_match_cases)
        avg_cover = sum(fully_cover_cases) / len(fully_cover_cases)
        avg_cover_ratio = sum(cover_ratio_list) / len(cover_ratio_list)
        
        print(f'Exact Match: {avg_exact_match:.2%} ({sum(exact_match_cases)}/{len(exact_match_cases)})')
        print(f'Fully Cover: {avg_cover:.2%} ({sum(fully_cover_cases)}/{len(fully_cover_cases)})')
        print(f'Cover Ratio: {avg_cover_ratio:.2%}')
    
    def _analyze_cov(self, target_focal_method_coverage, focal_file_coverage, focal_method_name, return_fm_cov=False):        
        generated_focal_method_coverage = self.get_generated_focal_method_coverage(focal_file_coverage, target_focal_method_coverage, focal_method_name)

        is_exact_match, is_fully_cover, cover_ratio = self.eval_generated_coverage(generated_focal_method_coverage, target_focal_method_coverage)

        if return_fm_cov:
            return is_exact_match, is_fully_cover, cover_ratio, generated_focal_method_coverage
        else:
            return is_exact_match, is_fully_cover, cover_ratio

    def get_generated_focal_method_coverage(self, focal_file_coverage, target_coverage, focal_method_name):
        focal_file = focal_file_coverage.strip().replace('<COVER>', '')
        focal_method = target_coverage.strip().replace('<COVER>', '')
        focal_file_lines = focal_file.split('\n')
        focal_method_lines = focal_method.split('\n')

        possible_fm_start_indices = []
        for ff_line_idx in range(len(focal_file_lines)):
            if focal_file_lines[ff_line_idx].strip() == focal_method_lines[0].strip() and focal_file_lines[ff_line_idx+1].strip() == focal_method_lines[1].strip():
                possible_fm_start_indices.append(ff_line_idx)

        for each_possible_idx in possible_fm_start_indices:
            possible_gen_fm_cov = focal_file_coverage.strip().split('\n')[each_possible_idx: each_possible_idx+len(focal_method_lines)]
            possible_gen_fm_cov = '\n'.join(possible_gen_fm_cov)

            # check 
            is_succes_match = True
            possible_fm_lines = possible_gen_fm_cov.replace('<COVER>', '').split('\n')
            for line_idx in range(len(possible_fm_lines)):
                if possible_fm_lines[line_idx].strip() != focal_method_lines[line_idx].strip():
                    is_succes_match = False
                    break
            if is_succes_match:
                break
        
        if not is_succes_match:
            print(f'focal_method_name: {focal_method_name}')
            print(f'focal_file_coverage: {focal_file_coverage}')
            print(f'possible_fm_start_indices: {possible_fm_start_indices}')
            print(f'target_coverage: {target_coverage}')
            raise ValueError(f'fail to determine generated coverage.')

        return possible_gen_fm_cov
    
    def eval_generated_coverage(self, generated_focal_method_coverage, target_focal_method_coverage):
        covered_lines_generated = []
        for line_idx, line in enumerate(generated_focal_method_coverage.split('\n')):
            if '<COVER>' in line:
                covered_lines_generated.append(line_idx)

        covered_lines_target = []
        for line_idx, line in enumerate(target_focal_method_coverage.split('\n')):
            if '<COVER>' in line:
                covered_lines_target.append(line_idx)

        is_exact_match = 1 if covered_lines_generated == covered_lines_target else 0

        covered_lines_set_generated, covered_lines_set_target = set(covered_lines_generated), set(covered_lines_target)
        is_fully_cover = 1 if covered_lines_set_generated >= covered_lines_set_target else 0

        cover_ratio = len(covered_lines_set_generated & covered_lines_set_target) / len(covered_lines_set_target)

        return is_exact_match, is_fully_cover, cover_ratio


if __name__ == '__main__':
    from configs import Configs

    configs = Configs('blade/blade-kit')
