# Generating Project-Specific Test Cases with Validation Intention
This is the official repository for the ISSTA 2026 paper: ***Generating Project-Specific Test Cases with Validation Intention***

## 🕹️ Setup
#### Python Environment
- python 3.11.7
- pytorch 2.2.2
- openai 1.30.5
- rank-bm25 0.2.2
- nltk 3.8.1
- beautifulsoup4 4.12.2
- javalang 0.13.0
- matplotlib 3.8.0
- tqdm 4.65.0
- tree-sitter 0.20.1

#### Java Environment
- JDK 1.8.0_311
- JDK 17.0.12
- Apache Maven 3.9.6
- JDTLS 1.9.0
- PIT/Pitest 1.17.0  
  - downloaded automatically by Maven
  - `pitest-junit5-plugin` 1.2.1 is used for JUnit 5 projects

>[!NOTE]
>Make sure JDK 1.8.0_311 and JDK 17.0.12 are installed correctly.

```bash
$ java --version
java version "1.8.0_311"
Java(TM) SE Runtime Environment (build 1.8.0_311-b11)
```

```bash
$ java17 --version
java 17.0.12 2024-07-16 LTS
Java(TM) SE Runtime Environment (build 17.0.12+8-LTS-286)
```

```bash
$ mvn --version
Apache Maven 3.9.6
Maven home: /usr/share/maven
Java version: 1.8.0_311, vendor: Oracle Corporation, runtime: ...
```

Before running the experiments, we recommend running the following command in each repository under `data/repos` to ensure that all projects can be compiled and tested successfully:

```bash
mvn clean test
```


## 🚀 Running Experiments
The following examples use the Java project `spark` and the LLM `gpt-5-mini`. You can replace them with other supported project names and LLM names.

### Prepare the Dataset
1. Download the [dataset](https://drive.google.com/file/d/170gysg_XhG4Rk8hYCVZnu_w3HR3YWGdG/view?usp=drive_link) into the `./data` directory.
2. Navigate to the `./data` directory.
3. Run `tar -xzvf dataset.tar.gz`.

### Configure API Keys
In `agents.py`: 
1. Set `GPT_KEY`, `GPT_BASE_URL`, `DEEPSEEK_KEY`, and `DEEPSEEK_BASE_URL` to a usable OpenAI API key.

### Generate validation intention descriptions for all tests
(can skip if generated descriptions exist in `data/test_desc_dataset`)

To generate validation intention descriptions for all tests, run:
```bash
python test_desc_generator.py
```

The validation intention descriptions obtained through reverse engineering are **not** used as target test inputs. They are used only as validation intention descriptions for historical candidate tests.

### Generate test cases
#### Generate tests using LLM inferred validation intention descriptions
1. `cd main/`
2. Generate candidate validation intention descriptions for focal methods.

   This step can be skipped if the generated descriptions already exist in `data/test_desc_from_fm_dataset`.
    ```bash
    # generated candidate validation description for focal methods.
    python -u generate_desc_from_fm.py --project_name spark 

    # match generated candidate validation descriptions to target tests.
    python -u match_desc_with_tc.py --project_name spark
    ```
3. Generate tests for java project `spark` based on LLM-inferred validation intention descriptions
    ```bash
    python -u generate_test.py --project_name spark --llm_name gpt-5-mini --junit_version 4
    ```

#### Generate tests using human-written validation intention descriptions
1. `cd main/`
2. Generate tests for java project `spark` based on validation descriptions written by humans
    ```bash
    python -u generate_test_using_manual_desc.py --project_name spark --llm_name gpt-5-mini --junit_version 4
    ```

### Calculate CMS
1. `cd cms_calculation/`
2. Run PIT on the ground-truth test cases:
    ```bash
    python -u main.py --project_name spark --llm_name gpt-5-mini --ground_truth
    ```
3. Run PIT on the generated test cases:
    ```bash
    python -u main.py --project_name spark --llm_name gpt-5-mini
    ```
4. Compute CMS scores (saved to `data/collected_mutation_scores/<llm_name>/<project_name>.csv`):
    ```bash
    python -u calculate_cms.py --project_name spark --llm_name gpt-5-mini
    ```

### Analyze the Effect of Validation Intention Granularity
1. `cd main/`
2. Generate tests using different validation intention settings.
    - `Objective`
      ```bash
      python -u generate_test.py --project_name spark --llm_name gpt-5-mini --junit_version 4 --test_desc_setting obj
      ```
    - `Objective + Precondition`
      ```bash
      python -u generate_test.py --project_name spark --llm_name gpt-5-mini --junit_version 4 --test_desc_setting obj_pre
      ```
    - `Objective + Expected Results`
      ```bash
      python -u generate_test.py --project_name spark --llm_name gpt-5-mini --junit_version 4 --test_desc_setting obj_exp
      ```
    - No Validation Intention Description
      ```bash
      python -u generate_test.py --project_name spark --llm_name gpt-5-mini --junit_version 4 --test_desc_setting none
      ```

### Empirical Study
1. Collect historical candidates for each test
    ```bash
    cd empirical_study/analyze_feasible
    python collect_temporal_candidates.py --project_name spark --num_workers 4 --cleanup > ./collect_temp_candidates_spark.log
    ```

2. Analyze Reference Availability and Referability Level
    ```bash
    python analyze_thres_for_retrieval_temporal.py --project_name spark > ./analyze_spark.log
    ```

## 💬 FAQ
Common problems and solutions are documented in [FAQ.md](FAQ.md).

## 📝 Citation
If you find this repository useful, please cite our paper:

```bibtex
@article{qi2026generating,
  title={Generating Project-Specific Test Cases with Requirement Validation Intention},
  author={Qi, Binhang and Lin, Yun and Weng, Xinyi and Huang, Yuhuan and Liu, Chenyan and Sun, Hailong and Jin, Zhi and Dong, Jin Song},
  journal={Proceedings of the ACM on Software Engineering},
  number={ISSTA},
  year={2026}
}
```
