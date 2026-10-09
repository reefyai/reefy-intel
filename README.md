# Reefy Intel provider

Reproducible host-extension payloads for Intel GPU and NPU access on Reefy OS.

One OCI manifest contains three read-only SquashFS layers:

- `common.squashfs`: matching i915, Xe, and Intel VPU firmware plus the
  provider-owned activation hook; and
- `kernel.squashfs`: the exact `i915`, `xe`, and `intel_vpu` modules staged
  from the Reefy kernel build; and
- `tools.squashfs`: Intel XPU-SMI 2.0.1 and its pinned private runtime
  libraries for host diagnostics.

The hook mounts those inputs into the host module and firmware paths, loads the
drivers, and publishes CDI entries only for device nodes bound to `i915`, `xe`,
or `intel_vpu`. If no matching hardware is present, it exits successfully
without publishing CDI. This avoids treating another vendor's `/dev/dri` node
as an Intel GPU on mixed-accelerator systems.

Generic DRM helpers and `libdrm` remain in Reefy OS because they are shared by
multiple providers. The activation hook exposes a read-only `/usr/bin/xpu-smi`
wrapper on the host and keeps its Level Zero runtime under
`/run/reefy-xpu-smi`. It does not add XPU-SMI files or mounts to CDI, so the
tool is not injected into application containers. OpenVINO, Intel media, and
other application runtimes remain in application images.

All XPU-SMI Debian package URLs and SHA-256 digests are pinned in
`versions.json`. The tools layer is independent of the exact-kernel layer, so
the artifact store can reuse its content digest across kernel and firmware
rebuilds. The pinned runtime is approximately 69 MiB as an XZ SquashFS layer
and 282 MiB when mounted.

Package downloads use a 30-second socket timeout and at most four attempts.
Transient HTTP 408, 429, 500, 502, 503 and 504 responses, connection failures,
and timeouts retry after 2, 4 and 8 seconds. Each attempt discards partial
files and verifies the pinned SHA-256 before replacing the destination.
Other HTTP failures and checksum mismatches fail immediately. The publish
workflow also limits the entire immutable-payload step to 10 minutes, since
the socket timeout bounds network inactivity rather than total download time.

The common layer reproduces Intel's VPU firmware redistribution notice. The
pinned firmware release contains the binaries referenced by linux-firmware
metadata but does not carry that notice in its archive, so the provider keeps
an explicit reviewed copy under `licenses/`.

The reusable publish workflow consumes exact modules, firmware, Reefy build ID,
and kernel ABI evidence from firmware CI, creates an SBOM, publishes to
`ghcr.io/reefyai/reefy-intel`, and signs the manifest through GitHub OIDC.
Desired state uses only resolved manifest digests.
