# Memory provider deadlines and chat availability

SuMeMe treats long-term memory as an optional enrichment layer on the interactive
chat path. A slow or unavailable memory backend must not prevent the configured
remote chat API from receiving the user's request.

## Runtime deadlines

| Variable | Default | Allowed range | Behavior |
| --- | ---: | ---: | --- |
| `MEMORY_RECALL_TIMEOUT_SECONDS` | `20` | `0.1`–`300` | Per memory component. A timeout returns that component's empty result and the chat continues. |
| `MEMORY_WRITE_TIMEOUT_SECONDS` | `180` | `0.1`–`1800` | Per memory component. A timeout is reported as `<provider>_write_timeout`. |

The default `MemPalace + Letta` provider applies the recall deadline separately
to both components. Therefore a fast MemPalace result can still be used when
Letta is slow, and vice versa. If both time out, the request is sent to the
remote chat API without injected memory.

The backup Supermemory provider uses the same operation deadlines, capped by
`SUPERMEMORY_TIMEOUT_SECONDS`.

## Blocking SDK calls

MemPalace and the current Letta Python SDK expose synchronous operations. SuMeMe
runs them in worker threads with cancellation abandonment enabled, so the async
request can return at the deadline instead of waiting for an unresponsive worker
thread. Letta requests additionally pass SDK `request_options.timeout_in_seconds`
to bound the underlying HTTP request.

## Safety and observability

- Timeout logs contain only component names, scope identifiers and durations.
- User prompts, memory text, provider responses and credentials are never logged.
- Recall fails open because it is optional context.
- Synchronous checkpoint writes remain explicit and return sanitized component
  status; background writes log stable error codes.
- Provider timeout does not trigger automatic switching or dual-write between
  `MemPalace + Letta` and Supermemory.
