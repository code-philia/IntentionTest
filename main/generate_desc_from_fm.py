import argparse
import json
import os
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from configs import Configs
from dataset import Dataset
from tqdm import tqdm


GPT_KEY = ''
GPT_BASE_URL = ''


class TestDesc(BaseModel):
    # # Requirements\n1. The length of Objective must be less than fifty words.\n2. The total length of Preconditions and Expected Results must be less than two hundred words.\n3. The program elements in Objective, Preconditions, and Expected Results must be enclosed by a pair of backticks, such as `ClassA` and `methodInov()`.\n4. Ensure the Objective, Preconditions, and Expected Results are written in a natural, human-like manner. MUST avoid containing many program elements; instead, use clear and natural language.
    objective: str = Field(..., description="The objective of the test case. Less than fifty words. Written in a natural, human-like manner. MUST avoid containing many program elements; instead, use clear and natural language.")
    preconditions: str = Field(..., description="The preconditions of the test case. Part of the total two hundred words limit with expected results. Written in a natural, human-like manner. MUST avoid containing many program elements; instead, use clear and natural language.")
    exp_results: str = Field(..., description="The expected results of the test case. Part of the total two hundred words limit with preconditions. Written in a natural, human-like manner. MUST avoid containing many program elements; instead, use clear and natural language.")


class ListOfTestDesc(BaseModel):
    test_descriptions: list[TestDesc] = Field(..., description="A list of test descriptions.")


class TestDescGenerator:
    def __init__(self, llm_name: str):
        self.llm_name = llm_name

        custom_client = OpenAI(
                api_key=GPT_KEY, base_url=GPT_BASE_URL
            )
        self.client = instructor.from_openai(custom_client)
        
    def generate_test_desc_list(self, focal_method: str, context: str) -> ListOfTestDesc:
        test_desc_prompt = self.construct_prompt(focal_method, context)
        response = self.client.chat.completions.create(
            model=self.llm_name,
            response_model=ListOfTestDesc,
            messages=[
                {
                    "role": "user",
                    "content": test_desc_prompt
                }
            ],
            temperature=0.1,
            max_tokens=10240,
        )

        test_descs = [f'# Objective\n{desc.objective}\n\n# Preconditions\n{desc.preconditions}\n\n# Expected Results\n{desc.exp_results}\n' for desc in response.test_descriptions]

        return test_descs


    def construct_prompt(self, focal_method: str, context: str) -> str:
        prompt = f"""# Focal Method\n```\n{focal_method}\n```\n\n# Context of Focal Method\n```\n{context}\n```\n\n# Instruction\nGiven the Focal Method and its Context, first infer what the method is supposed to do. Then identify meaningful test scenarios (including typical, edge, and error cases where applicable).\nFor each test scenario, write a test description with the following structure:\n1. Objective: \nBriefly state what this test scenario is verifying (the main behavior, condition, or edge case under test).\n\n2. Preconditions: \nDescribe:\n   - The required state of the system, environment, and data before executing the test.\n   - Any special constraints or assumptions.\n   - The actions (if any) needed to prepare the system so that the expected result can be compared with the actual result.  \n   Tailor the level of detail to a typical test executor (not necessarily the original developer).\n\n3. Expected Results: \n   - The expected outputs and observable behavior of the method when executed under the given preconditions.\n   - The expected values for each relevant output.\n   - Any side effects or state changes that should occur. # Requirement\nMake the test description natural and human-like by translating the program elements to natural language descprition.\nFor example:\n1. Split the camel words and then transform them from program elements to natural language descriptions (such as `IpAddress` -> ip address).\n2. Using natural language to describe invocation (such as `Obj.getPrefix(Param)` -> get the prefix of Param, and `program.version=0.1` -> version of program is 0.1)."""

        return prompt


def main():
    test_desc_agent = TestDescGenerator(llm_name)

    save_path = configs.test_desc_from_fm_dataset_path
    if not os.path.exists(os.path.dirname(save_path)):
        os.makedirs(os.path.dirname(save_path))

    test_desc_dataset = []
    generated_fm_set = set()
    if resume_generation_at > 0:
        for existing_entry in existing_data:
            test_desc_dataset.append(existing_entry)
            generated_fm_set.add(existing_entry['focal_method'])

    for target_pair_idx, each_target_pair in tqdm(enumerate(coverage_data), total=len(coverage_data), ncols=80, desc='Generating test descriptions'):
        if target_pair_idx < resume_generation_at:
            continue

        tar_fm = each_target_pair.focal_method
        tar_context = each_target_pair.focal_file_skeleton

        if tar_fm in generated_fm_set:
            continue

        test_desc_list = test_desc_agent.generate_test_desc_list(tar_fm, tar_context)

        data = {
            'coverage_idx': target_pair_idx,
            'focal_method': tar_fm,
            'test_desc_list': test_desc_list
        }

        print(f'Generated {len(test_desc_list)} test descriptions for focal method index {target_pair_idx}.')

        test_desc_dataset.append(data)
        generated_fm_set.add(tar_fm)

        with open(save_path, 'w') as f:
            json.dump(test_desc_dataset, f, indent=4)
            

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project_name', type=str, required=True, help='The name of the project.')
    parser.add_argument('--resume_generation_at', type=int, default=0, help='The index to resume generation at.')
    args = parser.parse_args()

    # llm_name = 'gpt-o1-mini'
    llm_name = 'claude-haiku-4-5-20251001'
    project_name = args.project_name
    resume_generation_at = args.resume_generation_at
    print(f'Project: {project_name}')

    configs = Configs(project_name, llm_name=llm_name)
    
    if resume_generation_at > 0:
        print(f'Resuming generation at index: {resume_generation_at}')
        # load existing data to avoid duplicate generation
        with open(configs.test_desc_from_fm_dataset_path, 'r') as f:
            existing_data = json.load(f)
        print(f'Loaded existing data with {len(existing_data)} entries.')

    print('Loading jacoco labelled coverages...')
    coverage_dataset = Dataset(configs)
    coverage_data = coverage_dataset.load_coverage_data_jacoco()

    main()