"""First-run phone viewport help and resize recovery without user data/network."""
import unittest
from unittest.mock import Mock, patch
from campus_lan.client import Client, terminal_fits, terminal_size_help

class Viewport:
    def __init__(self, rows, columns):
        self.rows, self.columns = rows, columns
        self.lines = []
    def getmaxyx(self): return self.rows, self.columns
    def erase(self): self.lines = []
    def refresh(self): pass
    def addnstr(self, y, x, text, count, attr):
        assert 0 <= y < self.rows
        assert len(text) <= self.columns-1
        self.lines.append(text)

class TerminalSizeUI(unittest.TestCase):
    def test_phone_portrait_and_landscape_show_complete_instructions(self):
        for rows, columns in [(50,60), (20,120)]:
            screen = Viewport(rows,columns)
            client = Client.__new__(Client)
            client.ish_terminal = True
            client.draw(screen)
            text = ' '.join(screen.lines)
            self.assertIn(f'Current: {columns} columns x {rows} rows',text)
            self.assertIn('gear > Appearance > Font Size',text)
            self.assertIn('continues automatically',text)
            self.assertIn('Ctrl-C',text)
            self.assertFalse(terminal_fits(screen))

    def test_resize_releases_gate_only_when_both_dimensions_fit(self):
        screen = Viewport(40,60)
        self.assertFalse(terminal_fits(screen))
        screen.columns = 76
        self.assertTrue(terminal_fits(screen))
        screen.rows = 27
        self.assertFalse(terminal_fits(screen))
        screen.rows = 28
        self.assertTrue(terminal_fits(screen))

    def test_desktop_has_no_ish_settings_instructions(self):
        text = ' '.join(terminal_size_help(70,25))
        self.assertIn('Enlarge the terminal',text)
        self.assertNotIn('iSH',text)

    def test_extremely_narrow_viewport_never_overflows(self):
        for width in (1,2,10,30):
            self.assertTrue(all(len(line) <= max(1,width-1)
                                for line in terminal_size_help(width,10,True)))


class HiddenInput(unittest.TestCase):
    def test_undersized_screen_does_not_process_typing(self):
        from contextlib import ExitStack
        from campus_lan import client as app
        client = Client.__new__(Client)
        client.role='game';client.input='unchanged';client.auth_destination=None
        client.connected=True;client.home=client.current='local'
        methods = ('consume','clusters_auto_open_tick','occupancy_tick','tracking_tick',
                   'announcement_tick','time_tick','quiet_tick','uwu_auto_tick',
                   'permission_tick','auto_login_tick','sound_tick','update_title')
        for name in methods: setattr(client,name,Mock())
        screen=Viewport(20,60);screen.timeout=Mock()
        screen.getch=Mock(side_effect=[ord('y'),KeyboardInterrupt])
        with ExitStack() as stack:
            for name in ('History','generation'):
                stack.enter_context(patch.object(app,name,return_value=0))
            stack.enter_context(patch('campus_lan.cohort_display.cohort_index',return_value={}))
            for name in ('mousemask','mouseinterval','curs_set'):
                stack.enter_context(patch.object(app.curses,name))
            stack.enter_context(patch.object(app.curses,'has_colors',return_value=False))
            with self.assertRaises(KeyboardInterrupt): client.run(screen)
        self.assertEqual(client.input,'unchanged')

class RealTerminalResize(unittest.TestCase):
    def test_curses_draws_phone_help_and_detects_resize_on_real_pty(self):
        import errno
        import fcntl
        import os
        import pty
        import struct
        import sys
        import termios
        pid, fd = pty.fork()
        if pid == 0:
            try:
                import curses
                os.environ['TERM']='xterm-256color'
                fcntl.ioctl(1,termios.TIOCSWINSZ,struct.pack('HHHH',40,60,0,0))
                def check(screen):
                    client=Client.__new__(Client);client.ish_terminal=True
                    client.draw(screen)
                    assert not terminal_fits(screen)
                    fcntl.ioctl(1,termios.TIOCSWINSZ,struct.pack('HHHH',30,90,0,0))
                    curses.resizeterm(30,90)
                    assert terminal_fits(screen)
                curses.wrapper(check)
                os.write(1,b'RESIZE_OK')
                os._exit(0)
            except BaseException:
                os._exit(1)
        output=b''
        try:
            while True:
                try: data=os.read(fd,65536)
                except OSError as exc:
                    if exc.errno == errno.EIO: break
                    raise
                if not data: break
                output+=data
        finally:
            os.close(fd)
            _,status=os.waitpid(pid,0)
        self.assertEqual(os.waitstatus_to_exitcode(status),0)
        self.assertIn(b'Appearance',output)
        self.assertIn(b'RESIZE_OK',output)
