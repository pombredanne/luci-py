#!/usr/bin/env python
# Copyright 2016 The LUCI Authors. All rights reserved.
# Use of this source code is governed under the Apache License, Version 2.0
# that can be found in the LICENSE file.

import sys
import unittest

from test_support import test_env
test_env.setup_test_env()

from protorpc import messages
from protorpc import remote
import endpoints
import webapp2

from test_support import test_case
import endpoints_webapp2


class Msg(messages.Message):
  s = messages.StringField(1)
  s2 = messages.StringField(2)


@endpoints.api('Service', 'v1')
class EndpointsService(remote.Service):

  @endpoints.method(Msg, Msg)
  def post(self, _request):
    return Msg()

  @endpoints.method(Msg, Msg, http_method='GET')
  def get(self, _request):
    return Msg()


class EndpointsWebapp2TestCase(test_case.TestCase):
  def test_decode_message_post(self):
    request = webapp2.Request(
        {
          'QUERY_STRING': 's2=b',
        },
        method='POST',
        body='{"s": "a"}',
    )
    msg = endpoints_webapp2.decode_message(
        EndpointsService.post.remote, request)
    self.assertEqual(msg.s, 'a')
    self.assertEqual(msg.s2, None)  # because it is not a ResourceContainer.

  def test_decode_message_get(self):
    request = webapp2.Request(
        {
          'QUERY_STRING': 's=a',
        },
        method='GET',
        route_kwargs={'s2': 'b'},
    )
    msg = endpoints_webapp2.decode_message(EndpointsService.get.remote, request)
    self.assertEqual(msg.s, 'a')
    self.assertEqual(msg.s2, 'b')


if __name__ == '__main__':
  if '-v' in sys.argv:
    unittest.TestCase.maxDiff = None
  unittest.main()
