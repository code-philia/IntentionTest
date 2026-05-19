# Experiments on LLM-inferred validation intention
1. Generate test descriptions based on the focal methods
```
python -u generate_desc_from_fm.py --project_name spark
```

2. Match generated test descriptions to the ground-truth tests
```
python -u match_desc_with_tc.py --project_name spark
```

3. Generate tests
```
python -u generate_test.py --project_name spark --llm_name gpt-o1-mini  --junit_version 4
```

# Experiments on human-written validation intention
1. Generate tests
```
python -u generate_test_using_manual_desc.py --project_name spark --llm_name gpt-o1-mini  --junit_version 4
```