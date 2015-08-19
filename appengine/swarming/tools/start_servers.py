#!/usr/bin/env python
# Copyright 2015 The Swarming Authors. All rights reserved.
# Use of this source code is governed by the Apache v2.0 license that can be
# found in the LICENSE file.

"""Starts local Swarming and Isolate servers."""

import argparse
import os
import shutil
import sys
import tempfile


APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)

from tool_support import gae_sdk_utils
gae_sdk_utils.setup_gae_env()

from tool_support import local_app


class LocalServers(object):
  """Local Swarming and Isolate servers."""
  def __init__(self, listen_all):
    self._isolate_server = None
    self._swarming_server = None
    self._listen_all = listen_all

  @property
  def isolate_server(self):
    return self._isolate_server

  @property
  def swarming_server(self):
    return self._swarming_server

  @property
  def http_client(self):
    """Returns the raw local_app.HttpClient."""
    return self._swarming_server.client

  def start(self):
    """Starts both the Swarming and Isolate servers."""
    self._swarming_server = local_app.LocalApplication(
        APP_DIR, 9050, self._listen_all)
    self._swarming_server.start()

    # We wait for the Swarming server to be started up so the isolate server
    # ports do not clash.
    self._isolate_server = local_app.LocalApplication(
        os.path.join(APP_DIR, '..', 'isolate'), 10050, self._listen_all)
    self._isolate_server.start()
    self._swarming_server.ensure_serving()
    self._isolate_server.ensure_serving()

    self.http_client.login_as_admin('smoke-test@example.com')
    self.http_client.url_opener.addheaders.append(
        ('X-XSRF-Token', self._swarming_server.client.xsrf_token))

  def stop(self):
    """Stops the local Swarming and Isolate servers.

    Returns the exit code with priority to non-zero.
    """
    exit_code = None
    try:
      if self._isolate_server:
        exit_code = exit_code or self._isolate_server.stop()
    finally:
      if self._swarming_server:
        exit_code = exit_code or self._swarming_server.stop()
    return exit_code

  def wait(self):
    """Wait for the processes to normally exit."""
    if self._isolate_server:
      self._isolate_server.wait()
    if self._swarming_server:
      self._swarming_server.wait()

  def dump_log(self):
    if self._isolate_server:
      self._isolate_server.dump_log()
    if self._swarming_server:
      self._swarming_server.dump_log()


def main():
  parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
  parser.add_argument('-a', '--all', action='store_true')
  args = parser.parse_args()
  servers = LocalServers(args.all)
  try:
    servers.start()
    print('Swarming: %s' % servers.swarming_server.url)
    print('Isolate : %s' % servers.isolate_server.url)
    servers.wait()
    servers.dump_log()
  except KeyboardInterrupt:
    print >> sys.stderr, '<Ctrl-C> received; stopping servers'
  finally:
    exit_code = servers.stop()
  return exit_code


if __name__ == '__main__':
  sys.exit(main())