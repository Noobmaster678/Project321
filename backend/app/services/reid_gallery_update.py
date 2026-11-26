"""Counted updates for MegaDescriptor identity prototypes.

Galleries built by ``scripts/reid_megadescriptor_hf_mvp.py`` store one
L2-normalized mean vector per individual and, historically, no sample
count. Treating a missing count as 1 makes a single newly confirmed crop
weigh as much as that entire mean, which warps later automatic re-ID.
"""
from __future__ import annotations

import numpy as np


def _as_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 1 else None
    if isinstance(value, float):
        if not value.is_integer():
            return None
        parsed = int(value)
        return parsed if parsed >= 1 else None
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _as_positive_int(item())
        except Exception:
            return None
    return None


def counts_are_trusted(raw_counts: object, n_classes: int) -> bool:
    """True when ``raw_counts`` is one positive sample count per class."""
    if isinstance(raw_counts, (str, bytes)) or not isinstance(raw_counts, (list, tuple)):
        return False
    if n_classes < 0 or len(raw_counts) != n_classes:
        return False
    return all(_as_positive_int(c) is not None for c in raw_counts)


def _normalize(vector: np.ndarray) -> np.ndarray:
    flat = np.asarray(vector, dtype=np.float64).reshape(-1)
    norm = float(np.linalg.norm(flat))
    if norm == 0.0:
        return flat
    return flat / norm


def apply_counted_prototype_update(
    names: list[str],
    prototypes: np.ndarray,
    counts: object,
    individual_id: str,
    embedding: np.ndarray,
) -> tuple[list[str], np.ndarray, list[int]] | None:
    """Blend one embedding into a prototype using its real sample count.

    Returns ``None`` without inventing counts when the gallery does not
    record how many crops formed each prototype. Callers must leave the
    checkpoint unchanged in that case.
    """
    protos = np.asarray(prototypes, dtype=np.float64)
    if protos.ndim != 2 or len(names) != protos.shape[0]:
        return None
    if not counts_are_trusted(counts, len(names)):
        return None

    emb = _normalize(embedding)
    if emb.shape[0] != protos.shape[1]:
        return None
    if not isinstance(counts, (list, tuple)):
        return None

    trusted = [_as_positive_int(c) for c in counts]
    counts_i = [int(c) for c in trusted if c is not None]
    if len(counts_i) != len(names):
        return None

    if individual_id in names:
        idx = names.index(individual_id)
        n = counts_i[idx]
        updated = _normalize(protos[idx] * n + emb)
        new_protos = protos.copy()
        new_protos[idx] = updated
        counts_i[idx] = n + 1
        return list(names), new_protos, counts_i

    new_names = list(names) + [individual_id]
    new_protos = np.vstack([protos, emb.reshape(1, -1)])
    counts_i.append(1)
    return new_names, new_protos, counts_i
