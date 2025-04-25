# Semaphore Optimization Report

Test Run: 20250424_075142

This report compares different combinations of PDF_PROCESSOR_SEMAPHORE and IMG_DESC_SEMAPHORE values to find the optimal configuration for throughput and stability.

All images can be found in the `images/` directory.

## Runtime Statistics

- Total test combinations: 60
- Total runtime: 8:32:40
- Average test runtime: 0:08:32
- Fastest test: 0:04:12
- Slowest test: 0:10:20

## Success Rate (%) - Concurrency: 4

|   pdf_sem |     1 |     2 |     4 |     8 |    16 |
|-----------|-------|-------|-------|-------|-------|
|         1 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
|         2 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
|         4 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
|         8 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

## Success Rate (%) - Concurrency: 8

|   pdf_sem |     1 |     2 |     4 |     8 |    16 |
|-----------|-------|-------|-------|-------|-------|
|         1 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
|         2 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
|         4 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
|         8 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

## Success Rate (%) - Concurrency: 16

|   pdf_sem |    1 |    2 |    4 |    8 |   16 |
|-----------|------|------|------|------|------|
|         1 | 62.5 | 62.5 | 62.5 | 62.5 | 62.5 |
|         2 | 68.8 | 62.5 | 62.5 | 68.8 | 62.5 |
|         4 | 62.5 | 68.8 | 62.5 | 68.8 | 62.5 |
|         8 | 68.8 | 68.8 | 62.5 | 62.5 | 62.5 |

## Average Processing Time (s) - Concurrency: 4

|   pdf_sem |      1 |      2 |      4 |      8 |     16 |
|-----------|--------|--------|--------|--------|--------|
|         1 | 153.14 | 374.94 | 364.10 | 372.63 | 358.02 |
|         2 | 378.01 | 355.25 | 377.87 | 373.21 | 354.57 |
|         4 | 361.33 | 382.79 | 352.12 | 377.11 | 355.09 |
|         8 | 375.95 | 349.52 | 348.24 | 365.61 | 369.78 |

## Average Processing Time (s) - Concurrency: 8

|   pdf_sem |      1 |      2 |      4 |      8 |     16 |
|-----------|--------|--------|--------|--------|--------|
|         1 | 251.64 | 249.54 | 248.10 | 245.01 | 244.83 |
|         2 | 252.70 | 243.90 | 252.78 | 255.52 | 250.75 |
|         4 | 244.92 | 253.43 | 246.21 | 240.62 | 247.07 |
|         8 | 252.30 | 244.83 | 255.08 | 250.05 | 246.80 |

## Average Processing Time (s) - Concurrency: 16

|   pdf_sem |      1 |      2 |      4 |      8 |     16 |
|-----------|--------|--------|--------|--------|--------|
|         1 | 309.21 | 302.42 | 307.83 | 301.18 | 316.92 |
|         2 | 323.16 | 307.63 | 308.88 | 327.95 | 308.72 |
|         4 | 307.76 | 328.14 | 303.46 | 325.51 | 307.39 |
|         8 | 319.92 | 315.83 | 302.28 | 304.81 | 305.72 |

## Max VRAM Usage (MiB) - Concurrency: 4

|   pdf_sem |    1 |    2 |    4 |    8 |   16 |
|-----------|------|------|------|------|------|
|         1 | 3964 | 3964 | 3964 | 3964 | 3964 |
|         2 | 3964 | 3964 | 3964 | 3964 | 3964 |
|         4 | 3964 | 3964 | 3964 | 3964 | 3964 |
|         8 | 3964 | 3964 | 3964 | 3964 | 3964 |

## Max VRAM Usage (MiB) - Concurrency: 8

|   pdf_sem |    1 |    2 |    4 |    8 |   16 |
|-----------|------|------|------|------|------|
|         1 | 3964 | 3964 | 3964 | 3964 | 3964 |
|         2 | 3964 | 3964 | 3964 | 3964 | 3964 |
|         4 | 3964 | 3964 | 3964 | 3964 | 3964 |
|         8 | 3964 | 3964 | 3964 | 3964 | 3964 |

## Max VRAM Usage (MiB) - Concurrency: 16

|   pdf_sem |    1 |    2 |    4 |    8 |   16 |
|-----------|------|------|------|------|------|
|         1 | 3964 | 3964 | 3964 | 3964 | 3964 |
|         2 | 3964 | 3964 | 3964 | 3964 | 3964 |
|         4 | 3964 | 3964 | 3964 | 3964 | 3964 |
|         8 | 3964 | 3964 | 3964 | 3964 | 3964 |

## Test Runtime (s) - Concurrency: 4

|   pdf_sem |   1 |   2 |   4 |   8 |   16 |
|-----------|-----|-----|-----|-----|------|
|         1 | 252 | 476 | 467 | 474 |  460 |
|         2 | 478 | 457 | 477 | 479 |  455 |
|         4 | 463 | 486 | 455 | 478 |  458 |
|         8 | 477 | 453 | 451 | 466 |  469 |

## Test Runtime (s) - Concurrency: 8

|   pdf_sem |   1 |   2 |   4 |   8 |   16 |
|-----------|-----|-----|-----|-----|------|
|         1 | 465 | 462 | 462 | 456 |  459 |
|         2 | 466 | 456 | 471 | 465 |  466 |
|         4 | 453 | 466 | 457 | 445 |  461 |
|         8 | 465 | 453 | 467 | 464 |  458 |

## Test Runtime (s) - Concurrency: 16

|   pdf_sem |   1 |   2 |   4 |   8 |   16 |
|-----------|-----|-----|-----|-----|------|
|         1 | 621 | 621 | 621 | 621 |  621 |
|         2 | 621 | 621 | 621 | 621 |  621 |
|         4 | 621 | 621 | 620 | 621 |  621 |
|         8 | 621 | 621 | 621 | 621 |  621 |

## Configurations Analysis: Throughput

Converting average processing times to actual throughput:

| Configuration | Concurrency | Avg Time (s) | Throughput (req/min) |
|---------------|-------------|--------------|----------------------|
| PDF=1, IMG=1, Conc=4 | 4 | 153.14 | ~1.57 |
| PDF=4, IMG=8, Conc=8 | 8 | 240.62 | ~1.99 |
| PDF=2, IMG=2, Conc=8 | 8 | 243.90 | ~1.97 |

## Throughput Recommendation

**RECOMMENDED CONFIGURATION:**

- PDF_PROCESSOR_SEMAPHORE=4
- IMG_DESC_SEMAPHORE=8
- Concurrency=8

## Configurations Analysis: Speed

Configurations with highest success rates, sorted by processing speed:

|   Rank |   PDF Semaphore |   IMG Semaphore |   Concurrency |   Success Rate (%) |   Avg Time (s) |   Max VRAM (MiB) | Test Runtime   |
|--------|-----------------|-----------------|---------------|--------------------|----------------|------------------|----------------|
|      1 |               1 |               1 |             4 |                100 |         153.14 |             3964 | 0:04:12        |
|     41 |               4 |               8 |             8 |                100 |         240.62 |             3964 | 0:07:24        |
|     20 |               2 |               2 |             8 |                100 |         243.9  |             3964 | 0:07:35        |
|     14 |               1 |              16 |             8 |                100 |         244.83 |             3964 | 0:07:38        |
|     50 |               8 |               2 |             8 |                100 |         244.83 |             3964 | 0:07:33        |

## Speed Recommendation

**RECOMMENDED CONFIGURATION:**

- PDF_PROCESSOR_SEMAPHORE=1
- IMG_DESC_SEMAPHORE=1
- Handles 4 concurrent requests with 100.0% success rate and 153.14s average processing time

## Visualizations

Click the links below to view the visualization images:

### Success Rate (Concurrency: 4)

![Success Rate (Concurrency: 4)](images/success_rate_heatmap_conc4.png)

[View full size](images/success_rate_heatmap_conc4.png)

### Success Rate (Concurrency: 8)

![Success Rate (Concurrency: 8)](images/success_rate_heatmap_conc8.png)

[View full size](images/success_rate_heatmap_conc8.png)

### Success Rate (Concurrency: 16)

![Success Rate (Concurrency: 16)](images/success_rate_heatmap_conc16.png)

[View full size](images/success_rate_heatmap_conc16.png)

### Average Time (Concurrency: 4)

![Average Time (Concurrency: 4)](images/avg_time_heatmap_conc4.png)

[View full size](images/avg_time_heatmap_conc4.png)

### Average Time (Concurrency: 8)

![Average Time (Concurrency: 8)](images/avg_time_heatmap_conc8.png)

[View full size](images/avg_time_heatmap_conc8.png)

### Average Time (Concurrency: 16)

![Average Time (Concurrency: 16)](images/avg_time_heatmap_conc16.png)

[View full size](images/avg_time_heatmap_conc16.png)

### VRAM Usage (Concurrency: 4)

![VRAM Usage (Concurrency: 4)](images/vram_usage_heatmap_conc4.png)

[View full size](images/vram_usage_heatmap_conc4.png)

### VRAM Usage (Concurrency: 8)

![VRAM Usage (Concurrency: 8)](images/vram_usage_heatmap_conc8.png)

[View full size](images/vram_usage_heatmap_conc8.png)

### VRAM Usage (Concurrency: 16)

![VRAM Usage (Concurrency: 16)](images/vram_usage_heatmap_conc16.png)

[View full size](images/vram_usage_heatmap_conc16.png)

### Test Runtime (Concurrency: 4)

![Test Runtime (Concurrency: 4)](images/test_runtime_heatmap_conc4.png)

[View full size](images/test_runtime_heatmap_conc4.png)

### Test Runtime (Concurrency: 8)

![Test Runtime (Concurrency: 8)](images/test_runtime_heatmap_conc8.png)

[View full size](images/test_runtime_heatmap_conc8.png)

### Test Runtime (Concurrency: 16)

![Test Runtime (Concurrency: 16)](images/test_runtime_heatmap_conc16.png)

[View full size](images/test_runtime_heatmap_conc16.png)
