# Copyright 2016 The LUCI Authors. All rights reserved.
# Use of this source code is governed under the Apache License, Version 2.0
# that can be found in the LICENSE file.

"""Utilities for operating on instance group managers."""

import logging

from google.appengine.ext import ndb

from components import gce
from components import net
from components import utils

import instance_templates
import models


def get_instance_group_manager_key(base_name, revision, zone):
  """Returns a key for an InstanceTemplateGroupManager.

  Args:
    base_name: Base name for the models.InstanceTemplate.
    revision: Revision string for the models.InstanceTemplateRevision.
    zone: Zone for the models.InstanceGroupManager.

  Returns:
    ndb.Key for a models.InstanceTemplate entity.
  """
  return ndb.Key(
      models.InstanceGroupManager,
      zone,
      parent=instance_templates.get_instance_template_revision_key(
          base_name, revision),
  )


def get_name(instance_group_manager):
  """Returns the name to use when creating an instance group manager.

  Args:
    instance_group_manager: models.InstanceGroupManager.

  Returns:
    A string.
  """
  # <base-name>-<revision>
  return '%s-%s' % (
      instance_group_manager.key.parent().parent().id(),
      instance_group_manager.key.parent().id(),
  )


def get_base_name(instance_group_manager):
  """Returns the base name to use when creating an instance group manager.

  The base name is suffixed randomly by GCE when naming instances.

  Args:
    instance_group_manager: models.InstanceGroupManager.

  Returns:
    A string.
  """
  # <base-name>-<abbreviated-revision>
  return '%s-%s' % (
      instance_group_manager.key.parent().parent().id(),
      instance_group_manager.key.parent().id()[:8],
  )


@ndb.transactional
def update_url(key, url):
  """Updates the given InstanceGroupManager with the instance group manager URL.

  Args:
    key: ndb.Key for a models.InstanceGroupManager entity.
    url: URL string for the instance group manager.
  """
  entity = key.get()
  if not entity:
    logging.warning('InstanceGroupManager does not exist: %s', key)
    return

  if entity.url == url:
    return

  logging.warning(
      'Updating URL for InstanceGroupManager: %s\nOld: %s\nNew: %s',
      key,
      entity.url,
      url,
  )

  entity.url = url
  entity.put()


def create(key):
  """Creates an instance group manager from the given InstanceGroupManager.

  Args:
    key: ndb.Key for a models.InstanceGroupManager entity.

  Raises:
    net.Error: HTTP status code is not 200 (created) or 409 (already created).
  """
  entity = key.get()
  if not entity:
    logging.warning('InstanceGroupManager does not exist: %s', key)
    return

  if entity.url:
    logging.warning(
        'Instance group manager for InstanceGroupManager already exists: %s',
        key,
    )
    return

  parent = key.parent().get()
  if not parent:
    logging.warning('InstanceTemplateRevision does not exist: %s', key.parent())
    return

  if not parent.project:
    logging.warning(
        'InstanceTemplateRevision project unspecified: %s', key.parent())
    return

  if not parent.url:
    logging.warning(
        'InstanceTemplateRevision URL unspecified: %s', key.parent())
    return

  api = gce.Project(parent.project)
  try:
    # Create the instance group manager with 0 instances. The resize cron job
    # will adjust this later.
    result = api.create_instance_group_manager(
        get_name(entity),
        parent.url,
        0,
        entity.key.id(),
        base_name=get_base_name(entity),
    )
  except net.Error as e:
    if e.status_code == 409:
      # If the instance template already exists, just record the URL.
      result = api.get_instance_group_manager(get_name(entity), entity.key.id())
      update_url(entity.key, result['selfLink'])
      return
    else:
      raise

  update_url(entity.key, result['targetLink'])


def schedule_creation():
  """Enqueues tasks to create missing instance group managers."""
  # For each active InstanceGroupManager without a URL, schedule creation
  # of its instance group manager. Since we are outside a transaction the
  # InstanceGroupManager could be out of date and may already have a task
  # scheduled/completed. In either case it doesn't matter since we make
  # creating an instance group manager and updating the URL idempotent.
  for instance_template in models.InstanceTemplate.query():
    if instance_template.active:
      instance_template_revision = instance_template.active.get()
      if instance_template_revision and instance_template_revision.url:
        for instance_group_manager_key in instance_template_revision.active:
          instance_group_manager = instance_group_manager_key.get()
          if instance_group_manager and not instance_group_manager.url:
            if not utils.enqueue_task(
                '/internal/queues/create-instance-group-manager',
                'create-instance-group-manager',
                params={
                    'key': instance_group_manager_key.urlsafe(),
                },
            ):
              logging.warning(
                  'Failed to enqueue task for InstanceGroupManager: %s',
                  instance_group_manager_key,
              )


def get_instance_group_manager_to_delete(key):
  """Returns the URL of the instance group manager to delete.

  Args:
    key: ndb.Key for a models.InstanceGroupManager entity.

  Returns:
    The URL of the instance group manager to delete, or None if there isn't one.
  """
  entity = key.get()
  if not entity:
    logging.warning('InstanceGroupManager does not exist: %s', key)
    return

  if entity.instances:
    logging.warning('InstanceGroupManager has active Instances: %s', key)
    return

  if not entity.url:
    logging.warning('InstanceGroupManager URL unspecified: %s', key)
    return

  return entity.url


def delete(key):
  """Deletes the instance group manager for the given InstanceGroupManager.

  Args:
    key: ndb.Key for a models.InstanceGroupManager entity.

  Raises:
    net.Error: HTTP status code is not 200 (deleted) or 404 (already deleted).
  """
  url = get_instance_group_manager_to_delete(key)
  if not url:
    return

  try:
    result = net.json_request(url, method='DELETE', scopes=gce.AUTH_SCOPES)
    if result['targetLink'] != url:
      logging.warning(
          'InstanceGroupManager mismatch: %s\nExpected: %s\nFound: %s',
          key,
          url,
          result['targetLink'],
      )
  except net.Error as e:
    if e.status_code != 404:
      # If the instance group manager isn't found, assume it's already deleted.
      raise

  update_url(key, None)


def get_drained_instance_group_managers():
  """Returns drained InstanceGroupManagers.

  Returns:
    A list of ndb.Keys for models.InstanceGroupManager entities.
  """
  keys = []

  for instance_template_revision in models.InstanceTemplateRevision.query():
    for key in instance_template_revision.drained:
      keys.append(key)

  # Also include implicitly drained InstanceGroupManagers, those that are active
  # but are members of drained InstanceTemplateRevisions.
  for instance_template in models.InstanceTemplate.query():
    for instance_template_revision_key in instance_template.drained:
      instance_template_revision = instance_template_revision_key.get()
      if instance_template_revision:
        for key in instance_template_revision.active:
          keys.append(key)

  return keys


def schedule_deletion():
  """Enqueues tasks to delete drained instance group managers."""
  for key in get_drained_instance_group_managers():
    entity = key.get()
    if entity and entity.url and not entity.instances:
      if not utils.enqueue_task(
          '/internal/queues/delete-instance-group-manager',
          'delete-instance-group-manager',
          params={
              'key': key.urlsafe(),
          },
      ):
        logging.warning(
          'Failed to enqueue task for InstanceGroupManager: %s', key)


def resize(key):
  """Resizes the given instance group manager.

  Args:
    key: ndb.Key for a models.InstanceGroupManager entity.
  """
  # To avoid a massive resize, impose a limit on how much larger we can
  # resize the instance group. Repeated calls will eventually allow the
  # instance group to reach its target size. Cron timing together with
  # this limit controls the rate at which instances are created.
  RESIZE_LIMIT = 100

  entity = key.get()
  if not entity:
    logging.warning('InstanceGroupManager does not exist: %s', key)
    return

  if not entity.url:
    logging.warning('InstanceGroupManager URL unspecified: %s', key)

  parent = key.parent().get()
  if not parent:
    logging.warning('InstanceTemplateRevision does not exist: %s', key)
    return

  if not parent.project:
    logging.warning('InstanceTemplateRevision project unspecified: %s', key)
    return

  # Determine how many total VMs exist for all other revisions of this
  # InstanceGroupManager. Different revisions will all have the same
  # grandparent InstanceTemplate.
  other_revision_total_size = 0
  for igm in models.InstanceGroupManager.query(ancestor=parent.key.parent()):
    # Find InstanceGroupManagers in the same zone, except the one being resized.
    if igm.key.id() == key.id() and igm.key != key:
        logging.info(
            'Found another revision of InstanceGroupManager: %s\nSize: %s',
            igm.key,
            igm.current_size,
        )
        other_revision_total_size += igm.current_size

  api = gce.Project(parent.project)
  response = api.get_instance_group_manager(get_name(entity), key.id())

  # Find out how many VMs are idle (i.e. not currently being created
  # or deleted). This helps avoid doing too many VM actions simultaneously.
  current_size = response.get('currentActions', {}).get('none')
  if current_size is None:
    logging.error('Unexpected response: %s', json.dumps(response, indent=2))
    return

  # Try to reach the configured size less the number that exist in other
  # revisions of the InstanceGroupManager, but avoid increasing the number of
  # instances by more than the resize limit. For now, the target size
  # is just the minimum size.
  target_size = min(
      entity.minimum_size - other_revision_total_size,
      current_size + RESIZE_LIMIT,
  )
  logging.info(
      'Key: %s\nSize: %s\nTarget: %s\nMin: %s\nMax: %s\nOther revisions: %s',
      key,
      current_size,
      target_size,
      entity.minimum_size,
      entity.maximum_size,
      other_revision_total_size,
  )
  if target_size <= current_size:
    return

  api.resize_managed_instance_group(response['name'], key.id(), target_size)


def schedule_resize():
  """Enqueues tasks to resize instance group managers."""
  for instance_template in models.InstanceTemplate.query():
    if instance_template.active:
      instance_template_revision = instance_template.active.get()
      if instance_template_revision:
        for instance_group_manager_key in instance_template_revision.active:
          if not utils.enqueue_task(
              '/internal/queues/resize-instance-group',
              'resize-instance-group',
              params={
                  'key': instance_group_manager_key.urlsafe(),
              },
          ):
            logging.warning(
                'Failed to enqueue task for InstanceGroupManager: %s',
                instance_group_manager_key,
            )
