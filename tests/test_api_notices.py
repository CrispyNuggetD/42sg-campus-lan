import collections
import contextlib
import io
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from campus_lan import api_pacing
from campus_lan.client import Client

class ApiNotices(unittest.TestCase):
    def test_background_rate_limit_notice_goes_to_ui_without_terminal_output(self):
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.api_pacing.config_dir',return_value=Path(tmp)),patch('campus_lan.api_pacing.time.time',return_value=100),patch('campus_lan.api_pacing.time.sleep') as sleep:
            (Path(tmp)/'api-pacing.lock').write_text('100')
            c=Client.__new__(Client);c.inbox=queue.Queue();c.lines=collections.deque()
            output=io.StringIO()
            with contextlib.redirect_stdout(output),api_pacing.ui_notices(lambda text:c.inbox.put_nowait(dict(type='local_api_notice',text=text))):
                worker=threading.Thread(target=api_pacing.wait);worker.start();worker.join()
                c.consume()
            self.assertEqual(output.getvalue(),'')
            self.assertIn('API queued',' '.join(c.lines))
            sleep.assert_called_once()

    def test_full_ui_queue_never_prints_and_cli_reporting_is_restored(self):
        output=io.StringIO();inbox=queue.Queue(maxsize=1);inbox.put('full')
        with contextlib.redirect_stdout(output):
            with api_pacing.ui_notices(inbox.put_nowait):api_pacing.report('hidden')
            self.assertEqual(output.getvalue(),'')
            api_pacing.report('CLI notice')
        self.assertEqual(output.getvalue(),'CLI notice\n')
