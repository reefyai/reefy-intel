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

Package downloads use a five-minute retry budget per package, at most 20
attempts, and a socket timeout capped at 30 seconds. Transient HTTP errors
(408, 429, 500, 502, 503, 504), connection failures and timeouts retry with
2, 4, 8 and 16-second backoff, then at most 30 seconds between attempts.
Request time and backoff both count toward the budget. An in-flight read
can take up to its socket timeout to return before the deadline is checked.
Partial files are discarded, and only checksum-verified packages replace
the destination. Permanent HTTP errors and checksum mismatches fail immediately.

The common layer reproduces Intel's VPU firmware redistribution notice. The
pinned firmware release contains the binaries referenced by linux-firmware
metadata but does not carry that notice in its archive, so the provider keeps
an explicit reviewed copy under `licenses/`.

The reusable publish workflow consumes exact modules, firmware, Reefy build ID,
and kernel ABI evidence from firmware CI, creates an SBOM, publishes to
`ghcr.io/reefyai/reefy-intel`, and signs the manifest through GitHub OIDC.
Desired state uses only resolved manifest digests.

### Pinned Ubuntu download backups

Ubuntu snapshot URLs in `versions.json` remain the canonical package identities.
If a snapshot request fails, the downloader tries the identical `pool/` path on
Ubuntu's primary archive, Azure archive and US-East EC2 archive over HTTPS.
Every source must match the existing SHA-256 before replacing a cached file or
staging a library. There is no package-version substitution or checksum refresh.
A checksum mismatch is fatal. Missing files advance to another source; transient
failures share the original total retry budget across all endpoints.

Live mirrors can prune superseded packages. Backups improve availability when
those bytes are retained, but cannot guarantee recovery of every historical pin.
A complete upstream outage still blocks publication safely. Ubuntu documents
its archive and snapshot services at
https://ubuntu.com/server/docs/how-to/software/snapshot-service/ and
https://ubuntu.com/docs/launchpad/developer/reference/services/ubuntu-mirrors-index/.

The self-hosted `Verify pinned package mirrors` Actions workflow reproduces the
unchanged downloader's failure and verifies recovery with the same real HTTPS
fixtures, including a pruned first mirror, unchanged package bytes, checksum
refusal and untrusted-certificate refusal. It also checks a real package against
its pre-existing hash. JSON results, source fingerprints and logs are retained.

Successful reusable publisher jobs also retain the original package files in an
Actions cache keyed by the exact `versions.json` contents, platform and cache
revision. The downloader rechecks every restored file against the existing hash;
a cache hit cannot bypass verification. A cache must be populated successfully
before it can help during an outage, and normal cache retention still applies.
