# Train-Test Leakage Risk in Feature Scaling

**Authors:** OpenCritique Commons maintainers  
**License:** Apache-2.0  
**Domain profile:** empirical_ml  
**Rights:** Maintainer-authored sample conformance manuscript. Not a natural research paper.

## Abstract

Empirical ML sample describing a common preprocessing mistake.

## Pipeline

Features were standardized using statistics computed on the full dataset.
The baseline uses default hyperparameters from the reference library.
Standardization on the full dataset risks optimistic evaluation through leakage.
Untuned baselines weaken comparative claims about proposed gains.

## Calibration

Calibration curves indicate near-perfect probability estimates.
Visual near-overlap is not a substitute for reported Brier or ECE statistics
in a complete evaluation, but this sample intentionally stays brief.
