"""
Simplified retriever for test-to-test similarity computation.

This retriever only handles test case similarity without requiring focal methods.
It is designed for the temporal candidate analysis where we only have test code.
"""

import re
import numpy as np
from nltk.corpus import stopwords
from typing import List
from rank_bm25 import BM25Okapi


class TestOnlyRetriever:
    """
    A simplified retriever that computes test-to-test similarity only.
    Unlike the full Retriever, this does not require focal methods.
    """
    
    def __init__(
        self, 
        corpus_tc: List[str], 
        corpus_tc_name: List[str], 
        corpus_tc_path: List[str]
    ) -> None:
        """
        Initialize the test-only retriever.
        
        Args:
            corpus_tc: List of test case code strings
            corpus_tc_name: List of test case names
            corpus_tc_path: List of test case file paths
        """
        super().__init__()
        self.corpus_tc = corpus_tc
        self.corpus_tc_name = corpus_tc_name
        self.corpus_tc_path = corpus_tc_path
        
        # Preprocess corpus for BM25
        self.corpus_tc_base = [self.preprocess_code(tc) for tc in corpus_tc]
        self.bm25_tc = BM25Okapi(self.corpus_tc_base) if len(self.corpus_tc_base) > 0 else None
    
    def preprocess_code(self, code: str) -> List[str]:
        """
        Preprocess code for BM25 similarity computation.
        Tokenizes, lowercases, and removes stop words.
        """
        # Tokenize the code
        tokens = re.split(r'\W+', code)
        
        # Convert tokens to lowercase
        tokens = [token.lower() for token in tokens]
        
        # Remove stop words
        stop_words = set(stopwords.words('english'))
        custom_stop_words = set([
            'public', 'private', 'protected', 'void', 'int', 'double', 
            'float', 'string', 'package', 'junit', 'assert', 'import', 
            'class', 'cn', 'org', 'test', 'static', 'final', 'new',
            'return', 'if', 'else', 'for', 'while', 'try', 'catch'
        ])
        filtered_tokens = [
            token for token in tokens 
            if token not in stop_words and token not in custom_stop_words
        ]
        filtered_tokens = [token for token in filtered_tokens if len(token) > 1]
        return filtered_tokens
    
    def get_score_self_and_ref_tc(self, target_tc: str) -> tuple:
        """
        Compute BM25 similarity scores between target test case and corpus.
        
        Args:
            target_tc: The target test case code
            
        Returns:
            (self_score, ref_sim_scores): 
                - self_score: BM25 score of target with itself
                - ref_sim_scores: numpy array of BM25 scores with each corpus item
        """
        target_tc_proc = self.preprocess_code(target_tc)
        
        # Add target to corpus temporarily to compute self-similarity
        corpus_added_self = self.corpus_tc_base + [target_tc_proc]
        bm25_tc_added_self = BM25Okapi(corpus_added_self)
        bm25_score = bm25_tc_added_self.get_scores(target_tc_proc)
        
        self_score = bm25_score[-1]
        ref_sim_scores = np.array(bm25_score[:-1])
        
        return self_score, ref_sim_scores
    
    def get_top_k_similar(self, target_tc: str, top_k: int = 5) -> tuple:
        """
        Get top-k most similar test cases to the target.
        
        Args:
            target_tc: The target test case code
            top_k: Number of top results to return
            
        Returns:
            Tuple of (test_codes, test_names, test_paths, scores)
        """
        if len(self.corpus_tc) == 0:
            return [], [], [], []
        
        self_score, ref_scores = self.get_score_self_and_ref_tc(target_tc)
        
        # Normalize scores
        if self_score > 0:
            norm_scores = ref_scores / self_score
        else:
            norm_scores = ref_scores
        
        # Get top-k indices
        sorted_indices = np.argsort(norm_scores)[::-1]
        top_k_indices = sorted_indices[:min(top_k, len(sorted_indices))]
        
        return (
            [self.corpus_tc[i] for i in top_k_indices],
            [self.corpus_tc_name[i] for i in top_k_indices],
            [self.corpus_tc_path[i] for i in top_k_indices],
            [norm_scores[i] for i in top_k_indices]
        )
    
    def get_corpus_size(self) -> int:
        """Return the size of the corpus."""
        return len(self.corpus_tc)
