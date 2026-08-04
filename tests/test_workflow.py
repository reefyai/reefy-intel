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

    def test_reusable_workflow_publishes_common_and_kernel_layers(self):
        workflow = (
            Path(__file__).parents[1] / '.github/workflows/publish.yml'
        ).read_text()

        self.assertIn('--modules-root inputs/modules-root', workflow)
        self.assertIn('--firmware-root inputs/firmware-root', workflow)
        self.assertIn('--kernel-release "$KERNEL_RELEASE"', workflow)
        self.assertIn(
            'output/common.squashfs:application/vnd.reefy.squashfs.v1',
            workflow)
        self.assertIn(
            'output/kernel.squashfs:application/vnd.reefy.squashfs.v1',
            workflow)

    def test_activator_filters_nodes_by_bound_intel_driver(self):
        activator = (
            Path(__file__).parents[1] / 'scripts/activate'
        ).read_text()

        self.assertIn("{'i915', 'xe'}", activator)
        self.assertIn("{'intel_vpu'}", activator)
        self.assertNotIn("glob.glob('/dev/dri", activator)


if __name__ == '__main__':
    unittest.main()
