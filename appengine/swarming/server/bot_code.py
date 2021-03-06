# Copyright 2014 The LUCI Authors. All rights reserved.
# Use of this source code is governed under the Apache License, Version 2.0
# that can be found in the LICENSE file.

"""Swarming bot code. Includes bootstrap and swarming_bot.zip.

It includes everything that is AppEngine specific. The non-GAE code is in
bot_archive.py.
"""

import collections
import logging
import os.path
import urllib

from google.appengine.api import memcache
from google.appengine.ext import ndb

from components import auth
from components import datastore_utils
from components import utils
from server import bot_archive


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


### Models.


File = collections.namedtuple('File', ('content', 'who', 'when', 'version'))


class VersionedFile(ndb.Model):
  """Versionned entity.

  Root is ROOT_MODEL. id is datastore_utils.HIGH_KEY_ID - version number.
  """
  created_ts = ndb.DateTimeProperty(indexed=False, auto_now_add=True)
  who = auth.IdentityProperty(indexed=False)
  content = ndb.BlobProperty(compressed=True)

  ROOT_MODEL = datastore_utils.get_versioned_root_model('VersionedFileRoot')

  @property
  def version(self):
    return datastore_utils.HIGH_KEY_ID - self.key.integer_id()

  @classmethod
  def fetch(cls, name):
    """Returns the current version of the instance."""
    return datastore_utils.get_versioned_most_recent(
        cls, cls._gen_root_key(name))

  def store(self, name):
    """Stores a new version of the instance."""
    # Create an incomplete key.
    self.key = ndb.Key(self.__class__, None, parent=self._gen_root_key(name))
    self.who = auth.get_current_identity()
    return datastore_utils.store_new_version(self, self.ROOT_MODEL)

  @classmethod
  def _gen_root_key(cls, name):
    return ndb.Key(cls.ROOT_MODEL, name)


### Public APIs.


def get_bootstrap(host_url, bootstrap_token=None, version=None):
  """Returns the mangled version of the utility script bootstrap.py.

  Returns:
    File instance.
  """
  host_url = host_url or ''
  bootstrap_token = bootstrap_token or ''
  header = ''
  if host_url or bootstrap_token:
    quoted = urllib.quote_plus(bootstrap_token)
    assert bootstrap_token == quoted, bootstrap_token
    header = 'host_url = %r\nbootstrap_token = %r\n' % (
        host_url, bootstrap_token)
  if version is not None:
    obj = ndb.Key(
        VersionedFile, datastore_utils.HIGH_KEY_ID - version,
        parent=VersionedFile._gen_root_key('bootstrap.py')).get()
    if not obj:
      return None
  else:
    obj = VersionedFile.fetch('bootstrap.py')
  if obj and obj.content:
    return File(
        header + obj.content, obj.who, obj.created_ts, obj.version)
  # Fallback to the one embedded in the tree.
  path = os.path.join(ROOT_DIR, 'swarming_bot', 'config', 'bootstrap.py')
  with open(path, 'rb') as f:
    return File(header + f.read(), None, None, None)


def store_bootstrap(content):
  """Stores a new version of bootstrap.py.

  Returns the ndb.Key of the new stored entity.
  """
  return VersionedFile(content=content).store('bootstrap.py')


def get_bot_config(version=None):
  """Returns the current version of bot_config.py and extra metadata.

  Returns:
    File instance.
  """
  if version is not None:
    obj = ndb.Key(
        VersionedFile, datastore_utils.HIGH_KEY_ID - version,
        parent=VersionedFile._gen_root_key('bot_config.py')).get()
    if not obj:
      return None
  else:
    obj = VersionedFile.fetch('bot_config.py')
  if obj:
    return File(obj.content, obj.who, obj.created_ts, obj.version)

  # Fallback to the one embedded in the tree.
  path = os.path.join(ROOT_DIR, 'swarming_bot', 'config', 'bot_config.py')
  with open(path, 'rb') as f:
    return File(f.read(), None, None, None)


def store_bot_config(content):
  """Stores a new version of bot_config.py.

  Returns the ndb.Key of the new stored entity.
  """
  out = VersionedFile(content=content).store('bot_config.py')
  # Clear the cached versions value since it has now changed.
  memcache.delete('versions', namespace='bot_code')
  return out


def get_bot_version(host):
  """Retrieves the bot version (SHA-1) loaded on this server.

  The memcache is first checked for the version, otherwise the value
  is generated and then stored in the memcache.

  Returns:
    The hash of the current bot version.
  """
  # This is invalidate everything bot_config is uploaded.
  bot_versions = memcache.get('versions', namespace='bot_code') or {}
  # CURRENT_VERSION_ID is unique per upload so it can be trusted.
  app_ver = host + '-' + os.environ['CURRENT_VERSION_ID']
  bot_version = bot_versions.get(app_ver)
  if bot_version:
    return bot_version

  # Need to calculate it.
  additionals = {'config/bot_config.py': get_bot_config().content}
  bot_dir = os.path.join(ROOT_DIR, 'swarming_bot')
  bot_version = bot_archive.get_swarming_bot_version(
      bot_dir, host, utils.get_app_version(), additionals)
  if len(bot_versions) > 100:
    # Lazy discard when too large.
    bot_versions = {}
  bot_versions[app_ver] = bot_version
  memcache.set('versions', bot_versions, namespace='bot_code')
  return bot_version


def get_swarming_bot_zip(host):
  """Returns a zipped file of all the files a bot needs to run.

  Returns:
    A string representing the zipped file's contents.
  """
  bot_version = get_bot_version(host)
  content = memcache.get('code-%s' + bot_version, namespace='bot_code')
  if content:
    logging.debug(
        'memcached bot code %s; %d bytes', bot_version, len(content))
    return content

  # Get the start bot script from the database, if present. Pass an empty
  # file if the files isn't present.
  additionals = {'config/bot_config.py': get_bot_config().content}
  bot_dir = os.path.join(ROOT_DIR, 'swarming_bot')
  content, bot_version = bot_archive.get_swarming_bot_zip(
      bot_dir, host, utils.get_app_version(), additionals)
  memcache.set('code-%s' + bot_version, content, namespace='bot_code')
  logging.info('generated bot code %s; %d bytes', bot_version, len(content))
  return content


### Bootstrap token.


class BootstrapToken(auth.TokenKind):
  expiration_sec = 3600
  secret_key = auth.SecretKey('bot_bootstrap_token', scope='local')
  version = 1


def generate_bootstrap_token():
  """Returns a token that authenticates calls to bot bootstrap endpoints.

  The authenticated bootstrap workflow looks like this:
    1. An admin visit Swarming server root page and copy-pastes URL to
       bootstrap.py that has a '?tok=...' parameter with the bootstrap token,
       generated by this function.
    2. /bootstrap verifies the token and serves bootstrap.py, with same token
       embedded into it.
    3. The modified bootstrap.py is executed on the bot. It fetches bot code
       from /bot_code, passing it the bootstrap token again.
    4. /bot_code verifies the token and serves the bot code zip archive.

  This function assumes the caller is already authorized.
  """
  # The embedded payload is mostly FYI. The important expiration time is added
  # by BootstrapToken already.
  return BootstrapToken.generate(message=None, embedded={
    'for': auth.get_current_identity().to_bytes(),
  })


def validate_bootstrap_token(tok):
  """Returns a token payload if the token is valid or None if not.

  The token is valid if its HMAC signature is correct and it hasn't expired yet.

  Doesn't recheck ACLs. Logs errors.
  """
  try:
    return BootstrapToken.validate(tok, message=None)
  except auth.InvalidTokenError as exc:
    logging.warning('Failed to validate bootstrap token: %s', exc)
    return None
