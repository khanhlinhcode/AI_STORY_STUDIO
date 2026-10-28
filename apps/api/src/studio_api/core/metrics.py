from prometheus_client import Counter, Gauge, Histogram

JOB_TOTAL = Counter("studio_job_total", "Production jobs by terminal state", ["status"])
JOB_DURATION = Histogram("studio_job_duration_seconds", "Job step duration", ["kind"])
QUEUE_DEPTH = Gauge("studio_queue_depth", "Pending jobs", ["queue"])
IMAGE_GENERATION = Histogram("studio_image_gen_seconds", "Image generation duration")
GPU_OOM_TOTAL = Counter("studio_gpu_oom_total", "GPU out-of-memory failures")
ACTIVE_WORKERS = Gauge("studio_active_workers", "Active workers")
STORAGE_BYTES = Gauge("studio_storage_bytes_used", "Storage by workspace", ["workspace"])
