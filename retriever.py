import re
import torch
import numpy as np
from nltk.corpus import stopwords
from typing import List
from rank_bm25 import BM25Okapi
from transformers import AutoModel, AutoTokenizer


class Retriever():
    def __init__(
        self, corpus_cov: List[str], corpus_fm: List[str], corpus_fm_name: List[str], corpus_tc: List[str], corpus_tc_desc: List[str], corpus_test_case_path,
        embedding_model=None, tokenizer=None
    ) -> None:
        super().__init__()
        self.top_k_fm = 30 
        self.embedding_model = embedding_model if embedding_model is not None else AutoModel.from_pretrained("Salesforce/codet5p-110m-embedding", trust_remote_code=True).eval().to('cuda')
        self.tokenizer = tokenizer if tokenizer is not None else AutoTokenizer.from_pretrained("Salesforce/codet5p-110m-embedding", trust_remote_code=True)
        self.corpus_cov = corpus_cov
        self.corpus_fm = corpus_fm
        self.corpus_fm_name = corpus_fm_name
        self.corpus_tc = corpus_tc
        self.corpus_tc_desc = corpus_tc_desc
        self.corpus_test_case_path = corpus_test_case_path
        self.corpus_tc_desc_base = torch.stack([self.tc_desc_embedding(tc_desc) for tc_desc in corpus_tc_desc])
        self.corpus_fm_base = [self.preprocess_code(doc) for doc in corpus_fm]
        self.corpus_cov_base = [self.preprocess_code(doc) for doc in corpus_cov]
        self.bm25_fm = BM25Okapi(self.corpus_fm_base)
        self.bm25_cov = BM25Okapi(self.corpus_cov_base)

    @torch.no_grad()
    def retrieve_with_threshold(self, target_fm: str, target_tc_desc, threshold: float = 0.2, top_k: int = 1):
        fm_self_sim_score, fm_ref_sim_scores = self.get_score_self_and_ref_fm(target_fm)
        norm_fm_ref_sim_scores = fm_ref_sim_scores / fm_self_sim_score
        filter_indices = norm_fm_ref_sim_scores >= threshold
        if sum(filter_indices) == 0:
            print(f'No reference. max score: {max(norm_fm_ref_sim_scores)} | threshold: {threshold}')
            return [], [], [], [], [], [], []

        # get the similarity between the target test case name and the test case names 
        target_tc_desc_embedding = self.tc_desc_embedding(target_tc_desc)
        tc_desc_similarities = torch.cosine_similarity(target_tc_desc_embedding, self.corpus_tc_desc_base, dim=1).cpu().numpy()
        
        # combine the scores of focal methods and the similarities of test case names
        combined_scores = norm_fm_ref_sim_scores + tc_desc_similarities

        # sort the combined scores
        combined_scores[~filter_indices] = -1
        sorted_indices = np.argsort(combined_scores)[::-1]
        top_k_indices = sorted_indices[:top_k]
        top_k_indices = [i for i in top_k_indices if combined_scores[i] != -1]
        
        return [self.corpus_cov[i] for i in top_k_indices], [self.corpus_fm[i] for i in top_k_indices], [self.corpus_fm_name[i] for i in top_k_indices], [self.corpus_tc[i] for i in top_k_indices], [self.corpus_tc_desc[i] for i in top_k_indices], [combined_scores[i] for i in top_k_indices], [self.corpus_test_case_path[i] for i in top_k_indices]
    
    def ideal_retrieve(self, target_tc: str, threshold: float = 0.6, top_k: int = 1):
        tc_self_sim_score, tc_ref_sim_scores = self.get_score_self_and_ref_tc(target_tc)
        norm_tc_ref_sim_scores = tc_ref_sim_scores / tc_self_sim_score
        filter_indices = norm_tc_ref_sim_scores >= threshold
        if sum(filter_indices) == 0:
            print(f'No reference. max score: {max(norm_tc_ref_sim_scores)} | threshold: {threshold}')
            return [], [], [], [], [], [], []

        # sort the combined scores
        norm_tc_ref_sim_scores[~filter_indices] = -1
        sorted_indices = np.argsort(norm_tc_ref_sim_scores)[::-1]
        top_k_indices = sorted_indices[:top_k]
        
        return [self.corpus_cov[i] for i in top_k_indices], [self.corpus_fm[i] for i in top_k_indices], [self.corpus_fm_name[i] for i in top_k_indices], [self.corpus_tc[i] for i in top_k_indices], [self.corpus_tc_desc[i] for i in top_k_indices], [norm_tc_ref_sim_scores[i] for i in top_k_indices], [self.corpus_test_case_path[i] for i in top_k_indices]
    
    def retrieve_low_similarity(self, target_tc: str, target_fm: str, percentile: float = 0.3, top_k: int = 1):
        """Retrieve references from the lowest percentile of test-to-test similarity.
        
        Args:
            target_tc: Target test case code
            target_fm: Target focal method (unused but kept for API consistency)
            percentile: Select from lowest X% of similarities (default 0.3 for 30%)
            top_k: Number of references to return
        """
        # get the embedding of the target test case
        target_tc_embedding = self.tc_desc_embedding(target_tc)
        
        # compute embeddings for all corpus test cases
        corpus_tc_embeddings = torch.stack([self.tc_desc_embedding(tc) for tc in self.corpus_tc])
        
        # compute test-to-test similarities
        tc_similarities = torch.cosine_similarity(target_tc_embedding, corpus_tc_embeddings, dim=1).cpu().numpy()
        
        # sort by similarity and get the lowest percentile
        sorted_indices = np.argsort(tc_similarities)
        n_lowest = max(1, int(len(sorted_indices) * percentile))
        lowest_percentile_indices = sorted_indices[:n_lowest]
        
        if len(lowest_percentile_indices) == 0:
            print(f'No candidates available in lowest {percentile*100}% percentile')
            return [], [], [], [], [], [], []
        
        # randomly select from the lowest percentile candidates
        if len(lowest_percentile_indices) <= top_k:
            top_k_indices = lowest_percentile_indices.tolist()
        else:
            top_k_indices = np.random.choice(lowest_percentile_indices, size=top_k, replace=False).tolist()
        
        print(f'Selected from lowest {percentile*100}% (top {n_lowest} candidates). Similarity range: [{tc_similarities[sorted_indices[0]]:.3f}, {tc_similarities[sorted_indices[n_lowest-1]]:.3f}]')
        
        return [self.corpus_cov[i] for i in top_k_indices], [self.corpus_fm[i] for i in top_k_indices], [self.corpus_fm_name[i] for i in top_k_indices], [self.corpus_tc[i] for i in top_k_indices], [self.corpus_tc_desc[i] for i in top_k_indices], [float(tc_similarities[i]) for i in top_k_indices], [self.corpus_test_case_path[i] for i in top_k_indices]

    def preprocess_code(self, code):
        # Tokenize the code
        tokens = re.split(r'\W+', code)
        
        # Convert tokens to lowercase
        tokens = [token.lower() for token in tokens]
        
        # Remove stop words
        stop_words = set(stopwords.words('english'))
        custom_stop_words = set(['public', 'private', 'protected', 'void', 'int', 'double', 'float', 'string', 'package', 'junit', 'assert', 'import', 'class', 'cn', 'org'])
        filtered_tokens = [token for token in tokens if token not in stop_words and token not in custom_stop_words]
        filtered_tokens = [token for token in filtered_tokens if len(token) > 1]
        return filtered_tokens
    
    @torch.no_grad()
    def tc_desc_embedding(self, test_desc):
        inputs = self.tokenizer.encode(test_desc, return_tensors="pt", truncation=True).to("cuda")
        embedding = self.embedding_model(inputs)[0]
        return embedding
    
    def get_score_self_and_ref_fm(self, target_fm):
        target_fm_proc = self.preprocess_code(target_fm)
        corpus_added_self = self.corpus_fm_base + [target_fm_proc]
        bm25_fm_added_self = BM25Okapi(corpus_added_self)
        bm25_score = bm25_fm_added_self.get_scores(target_fm_proc)
        self_score = bm25_score[-1]
        # max_score = max(bm25_score)
        # assert self_score == max_score
        ref_sim_scores = bm25_score[:-1]
        return self_score, ref_sim_scores
    
    def get_score_self_and_ref_tc(self, target_tc):
        target_tc_proc = self.preprocess_code(target_tc)
        corpus_tc_base = [self.preprocess_code(tc) for tc in self.corpus_tc]
        corpus_added_self = corpus_tc_base + [target_tc_proc]
        bm25_tc_added_self = BM25Okapi(corpus_added_self)
        bm25_score = bm25_tc_added_self.get_scores(target_tc_proc)
        self_score = bm25_score[-1]
        ref_sim_scores = bm25_score[:-1]
        return self_score, ref_sim_scores


def retrieve_reference(corpus_code, corpus_desc, target_focal_method, target_test_case, target_test_desc, threshold, retriever_tokenizer, retriever_embedding_model, setting, top_k=1):
    corpus_cov, corpus_fm, corpus_fm_name, corpus_tc, corpus_tc_desc, corpus_test_case_path = [], [], [], [], [], []
    for idx, each_pair_cor in enumerate(corpus_code):
        corpus_cov.append(each_pair_cor.coverage)
        corpus_fm.append(each_pair_cor.focal_method)
        corpus_fm_name.append(each_pair_cor.focal_method_name)
        corpus_tc.append(each_pair_cor.test_case)
        corpus_test_case_path.append(each_pair_cor.test_case_path)

        assert corpus_desc[idx]['target_test_case'] == each_pair_cor.test_case
        corpus_tc_desc.append(corpus_desc[idx]['test_desc']['under_setting'])

    retriever = Retriever(corpus_cov, corpus_fm, corpus_fm_name, corpus_tc, corpus_tc_desc, corpus_test_case_path, retriever_embedding_model, retriever_tokenizer)
    assert top_k == 1  # for now, only consider the top 1

    if setting == 'golden':
        references_cov_rag, references_fm_rag, references_fm_name_rag, references_tc_rag, reference_tc_desc_rag, references_score, references_tc_path = retriever.ideal_retrieve(
            target_tc=target_test_case,
            threshold=threshold,
            top_k=top_k
            )
    elif setting == 'retrieve':
        references_cov_rag, references_fm_rag, references_fm_name_rag, references_tc_rag, reference_tc_desc_rag, references_score, references_tc_path = retriever.retrieve_with_threshold(
            target_fm=target_focal_method,
            target_tc_desc=target_test_desc,
            threshold=threshold,
            top_k=top_k
            )
    else:
        raise ValueError
    return references_cov_rag, references_fm_rag, references_fm_name_rag, references_tc_rag, reference_tc_desc_rag, references_score, references_tc_path