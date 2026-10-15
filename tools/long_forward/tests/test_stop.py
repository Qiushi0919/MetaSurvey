"""STOP interrupts queued requests without reading credentials or network."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from tools.long_forward import capture

class StopTests(TestCase):
 def test_stop_before_queue(self):
  with TemporaryDirectory() as d,patch.object(capture,'ARCHIVE',Path(d)):
   (Path(d)/'STOP').touch()
   with self.assertRaises(capture.CaptureStopped):
    with capture.queue('history'):self.fail('must not enter request')
   self.assertFalse((Path(d)/'queue').exists())
 def test_stop_while_cadence_waiting(self):
  with TemporaryDirectory() as d,patch.object(capture,'ARCHIVE',Path(d)):
   with capture.queue('history'):pass
   def stop(_):(Path(d)/'STOP').touch()
   with patch.object(capture.time,'sleep',side_effect=stop):
    with self.assertRaises(capture.CaptureStopped):
     with capture.queue('forward'):self.fail('must not enter request')
   self.assertFalse((Path(d)/'queue/forward-priority.json').exists())
 def test_retry_wait_checks_stop(self):
  with TemporaryDirectory() as d,patch.object(capture,'ARCHIVE',Path(d)):
   (Path(d)/'STOP').touch()
   with self.assertRaises(capture.CaptureStopped):capture.controlled_sleep(20)
