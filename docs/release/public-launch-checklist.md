# Public Launch Checklist

- OAuth credentials configured for Google and GitHub.
- JWT secret rotated from development default.
- Postgres backups enabled.
- Rate limits and abuse controls tested.
- Nginx streaming proxy configured with buffering off.
- `/health` and `/metrics` monitored.
- MCP connector allowlist reviewed.
- Destructive MCP tool confirmation enabled in production.
- Tenant isolation tests passing.
- Frontend and backend release artifacts tagged.