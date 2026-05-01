import { expect, test } from "@playwright/test";

test.describe("VoiceNav admin dashboard", () => {
  test("loads overview metrics", async ({ page }) => {
    await page.route("http://127.0.0.1:8000/health", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "ok",
          active_sessions: 2,
          transcript_queue_depth: 1,
          webhook_dedupe_cache: 3,
        }),
      });
    });
    await page.route("http://127.0.0.1:8000/api/presentations", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            presentation_id: "demo",
            filename: "deck.pdf",
            status: "ready",
            total_pages: 10,
            indexed_pages: 10,
          },
        ]),
      });
    });
    await page.route("http://127.0.0.1:8000/api/agents", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            agent_name: "default",
            active_version: 1,
            active_presentation_id: "demo",
            updated_at: "2026-01-01T12:00:00Z",
            version_count: 1,
            prompt_preview: "You are VoiceNav.",
          },
        ]),
      });
    });

    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible();
    await expect(page.getByText("Active sessions")).toBeVisible();
    await expect(page.getByText("Transcript queue")).toBeVisible();
    await expect(page.getByRole("main").getByText("Presentations")).toBeVisible();
  });

  test("supports upload then launch and session monitoring flow", async ({ page }) => {
    await page.route("http://127.0.0.1:8000/health", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "ok",
          active_sessions: 0,
          transcript_queue_depth: 0,
          webhook_dedupe_cache: 0,
        }),
      });
    });

    await page.route("http://127.0.0.1:8000/api/presentations", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            presentation_id: "demo",
            filename: "demo-deck.pdf",
            status: "ready",
            total_pages: 20,
            indexed_pages: 20,
          },
        ]),
      });
    });
    await page.route("http://127.0.0.1:8000/api/agents", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            agent_name: "default",
            active_version: 1,
            active_presentation_id: "demo",
            updated_at: "2026-01-01T12:00:00Z",
            version_count: 1,
            prompt_preview: "You are VoiceNav.",
          },
        ]),
      });
    });

    await page.route("http://127.0.0.1:8000/api/upload", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          presentation_id: "demo",
          filename: "deck.pdf",
          status: "uploaded",
          total_pages: null,
          indexed_pages: 0,
        }),
      });
    });

    await page.route("http://127.0.0.1:8000/api/presentations/demo", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          presentation_id: "demo",
          filename: "deck.pdf",
          status: "ready",
          total_pages: 12,
          indexed_pages: 12,
        }),
      });
    });

    await page.route("http://127.0.0.1:8000/api/launch-bot", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "sid-123",
          bot_id: "bot-123",
          presentation_id: "demo",
          agent_mode: "realtime",
          agent_name: "default",
          agent_version: 1,
          output_media_url:
            "http://127.0.0.1:5173/?session=sid-123&presentation=demo&mode=realtime&wss=ws%3A%2F%2F127.0.0.1%3A8000%2Fws%2Frealtime%2Fsid-123",
          realtime_relay_url: "ws://127.0.0.1:8000/ws/realtime/sid-123",
          transcript_webhook_enabled: false,
          relay_profile: "voicenav",
          message: "Bot creation requested",
        }),
      });
    });

    await page.route("http://127.0.0.1:8000/api/session/sid-123", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "sid-123",
          presentation_id: "demo",
          bot_id: "bot-123",
          bot_name: "VoiceNav Presenter",
          meeting_url: "https://teams.microsoft.com/l/meetup-join/example",
          agent_mode: "realtime",
          agent_name: "default",
          agent_version: 1,
          state: "in_call",
          last_status_code: "in_call_not_recording",
          last_status_message: null,
          last_transcript_snippet: "Can you show me slide 3?",
          created_at: "2026-01-01T12:00:00Z",
          updated_at: "2026-01-01T12:00:10Z",
          expires_at: "2026-01-02T12:00:00Z",
          relay_status: "connected",
          relay_connected_at: "2026-01-01T12:00:01Z",
          relay_last_event_at: "2026-01-01T12:00:09Z",
          relay_last_error: null,
          first_audio_latency_ms: 240,
          tool_calls: 4,
          tool_failures: 1,
          fallback_active: false,
        }),
      });
    });

    await page.goto("/upload");
    await page
      .locator('input[type="file"]')
      .setInputFiles({ name: "deck.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF mock") });
    await expect(page.getByRole("heading", { name: "Knowledge base catalog" })).toBeVisible();
    await expect(page.locator("code").filter({ hasText: "demo" }).first()).toBeVisible();

    await page.goto("/launch");
    await page.getByLabel("Meeting URL (Teams / Zoom / Meet)").fill("https://teams.microsoft.com/l/meetup-join/example");
    await page.getByLabel("Agent mode").selectOption("realtime");
    await page.getByRole("button", { name: "Connect bot" }).click();
    await expect(page.getByRole("heading", { name: "Bot launched" })).toBeVisible();
    await expect(page.getByText("Agent mode: realtime")).toBeVisible();
    await expect(page.getByText("Transcript webhook enabled: no")).toBeVisible();

    await page.getByRole("button", { name: "Open session monitor" }).click();
    await expect(page.getByRole("heading", { name: "Live session monitor" })).toBeVisible();
    await expect(page.getByText("in call")).toBeVisible();
    await expect(page.getByText("Realtime relay: connected")).toBeVisible();
    await expect(page.getByText("Tool calls / failures: 4 / 1")).toBeVisible();
    await expect(page.getByText("Can you show me slide 3?")).toBeVisible();
  });
});
