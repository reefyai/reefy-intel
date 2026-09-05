import unittest
from pathlib import Path


class WorkflowTests(unittest.TestCase):
    def test_reusable_workflow_checks_out_its_exact_source(self):
        workflow = (
            Path(__file__).parents[1] / '.github/workflows/publish.yml'
        ).read_text()

        self.assertIn('repository: ${{ job.workflow_repository }}', workflow)
        self.assertIn('ref: ${{ job.workflow_sha }}', workflow)
        self.assertNotIn('ref: main', workflow)

    def test_reusable_workflow_publishes_all_three_layers(self):
        workflow = (
            Path(__file__).parents[1] / '.github/workflows/publish.yml'
        ).read_text()

        self.assertIn('--modules-root inputs/modules-root', workflow)
        self.assertIn('--firmware-root inputs/firmware-root', workflow)
        self.assertIn('--xpu-smi-root inputs/xpu-smi-root', workflow)
        self.assertIn('--kernel-release "$KERNEL_RELEASE"', workflow)
        self.assertIn(
            'output/common.squashfs:application/vnd.reefy.squashfs.v1',
            workflow)
        self.assertIn(
            'output/kernel.squashfs:application/vnd.reefy.squashfs.v1',
            workflow)
        self.assertIn(
            'output/tools.squashfs:application/vnd.reefy.squashfs.v1',
            workflow)

    def test_activator_filters_nodes_by_bound_intel_driver(self):
        activator = (
            Path(__file__).parents[1] / 'scripts/activate'
        ).read_text()

        self.assertIn("{'i915', 'xe'}", activator)
        self.assertIn("{'intel_vpu'}", activator)
        self.assertNotIn("glob.glob('/dev/dri", activator)

    def test_activator_waits_for_udev_and_stable_device_set(self):
        activator = (
            Path(__file__).parents[1] / 'scripts/activate'
        ).read_text()

        self.assertIn('udevadm settle --timeout=10', activator)
        self.assertIn('stable_attempts >= 4', activator)
        self.assertNotIn('if gpu or npu:\n        break', activator)

    def test_xpu_smi_is_exposed_only_on_the_host(self):
        activator = (
            Path(__file__).parents[1] / 'scripts/activate'
        ).read_text()

        self.assertIn('/run/reefy-xpu-smi', activator)
        self.assertIn('/usr/bin/xpu-smi', activator)
        self.assertIn("'deviceNodes':", activator)
        self.assertNotIn("'mounts':", activator)


if __name__ == '__main__':
    unittest.main()
