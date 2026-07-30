# AutoDevOps Bridge

AutoDevOps Bridge is a reusable ChatGPT/Codex plugin for operating self-hosted software projects through GitHub Actions and self-hosted runners.

It deliberately **does not expose SSH, root credentials, or an unrestricted shell** to the model. ChatGPT works through auditable, allow-listed GitHub workflows instead:

```text
ChatGPT / Codex
       │
       ▼
AutoDevOps MCP server
       │ GitHub API
       ▼
Repository workflows
       │
       ▼
Self-hosted GitHub Runner on the VPS
       │
       ├─ deploy
       ├─ diagnose
       ├─ publish sanitized status
       └─ rollback
```

## What the first version supports

- Register one or more GitHub repositories as projects.
- Read a sanitized production snapshot from an `ops-status` branch.
- Inspect recent GitHub Actions runs.
- Trigger an allow-listed deployment workflow.
- Trigger an allow-listed diagnostic workflow.
- Trigger rollback only with an explicit `ROLLBACK` confirmation value.
- Give ChatGPT a reusable skill that enforces the safe development sequence:
  inspect → branch → change → test → review → merge → deploy → verify.

## Plugin contents

```text
.codex-plugin/plugin.json   Plugin package metadata
.mcp.json                   Local Codex MCP launch configuration
skills/autodevops/SKILL.md  Operating policy and workflow instructions
mcp-server/                 Streamable HTTP MCP service
examples/projects.json      Project registry example
docs/                       Security and publication documentation
```

## Local single-user setup

The initial implementation is suitable for private testing. It uses a GitHub fine-grained token stored only on the MCP server.

1. Copy the environment file:

```bash
cd mcp-server
cp .env.example .env
```

2. Set a fine-grained GitHub token with access only to the selected repositories and Actions permissions required by the tools.

3. Define projects in `AUTODEVOPS_PROJECTS_JSON`.

4. Install and run:

```bash
npm ci
npm run build
npm start
```

The Streamable HTTP endpoint is:

```text
https://your-domain.example/mcp
```

The health endpoint is:

```text
https://your-domain.example/health
```

## Required repository convention

Each managed repository should contain allow-listed workflow files and publish a sanitized status snapshot:

```text
.github/workflows/ci.yml
.github/workflows/deploy-production.yml
.github/workflows/diagnose-production.yml
.github/workflows/rollback-production.yml
.github/workflows/publish-status.yml

ops-status branch:
  status/status.json
  status/STATUS.md
```

The workflow names are configurable per project.

## Public publication roadmap

The private MVP uses a server-side GitHub token and shared bearer secret. A public ChatGPT release must add:

- OAuth 2.1 authorization per user;
- encrypted token storage and revocation;
- a public HTTPS MCP endpoint;
- verified developer identity and domains;
- privacy policy, terms, support page, icons and screenshots;
- tool annotations and positive/negative review test cases;
- tenant isolation, audit logs, retention controls and abuse limits.

See `docs/PUBLICATION.md` and `docs/SECURITY.md`.

## Safety principles

- No arbitrary shell tool.
- No SSH private keys in ChatGPT or the MCP service.
- Deploy only a tested Git commit or trusted branch.
- Read sanitized status rather than raw `.env` or unrestricted logs.
- Destructive actions require explicit confirmation.
- Every action remains visible in GitHub Actions audit history.

## License

MIT for the AutoDevOps Bridge plugin code. Upstream project and service licenses remain separate.
