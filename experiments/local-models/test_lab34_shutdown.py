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


NEW_RAW=RAW.parent.parent/'LAB34-apple-load-complete-20261008/raw'
new_resources_spec=importlib.util.spec_from_file_location('load_resources',NEW_RAW/'resources.py')
new_resources=importlib.util.module_from_spec(new_resources_spec);new_resources_spec.loader.exec_module(new_resources)
new_spec=importlib.util.spec_from_file_location('load_complete',NEW_RAW/'run_load.py')
new_module=importlib.util.module_from_spec(new_spec)
with patch.dict(sys.modules,resources=new_resources):new_spec.loader.exec_module(new_module)


class ConcurrentInterrupt(unittest.TestCase):
    def test_monitor_and_cleanup_cannot_send_two_interrupts(self):
        import threading
        campaign=new_module.Campaign()
        campaign.process=Mock(pid=123456,returncode=0)
        campaign.process.poll.return_value=None
        with patch.object(new_module.os,'killpg') as kill:
            threads=[threading.Thread(target=campaign.interrupt,args=('synthetic race',)) for _ in range(20)]
            for thread in threads:thread.start()
            for thread in threads:thread.join()
        kill.assert_called_once_with(123456,signal.SIGINT)
        self.assertEqual(len(campaign.record['interrupts']),1)

    def test_new_guard_requires_all_measured_signals(self):
        import copy
        row={'commands':{'sample':{'returncode':0}},'pressure_level':1,'free_pages_bytes':8*2**30,'speculative_pages_bytes':0,
             'pressure_free_percentage':75,'swap_used_bytes':0,'on_ac_power':True,'ac_power_mode':0}
        self.assertTrue(new_resources.safe(copy.deepcopy(row)))
        for field,value in [('pressure_level',2),('free_pages_bytes',8*2**30-1),('pressure_free_percentage',49),
                            ('swap_used_bytes',1),('on_ac_power',False),('ac_power_mode',1)]:
            changed=copy.deepcopy(row);changed[field]=value
            with self.subTest(field=field):self.assertFalse(new_resources.safe(changed))
        changed=copy.deepcopy(row);changed['commands']['sample']['returncode']=1
        self.assertFalse(new_resources.safe(changed))


if __name__=='__main__':unittest.main()
