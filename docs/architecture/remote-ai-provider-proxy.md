# Remote AI Provider Proxy

## Purpose

Some OpenAI-compatible relays expose chat and model-list endpoints but do not
expose `/v1/embeddings`. SuMeMe still requires embeddings for raw-memory search
and for Letta's structured memory. Local embedding models are forbidden by the
product architecture.

The internal Provider Proxy gives MemPalace and Letta one OpenAI-compatible
endpoint without adding a local model runtime:

```text
MemPalace ───────────────┐
                         ├─> ai-provider-proxy ─> configured relay / official API
Letta OpenAI provider ───┘
```

The service has no public port. It is reachable only on the Compose network and
requires `PROVIDER_PROXY_API_KEY`, which Compose maps from the existing gateway
secret.

## Endpoints

- `GET /v1/models`: transparent relay model discovery;
- `GET /v1/models/{id}`: transparent relay model metadata;
- `POST /v1/chat/completions`: transparent buffered or streaming relay proxy;
- `POST /v1/responses`: transparent buffered or streaming relay proxy;
- `POST /v1/embeddings`: native embedding proxy or remote semantic fallback;
- `GET /health`: configuration-safe status only.

The proxy does not call MemPalace, Letta, Supermemory, the Vault registry or the
memory gateway. Therefore Letta can use it without creating a recursive memory
request.

## Embedding modes

### `native`

Only the relay's `/v1/embeddings` endpoint is accepted. An unavailable endpoint
is an error.

### `remote-semantic-hash`

The proxy sends the input text to the configured remote semantic model using
`/v1/chat/completions`. The remote model returns canonical semantic keyphrases.
The proxy then performs deterministic feature hashing and L2 normalization.
Hashing is a non-AI operation and uses no model weights.

### `auto` (default)

The proxy attempts native embeddings once. A missing or unsupported embedding
endpoint (for example 404/405/501 or a compatible 400/422 rejection) marks the
native endpoint unavailable for the process lifetime and selects
`remote-semantic-hash` for subsequent calls.

Authentication failures, rate limits and upstream server failures are not hidden
by fallback. They remain visible as errors.

This is an AI transport choice inside one configured remote provider. It is not
memory-provider failover: SuMeMe does not silently switch between
`MemPalace + Letta` and Supermemory and does not dual-write memories.

## Semantic vector contract

The remote model receives untrusted input as quoted JSON data and is instructed
to return one tag array per input. The proxy:

1. validates exact item count;
2. normalizes Unicode and whitespace;
3. requires at least four unique tags;
4. limits tag count and length;
5. maps tags into a fixed vector using SHA-256 feature hashing;
6. L2-normalizes the vector.

The default dimension is 1536 so Letta's standard
`openai/text-embedding-3-small` handle remains dimension-compatible.

## Letta model resolution

An explicit, valid `LETTA_MODEL` remains authoritative. Placeholder values such
as `openai/replace_me` are resolved to:

```text
openai-proxy/<OPENAI_MEMORY_MODEL or OPENAI_CHAT_MODEL>
```

This matches the custom OpenAI-compatible provider handles exposed by the
self-hosted Letta server. Letta's OpenAI base URL and key point to the internal
Provider Proxy, so both LLM and embedding calls still terminate at the approved
relay or official API.

## Security

- no local model packages or weights;
- no arbitrary upstream URL supplied by clients;
- fixed server-side relay endpoint and credentials;
- bearer authentication on every provider endpoint except health;
- provider errors are reduced to stable codes where SuMeMe records them;
- no user content is written to Provider Proxy disk or logs;
- the service does not expose a host port;
- memory account/Vault isolation remains enforced by the memory layer, not by
  the embedding vector service.
