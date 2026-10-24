# NOTES — CXR AI Teaching Sandbox

## Method
- TorchXRayVision `densenet121-res224-all`, CPU, loaded once at start-up.
- Input: any PNG/JPEG/WebP/BMP up to 10 MB and 4096 px a side → greyscale → square centre crop (`XRayCenterCrop` behaviour) → bilinear resize to 224 → scaled to [-1024, 1024].
- Output: the library's calibrated scores (`op_norm`, 0.5 = per-label operating threshold); top 6 shown.
- Grad-CAM: gradients of the chosen label's calibrated score w.r.t. the ReLU'd last feature map (7×7), channel-averaged weights, ReLU, normalised, bicubic upsampling, semi-transparent overlay.
- An earlier version letterboxed images to a square instead of cropping; it changed scores noticeably (e.g. the pneumothorax film's pneumothorax score fell out of the top 6), so the training-style centre crop was kept.

## Data sources
All six bundled films are from Wikimedia Commons; per-image author, licence and URL are in `samples/ATTRIBUTION.md` and `samples/samples.json`. Images were converted to greyscale, resized to ≤1400 px and re-encoded (no metadata carried over). Candidates were checked for burned-in identifiers; one effusion film (Yale Rosen, CC BY-SA 2.0) was rejected because it showed a name and study date.

There is no Radiopaedia content (its default licence, CC BY-NC-SA, does not fit an openly licensed repo).

## Limitations
- **Not a clinical device.** Research weights; no regulatory clearance.
- **Training data are mostly upright PA/AP films from US/European hospitals.** Supine portable ICU films, paediatric films, photographs of films and phone screenshots are out of distribution.
- **No tube/line position output.** The most frequent ICU CXR question cannot be answered by this model.
- **Hardware shortcuts.** Lines, tubes, ECG leads and side markers can raise scores (the model may learn them as markers of sick patients).
- **Scores are calibrated thresholds, not probabilities.** Many labels sit near 0.5 on normal films.
- **Grad-CAM is coarse** (7×7 grid) and shows what drove the score, not where disease is.
- **Centre crop** can cut off apices or costophrenic angles on very tall or wide images.
- Six images is a demonstration, not an evaluation.
