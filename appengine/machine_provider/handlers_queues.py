# Copyright 2015 The LUCI Authors. All rights reserved.
# Use of this source code is governed under the Apache License, Version 2.0
# that can be found in the LICENSE file.

"""Task queues for fulfilling lease requests."""

import json
import logging

from google.appengine.ext import ndb
import webapp2

from components import decorators
from components import net
from components import pubsub
from components.machine_provider import rpc_messages

import metrics
import models


def maybe_notify_backend(message, hostname, policies):
  """Informs the backend of the status of a request if there's a Pub/Sub topic.

  Args:
    message: The message string to send.
    hostname: The hostname of the machine this message concerns.
    policies: A dict representation of an rpc_messages.Policies instance.
  """
  if policies.get('backend_topic'):
    topic = pubsub.full_topic_name(
        policies['backend_project'], policies['backend_topic'])
    attributes = {
        attribute['key']: attribute['value']
        for attribute in policies['backend_attributes']
    }
    attributes['hostname'] = hostname
    pubsub.publish(topic, message, attributes)
    # There are relatively few backends, so it's safe to include the
    # backend topic/project as the value for the target field.
    metrics.pubsub_messages_sent.increment(fields={'target': topic})


def maybe_notify_lessee(request, response):
  """Informs the lessee of the status of a request if there's a Pub/Sub topic.

  Args:
    request: A dict representation of an rpc_messages.LeaseRequest instance.
    response: A dict representation of an rpc_messages.LeaseResponse instance.
  """
  if request.get('pubsub_topic'):
    pubsub.publish(
        pubsub.full_topic_name(
            request['pubsub_project'], request['pubsub_topic']),
        json.dumps(response),
        {},
    )
    metrics.pubsub_messages_sent.increment(fields={'target': 'lessee'})


class LeaseRequestFulfiller(webapp2.RequestHandler):
  """Worker for fulfilling lease requests."""

  @decorators.require_taskqueue('fulfill-lease-request')
  def post(self):
    """Fulfill a lease request.

    Params:
      machine_project: Project that the machine communication topic is contained
        in.
      machine_topic: Topic that the machine communication should occur on.
      policies: JSON-encoded string representation of the
        rpc_messages.Policies governing this machine.
      request_json: JSON-encoded string representation of the
        rpc_messages.LeaseRequest being fulfilled.
      response_json: JSON-encoded string representation of the
        rpc_messages.LeaseResponse being delivered.
    """
    machine_project = self.request.get('machine_project')
    machine_topic = self.request.get('machine_topic')
    policies = json.loads(self.request.get('policies'))
    request = json.loads(self.request.get('request_json'))
    response = json.loads(self.request.get('response_json'))

    maybe_notify_backend('LEASED', response['hostname'], policies)
    maybe_notify_lessee(request, response)

    # Inform the machine.
    messages = {
        'LEASED': {'lease_expiration_ts': str(response['lease_expiration_ts'])}
    }
    if request.get('on_lease', {}).get('swarming_server'):
      messages['CONNECT'] = {
          'swarming_server': request['on_lease']['swarming_server']
      }
    pubsub.publish_multi(
        pubsub.full_topic_name(machine_project, machine_topic), messages)
    metrics.pubsub_messages_sent.increment_by(
        len(messages), fields={'target': 'machine'})


@ndb.transactional(xg=True)
def reclaim(machine_key):
  """Reclaims a machine.

  Args:
    machine_key: ndb.Key for a models.CatalogMachineEntry.
  """
  machine = machine_key.get()
  if not machine:
    return

  lease = models.LeaseRequest.get_by_id(machine.lease_id)
  lease.machine_id = None
  lease.response.hostname = None
  machine.key.delete()
  lease.put()


class MachineReclaimer(webapp2.RequestHandler):
  """Worker for reclaiming machines."""

  @decorators.require_taskqueue('reclaim-machine')
  def post(self):
    """Reclaim a machine.

    Params:
      hostname: Hostname of the machine being reclaimed.
      machine_key: URL-safe ndb.Key for a models.CatalogMachineEntry.
      machine_subscription: Subscription created for the machine to listen
        for instructions on.
      machine_subscription_project: Project that the machine subscription is
        contained in.
      machine_topic: Topic that the machine communication should occur on.
      machine_topic_project: Project that the machine communication topic is
        contained in.
      policies: JSON-encoded string representation of the
        rpc_messages.Policies governing this machine.
      request_json: JSON-encoded string representation of the
        rpc_messages.LeaseRequest being fulfilled.
      response_json: JSON-encoded string representation of the
        rpc_messages.LeaseResponse being delivered.
    """
    hostname = self.request.get('hostname')
    machine_key = ndb.Key(urlsafe=self.request.get('machine_key'))
    machine_subscription = self.request.get('machine_subscription')
    machine_subscription_project = self.request.get(
        'machine_subscription_project')
    machine_topic = self.request.get('machine_topic')
    machine_topic_project = self.request.get('machine_topic_project')
    policies = json.loads(self.request.get('policies'))
    request = json.loads(self.request.get('request_json'))
    response = json.loads(self.request.get('response_json'))

    assert machine_key.kind() == 'CatalogMachineEntry', machine_key

    maybe_notify_backend('RECLAIMED', hostname, policies)
    maybe_notify_lessee(request, response)

    # Delete machine Pub/Sub channel.
    pubsub.ensure_subscription_deleted(
        pubsub.full_subscription_name(
            machine_subscription_project, machine_subscription))
    pubsub.ensure_topic_deleted(
        pubsub.full_topic_name(machine_topic_project, machine_topic))

    reclaim(machine_key)
    metrics.lease_requests_expired.increment()


@ndb.transactional
def set_available(machine_key, topic, subscription):
  """Sets a machine as AVAILABLE.

  Args:
    machine_key: ndb.Key for a models.CatalogMachineEntry instance.
    topic: Name of the Pub/Sub topic for communicating with this machine.
    subscription: Name of the Pub/Sub subscription created for this machine.
  """
  machine = machine_key.get()
  if not machine:
    logging.error('CatalogMachineEntry does not exist: %s', machine_key)
    return

  if machine.state == models.CatalogMachineEntryStates.NEW:
    machine.pubsub_subscription = subscription
    machine.pubsub_topic = topic
    machine.state = models.CatalogMachineEntryStates.AVAILABLE
    machine.put()
  elif machine.state == models.CatalogMachineEntryStates.AVAILABLE:
    logging.info('CatalogMachineEntry already AVAILABLE:\n%s', machine)
  else:
    logging.error('CatalogMachineEntry in unexpected state:\n%s', machine)


class MachineSubscriber(webapp2.RequestHandler):
  """Worker for subscribing machines to a Cloud Pub/Sub topic."""

  @decorators.require_taskqueue('subscribe-machine')
  def post(self):
    """Subscribe a machine to a Cloud Pub/Sub topic.

    Params:
      backend_project: If specified, project that the machine subscription
        topic is contained in for the backend.
      backend_attributes: If specified, JSON-encoded dict of attributes to
        include in the machine subscription message for the backend.
      backend_topic: If specified, topic that the machine subscription should
        be published to for the backend.
      hostname: Hostname being reclaimed.
      machine_id: ID of the CatalogMachineEntry being reclaimed.
      machine_service_account: Service account to authorize to consume the
        subscription.
      machine_subscription: Cloud Pub/Sub subscription to create for the
        machine.
      machine_subscription_project: Project the Cloud Pub/Sub subscription
        should live in.
      machine_topic: Cloud Pub/Sub topic to create for the machine.
      machine_topic_project: Project the Cloud Pub/Sub topic should live in.
    """
    backend_attributes = json.loads(self.request.get('backend_attributes', {}))
    backend_project = self.request.get('backend_project')
    backend_topic = self.request.get('backend_topic')
    hostname = self.request.get('hostname')
    machine_id = self.request.get('machine_id')
    machine_service_account = self.request.get('machine_service_account')
    machine_subscription = self.request.get('machine_subscription')
    machine_subscription_project = self.request.get(
        'machine_subscription_project')
    machine_topic = self.request.get('machine_topic')
    machine_topic_project = self.request.get('machine_topic_project')

    topic = pubsub.full_topic_name(machine_topic_project, machine_topic)
    subscription = pubsub.full_subscription_name(
        machine_subscription_project, machine_subscription)
    pubsub.ensure_subscription_exists(subscription, topic)

    with pubsub.iam_policy(subscription) as policy:
      policy.add_member(
          'roles/pubsub.subscriber',
          'serviceAccount:%s' % machine_service_account,
      )

    if backend_topic:
      topic = pubsub.full_topic_name(backend_project, backend_topic)
      attributes = backend_attributes.copy()
      attributes['hostname'] = hostname
      attributes['subscription'] = machine_subscription
      attributes['subscription_project'] = machine_subscription_project
      attributes['topic'] = machine_topic
      attributes['topic_project'] = machine_topic_project
      pubsub.publish(topic, 'SUBSCRIBED', attributes)
      # There are relatively few backends, so it's safe to include the
      # backend topic/project as the value for the target field.
      metrics.pubsub_messages_sent.increment(fields={'target': topic})

    set_available(
        ndb.Key(models.CatalogMachineEntry, machine_id),
        machine_topic,
        machine_subscription,
    )


def create_queues_app():
  return webapp2.WSGIApplication([
      ('/internal/queues/fulfill-lease-request', LeaseRequestFulfiller),
      ('/internal/queues/reclaim-machine', MachineReclaimer),
      ('/internal/queues/subscribe-machine', MachineSubscriber),
  ])
