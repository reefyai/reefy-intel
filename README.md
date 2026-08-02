# Reefy Intel provider

Reproducible host-extension payloads for Intel GPU and NPU access on Reefy OS.

The first provider is deliberately small. Intel GPU and NPU kernel drivers and
firmware remain part of Reefy OS while they are also needed for hardware
discovery and early device initialization. The OCI artifact supplies a marker
payload and its provider-owned activation hook. The hook generates CDI entries
only for usable Intel device nodes present on that machine. If no matching
hardware is present, it exits successfully without publishing CDI.

This preserves the same fixed-hook host-extension contract used by other
providers and gives Intel a separate release and promotion path. Future
measured Intel userspace or firmware payloads can be added here without
changing APP-SPEC.

The reusable publish workflow consumes an exact Reefy build ID and kernel ABI
digest from firmware CI, creates an SBOM, publishes to
`ghcr.io/reefyai/reefy-intel`, and signs the manifest through GitHub OIDC.
Desired state uses only resolved manifest digests.
