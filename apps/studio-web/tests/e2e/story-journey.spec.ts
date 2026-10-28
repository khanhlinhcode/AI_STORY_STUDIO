import { expect, test } from "@playwright/test";

test("one click selects a recent science article and queues a story", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const suffix = Date.now().toString(36);
  await page.goto("/register");
  await page.getByLabel("Tên của bạn").fill("Người kiểm tra");
  await page.getByLabel("Email").fill(`autopilot-${suffix}@example.com`);
  await page.getByLabel("Tên workspace").fill(`Autopilot ${suffix}`);
  await page.getByLabel("Mật khẩu").fill("browser-test-password-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 30_000 });

  await page.getByRole("button", { name: "Bật Autopilot & tạo video" }).click();
  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/, { timeout: 45_000 });
  await expect(page.getByText("Truyện từ nguồn mới")).toBeVisible();
  await expect(
    page
      .locator('a[href^="https://science.nasa.gov/earth/earth-observatory/"]')
      .first(),
  ).toBeVisible();
  await expect(page.getByText("Chạy tự động 07:00 mỗi ngày")).toBeVisible();
});

test("register, produce a Studio episode, and record a review", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const suffix = Date.now().toString(36);
  const projectTitle = `Vườn sao ${suffix}`;
  const topic = `Chiếc lá biết hát ${suffix}`;

  await page.goto("/register");
  await page.getByLabel("Tên của bạn").fill("Người kiểm tra");
  await page.getByLabel("Email").fill(`story-${suffix}@example.com`);
  await page.getByLabel("Tên workspace").fill(`Story Studio ${suffix}`);
  await page.getByLabel("Mật khẩu").fill("browser-test-password-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 30_000 });

  await page.goto("/projects");
  await page.getByRole("button", { name: "Dự án mới" }).click();
  await page.getByLabel("Tên dự án").fill(projectTitle);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Tạo dự án" })
    .click();
  await page.getByText(projectTitle, { exact: true }).click();
  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/);

  await page.getByRole("button", { name: "Tập mới" }).click();
  await page.getByLabel("Chủ đề").fill(topic);
  await page.getByLabel("Chế độ").selectOption("studio");
  await page.getByRole("button", { name: "Tạo storyboard" }).click();
  await expect(page).toHaveURL(/\/storyboard$/, { timeout: 120_000 });
  const episodeId = page.url().split("/").at(-2);
  expect(episodeId).toBeTruthy();
  await expect(page.getByText("Các cảnh · 6")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sản xuất" })).toBeEnabled();
  await page.getByRole("button", { name: "Sản xuất" }).click();
  await expect(page).toHaveURL(/\/jobs\/[0-9a-f-]+$/);
  await expect(
    page.getByRole("heading", { name: "Step timeline" }),
  ).toBeVisible();
  await page.goto(`/episodes/${episodeId}/export`);
  await expect(
    page.getByRole("heading", { name: "Duyệt nội dung Studio" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Duyệt script" }).click();
  await expect(page.getByText("Script mới nhất: đã duyệt.")).toBeVisible();
  await page.getByRole("button", { name: "Nhận nhiệm vụ review" }).click();
  await page
    .getByLabel("Ghi chú review")
    .fill("Đã đọc và kiểm tra cả sáu cảnh.");
  await page.getByRole("button", { name: "Duyệt nội dung" }).click();
  await expect(page.getByText(/Review revision .*: approved/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Tạo gói export" }),
  ).toBeDisabled();
});
