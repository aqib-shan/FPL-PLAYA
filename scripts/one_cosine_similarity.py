#!/usr/bin/env python3
"""
Compute cosine similarity between one player text and one position query.

Usage:
  python scripts/one_cosine_similarity.py

Uses: Victor Gyökeres (FWD) embedding vs GK position query encoding.
Model and GK query come from config (same as EmbeddingFilter).
"""
import os
import sys

# Project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Same model as config
MODEL = "BAAI/bge-base-en-v1.5"
# GK position query from config.yaml
GK_QUERY = (
    "Must-have OR recommended, fit, high points, clean sheet, saves, "
    "consistent starter, good fixtures. NOT out of form, injured, suspended."
)
# Victor Gyökeres text (same format we embed in the app)
GYOKERES_TEXT = (
    "Victor Gyökeres | Arsenal | FWD | Must-have - Gyökeres is Arsenal's primary striker "
    "and a consistent goal threat, making him a top pick for the double gameweek against "
    "potentially weaker defenses. | Fit - Gyökeres is a key striker and is expected to be "
    "available for both fixtures."
)


def main():
    print("Loading model:", MODEL)
    model = SentenceTransformer(MODEL)

    print("Encoding GK position query...")
    gk_enc = model.encode(GK_QUERY)

    print("Encoding Victor Gyökeres text...")
    player_enc = model.encode(GYOKERES_TEXT)

    # Cosine similarity: (1, 768) vs (768,) -> need (1, 768) vs (1, 768)
    sim = cosine_similarity(gk_enc.reshape(1, -1), player_enc.reshape(1, -1))[0, 0]
    print()
    print("Cosine similarity (Victor Gyökeres vs GK position query):", round(sim, 6))


if __name__ == "__main__":
    main()
