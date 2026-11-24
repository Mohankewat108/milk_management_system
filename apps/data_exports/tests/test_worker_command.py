from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.data_exports.management.commands.process_data_jobs import Command


class ProcessDataJobsCommandTests(SimpleTestCase):
    def test_one_shot_runs_a_single_batch(self):
        with patch.object(Command, "process_batch") as process_batch:
            call_command("process_data_jobs", limit=1)
        process_batch.assert_called_once_with(1)

    def test_loop_runs_batches_until_interrupted(self):
        with patch.object(Command, "process_batch") as process_batch, patch(
            "apps.data_exports.management.commands.process_data_jobs.time.sleep",
            side_effect=KeyboardInterrupt,
        ):
            with self.assertRaises(KeyboardInterrupt):
                call_command("process_data_jobs", limit=1, loop=True, interval=1)
        process_batch.assert_called_once_with(1)
