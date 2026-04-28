# Quoll re-identification (prototype) — results for your report

This document summarizes what was built, what the numbers mean, and **why** accuracy is in the range you are seeing. Use it when explaining the work to your professor.

## What we implemented

1. **Pipeline (offline scripts)**  
   - Crops from ecologist-labelled folders.  
   - **MegaDescriptor-L-384** ([Hugging Face](https://huggingface.co/BVRA/MegaDescriptor-L-384)) loaded via `timm`, used as a **frozen** image encoder (no full fine-tune in the MVP path).  
   - **Gallery**: one **prototype embedding per individual** = mean of that individual’s training crop embeddings, L2-normalized.  
   - **Decision**: pick the class with highest **cosine similarity** to the query embedding.

2. **UNKNOWN (abstain) rule**  
   To avoid wrong names on ambiguous crops, the system can output **UNKNOWN** when:  
   - top-1 similarity is below `sim_threshold`, **or**  
   - the margin between top-1 and top-2 is below `gap_threshold` (two identities look equally close).  

   Thresholds can be compared systematically with:

   `python -m scripts.reid_megadescriptor_hf_mvp --load-gallery storage/models/megadescriptor_l384_gallery.pt --root-dir "<your_crops_parent>" --sweep-thresholds`

3. **In-app integration**  
   - `GET /api/reid/info` returns the same summary as `docs/reid_model_info.json` (no GPU on the server).  
   - Individual profile pages can show this block as “prototype / research status.”

## Typical numbers (your runs)

Numbers move slightly if you change **train/test split**, **quality filters**, or **which IDs** are included (e.g. minimum crops per ID).

| Metric | Typical range | Meaning |
|--------|----------------|--------|
| **Closed-set Rank-1** | ~**62–69%** | Always commit to the top-1 ID; no UNKNOWN. |
| **Accuracy when accepting** | ~**84–91%** | Among queries where the system does **not** say UNKNOWN, how often the top-1 ID is correct. |
| **UNKNOWN rate** | **Depends on thresholds** | Stricter thresholds → more UNKNOWN, usually higher accuracy on what remains. |

So: **the system is not “broken” at ~65% Rank-1** — it reflects a **hard** problem under a **strict evaluation**. The **UNKNOWN gate** is the intended way to trade coverage for reliability in a demo or product.

## Why full Rank-1 is not higher (honest reasons)

1. **Appearance variability**  
   Same quoll across IR night shots, motion blur, partial body, and different poses produces embeddings that are harder to separate than textbook face re-ID.

2. **Frozen backbone**  
   MegaDescriptor is strong for **many** species, but your population is **narrow** (a few quolls). The best gains usually come from **fine-tuning** or **multi-prototype** galleries (several cluster centers per ID), which we did not fully do in the fastest MVP.

3. **Single mean prototype**  
   Averaging all embeddings into **one** vector per ID throws away multi-modal structure (e.g. “side view” vs “frontal”).

4. **Class imbalance and long tail**  
   Some individuals have very few usable crops; the demo subset often uses a **minimum image count** per ID, which is correct for stability but does not solve similarity between two abundant IDs.

5. **Licence / scope**  
   MegaDescriptor is **CC BY-NC 4.0** — fine for university demonstration; check terms before any commercial deployment.

## What to say in the demo (one sentence)

> “On held-out crops, raw top-1 matching is moderate because quoll re-ID is visually hard; we add an **uncertainty gate** so the app only assigns an ID when similarity and margin are confident, which pushes **accuracy on accepted predictions** much higher at the cost of sometimes answering **unknown**.”

## Files to cite in the repo

- `scripts/reid_megadescriptor_hf_mvp.py` — frozen MegaDescriptor + prototype gallery + threshold sweep.  
- `docs/reid_model_info.json` — machine-readable summary for `GET /api/reid/info`.  
- `scripts/train_megadescriptor_5quolls.py` — smaller **ResNet** baseline trained on five folders (alternative line of work).
