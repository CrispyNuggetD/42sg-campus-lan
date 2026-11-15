"""Worker error/recovery messages with no real storage, transfers or network."""
import queue
import unittest
from unittest.mock import Mock
from campus_lan.file_sharing.client import Courier
from campus_lan.file_sharing.security import Denied


class RecoveryTests(unittest.TestCase):
    def test_failed_sync_retries_and_reports_recovery(self):
        worker=Courier('fake-token',1,'fixture',queue.Queue(),remote=Mock(),interval=5)
        worker.sync=Mock()
        worker.jobs.put(('sync',()))
        worker.jobs.put(('sync',()))
        def perform(operation,args):
            if not getattr(worker,'attempted',False):
                worker.attempted=True
                raise Denied('Fresh campus presence unavailable.')
            worker.stopped.set()
        worker.perform=perform
        worker.run()
        messages=[]
        while not worker.inbox.empty():messages.extend(worker.inbox.get()['lines'])
        self.assertEqual(len(messages),2)
        self.assertIn('Fresh campus presence unavailable',messages[0])
        self.assertIn('retry in 5 seconds',messages[0])
        self.assertNotIn('Sharing is paused',messages[0])
        self.assertIn('sync recovered',messages[1])

    def test_os_error_does_not_expose_private_path(self):
        worker=Courier('fake-token',1,'fixture',queue.Queue(),remote=Mock())
        worker.jobs.put(('sync',()))
        def perform(*args):
            worker.stopped.set()
            raise PermissionError(13,'permission denied','/private/secret-path')
        worker.perform=perform
        worker.run()
        text=' '.join(worker.inbox.get()['lines'])
        self.assertIn('Permission denied',text)
        self.assertNotIn('secret-path',text)
