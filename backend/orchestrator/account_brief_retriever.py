import json
import logging
import math
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from config import get_settings
from services import embeddings as embeddings_service

logger = logging.getLogger(__name__)

BRIEF_DATA_PATH = Path("data/account_brief_68.json")
EMBEDDINGS_CACHE_PATH = Path("data/account_brief_68_embeddings.json")

_cached_indexed_data = None
_cached_bm25 = None

def _clean(text: str) -> str:
    return " ".join(str(text).split())

def _chunk_account_brief(data: Dict[str, Any]) -> List[str]:
    """Parse the complex JSON into searchable semantic text chunks."""
    chunks = []
    
    # 1. Meta & Account Context
    meta = data.get("meta", {})
    context = data.get("account_context_card", {})
    summary = data.get("account_summary", {})
    
    if meta or context or summary:
        chunk = "ACCOUNT SUMMARY AND CONTEXT:\n"
        if meta.get("agenda"):
            chunk += f"Agenda: {meta['agenda']}\n"
        if context.get("primary_goal"):
            chunk += f"Primary Goal: {context['primary_goal']}\n"
            
        at_a_glance = context.get("at_a_glance", {})
        if at_a_glance:
            chunk += f"Total Spend: {at_a_glance.get('spend')}\n"
            chunk += f"Total ROAS: {at_a_glance.get('roas')}\n"
            chunk += f"Total CPA: {at_a_glance.get('cpa')}\n"
            chunk += f"Total Conversions: {at_a_glance.get('conversions')}\n"
            
        performance = summary.get("performance", {})
        if performance:
            chunk += f"Performance context: Spend delta {performance.get('spend_delta', {}).get('pct')}, "
            chunk += f"ROAS delta {performance.get('roas_delta', {}).get('pct')}.\n"
            
        chunks.append(_clean(chunk))

    # 2. Performance Trends
    trends = data.get("performance_trends", {})
    if trends:
        chunk = "PERFORMANCE TRENDS:\n"
        for tk, tv in trends.items():
            if isinstance(tv, dict):
                chunk += f"{tk}: " + ", ".join([f"{k}={v}" for k,v in tv.items()]) + "\n"
        chunks.append(_clean(chunk))
        
    # 3. Campaigns
    campaigns_dict = data.get("campaigns", {})
    campaigns = campaigns_dict.get("all", []) if isinstance(campaigns_dict, dict) else []
    for c in campaigns:
        chunk = f"CAMPAIGN METRICS:\nCampaign ID: {c.get('campaign_id')}\nName: {c.get('campaign_name')}\nStatus: {c.get('status')}\n"
        chunk += f"Cost: ${c.get('spend', 0):.2f}\nClicks: {c.get('clicks')}\nConversions: {c.get('conversions')}\n"
        chunk += f"CPA: ${c.get('cpa', 0):.2f}\nROAS: {c.get('roas', 0):.2f}x\n"
        chunks.append(_clean(chunk))
        
    # 4. Ad Groups (Batched by campaign to reduce chunk bloat)
    ad_groups_dict = data.get("ad_groups", {})
    ad_groups = ad_groups_dict.get("all", []) if isinstance(ad_groups_dict, dict) else []
    campaign_to_adgroups = {}
    for ag in ad_groups:
        cid = ag.get("campaign_id")
        if cid not in campaign_to_adgroups:
            campaign_to_adgroups[cid] = []
        campaign_to_adgroups[cid].append(ag)
        
    for cid, ags in campaign_to_adgroups.items():
        # chunk per 10 ad groups
        for i in range(0, len(ags), 10):
            batch = ags[i:i+10]
            chunk = f"AD GROUPS FOR CAMPAIGN {cid}:\n"
            for ag in batch:
                chunk += f"  - AdGroup '{ag.get('adgroup_name')}' (ID: {ag.get('adgroup_id')}, Status: {ag.get('status')}): Cost ${ag.get('spend', 0):.2f}, Conv {ag.get('conversions', 0)}, ROAS {ag.get('roas', 0):.2f}x\n"
            chunks.append(_clean(chunk))
            
    # 5. Zero Conv Keywords (Batched)
    keywords_dict = data.get("keywords", {})
    zero_conv = keywords_dict.get("zero_conversion_keywords", []) if isinstance(keywords_dict, dict) else []
    for i in range(0, len(zero_conv), 20):
        batch = zero_conv[i:i+20]
        chunk = "ZERO CONVERSION KEYWORDS (HIGH SPEND):\n"
        for kw in batch:
            chunk += f"  - '{kw.get('keyword')}' (Match: {kw.get('match_type')}, Campaign: {kw.get('campaign_name')}): Cost ${kw.get('spend', 0):.2f}, Clicks {kw.get('clicks', 0)}\n"
        chunks.append(_clean(chunk))

    # 6. Recent Changes
    changes = data.get("recent_changes", [])
    for i in range(0, len(changes), 10):
        batch = changes[i:i+10]
        chunk = "RECENT ACCOUNT CHANGES:\n"
        for ch in batch:
            chunk += f"  - Date {ch.get('date')}: Changed {ch.get('resource_type')} ID {ch.get('resource_id')}. Updates: {ch.get('changed_fields')}\n"
        chunks.append(_clean(chunk))

    return chunks

class SimpleBM25:
    """A lightweight BM25 implementation."""
    def __init__(self, corpus: List[str]):
        self.corpus_size = len(corpus)
        self.avgdl = 0
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.k1 = 1.5
        self.b = 0.75
        
        nd = {}
        num_doc = 0
        for doc in corpus:
            tokens = doc.lower().split()
            self.doc_len.append(len(tokens))
            num_doc += len(tokens)
            
            frequencies = dict(Counter(tokens))
            self.doc_freqs.append(frequencies)
            
            for word, freq in frequencies.items():
                nd[word] = nd.get(word, 0) + 1
                
        self.avgdl = num_doc / self.corpus_size if self.corpus_size > 0 else 0
        
        for word, freq in nd.items():
            # IDF formula
            self.idf[word] = math.log(((self.corpus_size - freq + 0.5) / (freq + 0.5)) + 1)

    def get_scores(self, query: str) -> List[float]:
        scores = [0.0] * self.corpus_size
        q_tokens = query.lower().split()
        for i in range(self.corpus_size):
            doc_len = self.doc_len[i]
            frequencies = self.doc_freqs[i]
            score = 0.0
            for token in q_tokens:
                if token not in frequencies:
                    continue
                freq = frequencies[token]
                numerator = self.idf.get(token, 0) * freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                score += numerator / denominator
            scores[i] = score
        return scores

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = math.sqrt(sum(a * a for a in v1))
    norm_v2 = math.sqrt(sum(b * b for b in v2))
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)

async def _get_or_create_embeddings(chunks: List[str]) -> List[Dict[str, Any]]:
    """Load cached embeddings or generate them asynchronously."""
    settings = get_settings()
    
    # Try to load from cache
    if EMBEDDINGS_CACHE_PATH.exists():
        try:
            with open(EMBEDDINGS_CACHE_PATH, "r", encoding="utf-8") as f:
                cached = json.load(f)
            
            # Simple integrity check
            if len(cached) == len(chunks) and cached[0]["text"] == chunks[0]:
                logger.info("Loaded %d embeddings from cache.", len(cached))
                return cached
        except Exception as e:
            logger.warning(f"Failed to load embedding cache: {e}")

    logger.info("Generating embeddings for %d chunks. This will take a moment...", len(chunks))
    
    results = []
    
    # Process in batches of 100 to avoid OpenAI rate limits and drastically speed up the process
    batch_size = 100
    
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    try:
        for i in range(0, len(chunks), batch_size):
            batch_texts = chunks[i:i+batch_size]
            # Replace empty strings with a single space to avoid API errors
            safe_batch = [text if text else " " for text in batch_texts]
            
            resp = await client.embeddings.create(
                model="text-embedding-3-large",
                input=safe_batch
            )
            
            for j, data in enumerate(resp.data):
                idx = i + j
                results.append({
                    "idx": idx,
                    "text": chunks[idx],
                    "embedding": data.embedding
                })
            
            logger.info(f"Processed batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}")
    except Exception as e:
        logger.error(f"Failed during batch embedding generation: {e}")
    finally:
        await client.close()
    
    # Cache to disk
    try:
        with open(EMBEDDINGS_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f)
        logger.info("Saved %d embeddings to cache.", len(results))
    except Exception as e:
        logger.warning(f"Failed to save embedding cache: {e}")
        
    return results

async def init_caches() -> None:
    """Pre-warm the embeddings and BM25 cache. Can be called safely multiple times."""
    global _cached_indexed_data, _cached_bm25
    if _cached_indexed_data is not None and _cached_bm25 is not None:
        return
        
    if not BRIEF_DATA_PATH.exists():
        logger.error("account_brief_68.json not found during init_caches.")
        return
        
    try:
        with open(BRIEF_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read account_brief_68.json during init_caches: {e}")
        return
        
    chunks = _chunk_account_brief(data)
    _cached_indexed_data = await _get_or_create_embeddings(chunks)
    
    valid_chunks = [item["text"] for item in _cached_indexed_data]
    _cached_bm25 = SimpleBM25(valid_chunks)
    logger.info("Deep RAG caches successfully initialized.")

async def search_account_brief(query: str, top_k: int = 5) -> str:
    """Perform a true hybrid search (BM25 + Dense) on the account brief."""
    global _cached_indexed_data, _cached_bm25
    
    t0 = time.monotonic()
    
    # Ensure caches are initialized
    await init_caches()
    
    if _cached_indexed_data is None or _cached_bm25 is None:
        return "ERROR: Failed to initialize brief caches."
        
    indexed_data = _cached_indexed_data
    bm25 = _cached_bm25
    valid_chunks = [item["text"] for item in indexed_data]
    
    # 2. Dense Search
    query_emb = await embeddings_service.generate_embedding(query, get_settings())
    dense_scores = []
    if query_emb:
        for item in indexed_data:
            score = cosine_similarity(query_emb, item["embedding"])
            dense_scores.append(score)
    else:
        dense_scores = [0.0] * len(valid_chunks)
        
    # 3. Sparse Search (BM25)
    sparse_scores = bm25.get_scores(query)
    
    # 4. Reciprocal Rank Fusion (RRF)
    # Sort indices by score descending
    dense_ranks = {idx: rank for rank, idx in enumerate(sorted(range(len(dense_scores)), key=lambda i: dense_scores[i], reverse=True))}
    sparse_ranks = {idx: rank for rank, idx in enumerate(sorted(range(len(sparse_scores)), key=lambda i: sparse_scores[i], reverse=True))}
    
    k = 60 # RRF constant
    final_scores = []
    for i in range(len(valid_chunks)):
        rrf_score = (1.0 / (k + dense_ranks[i])) + (1.0 / (k + sparse_ranks[i]))
        final_scores.append((rrf_score, valid_chunks[i]))
        
    final_scores.sort(key=lambda x: x[0], reverse=True)
    
    top_results = final_scores[:top_k]
    
    logger.info("⏱ Brief Hybrid RAG search completed in %.1fms", (time.monotonic() - t0) * 1000)
    
    result_text = f"DEEP SEARCH RESULTS FOR: '{query}'\n\n"
    for idx, (score, text) in enumerate(top_results, 1):
        result_text += f"--- Result {idx} ---\n{text}\n\n"
        
    return result_text.strip()
