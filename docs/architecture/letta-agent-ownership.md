# Letta agent ownership boundary

Updated: 2026-07-30

## Rule

Every Letta Agent used by SuMeMe has exactly one external owner:

```text
principal_type + account_id + vault_id
```

The canonical owner key is the same `MemoryScope.storage_key` used by MemPalace,
Supermemory, the Vault registry and private-object metadata.

```text
acct.<account_id>.vault.<vault_id>
svc.<service_id>.vault.<vault_id>
```

An Agent ID is never intentionally shared between two keys, even when textual account
or Vault identifiers overlap across account and service principals.

## Persistent state

The local mapping file is `/data/gateway/letta-agent.json`. Schema 4 stores only the
forward map and declares the ownership rule:

```json
{
  "schema_version": 4,
  "scope_format": "principal.account.vault",
  "ownership": "one-agent-per-scope",
  "agents": {
    "acct.example.vault.default": "agent-id"
  }
}
```

The reverse Agent-ID owner map is reconstructed in memory. Persisting one source of truth
avoids forward/reverse divergence.

## Collision handling

During state loading, SuMeMe registers every mapping in both directions. When the same
Agent ID is found under different unprotected scopes:

1. the Agent ID is marked invalid for the current process;
2. every local scope mapping that points to it is removed;
3. the sanitized state file is rewritten without that Agent ID;
4. each affected scope receives a newly created Agent on its next operation.

SuMeMe does not choose one scope as the winner because doing so could expose another
scope's structured memory. Invalidating all conflicting local mappings is the safe,
fail-closed action. Existing remote Agents are not automatically deleted because their
ownership cannot be proven after a collision; they become unreachable from SuMeMe and
can be reviewed by a separate administrative cleanup process.

If the Letta server returns an Agent ID that is already owned by another scope during
Agent creation, the new operation fails with:

```text
letta_agent_ownership_conflict
```

Both unprotected local mappings are invalidated rather than sending a recall or update to
an ambiguously owned Agent.

## Explicit configured Agent

`LETTA_AGENT_ID` is a protected migration/configuration binding for only the default
account/default Vault scope. It retains priority over the persisted state file.

A state row or newly created scope that attempts to claim this configured Agent ID is
rejected without invalidating the configured default mapping. Likewise, a stale state row
cannot replace the default scope's configured Agent with a different ID.

This preserves backward compatibility while preventing the configured Agent from leaking
to smoke, service, secondary-account or secondary-Vault scopes.

## Request path

Before every recall or memory update:

1. resolve the canonical scope;
2. load or create the scope mapping;
3. verify the reverse Agent owner equals the same scope;
4. only then send the Letta request using the Agent ID.

A mapping that fails the reverse-owner check is removed and treated as unavailable.

## Logging and errors

Ownership failures log only Agent IDs and normalized scope keys. They do not log user
messages, memory text, provider response bodies, passwords or API keys.

Stable errors include:

```text
letta_agent_ownership_conflict
letta_agent_unavailable
letta_agent_not_found
```

## Acceptance

Code acceptance requires tests proving:

- account, Vault and service scopes receive different Agent IDs;
- a duplicate persisted ID is invalidated for every conflicting scope;
- a server-returned duplicate ID fails closed;
- the explicit configured Agent remains bound only to the default scope;
- schema 2/3 and single-Agent legacy files migrate to schema 4.

Production acceptance still requires a GHS deployment and successful isolated write and
recall checks. Letta remains optional and observable until that acceptance succeeds.
