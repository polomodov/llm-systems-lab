"""An already interrupted owned server must never receive a second SIGINT."""
import importlib.util
import pathlib
import signal
import sys
import unittest
from unittest.mock import Mock, patch

RAW=pathlib.Path(__file__).resolve().parent/'measurements/LAB34-apple-direct-load-20261008/raw'
spec=importlib.util.spec_from_file_location('lab34_load',RAW/'run_load.py')
module=importlib.util.module_from_spec(spec)
# The standalone report keeps its resource helper next to the controller.
resource_spec=importlib.util.spec_from_file_location('resources',RAW/'resources.py')
resources=importlib.util.module_from_spec(resource_spec);resource_spec.loader.exec_module(resources)
with patch.dict(sys.modules,resources=resources):spec.loader.exec_module(module)


class Shutdown(unittest.TestCase):
    def test_guard_interrupt_is_not_repeated_by_cleanup(self):
        campaign=module.Campaign()
        campaign.process=Mock(pid=123456,returncode=0)
        campaign.process.poll.return_value=None
        campaign.interrupt_sent=True
        campaign.guard='Synthetic resource stop'
        with patch.object(module.os,'killpg') as kill, patch.object(module,'sample',return_value={}), patch.object(module,'write'), patch.object(module,'result'):
            campaign.shutdown()
        kill.assert_not_called()
        campaign.process.wait.assert_called_once_with(timeout=30)

    def test_normal_cleanup_sends_one_owned_interrupt(self):
        campaign=module.Campaign()
        campaign.process=Mock(pid=123456,returncode=0)
        campaign.process.poll.return_value=None
        with patch.object(module.os,'killpg') as kill, patch.object(module,'sample',return_value={}), patch.object(module,'write'), patch.object(module,'result'):
            campaign.shutdown()
        kill.assert_called_once_with(123456,signal.SIGINT)
        self.assertTrue(campaign.interrupt_sent)


if __name__=='__main__':unittest.main()
