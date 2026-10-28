# n8n workflow templates

Run `make automation` after `make up`, then open `http://localhost:5678` and import the three JSON files in `workflows/`. They are inactive on import.

Before activating them, set `STUDIO_PROJECT_ID` to a project in `.env`, set the Telegram bot token/chat ID, and restart n8n. The daily workflow additionally needs `TOPICS_SHEET_ID` and a Google Sheets OAuth credential on the **Read Google Sheets topics** node. The sheet needs `topic` and `status` columns. The topic webhook receives `{ "topic": "...", "project_id": "..." }` at n8n's `/webhook/studio/topic` path.

The workflows use `STUDIO_INTERNAL_KEY` only for internal API webhooks. The API rejects a missing or incorrect key. They notify about completion or failure but leave publication to a person. The daily template reads pending topics; writing `status=done` back to Google Sheets still needs to be configured and tested with the user's sheet. Verify imported node versions and execute each workflow once before activation, since no Google or Telegram credentials are provided in this repository.
