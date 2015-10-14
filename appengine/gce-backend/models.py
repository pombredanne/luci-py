# Copyright 2015 The Swarming Authors. All rights reserved.
# Use of this source code is governed by the Apache v2.0 license that can be
# found in the LICENSE file.

"""Datastore models for the Machine Provider messages."""

import hashlib

from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop

from components.machine_provider import rpc_messages


class Enum(frozenset):
  def __getattr__(self, attr):
    if attr in self:
      return attr
    raise AttributeError(attr)


OSFamilies = Enum(rpc_messages.OSFamily.names())


class InstanceTemplate(ndb.Model):
  """Datastore representation of a GCE instance template.

  Key:
    InstanceTemplate is a root entity.
    id: Hash of the instance template name and project.
  """
  # Initial size when newly creating the instance group manager.
  initial_size = ndb.IntegerProperty(required=True)
  # Name of the instance group manager that should be created from the template.
  instance_group_name = ndb.StringProperty(required=True)
  # Project the instance group manager should be created in.
  instance_group_project = ndb.StringProperty(required=True)
  # rpc_messages.OSFamily of this instance.
  os_family = ndb.StringProperty(choices=OSFamilies, required=True)
  # Name of the instance template.
  template_name = ndb.StringProperty(required=True)
  # Project containing the instance template.
  template_project = ndb.StringProperty(required=True)
  # Zone the instance group manager should be created in.
  zone = ndb.StringProperty(required=True)

  @classmethod
  def generate_key(cls, name, project):
    """Generates the key for an InstanceTemplate with the given name/project.

    Args:
      name: Name of this instance template.
      project: Project containing this instance template.

    Returns:
      An ndb.Key instance.
    """
    return ndb.Key(cls, hashlib.sha1('%s\0%s' % (name, project)).hexdigest())


class InstanceGroup(ndb.Model):
  """Datastore representation of a GCE instance group.

  Key:
    InstanceGroup is a root entity.
    id: Hash of the instance group name.
  """
  # rpc_messages.Dimensions describing members of this instance group.
  dimensions = msgprop.MessageProperty(rpc_messages.Dimensions, required=True)
  # Names of members of this instance group.
  members = ndb.StringProperty(repeated=True)
  # Name of this instance group.
  name = ndb.StringProperty(required=True)
  # rpc_messages.Policies governing members of this instance group.
  policies = msgprop.MessageProperty(rpc_messages.Policies, required=True)

  @classmethod
  def create_and_put(cls, name, dimensions, policies, members):
    """Creates a new InstanceGroup entity and puts it in the datastore.

    Args:
      name: Name of this instance group.
      dimensions: rpc_messages.Dimensions describing members of this instance
        group.
      policies: rpc_messages.Policies governing members of this instance group.
      members: A list of names of members of this instance group.
    """
    assert dimensions.backend == rpc_messages.Backend.GCE
    cls(
        key=cls.generate_key(name),
        dimensions=dimensions,
        members=members,
        name=name,
        policies=policies,
    ).put()

  @classmethod
  def generate_key(cls, name):
    """Generates the key for an InstanceGroup with the given name.

    Args:
      name: Name of this instance group.

    Returns:
      An ndb.Key instance.
    """
    return ndb.Key(cls, hashlib.sha1(name).hexdigest())


InstanceStates = Enum([
  'CATALOGED', 'UNCATALOGED', 'PENDING_DELETION', 'DELETED'])


class Instance(ndb.Model):
  """Datastore representation of a GCE instance.

  Key:
    Instance is a root entity.
    id: Hash of the instance group name + the instance name.
  """
  # Name of the instance group this instance belongs to.
  group = ndb.StringProperty(required=True)
  # Name of this instance.
  name = ndb.StringProperty(required=True)
  # Project this instance is located in.
  project = ndb.StringProperty(required=True)
  # State of this instance.
  state = ndb.StringProperty(choices=InstanceStates, required=True)
  # URL for this instance.
  url = ndb.StringProperty(required=True)
  # Zone this instance is located in.
  zone = ndb.StringProperty(required=True)

  @classmethod
  def generate_key(cls, name):
    """Generates the key for an Instance with the given name.

    Args:
      name: Name of this instance.

    Returns:
      An ndb.Key instance.
    """
    return ndb.Key(cls, hashlib.sha1(name).hexdigest())