import asyncio
import base64
import shutil
import unittest
from campus_lan.hexbot import SDK, compile_bot
import test_network


class HexNetwork(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_network.Network.asyncSetUp
    asyncTearDown = test_network.Network.asyncTearDown
    send = test_network.Network.send
    receive = test_network.Network.receive
    connect = test_network.Network.connect
    cmd = test_network.Network.cmd

    async def setup_room(self):
        a, _ = await self.connect('alice', 'game')
        b, _ = await self.connect('bob', 'game')
        await self.cmd(a, '/host hexwars')
        await self.receive(a, lambda m: m.get('phase') == 'waiting')
        await self.cmd(b, '/join 1')
        await self.receive(b, lambda m: m.get('phase') == 'waiting')
        return a, b

    async def test_ready_start_tick_lock_upload_and_disconnect(self):
        a, b = await self.setup_room()
        await self.cmd(a, '/start')
        await self.receive(a, lambda m: 'Every player' in m.get('text', ''))
        for peer in (a, b):
            await self.cmd(peer, '/bot demo')
            await self.receive(peer, lambda m: 'Built-in' in m.get('text', ''))
        await self.cmd(b, '/start')
        await self.receive(b, lambda m: 'Only this room host' in m.get('text', ''))
        await self.cmd(a, '/start')
        state = await self.receive(a, lambda m: m.get('phase') == 'running')
        self.assertEqual(len(state['cells']), 61)
        await self.receive(b, lambda m: m.get('turn', 0) >= 1)
        await self.cmd(a, '/bot demo')
        await self.receive(a, lambda m: 'Wait until' in m.get('text', ''))
        c, _ = await self.connect('carol', 'game')
        await self.cmd(c, '/join 1')
        await self.receive(c, lambda m: 'Match running' in m.get('text', ''))
        await self.cmd(b, '/leave')
        result = await self.receive(a, lambda m: m.get('phase') == 'results')
        self.assertIn('alice', result['result'])
        await self.cmd(a, '/practice')
        await self.cmd(a, '/start')
        rematch = await self.receive(a, lambda m: m.get('phase') == 'running' and m.get('turn') == 0)
        self.assertEqual([s['name'] for s in rematch['scores']], ['alice', 'Practice bot'])

    async def test_rejects_wrong_room_bad_upload_and_room_overfill(self):
        a, b = await self.setup_room()
        await self.send(a, type='hex_bot', room='99', wasm='aGVsbG8=')
        await self.receive(a, lambda m: 'different room' in m.get('text', ''))
        await self.send(a, type='hex_bot', room='1', wasm='%%%')
        await self.receive(a, lambda m: 'Malformed bot' in m.get('text', ''))
        self.assertFalse(self.lobby.rooms['1'].get('bots'))
        await self.cmd(a, '/practice')
        for i in range(3):
            peer, _ = await self.connect('extra' + str(i), 'game')
            await self.cmd(peer, '/join 1')
            await self.receive(peer, lambda m: m.get('phase') == 'waiting')
        peer, _ = await self.connect('overflow', 'game')
        await self.cmd(peer, '/join 1')
        await self.receive(peer, lambda m: 'at most 6' in m.get('text', ''))

    async def test_simultaneous_joins_cannot_overfill_room(self):
        a, b = await self.setup_room()
        for i in range(3):
            peer, _ = await self.connect('member' + str(i), 'game')
            await self.cmd(peer, '/join 1')
            await self.receive(peer, lambda m: m.get('phase') == 'waiting')
        contenders = [(await self.connect('contender' + str(i), 'game'))[0] for i in range(2)]
        await asyncio.gather(*(self.cmd(peer, '/join 1') for peer in contenders))
        replies = await asyncio.gather(*(self.receive(peer, lambda m:
            m.get('phase') == 'waiting' or 'at most 6' in m.get('text', '')) for peer in contenders))
        self.assertEqual(len(self.lobby.rooms['1']['members']), 6)
        self.assertEqual(sum('at most 6' in m.get('text', '') for m in replies), 1)

    @unittest.skipUnless(shutil.which('wasm-ld') and shutil.which('clang') and shutil.which('node'),
                         'C toolchain unavailable')
    async def test_real_c_upload_over_tcp_then_battle(self):
        a, b = await self.setup_room()
        bot = await asyncio.to_thread(compile_bot, SDK / 'examples' / 'expander.c')
        await self.send(a, type='hex_bot', room='1', wasm=base64.b64encode(bot).decode())
        await self.receive(a, lambda m: 'Bot ready' in m.get('text', ''))
        await self.cmd(b, '/bot demo')
        await self.receive(b, lambda m: 'Built-in' in m.get('text', ''))
        await self.cmd(a, '/start')
        state = await self.receive(a, lambda m: m.get('turn', 0) >= 2)
        self.assertGreater(state['scores'][0]['tiles'], 1)
        self.assertEqual(state['scores'][0]['faults'], 0)
        # No executable bytes or source code are broadcast in game snapshots.
        self.assertNotIn('wasm', str(state))


if __name__ == '__main__':
    unittest.main()
