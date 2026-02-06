from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np
from janome.tokenizer import Tokenizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .utils import is_probably_japanese

_SENT_SPLIT_RE = re.compile(r"(?<=[。！？!?\.])\s+|\n+")
_word_re = re.compile(r"[A-Za-z][A-Za-z0-9\-']{1,}")

_JA_TOKENIZER = Tokenizer(wakati=True)

EN_STOP = set([
    "the","a","an","and","or","to","of","in","for","on","with","as","by","at","from",
    "is","are","was","were","be","been","being","this","that","these","those","it",
    "we","you","they","i","he","she","them","his","her","their","our","your",
])

JA_STOP = set([
    "これ","それ","あれ","こと","ため","よう","もの","ところ","そして","しかし","また",
    "です","ます","する","いる","ある","なる","できる","られる","など","にて","による",
])

def split_sentences(text: str) -> List[str]:
    raw = [s.strip() for s in _SENT_SPLIT_RE.split(text) if s and s.strip()]
    # merge tiny fragments
    out: List[str] = []
    buf = ""
    for s in raw:
        if len(s) < 20 and buf:
            buf = (buf + " " + s).strip()
        else:
            if buf:
                out.append(buf)
            buf = s
    if buf:
        out.append(buf)
    return out

def tokenize(text: str) -> List[str]:
    if is_probably_japanese(text):
        tokens = [t for t in _JA_TOKENIZER.tokenize(text) if t.strip()]
        tokens = [t for t in tokens if t not in JA_STOP and len(t) > 1]
        return tokens
    # English-ish
    tokens = [m.group(0).lower() for m in _word_re.finditer(text)]
    tokens = [t for t in tokens if t not in EN_STOP and len(t) > 2]
    return tokens

def summarize(text: str, sentences: int = 7) -> str:
    sents = split_sentences(text)
    if not sents:
        return ""
    # score sentences by token frequency
    freq = {}
    for tok in tokenize(text):
        freq[tok] = freq.get(tok, 0) + 1
    if not freq:
        # fallback: head
        return "\n".join(sents[:sentences])

    maxf = max(freq.values())
    for k in list(freq.keys()):
        freq[k] = freq[k] / maxf

    scored: List[Tuple[int, float]] = []
    for i, s in enumerate(sents):
        toks = tokenize(s)
        if not toks:
            scored.append((i, 0.0))
            continue
        score = sum(freq.get(t, 0.0) for t in toks) / (1.0 + math.log(1 + len(toks)))
        scored.append((i, score))

    top_idx = sorted(sorted(scored, key=lambda x: x[1], reverse=True)[:sentences], key=lambda x: x[0])
    chosen = [sents[i] for i, _ in top_idx]
    return "\n".join(chosen).strip()

@dataclass(frozen=True)
class CompareResult:
    similarity: float
    common_terms: List[Tuple[str, float]]
    doc1_unique_terms: List[Tuple[str, float]]
    doc2_unique_terms: List[Tuple[str, float]]

def compare_texts(text1: str, text2: str, top_terms: int = 15) -> CompareResult:
    vec = TfidfVectorizer(
        tokenizer=tokenize,
        lowercase=False,
        min_df=1,
        max_df=0.95,
        ngram_range=(1,2),
    )
    X = vec.fit_transform([text1, text2])
    sim = float(cosine_similarity(X[0], X[1])[0][0])

    feature_names = np.array(vec.get_feature_names_out())
    v1 = X[0].toarray().ravel()
    v2 = X[1].toarray().ravel()

    common = np.minimum(v1, v2)
    c_idx = common.argsort()[::-1][:top_terms]
    common_terms = [(feature_names[i], float(common[i])) for i in c_idx if common[i] > 0]

    u1 = np.maximum(v1 - v2, 0.0)
    u1_idx = u1.argsort()[::-1][:top_terms]
    doc1_unique = [(feature_names[i], float(u1[i])) for i in u1_idx if u1[i] > 0]

    u2 = np.maximum(v2 - v1, 0.0)
    u2_idx = u2.argsort()[::-1][:top_terms]
    doc2_unique = [(feature_names[i], float(u2[i])) for i in u2_idx if u2[i] > 0]

    return CompareResult(
        similarity=sim,
        common_terms=common_terms,
        doc1_unique_terms=doc1_unique,
        doc2_unique_terms=doc2_unique,
    )

def pairwise_similarity(texts: Sequence[str]) -> np.ndarray:
    vec = TfidfVectorizer(
        tokenizer=tokenize,
        lowercase=False,
        min_df=1,
        max_df=0.95,
        ngram_range=(1,2),
    )
    X = vec.fit_transform(list(texts))
    return cosine_similarity(X)
