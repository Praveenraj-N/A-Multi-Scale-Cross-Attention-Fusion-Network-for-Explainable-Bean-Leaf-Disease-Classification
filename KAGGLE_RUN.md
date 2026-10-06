# Running MSCAF-Net baseline training on Kaggle

## One-time setup
1. kaggle.com -> Settings -> **Phone verification** (needed for GPU + internet).
2. **Create -> New Dataset**, upload `MSCAF-Net_kaggle.zip` (Kaggle unzips it), name it `mscaf-net`.
3. **Create -> New Notebook** -> **Add Input** -> your `mscaf-net` dataset.
4. Notebook settings (right sidebar):
   - **Accelerator:** GPU P100 (if you get `no kernel image is available`, switch to **GPU T4**)
   - **Internet:** On (needed once to download the pretrained PVT weights)
   - **Persistence:** Files only (optional)

## Notebook cells (paste one per cell)

**Cell 1 - copy the project to the writable folder**
```python
import os, glob, shutil
hits = glob.glob('/kaggle/input/**/training/train_baseline.py', recursive=True)
if hits:                                   # Kaggle auto-extracted the zip
    src = os.path.dirname(os.path.dirname(hits[0]))
    shutil.copytree(src, '/kaggle/working/MSCAF-Net', dirs_exist_ok=True)
else:                                      # zip left as-is
    z = glob.glob('/kaggle/input/**/*.zip', recursive=True)[0]
    shutil.unpack_archive(z, '/kaggle/working')
os.chdir('/kaggle/working/MSCAF-Net')
print(os.listdir('.'))
```

**Cell 2 - check GPU and libraries**
```python
!nvidia-smi
import torch, timm; print(torch.__version__, timm.__version__, torch.cuda.is_available())
```
(If `import timm` fails: `!pip install -q timm`.)

**Cell 3 - build the augmented dataset (about 1 minute)**
```python
!python -m preprocessing.augment_dataset
```

**Cell 4 - train.** Run one mode per cell/notebook version. The Kaggle GPU has 16 GB, so use the paper's batch size 32 directly (no accumulation). `--resume` continues from the last saved epoch if the session is cut off.
```python
!python -m training.train_baseline --mode gcadsn --physical-batch-size 32 --accumulation-steps 1 --num-workers 4 --resume
```
```python
!python -m training.train_baseline --mode pvt    --physical-batch-size 32 --accumulation-steps 1 --num-workers 4 --resume
```
```python
!python -m training.train_baseline --mode fused  --physical-batch-size 32 --accumulation-steps 1 --num-workers 4 --resume
```
Look at the time of the first epoch, then decide how many modes fit in one 12-hour session.

**Cell 5 - evaluate on the test set and build the ablation table**
```python
for m in ['gcadsn', 'pvt', 'fused']:
    !python -m evaluation.evaluate_baseline --mode {m}
!python -m evaluation.build_ablation_table
```

**Cell 6 (optional) - more seeds, to report mean +/- std**
```python
!python -m training.train_baseline --mode fused --physical-batch-size 32 --accumulation-steps 1 --num-workers 4 --seed 1 --tag s1 --resume
!python -m evaluation.evaluate_baseline --mode fused --tag s1
```

## MSCAF-Net (your architecture)
Same training recipe as the baseline; only `--mode mscaf` and its options change.
Files are named `baseline_mscaf_<tag>_best.pth` / `results/test_metrics_mscaf_<tag>.json`.

**Main run first - the full model (multi-scale + cross-attention + adaptive fusion):**
```python
!python -m training.train_baseline --mode mscaf --tag full --physical-batch-size 32 --accumulation-steps 1 --num-workers 4 --resume
!python -m evaluation.evaluate_baseline --mode mscaf --tag full
```
Compare its test accuracy with the base paper's fused model (97.66%).

**Ablation ladder (one run each, same recipe) - shows what each idea contributes:**
```python
# A  ~ base paper structure inside MSCAF-Net (last scale only, concat, no cross-attention)
!python -m training.train_baseline --mode mscaf --tag A --mscaf-scales 7 --fusion concat --no-cross-attention --physical-batch-size 32 --accumulation-steps 1 --num-workers 4 --resume
# B  + multi-scale
!python -m training.train_baseline --mode mscaf --tag B --mscaf-scales 28,14,7 --fusion concat --no-cross-attention --physical-batch-size 32 --accumulation-steps 1 --num-workers 4 --resume
# C  + cross-attention
!python -m training.train_baseline --mode mscaf --tag C --mscaf-scales 28,14,7 --fusion concat --physical-batch-size 32 --accumulation-steps 1 --num-workers 4 --resume
# D  + adaptive fusion  (= the full model, same as --tag full)
```
Evaluate each with `!python -m evaluation.evaluate_baseline --mode mscaf --tag A` (B, C, ...),
then `!python -m evaluation.build_ablation_table` lists every run it finds in `results/`.

**Seeds:** repeat the full model with `--seed 1 --tag full_s1`, `--seed 2 --tag full_s2`
and do the same for the base paper (`--mode fused --seed 1 --tag s1`) so both are reported as mean +/- std.

**Grad-CAM for the new model:** `!python -m explainability.run_gradcam --mode mscaf --tag full`

**If it under-performs:** things to tune (one at a time): `--lr 5e-4` (lr of the new layers),
`--mscaf-dropout 0.2`, `--mscaf-dim 96`, `--mscaf-scales 14,7`.

## Long runs
Use **Save Version -> Save & Run All (Commit)** so training keeps running after you close the browser tab. Everything in `/kaggle/working` is kept as the notebook's Output.

## Bringing results back
From the notebook's **Output** tab download `results/` and `checkpoints/*_best.pth`
(the `*_last.pth` files are only for resuming and are large; delete them first with
`!rm checkpoints/*_last.pth` if you want a smaller download).
Put them into the same folders of the local project.

## What the training script does now (differences from the first version)
- Fused model projects PVT 512 -> 48 channels before concatenation (paper Fig. 8: 48 + 48).
- Trains the full 50 epochs by default (early stopping effectively off).
- Picks the best checkpoint on the **original** 133 validation photos (ties broken by lower validation loss).
- PVT backbone lr 1e-4, other layers 1e-3, 1 warmup epoch then cosine decay.
- Mixed precision (AMP), `--seed`, `--tag`, `--resume`, `--num-workers`.
- Pass `--augmented-validation` to validate on the augmented validation copies like the paper.
