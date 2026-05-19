import os
import re
import json
import difflib
import time
from parser.java_code_parser import JavaCodeParser
from LSPs.java_lsp import JavaLanguageServer
from openai import OpenAI

GPT_KEY = ''
GPT_BASE_URL = ''

DEEPSEEK_KEY = ''
DEEPSEEK_BASE_URL = ''


class Agent:
    def __init__(self, llm_name: str):
        self.system_prompt = None

        if llm_name == 'gpt-4o':
            # GPT-4o 
            os.environ['OPEN_AI_KEY'] = GPT_KEY
            os.environ['OPENAI_BASE_URL'] = GPT_BASE_URL
            self.model_name = 'gpt-4o-2024-08-06'
        elif llm_name in ('deepseek-7B', 'deepseek-32B'):
            # DeepSeek-R1-Distill-Qwen-7B
            # deploy using `vllm serve deepseek-ai/DeepSeek-R1-Distill-Qwen-7B --tensor-parallel-size 1 --max-model-len 10240 --enforce-eager --host 0.0.0.0 --port 12030 --served-model-name deepseek-7B`
            port = 12030
            os.environ['OPEN_AI_KEY'] = DEEPSEEK_KEY
            os.environ['OPENAI_BASE_URL'] = DEEPSEEK_BASE_URL
            self.model_name = llm_name
        elif llm_name == 'deepseek-infra':  # deepseek-32B API
            os.environ['OPEN_AI_KEY'] = DEEPSEEK_KEY
            os.environ['OPENAI_BASE_URL'] = f"https://api.deepinfra.com/v1/openai"
            self.model_name = DEEPSEEK_BASE_URL
        elif llm_name == 'gpt-3.5':
            os.environ['OPEN_AI_KEY'] = GPT_KEY
            os.environ['OPENAI_BASE_URL'] = GPT_BASE_URL
            self.model_name = 'gpt-3.5-turbo'
        elif llm_name == 'gpt-5-mini':
            os.environ['OPEN_AI_KEY'] = GPT_KEY
            os.environ['OPENAI_BASE_URL'] = GPT_BASE_URL
            self.model_name = 'gpt-5-mini'
        elif llm_name == 'gpt-o4-mini':
            os.environ['OPEN_AI_KEY'] = GPT_KEY
            os.environ['OPENAI_BASE_URL'] = GPT_BASE_URL
            self.model_name = 'o4-mini-2025-04-16'
        elif llm_name == 'deepseek-v3.2':
            os.environ['OPEN_AI_KEY'] = DEEPSEEK_KEY
            os.environ['OPENAI_BASE_URL'] = DEEPSEEK_BASE_URL
            self.model_name = 'deepseek-v3.2'
        else:
            raise ValueError(f"Unknown LLM name: {llm_name}")

        self.client = OpenAI(
            api_key=os.environ.get('OPEN_AI_KEY'), 
            base_url=os.environ.get('OPENAI_BASE_URL')
            )
        self.temp = 0.0  # for GPT-4o. For DeepSeek-R1-Distill-Qwen-7B, the temperature is fixed to 0.5
        self.top_p = 0.1
        self.seed = 1203
        self.max_completion_tokens = 10240
        if self.model_name == 'deepseek-v3.2':
            self.max_completion_tokens = 8000

    def get_response(self, messages, n=1, skip_deepseek_think: bool=False):
        if self.model_name in ('gpt-4o-2024-08-06', 'gpt-3.5-turbo', 'gpt-5-mini'):
            if self.system_prompt:
                messages = [{'role': 'system', 'content': self.system_prompt}] + messages
            response = self._get_gpt_response(messages, n=n)
        elif self.model_name in ('deepseek-7B', 'deepseek-32B', 'deepseek-ai/DeepSeek-R1-Distill-Qwen-32B'):
            if self.system_prompt:
                messages[0]['content'] = self.system_prompt + '\n\n\n' + messages[0]['content']
            response = self._get_deepseek_qwen_response(messages, n=n, skip_deepseek_think=skip_deepseek_think)
        elif self.model_name in ('o1-mini-2024-09-12', 'o4-mini-2025-04-16', 'o1-mini'):
            if self.system_prompt:
                messages = [{'role': 'user', 'content': self.system_prompt}] + messages
            for _attempt in range(5):
                response = self._get_gpt_o1_mini_response(messages, n=n)
                if len(response) > 0:
                    break
                print('\nsleeping for 5 seconds... Then retrying...\n\n')
                if _attempt < 4:
                    time.sleep(5)
                else:
                    print(f'response:\n\n{response}')
                    raise ValueError("Failed to get response from o-series model after multiple attempts.")
        elif self.model_name == 'deepseek-v3.2':
            if self.system_prompt:
                messages[0]['content'] = self.system_prompt + '\n\n\n' + messages[0]['content']
            response = self._get_deepseek_v_3_2_response(messages, n=n)
        else:
            raise ValueError(f"Unknown LLM name: {self.model_name}")
        return response
    
    def _get_gpt_response(self, messages, n=1):
        response = []
        max_tries = n + 2
        n_tries = 0
        while len(response) < n:
            s_time = time.time()
            try:
                print(f'\n\n{messages}\n\n')
                each_response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temp,
                    top_p=self.top_p,
                    seed=self.seed,
                    stream=False,
                    max_completion_tokens=self.max_completion_tokens,
                    n=n,
                )
            except Exception as e:
                print(f'\nError: {e}\n\n')
                n_tries += 1
                if n_tries > max_tries:
                    each_response = '```\n\n[ERROR] Failed to generate\n\n```'
                    break
                continue
            
            print(f'\nTime consuming for one generation: {time.time()-s_time:.2f} seconds\n\n\n')
            print(f'Tokens used: prompt={each_response.usage.prompt_tokens}, completion={each_response.usage.completion_tokens}')

            response.append(each_response.choices[0].message.content)

        if n == 1:
            response = response[0]

        return response

    def _get_gpt_o1_mini_response(self, messages, n=1):
        response = []
        max_tries = n + 2
        n_tries = 0
        while len(response) < n:
            s_time = time.time()
            try:
                print(f'\n\n{messages}\n\n')
                each_response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temp,
                    seed=self.seed,
                    stream=False,
                    max_completion_tokens=self.max_completion_tokens,
                    n=n,
                )
            except Exception as e:
                print(f'\nError: {e}\n\n')
                if "无可用渠道" in str(e):
                    time.sleep(2)
                    continue

                if "potentially violating our usage policy" in str(e) or 'bad response status' in str(e):  # triggered by o1-mini
                    content = messages[1]['content']
                    print(f'Content: {content}\n\n')
                    part_1, part_2 = content.split('(with some details omitted):\n```\n')
                    part_2 = part_2.split('\n```')
                    part_2_1, part_2_2 = part_2[0], '\n```'.join(part_2[1:])

                    part_2_1_lines = part_2_1.split('\n')
                    if len(part_2_1_lines) > 10:
                        part_2_1_lines = part_2_1_lines[:len(part_2_1_lines)-10]
                    else:
                        raise ValueError(f"Failed to reduce the length of the input: {part_2_1} to address:\n{e}")
                    
                    part_2_1 = '\n'.join(part_2_1_lines)
                    messages[1]['content'] = part_1 + '(with some details omitted):\n```\n' + part_2_1 + '\n```' + part_2_2

                    continue

                if "quota is not enough" in str(e):
                    time.sleep(10)
                    continue
                
                n_tries += 1
                if n_tries > max_tries:
                    each_response = '```\n\n[ERROR] Failed to generate\n\n```'
                    break
                continue
            
            print(f'\nTime consuming for one generation: {time.time()-s_time:.2f} seconds\n\n\n')
            print(f'Tokens used: prompt={each_response.usage.prompt_tokens}, completion={each_response.usage.completion_tokens}')

            response.append(each_response.choices[0].message.content)

        if n == 1:
            response = response[0]

        return response

    def _get_deepseek_qwen_response(self, messages, n=1, skip_deepseek_think: bool=False):
        response = []
        max_tries = 2
        n_tries = 0

        if skip_deepseek_think:
            messages[0]['content'] += '\n\n<think>\nSkip Thinking\n</think>\n\n'

        while len(response) < n:
            s_time = time.time()
            try:
                each_response_raw = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.6,
                    seed=self.seed,
                    stream=False,
                    max_completion_tokens=self.max_completion_tokens,
                    n=1
                )
            except Exception as e:
                # the input is too long
                if 'Please reduce the length' in str(e):
                    context_part = messages[0]['content'].split('(with some details omitted):')[1]
                    context_part = re.findall(r'```(.+?)```', context_part, re.DOTALL)[0]
                    assert len(context_part) > 0
                    # get the idx of the line whose length is the largest among all lines. can use argmax?
                    context_lines = context_part.split('\n')
                    context_lengths = [len(line.split()) for line in context_lines]
                    max_len_idx = context_lengths.index(max(context_lengths))
                    # remove the line whose length is the largest
                    context_lines.pop(max_len_idx)
                    reduced_context_part = '\n'.join(context_lines)
                    messages[0]['content'] = messages[0]['content'].replace(context_part, reduced_context_part)

                    continue

            print(f'Time consuming for one generation: {time.time()-s_time:.2f} seconds\n\n')
            print(f'[INFO] Response:\n{each_response_raw.choices[0].message.content}\n\n\n')
            
            each_response = self.remove_thinking(each_response_raw.choices[0].message.content)
            if each_response is None:
                messages[0]['content'] += '\n\n<think>\n\n</think>\n\n'
                print('Seems a too long thinking. Enforcing the model to skip thinking.\n')
                print('Messages (after modified):', messages, '\n\n\n')
                print('Response:\n', each_response_raw.choices[0].message.content, '\n\n\n')
                n_tries += 1

                if n_tries < max_tries:
                    continue
                else:
                    each_response = '```\nFailed to generate\n```'

            response.append(each_response)
        
        if n == 1:
            response = response[0]

        return response

    def _get_deepseek_v_3_2_response(self, messages, n=1):
        response = []
        max_tries = 2
        n_tries = 0

        while len(response) < n:
            s_time = time.time()
            try:
                each_response_raw = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.2,
                    seed=self.seed,
                    stream=False,
                    max_completion_tokens=self.max_completion_tokens,
                    n=1
                )
                each_response_content = each_response_raw.choices[0].message.content
            except Exception as e:
                # the input is too long
                if 'Please reduce the length' in str(e):
                    context_part = messages[0]['content'].split('(with some details omitted):')[1]
                    context_part = re.findall(r'```(.+?)```', context_part, re.DOTALL)[0]
                    assert len(context_part) > 0
                    # get the idx of the line whose length is the largest among all lines. can use argmax?
                    context_lines = context_part.split('\n')
                    context_lengths = [len(line.split()) for line in context_lines]
                    max_len_idx = context_lengths.index(max(context_lengths))
                    # remove the line whose length is the largest
                    context_lines.pop(max_len_idx)
                    reduced_context_part = '\n'.join(context_lines)
                    messages[0]['content'] = messages[0]['content'].replace(context_part, reduced_context_part)

                n_tries += 1
                if n_tries > max_tries:
                    each_response_content = '```\n\n[ERROR] Failed to generate\n\n```'
                    break
                continue

            print(f'Time consuming for one generation: {time.time()-s_time:.2f} seconds\n\n')
            print(f'[INFO] Response:\n{each_response_content}\n\n\n')
            response.append(each_response_content)
        
        if n == 1:
            response = response[0]

        return response

    def remove_thinking(self, response):
        if '</think>' not in response:
            return None
        answer = response.split('</think>')[-1].strip()
        return answer
    
    def extract_code_from_response(self, response: str):
        code = re.findall(r'```java(.*)```', response, re.DOTALL)
        if len(code) == 0:
            code = re.findall(r'```(.*)```', response, re.DOTALL)
            if len(code) == 0:
                print(f"[Warning] The response does not contain any code: {response}")
                return " "  # TODO: refine this process
                
        if len(code) > 1:
            print(f'WARNING: The response contains multiple code blocks:\n{response}\n\n')

        code = code[0].strip()
        return code

    def add_line_numbers(self, content):
        lines = content.split('\n')
        for i in range(len(lines)):
            lines[i] = f'{i+1}:{lines[i]}'
        return '\n'.join(lines)
    
    def remove_line_numbers(self, content):
        lines = content.split('\n')
        removed_lines = []
        for line in lines:
            removed_lines.append(self.remove_single_line_number(line))
        return '\n'.join(removed_lines)
    
    def remove_single_line_number(self, line):
        marker_index = line.find(':')
        return line[marker_index+1:]


class TestDescAgent(Agent):
    def __init__(self, llm_name: str):
        super().__init__(llm_name)
    
    def generate_test_desc(self, test_case, focal_method):
        prompt = self.construct_prompt(test_case, focal_method)
        messages = [{'role': 'user', 'content': prompt}]

        for _ in range(3):
            response = self.get_response(messages)
            is_success = self.check_generation(response)
            if is_success:
                break
        if is_success:
            response = self.polish_test_desc(response)
        else:
            print(f'WARNING: The generated test description does not follow the expected format:\n{response}\n\n')

        return response

    def construct_prompt(self, test_case, focal_method):
        instruction = f"""# Test Case\n```\n{test_case}\n```\n\n# Focal Method\n```\n{focal_method}\n```\n\n# Objective\n// Identifies and briefly describes the special focus or objective of #Test Case#. \n\n# Preconditions\n// Describes the required state of the test environment and test data and any special constraints pertaining to the execution of #Test Case#. Also, specifies each action required to bring the test item into a state where the expected result can be compared to the actual results. The level of detail provided by the descriptions should be tailored to fit the knowledge of the test executors.\n\n# Expected Results\n// Specifies the expected outputs and behaviour required of the test item in response to the inputs that are given to the test item when it is in its precondition state. Provides the expected values (with tolerances where appropriate) for each required output.\n\n# Instruction\nPlease generate the #Objective#, #Preconditions#, and #Expected Results# of #Test Case#.\nEnsure that the output follows the expected format:\n```\n# Objective\n...\n\n# Preconditions\n1. ...\n2. ...\n...\n\n# Expected Results\n1. ...\n2. ...\n...\n```\n\n# Requirements\n1. The length of #Objective# must be less than fifty words.\n2. The total length of #Preconditions# and #Expected Results# must be less than two hundred words.\n3. The program elements in #Objective#, #Preconditions#, and #Expected Results# must be enclosed by a pair of backticks, such as `ClassA` and `methodInov()`.\n4. Ensure the #Objective#, #Preconditions#, and #Expected Results# are written in a natural, human-like manner. MUST avoid containing many program elements; instead, use clear and natural language."""

        return instruction

    def polish_test_desc(self, test_desc):
        prompt = f"""# Test Case Description\n```\n{test_desc}\n```\n\n# Instruction\nRewrite the #Test Case Description# to make it more natural and human-like by translating the program elements (enclosed by `) to natural language descprition.\nFor example:\n1. Split the camel words and then transform them from program elements to natural language descriptions (such as `IpAddress` -> ip address).\n2. Using natural language to describe invocation (such as `Obj.getPrefix(Param)` -> get the prefix of Param, and `program.version=0.1` -> version of program is 0.1).\n\nAdditionally, ensure that the output follows the expected format:\n```\n# Objective\n...\n\n# Preconditions\n1. ...\n2. ...\n...\n\n# Expected Results\n1. ...\n2. ...\n...\n```\n\n# Requirements\n1. The length of #Objective# must be less than fifty words.\n2. The total length of #Preconditions# and #Expected Results# must be less than two hundred words."""

        messages = [{'role': 'user', 'content': prompt}]

        new_test_desc = test_desc
        for _ in range(2):
            response = self.get_response(messages)
            is_success = self.check_generation(response)
            if is_success:
                new_test_desc = response
                break
        return new_test_desc

    def check_generation(self, desc):
        n_obj = desc.count('# Objective')
        n_pre = desc.count('# Preconditions')
        n_exp = desc.count('# Expected Results')
        if n_obj == 1 and n_pre == 1 and n_exp == 1:
            return True
        else:
            return False

class TestGenAgent(Agent):
    def __init__(self, llm_name: str, project_name: str, project_url: str, n_responses: int=1, skip_deepseek_think: bool=False):
        super(TestGenAgent, self).__init__(llm_name)
        self.n_responses = n_responses
        self.skip_deepseek_think = skip_deepseek_think
        self.gen_prefix = '```package '
        self.gen_suffix = '```'
        self.system_prompt = f"""You may have memorized information from the GitHub repository '{project_name}' (URL is {project_url}). For this task, you must not use any of that memorized information in your responses. Instead, base your answers exclusively on the context I provide in the document. During your thinking, you must double-check all program elements within the context. If your response would otherwise rely on memorized '{project_name}' data, replace that content with generic or random information unrelated to '{project_name}'."""

    def generate_test_case(self, target_focal_method, target_context, target_test_class_name, target_test_desc, referable_test: str, facts: str, junit_version: str, forbid_using_facts: bool=False):
        prompt = self.construct_prompt(target_focal_method, target_context, target_test_class_name, target_test_desc, referable_test, facts, junit_version, forbid_using_facts)
        messages = [{'role': 'user', 'content': prompt}]        
        
        raw_response = self.get_response(messages, n=self.n_responses, skip_deepseek_think=self.skip_deepseek_think)

        if self.n_responses == 1:
            raw_response = [raw_response]
        
        generated_tc_list = [self.extract_code_from_response(each) for each in raw_response]
        return generated_tc_list, prompt

    def construct_prompt(self, target_focal_method, target_context, target_test_class_name, target_test_desc, referable_test: str, facts: list, junit_version: str, forbid_using_facts: bool=False):
        instruction = f"""# Target Focal Method\n```\n{target_focal_method}\n```\n\n# Target Focal Method Context\nThe Target Focal Method belongs to the following class (with some details omitted):\n```\n{target_context}\n```\n\n# Target Test Case\n// A JUnit {junit_version} test case to be generated, whose class name is {target_test_class_name}.\n\n# Target Test Case Description\n```\n{target_test_desc}\n```\n\n"""

        if referable_test:
            instruction += f"""# Referable Test Case\n```\n{referable_test}\n```\n\n"""
        
        if facts:
            facts_str = '\n\n'.join([f'## Fact {i+1}:\n{each}' for i, each in enumerate(facts)])
            if forbid_using_facts:
                facts_str = facts_str.replace('## Fact ', '## API ')
                instruction += f"""# Prohibited APIs\nMUST NOT include the following APIs in the generated #Target Test Case#\n```\n{facts_str}\n```\n\n"""
            else:
                instruction += f"""# Relevant Project Information\n```\n{facts_str}\n```\n\n"""

        instruction += f"""# Instruction\nPlease generate ONE #Target Test Case# for #Target Focal Method# by strictly following #Target Test Case Description#"""
        
        if referable_test or (facts and not forbid_using_facts):
            instruction += f""" and referring to """

        if referable_test:
            instruction += f"""#Referable Test Case#"""

        if facts:
            instruction = instruction + " and " if referable_test else instruction
            if forbid_using_facts:
                instruction += f"""#Prohibited APIs#.\nNOTE: #Prohibited APIs# contains the APIs that MUST NOT be included in your generated #Target Test Case#.\n\n"""
            else:
                instruction += f"""#Relevant Project Information#.\nNOTE: #Relevant Project Information# contains key facts about the project. These facts MUST be FULLY reflected in your generated #Target Test Case#.\n\n"""
            
        else:
            instruction += ".\n\n"
        
        instruction += f"""# Output Requirements\nYour final output must contain only ONE test method annotated `@Test`, omit comments, and strictly adhere to the following format:\n1: Begin with the exact prefix: "{self.gen_prefix}".\n2: End with the exact suffix: "{self.gen_suffix}".\nEnsure that no additional text appears before the prefix or after the suffix."""

        return instruction


class TestRefineAgent(Agent):
    def __init__(self, llm_name: str, project_name: str, project_url: str, n_responses, skip_deepseek_think: bool=False):
        super().__init__(llm_name)
        self.n_responses = n_responses
        self.skip_deepseek_think = skip_deepseek_think
        self.gen_prefix = '```package '
        self.gen_suffix = '```'
        self.system_prompt = f"""You may have memorized information from the GitHub repository '{project_name}' (URL is {project_url}). For this task, you must not use any of that memorized information in your responses. Instead, base your answers exclusively on the context I provide in the document. During your thinking, you must double-check all program elements within the context. If your response would otherwise rely on memorized '{project_name}' data, replace that content with generic or random information unrelated to '{project_name}'."""
    
    def refine(self, gen_test_case, error_msg, target_focal_method, target_context, target_test_case_desc, referable_test_case, facts: list, forbid_using_facts: bool=False):
        prompt = self.construct_prompt(gen_test_case, error_msg, target_focal_method, target_context, target_test_case_desc, referable_test_case, facts, forbid_using_facts)
        messages = [{'role': 'user', 'content': prompt}]

        raw_response = self.get_response(messages, n=self.n_responses, skip_deepseek_think=self.skip_deepseek_think)

        if self.n_responses == 1:
            raw_response = [raw_response]
        
        generated_tc_list = [self.extract_code_from_response(each) for each in raw_response]
        return generated_tc_list, prompt

    def construct_prompt(self, gen_test_case, error_msg, target_focal_method, target_context, target_test_desc, referable_test_case, facts: list, forbid_using_facts: bool=False):
        instruction = f"""# Target Focal Method\n```\n{target_focal_method}\n```\n\n# Target Focal Method Context\nThe Target Focal Method belongs to the following class (with some details omitted):\n```\n{target_context}\n```\n\n# Target Test Case Description\n```\n{target_test_desc}\n```\n\n# Referable Test Case\n```\n{referable_test_case}\n```\n\n"""
        
        if facts:
            facts_str = '\n\n'.join([f'## Fact {i+1}:\n{each}' for i, each in enumerate(facts)])
            if forbid_using_facts:
                facts_str = facts_str.replace('## Fact ', '## API ')
                instruction += f"""# Prohibited APIs\nMUST NOT include the following APIs in the generated #Target Test Case#\n```\n{facts_str}\n```\n\n"""
            else:
                instruction += f"""# Relevant Project Information\n```\n{facts_str}\n```\n\n"""

        instruction += f"""# Generated Target Test Case\n```\n{gen_test_case}\n```\n\n# Error Message\nWhen compiling and executing #Generated Target Test Case#, encounter the following errors:\n```\n{error_msg}\n```\n\n"""

        instruction += f"""# Instruction\nPlease modify #Generated Target Test Case# to resolve the errors shown in #Error Message#. """
        
        if facts:
            if forbid_using_facts:
                instruction += f"""NOTE: #Prohibited APIs# contains the APIs that MUST NOT be included in your generated #Target Test Case#.\n\n"""
            else:
                instruction += f"""#Relevant Project Information# provides some key facts in the project that MUST be considered to resolve the errors.\n\n"""
        else:
            instruction += "\n\n"
        
        instruction += f"""# Output Requirements\nYour final output must strictly adhere to the following format:\n1: Begin with the exact prefix: "{self.gen_prefix}".\n2: End with the exact suffix: "{self.gen_suffix}".\nEnsure that no additional text appears before the prefix or after the suffix."""

        return instruction