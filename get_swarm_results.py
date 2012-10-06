#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# get_swarm_results.py: Retrieves and output swarm test results for a given
# test request name.

"""Takes in a test name and retrieves all the output that the swarm server
has produced for tests with that name.
"""

import json
import optparse
import socket
import sys
import time
import urllib
import urllib2

#from common import find_depot_tools  # pylint: disable=W0611
#
## From the depot tools
#import fix_encoding


MAX_RETRY_ATTEMPTS = 20


def fetch_with_retry(url):
  """Try multiple times to connect to the swarm server and return the response,
     or None if unable to connect.
  """
  for attempt in range(MAX_RETRY_ATTEMPTS):
    try:
      return urllib2.urlopen(url).read()
    except (socket.error, urllib2.URLError) as e:
      print 'Error: Calling %s threw %s' % (url, e)
      time.sleep(0.1 + 0.5 * attempt)

  # We were unable to connect to the url.
  print('Unable to connect to the given url, %s, after %d attempts. Aborting.'
        % (url, MAX_RETRY_ATTEMPTS))
  return None


def get_test_keys(swarm_base_url, test_name):
  key_data = urllib.urlencode([('name', test_name)])
  test_keys_url = '%s/get_matching_test_cases?%s' % (
      swarm_base_url.rstrip('/'), key_data)

  result = fetch_with_retry(test_keys_url)
  if result is None:
    return []

  if 'No matching' in result:
    print ('Error: Unable to find any tests with the name, %s, on swarm server'
           % test_name)
    return []

  # TODO(csharp): return in a proper format (like json)
  return result.split()


def get_swarm_results(swarm_base_url, test_keys):
  """Retrieves the given swarm test results from the swarm server and print it
  to stdout.
  """
  outputs = []
  for test in test_keys:
    result_url = '%s/get_result?r=%s' % (swarm_base_url.rstrip('/'), test)
    result = fetch_with_retry(result_url)
    if result is None:
      continue
    outputs.append(json.loads(result))
  return outputs


def print_results(outputs):
  for output in outputs:
    print '%s: %s' % (output['machine_id'], output['exit_codes'])
    print ''.join('  %s\n' % l for l in output['output'].splitlines())


def main():
  parser = optparse.OptionParser(
      usage='%prog [options] test_name',
      description=sys.modules[__name__].__doc__)
  parser.add_option(
      '-u', '--url', default='http://localhost:8080',
      help='Specify the url of the Swarm server, defaults: %default')
  parser.add_option(
      '-v', '--verbose', action='store_true',
      help='Print verbose logging')
  (options, args) = parser.parse_args()
  if not args:
    parser.error('Must specify one test name.')
  elif len(args) > 1:
    parser.error('Must specify only one test name.')

  test_name = args[0]
  test_keys = get_test_keys(options.url, test_name)
  print_results(get_swarm_results(options.url, test_keys))
  return 0


if __name__ == '__main__':
  #fix_encoding.fix_encoding()
  sys.exit(main())
