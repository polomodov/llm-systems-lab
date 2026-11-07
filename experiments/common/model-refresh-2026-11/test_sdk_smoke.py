"""Regression coverage for asynchronous local fixture instrumentation only."""
import asyncio
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('lab_fixture_smoke', Path(__file__).with_name('sdk-smoke.py'))
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class LocalSubprocessTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_parser_input_does_not_block_the_event_loop(self):
        script = ('let text="";for await(const chunk of process.stdin)text+=chunk;'
                  'await new Promise(resolve=>setTimeout(resolve,200));'
                  'console.log(JSON.stringify({input:JSON.parse(text)}));')
        child = asyncio.create_task(smoke.node_json(script, '{"fixture":true}'))
        await asyncio.sleep(0.05)
        self.assertFalse(child.done(), 'The Node child blocked the event loop until completion')
        self.assertEqual(await child, {'input': {'fixture': True}})

    async def test_nonzero_exit_and_timeout_are_not_success(self):
        with self.assertRaisesRegex(RuntimeError, 'fixture failure'):
            await smoke.node_json('console.error("fixture failure");process.exit(2);')
        with self.assertRaises(TimeoutError):
            await smoke.node_json('setInterval(()=>{},1000);', timeout_s=0.05)


if __name__ == '__main__':
    unittest.main()
