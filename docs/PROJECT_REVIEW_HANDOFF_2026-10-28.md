# AI Story Studio — báo cáo hiện trạng để Claude đánh giá

**Ngày chốt bằng chứng:** 2026-10-28, giờ Việt Nam.  
**Phạm vi:** mã nguồn và stack cục bộ tại `AI_STORY_STUDIO`, đối chiếu với *Complete Plan v2.0 + Claude Code Prompts P01–P13* và *Master Implementation Plan* do chủ dự án cung cấp.  
**Mục đích:** giúp người đánh giá độc lập nhận diện chính xác phần đã chạy thật, phần mới có mã, điểm lệch kế hoạch và thứ tự xử lý tiếp theo. Đây không phải biên bản nghiệm thu sản phẩm.

## 1. Kết luận điều hành

| Câu hỏi | Kết luận có bằng chứng |
| --- | --- |
| Dự án đang ở mức nào? | **Alpha nội bộ / MVP kỹ thuật cục bộ.** Luồng một nút từ bài khoa học/thiên nhiên mới đến MP4 đã chạy end to end; video **chưa đủ điều kiện xuất bản tự động**. Không gán điểm readiness `/100` vì kế hoạch yêu cầu kiểm toán độc lập và dữ liệu đo trước khi chấm. |
| Đã làm được việc gì quan trọng nhất? | Dashboard tạo dự án Autopilot, đọc NASA Earth Observatory RSS trong 7 ngày gần nhất, lưu URL/ngày/ảnh nguồn, viết truyện 6 cảnh, tạo WAV tiếng Việt, render H.264/AAC dọc và ngang, hiển thị job và chặn export khi QC chưa đạt. Có lịch 07:00 hằng ngày theo dự án. |
| Model và media đang chạy? | `AI_STORY_MODE=ollama`, `OLLAMA_MODEL=qwen3:4b`; `AI_ADAPTER_MODE=fake` nhưng **Autopilot dùng ảnh gốc NASA** thay cho ảnh fixture; `AI_VOICE_MODE=macos` dùng giọng hệ thống Apple Linh qua bridge. MFLUX/ComfyUI, VieNeu và Wan chưa được kiểm chứng trong đường chạy thực tế này. |
| Có LoRA chưa? | **Chưa.** `ACTIVE_LORA_NAME` rỗng; không có checkpoint, dataset, training run hay promotion/rollback LoRA đã xác minh. Mã có nhánh gắn LoRA vào workflow ComfyUI và một test cấu trúc, không đồng nghĩa có LoRA đang chạy. |
| Rủi ro chặn phát hành lớn nhất? | Kịch bản còn sai/khó hiểu về địa lý dù một số lỗi hiển nhiên đã được lọc; 6 cảnh lặp cùng ảnh nguồn; chưa có kiểm định tự động đáng tin cậy cho sự thật khoa học, an toàn trẻ em, chất lượng hình/giọng và quyền sử dụng media. QC đang `blocking=true`. |
| Kết quả kinh doanh? | Chưa có bằng chứng video công khai hay analytics; database local hiện có `0` bản `exports`. Các KPI của kế hoạch chưa được chứng minh. |

## 2. Cách đọc trạng thái

| Nhãn | Ý nghĩa |
| --- | --- |
| **Đã chạy thật** | Có bằng chứng từ lần chạy trên stack cục bộ, không chỉ là file nguồn. |
| **Có mã + test** | Chức năng có implementation và test tự động, chưa chứng minh đầy đủ trên backend/model thật. |
| **Một phần** | Có nền tảng, nhưng thiếu tiêu chí chấp nhận quan trọng trong prompt. |
| **Chưa kiểm chứng** | Có cấu hình/adapter/template, chưa có lần chạy thành công tương ứng. |
| **Chưa làm** | Không thấy implementation hoặc bằng chứng đáp ứng mục tiêu. |

## 3. Môi trường và kiến trúc đang dùng

| Thành phần | Hiện trạng | Đối chiếu kế hoạch / lưu ý |
| --- | --- | --- |
| Máy | Apple M1, 8 GiB RAM hợp nhất; audit chi tiết tại `docs/architecture/RUNTIME_COMPATIBILITY.md`. | Thấp hơn ngưỡng 32 GiB mà Plan v2 gợi ý cho tạo ảnh local; cần đánh giá lại backend ảnh. |
| Web | Next.js **16.4.3**, React 19.1.0, TypeScript; `http://localhost:3000`. | Prompt P01/P10 ghi Next.js 15; đây là lệch phiên bản thực tế, cần Claude đánh giá rủi ro tương thích. |
| API | FastAPI 0.115.12, SQLAlchemy 2.0.41, PostgreSQL 16; `http://localhost:8000/docs`. | Modular monolith, auth/roles/workspace và route theo module đã có. |
| Hàng đợi | Redis 7 + Celery 5.5.3; dispatcher, CPU worker, beat. | Job và bước được lưu trong PostgreSQL; có outbox, lease và khôi phục lượt sinh nguồn bỏ dở sau 20 phút. |
| Storage | Silo chạy S3 API tương thích MinIO, content-addressed SHA-256. | Thay image `minio/minio` trong plan vì vấn đề image; cần thẩm định license/backup/tương thích trước production. |
| Script | Ollama 0.40.11 + **Qwen3 4B**, local, structured JSON. | Prompt gốc đề xuất Qwen2.5 7B. Bản nhỏ hơn phù hợp máy hơn nhưng lỗi factual vẫn rõ. |
| Ảnh | Một ảnh chính từ bài NASA cho cả 6 cảnh; chủ đề nhập tay vẫn có thể dùng fixture. | **Chưa có 6 ảnh riêng, nhất quán nhân vật**, chưa phải pipeline MFLUX/FLUX.2 đã benchmark. |
| Giọng | macOS `say`/Apple Linh `vi_VN` qua local voice bridge; WAV từng cảnh. | Là giọng hệ thống, **không phải** VieNeu-TTS hay voice model/voice clone. Chưa có đánh giá người nghe bản ngữ và quyền giọng cho mục đích phát hành. |
| Video | FFmpeg; preview H.264/AAC + SRT + thumbnail. | Với `AI_ADAPTER_MODE=fake`, output chỉ **640×360** và **360×640**, thấp hơn mục tiêu 1920×1080 và 1080×1920 của P08. Không có Wan2.2 motion. |
| MLOps/ops phụ trợ | Compose có MLflow, n8n, Prometheus, Grafana, Jaeger; CI YAML và dashboard template có mặt. | Các service phụ trợ không nằm trong tập core đang chạy khi kiểm tra; không suy ra workflow, cảnh báo, tracing hay training đã hoạt động. |
| Repository | Thư mục hiện **không có `.git`** (`git rev-parse` thất bại). | Không thể kiểm chứng commit, remote, branch, kết quả GitHub Actions hoặc lịch sử thay đổi từ bản sao hiện tại. |

**Đường đi đã chạy thật:** Dashboard/Next.js → FastAPI → NASA RSS → `SourceStory`/PostgreSQL → Celery → Ollama → 6 `SceneRevision` → ảnh NASA + 6 WAV Apple Linh → FFmpeg → S3 assets + manifest/QC → Job Center. Chủ đề nhập tay vẫn tồn tại như một lựa chọn riêng.

## 4. Bảng đối chiếu từng prompt P01–P13

| Prompt | Đã có / bằng chứng | Còn thiếu so với acceptance của prompt | Đánh giá |
| --- | --- | --- | --- |
| **P01 — Foundation/Compose** | Monorepo `apps/`, `workers/`, `packages/`, `infra/`, 9 ADR; 4 JSON Schema; Compose; `.env.example`; CI workflow; core stack đang chạy. `make check` qua. | Chưa có `.git`; không có chứng cứ CI remote xanh. Chưa xác minh đồng thời toàn bộ MLflow/n8n/Grafana/Jaeger healthy; một số thư mục `ml/`/training trong plan chưa thành pipeline thực. | **Một phần; nền tảng cục bộ tốt.** |
| **P02 — Backend core** | Auth register/login/refresh, workspace/role, health và capabilities, module routers; test BOLA, viewer không POST, SSRF loopback. `/health` báo DB/Redis/Ollama/voice ready. | Chưa có audit toàn bộ route cho BOLA/RBAC, chưa có bài test “DB down”/load/staging theo acceptance; chưa chứng minh chuẩn OTel toàn tuyến. | **Có mã + test; chưa nghiệm thu bảo mật.** |
| **P03 — AI adapters** | Protocol/types, Fake, Ollama, ComfyUI/MFLUX bridge, TTS, FFmpeg, Wan stub; test LoRA node injection; Ollama và Mac voice chạy thật. | ComfyUI/MFLUX, VieNeu, Wan chưa benchmark/chạy thành công trên máy này; MFLUX class hiện kế thừa cách gọi HTTP của ComfyUI. Image generation thực chưa nằm trong demo. | **Một phần.** |
| **P04 — Models/migrations** | Các model chính cho user/workspace/project/episode/script/scene/asset/job/outbox/QC/export/AI model/source; migration `0001`–`0004`, DB báo `0004 (head)`. | `0001_initial.py` gọi `Base.metadata.create_all()`/`drop_all()` thay vì DDL từng bảng, khó kiểm tra/sửa migration lịch sử; test FK/index/optimistic conflict chưa bao phủ toàn bộ yêu cầu. | **Một phần.** |
| **P05 — Story/Character** | Qwen3 4B sinh JSON 6 cảnh, validate schema, lưu script/scene revisions; có CRUD/history nhân vật và bộ lọc keyword/địa lý đơn giản. | LLM vẫn tạo câu sai/khó hiểu về khoa học; chưa chứng minh 2 nhân vật nhất quán qua 6 cảnh, Character Bible/rights được duyệt và test đầy đủ. Một số API flow khác chi tiết P05 (ví dụ trả `202 + job_id` cho script) cần audit. | **Một phần; factual là blocker.** |
| **P06 — Jobs/outbox** | ProductionJob/JobStep, idempotency, outbox, Celery, 14/14 bước trên demo thật, retry và stale source recovery; SSE endpoint có mã. | Chưa có đầy đủ 5 fault-injection tests của prompt, đặc biệt kill worker giữa render, duplicate delivery, storage full, cancel/orphan cleanup dưới stack thật. SSE phía UI chưa được xác minh live. | **Một phần; happy path đã chạy thật.** |
| **P07 — Asset/image** | Upload MIME/size/hash, dedup SHA-256, dependency DAG; scene variant/regenerate UI; ảnh NASA có URL/credit/rights flag và lưu S3. | Native image backend chưa chạy; tất cả 6 scene của Autopilot dùng **cùng ảnh NASA**. Chưa có ảnh minh họa AI riêng, kiểm tra độ nhất quán nhân vật, model/seed reproducibility thực. | **Asset registry có mã; image generation chưa đạt.** |
| **P08 — Audio/video** | Apple Linh tạo WAV 6 cảnh; FFmpeg render dọc/ngang, SRT, thumbnail, ffprobe H.264/AAC; demo 58,755 giây. | VieNeu chưa chạy; output preview 360/640 thay vì full HD; chưa đo loudness −14 LUFS, silence, pronunciation/sync bởi người nghe; BRISQUE và music mix chưa được nghiệm thu. | **Preview kỹ thuật đã chạy thật, P08 chưa đủ.** |
| **P09 — Automation/n8n** | NASA feed mới ≤7 ngày, lọc chủ đề nhạy cảm, chống dùng lại bài theo dự án; một nút Autopilot; Celery beat 07:00; batch/webhook và 3 template n8n. | Template n8n đang inactive; Google Sheets status writeback/credential và Telegram delivery chưa xác minh; chưa có chứng cứ batch 3 chủ đề hoàn tất thực tế. Nguồn hiện chỉ là NASA Earth Observatory RSS. | **Autopilot native đã chạy; n8n tích hợp một phần.** |
| **P10 — Studio web** | Register/login; dashboard/project/storyboard/Job Center/Models/Assets/Admin/export; reorder/compare/variant trong storyboard; test Vitest 3 cases; Playwright specs có mặt. | Không dùng Auth.js theo prompt mà dùng session cookie route; chưa có số đo Lighthouse/Web Vitals, axe-core/accessibility, usability test; chưa chạy lại E2E trong lần đánh giá này. | **Giao diện dùng được cục bộ; acceptance UX chưa đủ.** |
| **P11 — QC/review/export** | SRT validation, technical checks, Studio script/review approval, QC record, ZIP/publish metadata; test export bị chặn và flow review. Demo thật có `blocking=true`, export DB `0`. | QC report hiện **cố ý luôn chặn** sourced preview; BRISQUE, silence/loudness, safety classifier, rights verification và human rubric chưa hoàn thiện. Chưa có một sourced package được duyệt và xuất đúng quy trình. | **Cổng chặn an toàn; chưa đủ để phát hành.** |
| **P12 — MLflow/DVC/LoRA** | Compose định nghĩa MLflow và S3 buckets; `AIModel`/`ModelDeployment` schema, LoRA injection branch. | Chưa có DVC dataset, training pipeline, Musubi run, MLflow run, checkpoint, eval/promote/rollback; `ACTIVE_LORA_NAME=`. Trigger ADR-007 chưa được chứng minh. | **Chưa triển khai LoRA.** |
| **P13 — Observability/security** | `/metrics`/Prometheus metric declarations, Grafana/alert configs, rate limit đơn node, SSRF URL guard, RBAC test; các cổng local ràng buộc `127.0.0.1`. | Chưa có OTel full trace, alert thử nghiệm, backup/restore, staging, runbook, security/load/a11y audit; rate limit in-memory không phù hợp đa instance. | **Một phần; chưa production-ready.** |

### Sai khác giữa hai tài liệu kế hoạch cần Claude phân xử

| Vấn đề | Bằng chứng / hệ quả |
| --- | --- |
| Gate LoRA | Plan v2 cuối văn bản nói P12–P13 chỉ sau **≥20 video đã published**; ADR-007 lại cho phép train character LoRA khi **≥5 episode published + ≥15 ảnh rights-verified + ≥30% ảnh bị reject cùng episode**. Hiện cả hai ngưỡng đều chưa có bằng chứng đạt. Cần thống nhất gate nào điều khiển *khởi động P12* và gate nào điều khiển *một training run*. |
| Khái niệm “Automation mode” | Plan nói tự động đến MP4 và dùng automated QC thay manual approval; implementation tạo preview tự động nhưng **không mở export** khi QC chưa có bằng chứng. Đây là lựa chọn an toàn, cần xác nhận là phù hợp mục tiêu sản phẩm. |
| P0 story format | Master Plan yêu cầu 2 nhân vật nhất quán và đầu ra gần 60 giây; demo kỹ thuật đạt thời lượng nhưng truyện nguồn NASA chủ yếu kể về một tảng băng và dùng cùng một ảnh. Cần quyết định ưu tiên sản phẩm giữa “truyện khoa học có nguồn” và “2 nhân vật hoạt hình” trước khi build image pipeline. |

## 5. Bằng chứng kiểm thử và ranh giới kết luận

| Bằng chứng kiểm tra ngày 2026-10-28 | Kết quả | Điều **không** được suy ra |
| --- | --- | --- |
| `make check` | 4 JSON Schemas valid; Ruff, mypy (74 source files), ESLint, TypeScript pass; **22 backend tests**, **3 frontend unit tests** pass. | Không chứng minh hiệu quả factual, quyền ảnh, a11y, CI remote, restore hoặc tải nhiều user. Có cảnh báo `jsonschema.RefResolver` deprecated và Vitest config loader. |
| `docker compose ... ps -a` + `GET /health` | Web/API/dispatcher/CPU worker/beat và Postgres/Redis/S3 core đang chạy; API báo `status=ok`, DB/Redis và Ollama/macOS voice ready; Wan unavailable. | Không chứng minh các service n8n/MLflow/Grafana/Jaeger đã chạy và tích hợp. |
| `alembic current` | `0004 (head)` trên PostgreSQL local. | Không chứng minh migration upgrade/downgrade trên DB staging có dữ liệu. |
| Lần Autopilot thực, job `073ebbd2-143f-4d8d-baa2-b3f0f3ad229a` | NASA source `A-81 Reaches South Georgia`; `SourceStory` và job `completed`; **14/14** steps completed. Video dọc 360×640, 13,359,753 bytes; ngang 640×360, 17,207,036 bytes; cả hai H.264/AAC, **58.755 giây**. | “Job completed” chỉ xác nhận dựng media; không xác nhận nội dung đạt chuẩn phát hành. |
| QC của job trên | `passed=false`, `blocking=true`; lý do: kiểm tra image quality, child safety và voice rights chưa được xác minh. `exports` trong DB local = **0**. | Không được gọi các MP4 này là bản xuất bản hoặc sản phẩm hoàn thiện. |
| Xem khung hình MP4 | Ảnh NASA, nhãn nguồn và caption nhìn thấy ở cả hai tỷ lệ; không có khung đen lớn. | Không thay thế kiểm tra toàn bộ từng khung hình/âm thanh trên điện thoại và review người dùng. |
| Review lời kể tự sinh | Lỗi “Bắc Cực”/đảo hướng đã từng xảy ra; rule mới loại được một số lượt. Bản được chấp nhận vẫn có câu “điểm cực Nam của Nam Cực” và “Bắc - Bắc Tây Nam Cực” sai/khó hiểu. | Bộ lọc regex hiện tại **không phải** fact checker và chưa đủ cho xuất bản khoa học tự động. |

**Video mẫu để xem nội bộ:** `local-data/exports/autopilot-portrait.mp4` và `local-data/exports/autopilot-landscape.mp4`. Cả hai chứa lời kể chưa duyệt. File `scripts/verify/live_stack.py` có chế độ `--autopilot --output-dir local-data/exports`; lệnh này tạo workspace/job kiểm thử mới, gọi Qwen3 4B và có thể mất nhiều phút trên máy 8 GiB. Browser Playwright specs nằm tại `apps/studio-web/tests/e2e/`; không chạy lại trong lần lập báo cáo này.

## 6. Rủi ro và việc cần làm, theo thứ tự

| Ưu tiên | Vấn đề thực tế | Tiêu chí đóng rõ ràng |
| --- | --- | --- |
| **P0 — trước mọi export** | Factual grounding: model trộn dữ kiện về đối tượng khác, đảo cực/hướng, tạo câu địa lý vô nghĩa. Nguồn RSS mới có thông tin nhưng prompt + regex không đảm bảo đúng. | Tạo bộ dữ kiện có trích dẫn đến đoạn nguồn, tách “đối tượng chính” khỏi phần so sánh; mỗi claim khoa học trong narration phải được liên kết với evidence hoặc bị chuyển thành hư cấu rõ ràng. Có tập benchmark các bài NASA với kiểm duyệt của người; zero lỗi nghiêm trọng trong tập nghiệm thu. |
| **P0** | Video lặp một ảnh NASA cho 6 cảnh; chưa đạt yêu cầu ảnh minh họa riêng, nhất quán nhân vật hay 2.5D motion theo plan. | Chốt backend ảnh khả thi với M1/8 GiB hoặc máy khác; benchmark RAM/thời gian/chất lượng/quyền weights. Dựng 6 ảnh riêng có lineage, review nhân vật và không dùng fixture ở bản phát hành. |
| **P0** | QC hiện chặn tất cả sourced preview vì thiếu kiểm định ảnh, trẻ em, giọng và quyền. | Triển khai/đo các gate script, image, audio, video, safety và quyền; review thủ công, ghi người duyệt/quyết định; chỉ mở export sau khi các gate thực sự pass. |
| **P0** | Metadata quyền ảnh NASA và quyền giọng mới ở mức “review required”. | Có ma trận license/terms cho chính ảnh, weights, voice, music và nội dung; ghi quyết định sử dụng và attribution theo asset trước mọi phát hành/monetization. |
| **P1** | Lời đọc Apple Linh chạy được nhưng chưa có đánh giá phát âm, loudness, silence, cảm giác nghe truyện. | Review mẫu bởi người Việt, đo audio tự động và xác nhận quyền giọng; so sánh với VieNeu nếu vẫn muốn bám kế hoạch. |
| **P1** | Reliability: đã có reaper cho generation bỏ dở nhưng thiếu fault injection đầy đủ và đo thời gian/memory. | Kill worker giữa các bước, duplicate task, storage full, cancel, restart Docker; chứng minh idempotency không tạo asset/job thừa; ghi p50/p95 latency và peak RAM. |
| **P1** | Repo chưa có `.git`; CI YAML không có run được kiểm chứng. | Khởi tạo/đưa repo vào version control, khóa phiên bản dependency và chạy CI trên branch/PR; staging riêng với migration + rollback drill. |
| **P1** | Monitoring, alert, backup, restore và bảo mật mới là phần khung. | Chạy stack phụ trợ, thử alert, backup/restore PostgreSQL/S3, kiểm thử cross-tenant + upload/SSRF/rate limit dưới staging, ghi runbook. |
| **Sau trigger** | LoRA/MLOps. | Chỉ khởi động khi gate trong ADR-007 và roadmap được chủ dự án thống nhất và đạt bằng chứng; dùng dataset có quyền, baseline, holdout, MLflow/DVC và rollback. LoRA không giải quyết factual story hiện tại. |

## 7. Đề nghị Claude phản biện độc lập

Sau khi nhận báo cáo **và repository**, đề nghị Claude:

1. Kiểm chứng từng dòng P01–P13 bằng cách mở mã/test/Compose, đánh dấu chỗ báo cáo nhận định sai hoặc thiếu bằng chứng; **không** suy “có file” thành “chạy thật”.
2. Đánh giá độ đúng của luồng NASA → script, đặc biệt việc tóm tắt RSS chứa dữ kiện của *đối tượng khác* và bộ lọc regex `apps/api/src/studio_api/modules/models/adapters/ollama.py`. Đề xuất kiến trúc claim/evidence và bài test cho lời kể trẻ em.
3. Xếp hạng blocker P0 để phát hành một video thật trên M1/8 GiB: backend ảnh, giọng, quyền media, QC, render resolution, hiệu năng. Đưa ra các acceptance test có thể chạy, không đưa điểm phần trăm thiếu dữ liệu.
4. Audit tính bền vững của Celery/outbox/lease/idempotency khi Docker hoặc Ollama dừng giữa lượt sinh/render; tìm race condition, stale revision và khả năng retry mất task.
5. So sánh hai gate LoRA/Phase 2 trong plan, đề xuất một decision record thống nhất. **Không** đề xuất train LoRA trước khi có dataset có quyền và baseline lỗi nhân vật.
6. Lập kế hoạch ngắn nhất để đi từ **alpha nội bộ** đến **một video được duyệt để phát hành**, với thứ tự, file cần sửa, test chứng minh và điều kiện dừng từng bước.

### Các file bắt đầu review

| Mục | Đường dẫn |
| --- | --- |
| Tổng quan/hiện trạng | `README.md`, `docs/IMPLEMENTATION_STATUS.md`, `docs/architecture/RUNTIME_COMPATIBILITY.md`, `docs/architecture/adr/ADR-007.md`, `docs/architecture/adr/ADR-009.md` |
| Source/Autopilot | `apps/api/src/studio_api/modules/workflows/source_feed.py`, `autopilot.py`, `automation_router.py`; `workers/dispatcher/tasks.py` |
| Script/AI | `apps/api/src/studio_api/modules/models/adapters/ollama.py`, `registry.py`, `source_image.py`, `tts.py`; `apps/api/src/studio_api/modules/narrative/service.py` |
| Media/QC/export | `workers/cpu_render/pipeline.py`, `render.py`; `apps/api/src/studio_api/modules/evaluation/auto_qc.py`; `apps/api/src/studio_api/modules/exports/service.py` |
| Infra/UI/tests | `infra/compose/local/docker-compose.yml`, `.github/workflows/ci.yml`, `apps/studio-web/src/app/(studio)/`, `apps/api/tests/`, `apps/studio-web/tests/e2e/`, `scripts/verify/live_stack.py` |

**Lệnh kiểm tra đọc lại:** `make check`; `docker compose --env-file infra/compose/local/.env -f infra/compose/local/docker-compose.yml ps -a`; `docker compose --env-file infra/compose/local/.env -f infra/compose/local/docker-compose.yml exec -T studio-api alembic current`. Không gửi nội dung `.env` vì có secret; các chế độ AI cần thiết đã nêu ở trên.
