# Deepening

Deepening a cluster of shallow modules safely, given its dependencies, in the vocabulary and principles of [SKILL.md](SKILL.md).

## Dependency categories

Classify a deepening candidate's dependencies; the category decides how the deepened module is tested across its seam.

### 1. In-process

Pure computation, in-memory state, no I/O. Always deepenable: merge the modules and test through the new interface directly. No adapter needed.

### 2. Local-substitutable

Dependencies with a local test stand-in (PGLite for Postgres, an in-memory filesystem). Deepenable where the stand-in exists: the test suite runs the deepened module against it. The seam is internal, with no port at the module's external interface.

### 3. Remote but owned (Ports & Adapters)

Your own services across a network boundary (microservices, internal APIs). Define a **port** (interface) at the seam: the deep module owns the logic, and the transport is injected as an **adapter**, in-memory in tests and HTTP, gRPC or a queue in production.

### 4. True external (Mock)

Third-party services (Stripe, Twilio, etc.) you don't control. The deepened module takes the external dependency as an injected port; tests provide a mock adapter.

## Testing strategy: replace, don't layer

- Old unit tests on shallow modules become waste once tests at the deepened module's interface exist; delete them.
- Tests describe behaviour, not implementation, so they survive internal refactors; a test that has to change when the implementation changes is testing past the interface.
