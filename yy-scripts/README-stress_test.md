**1. Parameters to Consider for Stress Testing:**

When using concurrent_api_stress_test_with_gpu_vram_monitoring.py to find the maximum concurrent requests, you should monitor and consider these factors:

* **`concurrent_request_num` (Stress Test Script):** This is the primary input you'll vary. Start low (e.g., 2, 4) and gradually increase it in subsequent test runs.
* **GPU VRAM Usage:** The script monitors this. Watch the "Max Used (MiB)" in the report. If it approaches your GPU's total VRAM, you've likely found a limit. Running out of VRAM will cause errors.
* **GPU Utilization:** Use `nvidia-smi` or `nvtop` in the terminal *during* the test. If utilization consistently hits 100%, the GPU compute power might be the bottleneck.
* **CPU Usage:** Monitor overall CPU usage (`top` or `htop`). High CPU usage could indicate bottlenecks in non-GPU parts like file conversion, text processing, or managing many async tasks.
* **System RAM Usage:** Ensure you aren't running out of system RAM.
* **Network I/O:** Check if network bandwidth is saturated, especially during file downloads, image uploads, or calls to the VL model.
* **Success Rate & Errors (Stress Test Report):** Aim for a high success rate (e.g., >99%). Analyze the "Failure Details" to understand *why* requests are failing (timeouts, specific errors from the API, resource exhaustion).
* **Task Completion Times (Stress Test Report):** Look at the average, max, and median times. A sharp increase in these times as concurrency goes up indicates the system is struggling.
* **External Service Limits:** The VL model (`VL_MODEL_URL`) and upload service (`UPLOAD_URL`) might have their own rate limits or performance constraints that become bottlenecks.
* **API Application Logs:** Check the logs of your running API service for specific error messages not captured by the stress test's status polling.

**2. Semaphore Configuration for Maximum Concurrency:**

2 semaphores:

* `SEMAPHORE = asyncio.Semaphore()` in config.py: This limits the number of `task_runner` coroutines that can execute the core processing logic (PDF extraction, chunking, etc.) concurrently. This directly impacts how many parallel GPU-intensive (`magic_pdf`) tasks run.
* `semaphore = asyncio.Semaphore()` in pdf_processor.py (`gen_img_desc`): This limits the number of concurrent calls *to the external VL model* for generating image descriptions *within* potentially multiple running `task_runner` instances.

**How to Set for Maximum Concurrency:**

Maximum concurrency isn't just about setting semaphores high; it's about matching them to your system's *actual* resource limits, primarily the GPU.

1. **config.py Semaphore (Controls GPU Tasks):**
    * This is likely your **main bottleneck**. The `magic_pdf` library heavily uses the GPU.
    * Monitor GPU VRAM and Utilization using `nvidia-smi` while running the stress test.
    * Find out how much VRAM a single task (`extract_pdf`) typically consumes.
    * Set this semaphore to the maximum number of tasks your GPU can handle simultaneously without running out of VRAM or hitting 100% utilization constantly (which can lead to timeouts). The current value of `4` might be a reasonable starting point or even the maximum if VRAM is limited. Increasing it further might lead to VRAM errors.
2. **pdf_processor.py Semaphore (Controls VL Model Calls):**
    * This controls concurrency towards an *external* service.
    * A value of `16` allows many parallel calls *per running task*. If the config.py semaphore is `4`, you could theoretically have up to `4 * 16 = 64` simultaneous requests to the VL model.
    * **Consider:** Can the VL model endpoint handle this load? Is network latency an issue?
    * If you see timeouts or errors specifically during the "generate image description" phase, or if that phase becomes very slow at higher overall concurrency, the VL model might be the bottleneck. In this case, you might need to *decrease* this semaphore (e.g., to 8 or 12) to avoid overwhelming the external service.

**Recommendation:**

1. **Start with current values:** config.py semaphore = 4, pdf_processor.py semaphore = 16.
2. **Run stress test:** Start `concurrent_request_num` in the script at 4.
3. **Monitor:** Watch GPU VRAM/Util (`nvidia-smi`), CPU (`htop`), and the test report.
4. **Increase `concurrent_request_num`:** Incrementally increase the script's concurrency (e.g., 6, 8, 10...).
5. **Identify Limit:** Find the `concurrent_request_num` where performance degrades significantly (high errors, long task times) or resources (GPU VRAM) are exhausted.
6. **Adjust Semaphores (if needed):**
    * If GPU VRAM is the limit, the config.py semaphore is likely set correctly or might even need lowering. The maximum sustainable `concurrent_request_num` will be close to this semaphore's value.
    * If errors point to the VL model step, consider *lowering* the pdf_processor.py semaphore.

The goal is to find the highest `concurrent_request_num` your system can reliably handle, constrained primarily by the config.py semaphore which gates the GPU-heavy work.

# Selecting Semaphore Test Values

I selected these test values based on established practices for concurrency optimization:

## Power-of-2 Scaling

```python
PDF_SEMAPHORE_VALUES = [1, 2, 4, 8]
IMG_DESC_SEMAPHORE_VALUES = [1, 2, 4, 8, 16]
CONCURRENT_REQUESTS = [4, 8, 16]
```

The power-of-2 sequence is ideal for concurrency testing because:

1. **Exponential Coverage**: It efficiently covers a wide range with fewer test points
2. **Common Threading Pattern**: Many systems perform best at power-of-2 concurrency levels aligned with CPU cores/threads

## Different Limits for Different Operations

* **PDF Processing** (max 8): Limited lower because it's likely more GPU-intensive (VRAM-bounded)
* **Image Description** (max 16): Can go higher because it's probably more API/network-bound than GPU-bound
* **Concurrent Requests** (4-16): Tests realistic load scenarios

## Finding the "Knee of the Curve"

This approach helps identify the "sweet spot" where:

* Adding more concurrency still improves throughput (not bottlenecked)
* But not so much that resources are oversubscribed (causing failures or diminishing returns)

## Recommendations

After initial testing, you might want to:

* **Refine the range**: If best performance is at the edges, expand testing in that direction
* **Add intermediate values**: Test values between the best performers (e.g., if 4 and 8 both perform well, try 6)
* **Test extreme values**: Try a very high value (like 32) to confirm when system degrades
