# Reefy Intel provider

Reproducible host-extension payloads for Intel GPU and NPU access on Reefy OS.

One OCI manifest contains two read-only SquashFS layers built for one exact
Reefy kernel:

- `common.squashfs`: matching i915, Xe, and Intel VPU firmware plus the
  provider-owned activation hook; and
- `kernel.squashfs`: the exact `i915`, `xe`, and `intel_vpu` modules staged
  from the Reefy kernel build.

The hook mounts those inputs into the host module and firmware paths, loads the
drivers, and publishes CDI entries only for device nodes bound to `i915`, `xe`,
or `intel_vpu`. If no matching hardware is present, it exits successfully
without publishing CDI. This avoids treating another vendor's `/dev/dri` node
as an Intel GPU on mixed-accelerator systems.

Generic DRM helpers and `libdrm` remain in Reefy OS because they are shared by
multiple providers. OpenVINO, Level Zero, Intel media, and other application
runtimes remain in application images.

The reusable publish workflow consumes exact modules, firmware, Reefy build ID,
and kernel ABI evidence from firmware CI, creates an SBOM, publishes to
`ghcr.io/reefyai/reefy-intel`, and signs the manifest through GitHub OIDC.
Desired state uses only resolved manifest digests.
