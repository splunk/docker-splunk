# Splunk Container Shutdown Contract

The full Splunk image exposes `/sbin/splunk-shutdown` as the single supported
local container-stop operation. PID 1 invokes it for TERM. Kubernetes `preStop`
hooks may invoke the same executable when their image compatibility check
confirms it is present.

This contract is local to one container. It does not perform Search Head
detention, search draining, captain transfer, cluster membership changes, or
Kubernetes rollout orchestration. Those operations must finish before a
controller authorizes planned Pod replacement. Forced deletion, process crash,
OOM, and node loss may skip `preStop`; TERM therefore remains a first-class
caller.

## Interface

```text
/sbin/splunk-shutdown --source=term
/sbin/splunk-shutdown --source=prestop
```

`--source=manual` is available for diagnostics and direct qualification.
Unsupported arguments or source values return `2`.

`SPLUNK_SHUTDOWN_TIMEOUT_SECONDS` controls the local stop deadline and defaults
to 600 seconds. It must be a positive integer and must fit inside the
Kubernetes termination grace period with time remaining for signal delivery
and forced cleanup. GNU `timeout` bounds the stop command and returns `124`
when the deadline expires.

The paired Splunk Operator lifecycle contract uses 660 seconds for a
startup- or liveness-probe restart: the 600-second image deadline plus a
60-second kubelet margin. Planned Pod deletion keeps its longer, independently
configurable grace. If the image timeout is increased, the startup and
liveness probe grace must also be increased; readiness probes do not terminate
containers and have no termination grace.

## State and ownership

The operation stores bounded, non-secret evidence under
`$CONTAINER_ARTIFACT_DIR`:

- `splunk-container.state` changes atomically to `stopping` before the stop
  command starts;
- `splunk-shutdown.lock/owner` records the owner PID and caller source; and
- `splunk-shutdown.lock/result` records the stop exit status.

Creating `splunk-shutdown.lock` is the single-owner decision. A concurrent
caller does not issue another stop. A later caller returns the recorded result,
so stop failure is not silently converted into success. The entrypoint TERM
trap exits PID 1 with the shutdown result after the bounded operation finishes;
it does not remain alive for the rest of the Kubernetes grace period.

The lock is intentionally retained for the remaining life of the container.
The `restart` entrypoint action is a different operation: it stops and starts
Splunk without terminating the container and does not use this terminal
shutdown contract.

## Qualification expectations

Runtime qualification must cover direct TERM, preStop followed by TERM,
concurrent callers, repeated calls, stop failure, timeout, missing tooling, and
the stopping-state transition. Kubernetes qualification must additionally
measure Service and EndpointSlice withdrawal, actual stop duration, grace
expiration, force deletion, and node-loss recovery.

On the current fixed Splunk runtime, a direct TERM qualification of an
established non-captain completed the local stop in 42 seconds, exited with
status zero, restarted the container exactly once without changing the Pod UID,
and restored the three-member SHC and all three client endpoints. This is a
bounded observation, not a guarantee that every workload will stop in 42
seconds; the configured deadline remains the acceptance boundary.
