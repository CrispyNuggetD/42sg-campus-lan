import os
from pathlib import Path
import shutil
import tempfile
import unittest
from campus_lan.hexbot import compile_bot, inspect_bot, run_bots, validate_wasm, SDK
from campus_lan.hexwars import HexWars
from test_hexwars import players


class WasmValidation(unittest.TestCase):
    def test_rejects_native_code_imports_unbounded_memory_and_oversized_memory(self):
        prefix = b'\0asm\x01\0\0\0'
        for data in (b'ELF', prefix + b'\x02\x01\x01',
                     prefix + b'\x05\x03\x01\x00\x01',
                     prefix + b'\x05\x04\x01\x01\x01\x11',
                     prefix + b'\x08\x01\x00', prefix + b'\xff\x00',
                     prefix + b'\x05\x01\xff', prefix + b'x' * 32768):
            with self.subTest(data=data[:16]), self.assertRaises(ValueError):
                validate_wasm(data)


@unittest.skipUnless(shutil.which('node') and shutil.which(os.environ.get('LAN42_CLANG', 'clang'))
                     and (os.environ.get('LAN42_WASM_LD') or shutil.which('wasm-ld')
                          or any(shutil.which('wasm-ld-' + str(v)) for v in range(11, 23))),
                     'C bot tests need Clang, wasm-ld and Node.js')
class BotExecution(unittest.TestCase):
    def compile_text(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bot.c'
            path.write_text('#include "hexwars.h"\n' + text)
            return compile_bot(path)

    def test_examples_compile_and_make_legal_moves(self):
        game = HexWars(players())
        for example, expected in [('expander.c', [4, 3, 2]), ('sentinel.c', [2, 2, 5])]:
            bot = compile_bot(SDK / 'examples' / example)
            self.assertEqual(inspect_bot(bot), expected)
            reply = run_bots([(bot, game.snapshot(0))])[0]
            self.assertTrue(game.valid(0, reply['action']))

    def test_compile_errors_and_attributes_are_reported(self):
        with self.assertRaises(ValueError):
            self.compile_text('not valid C')
        bot = self.compile_text('void bot_config(t_hw_attributes *a) {a->attack = 99;}\n'
                                'void bot_turn(const t_hw_state *s, t_hw_action *a) {(void)s; (void)a;}')
        with self.assertRaisesRegex(ValueError, 'attributes'):
            inspect_bot(bot)

    def test_infinite_loop_and_trap_are_contained(self):
        config = 'void bot_config(t_hw_attributes *a) {(void)a;}\n'
        game = HexWars(players())
        for body in ('volatile int i = 0; while (1) {i++;}', '__builtin_trap();'):
            bot = self.compile_text(config + 'void bot_turn(const t_hw_state *s, t_hw_action *a) '
                                    '{(void)s; (void)a; ' + body + '}')
            reply = run_bots([(bot, game.snapshot(0))])[0]
            self.assertIn('error', reply)
        # A healthy bot in the same batch still runs after a looping opponent.
        healthy = compile_bot(SDK / 'examples' / 'expander.c')
        self.assertIn('action', run_bots([(bot, game.snapshot(0)), (healthy, game.snapshot(1))])[1])

    def test_state_layout_and_no_persistence_between_turns(self):
        bot = self.compile_text('void bot_config(t_hw_attributes *a) {(void)a;}\n'
            'void bot_turn(const t_hw_state *s, t_hw_action *a) {static int n; '
            'a->from=s->api_version + s->cell_count + s->me + s->turn; '
            'a->to=s->cells[60].q; a->units=++n;}')
        game = HexWars(players())
        for _ in range(2):
            reply = run_bots([(bot, game.snapshot(1))])[0]
            self.assertEqual(reply['action'], [63, game.cells[60]['q'], 1])


if __name__ == '__main__':
    unittest.main()
