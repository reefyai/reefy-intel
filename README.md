# Reefy Intel provider

Reproducible host-extension payloads for Intel GPU and NPU access on Reefy OS.

The first provider is deliberately small. Intel GPU and NPU kernel drivers and
firmware remain part of Reefy OS while they are also needed for hardware
discovery and early device initialization. The OCI artifact supplies a marker
payload and selects Reefy OS's built-in `intel-accelerator` activator, which
generates CDI entries for the Intel devices present on that machine.

This preserves the same data-only artifact contract used by other providers
and gives Intel a separate release and promotion path. Future measured Intel
userspace or firmware payloads can be added here without changing APP-SPEC.

The reusable publish workflow consumes an exact Reefy build ID and kernel ABI
digest from firmware CI, creates an SBOM, publishes to
`ghcr.io/reefyai/reefy-intel`, and signs the manifest through GitHub OIDC.
Desired state uses only resolved manifest digests.
