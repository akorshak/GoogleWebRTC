# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest
import shutil
import tempfile

from telemetry.page import page_set
from telemetry.timeline import tracing_timeline_data
from telemetry.unittest_util import system_stub
from telemetry.util import file_handle
from telemetry.value import trace


class TestBase(unittest.TestCase):

  def setUp(self):
    self.page_set = page_set.PageSet(file_path=os.path.dirname(__file__))
    self.page_set.AddPageWithDefaultRunNavigate('http://www.bar.com/')
    self.page_set.AddPageWithDefaultRunNavigate('http://www.baz.com/')
    self.page_set.AddPageWithDefaultRunNavigate('http://www.foo.com/')

    self._cloud_storage_stub = system_stub.Override(trace, ['cloud_storage'])

  def tearDown(self):
    if self._cloud_storage_stub:
      self._cloud_storage_stub.Restore()
      self._cloud_storage_stub = None

  @property
  def pages(self):
    return self.page_set.pages


class TestSet(object):
  """ A test set that represents a set that contains any key. """

  def __contains__(self, key):
    return True


class TestDefaultDict(object):
  """ A test default dict that represents a dictionary that contains any key
  with value |default_value|. """

  def __init__(self, default_value):
    self._default_value = default_value
    self._test_set = TestSet()

  def __contains__(self, key):
    return key in self._test_set

  def __getitem__(self, key):
    return self._default_value

  def keys(self):
    return self._test_set


class ValueTest(TestBase):

  def testAsDictWhenTraceSerializedAndUploaded(self):
    tempdir = tempfile.mkdtemp()
    try:
      v = trace.TraceValue(
          None, tracing_timeline_data.TracingTimelineData({'test': 1}))
      fh = v.Serialize(tempdir)
      trace.cloud_storage.SetCalculatedHashesForTesting(
          {fh.GetAbsPath(): 123})
      bucket = trace.cloud_storage.PUBLIC_BUCKET
      cloud_url = v.UploadToCloud(bucket)
      d = v.AsDict()
      self.assertEqual(d['file_id'], fh.id)
      self.assertEqual(d['cloud_url'], cloud_url)
    finally:
      shutil.rmtree(tempdir)

  def testAsDictWhenTraceIsNotSerializedAndUploaded(self):
    test_temp_file = tempfile.NamedTemporaryFile(delete=False)
    try:
      v = trace.TraceValue(
          None, tracing_timeline_data.TracingTimelineData({'test': 1}))
      trace.cloud_storage.SetCalculatedHashesForTesting(
          TestDefaultDict(123))
      bucket = trace.cloud_storage.PUBLIC_BUCKET
      cloud_url = v.UploadToCloud(bucket)
      d = v.AsDict()
      self.assertEqual(d['cloud_url'], cloud_url)
    finally:
      if os.path.exists(test_temp_file.name):
        test_temp_file.close()
        os.remove(test_temp_file.name)


def _IsEmptyDir(path):
  return os.path.exists(path) and not os.listdir(path)


class NoLeakedTempfilesTests(TestBase):

  def setUp(self):
    super(NoLeakedTempfilesTests, self).setUp()
    self.temp_test_dir = tempfile.mkdtemp()
    self.actual_tempdir = trace.tempfile.tempdir
    trace.tempfile.tempdir = self.temp_test_dir

  def testNoLeakedTempFileWhenTraceSerialize(self):
    tempdir = tempfile.mkdtemp()
    v = trace.TraceValue(
        None, tracing_timeline_data.TracingTimelineData({'test': 1}))
    fh = v.Serialize(tempdir)
    try:
      shutil.rmtree(fh.GetAbsPath(), ignore_errors=True)
      self.assertTrue(tempdir)
    finally:
      shutil.rmtree(tempdir)
      self.assertTrue(_IsEmptyDir(self.temp_test_dir))

  def testNoLeakedTempFileWhenUploadingTrace(self):
    v = trace.TraceValue(
        None, tracing_timeline_data.TracingTimelineData({'test': 1}))
    trace.cloud_storage.SetCalculatedHashesForTesting(
        TestDefaultDict(123))
    bucket = trace.cloud_storage.PUBLIC_BUCKET
    v.UploadToCloud(bucket)
    self.assertTrue(_IsEmptyDir(self.temp_test_dir))

  def tearDown(self):
    super(NoLeakedTempfilesTests, self).tearDown()
    shutil.rmtree(self.temp_test_dir)
    trace.tempfile.tempdir = self.actual_tempdir
