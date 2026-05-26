import sys
sys.path.append('..')
from dataset import Dataset
from configs import Configs
import torch
import numpy as np


class FactDiscriminator:
    def __init__(self, configs: Configs, embedding_model, tokenizer, is_golden: bool = False, similarity_weight: float = 0.8):
        self.configs = configs
        self.embedding_model = embedding_model
        self.tokenizer = tokenizer
        self.similarity_weight = similarity_weight

        self.golden_fact_set = None

    def get_golden_facts(self, target_idx: int, focal_method_name: str):
        info = self.golden_fact_set[target_idx]
        assert info['target_coverage_idx'] == target_idx, f'Inconsistent coverage_idx: {target_idx} vs {info["target_coverage_idx"]}'
        assert focal_method_name in info['focal_method_name'], f'Inconsistent focal_method_name: {focal_method_name} vs {info["focal_method_name"]}'

        golden_facts = info['golden_facts']

        return golden_facts

    def get_crucial_facts(self, candidate_facts: list, test_desc: str, threshold: float, top_k: int):
        test_desc_emb = self.embedding(test_desc)
        candidate_facts_emb = [self.embedding(each_fact) for each_fact in candidate_facts]
        candidate_facts_emb = torch.stack(candidate_facts_emb).to("cuda")
        similarities = torch.cosine_similarity(test_desc_emb, candidate_facts_emb, dim=1).cpu().numpy()
        # filter according to threshold
        filter_indices = similarities >= threshold
        if sum(filter_indices) == 0:
            return [], []
        
        valid_indices = np.where(similarities >= threshold)[0]
        sorted_valid_indices = valid_indices[np.argsort(similarities[valid_indices])[::-1]]
        top_k_indices = sorted_valid_indices[:top_k]
        return [candidate_facts[i] for i in top_k_indices], [float(similarities[i]) for i in top_k_indices]
        
    @torch.no_grad()
    def embedding(self, text: str):
        inputs = self.tokenizer.encode(text, return_tensors="pt", truncation=True).to("cuda")
        embedding = self.embedding_model(inputs)[0]
        return embedding
    
    def get_crucial_facts_v2(self, candidate_facts: list, focal_method_usages: list, test_desc: str, threshold: float, top_k: int):
        test_desc_emb = self.embedding(test_desc)
        
        ###
        # similarity between candidate facts and test description
        ###
        candidate_facts_string = []
        for each_fact in candidate_facts:
            if each_fact[0] == each_fact[1]:
                candidate_facts_string.append(f"{each_fact[0]}" + "{\n" + f"{each_fact[2]}" + "\n}")  # for field facts.
            else:
                candidate_facts_string.append(f"{each_fact[0]}" + "{\n" + f"{each_fact[1]} {each_fact[2]}" + "\n}")
        candidate_facts_string = set(list(candidate_facts_string))
        candidate_facts_emb = [self.embedding(each_fact) for each_fact in candidate_facts_string]
        candidate_facts_emb = torch.stack(candidate_facts_emb).to("cuda")
        candidate_sim = torch.cosine_similarity(test_desc_emb, candidate_facts_emb, dim=1).cpu().numpy()

        top_2_usages, top_2_usages_sim = [], []
        if len(focal_method_usages) > 0:
            ###
            # similarity between focal method usages and test description
            ###
            usages_emb = [self.embedding(each_usage[0]) for each_usage in focal_method_usages]
            usages_emb = torch.stack(usages_emb).to("cuda")
            usages_sim = torch.cosine_similarity(test_desc_emb, usages_emb, dim=1).cpu().numpy()

            top_2_usages_idx = np.argsort(usages_sim)[::-1][:2]
            top_2_usages = [focal_method_usages[i] for i in top_2_usages_idx]
            top_2_usages_sim = [float(usages_sim[i]) for i in top_2_usages_idx]

            ###
            # count the occurrence frequency of each candidate fact
            ###
            occurrence_frequencies = [0 for _ in range(len(candidate_facts))]
            occurrence_count = np.zeros((len(candidate_facts), len(focal_method_usages)))

            for i, each_candidate in enumerate(candidate_facts):
                candidate_class, candidate_signature = each_candidate[0], each_candidate[1]

                for j, each_usage in enumerate(focal_method_usages):
                    if (candidate_class, candidate_signature) in each_usage[1]:
                        occurrence_count[i][j] = 1

            # calculate the score
            for i, each_candidate in enumerate(candidate_facts):
                for j, each_usage in enumerate(focal_method_usages):
                    occurrence_frequencies[i] += occurrence_count[i][j] * usages_sim[j]
                occurrence_frequencies[i] = occurrence_frequencies[i] / sum(occurrence_count[i]) if sum(occurrence_count[i]) != 0 else 0
            occurrence_frequencies = np.array(occurrence_frequencies)

        ###
        # rank based on the two scores
        ###
        total_scores = self.similarity_weight * candidate_sim + (1 - self.similarity_weight) * occurrence_frequencies if len(focal_method_usages) > 0 else candidate_sim

        filter_indices = total_scores >= threshold
        if sum(filter_indices) == 0:
            return [], [], [], []
        
        valid_indices = np.where(total_scores >= threshold)[0]
        sorted_valid_indices = valid_indices[np.argsort(total_scores[valid_indices])[::-1]]
        top_k_indices = sorted_valid_indices[:top_k]

        return [candidate_facts[i] for i in top_k_indices], [float(total_scores[i]) for i in top_k_indices], top_2_usages, top_2_usages_sim
        
