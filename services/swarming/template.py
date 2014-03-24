# Copyright 2013 The Swarming Authors. All rights reserved.
# Use of this source code is governed by the Apache v2.0 license that can be
# found in the LICENSE file.

"""Setups jinja2 environment."""

import datetime
import os

import jinja2

from google.appengine.api import users


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

JINJA = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(ROOT_DIR, 'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


# Registers library custom filters.


def datetimeformat(value, f='%Y-%m-%d %H:%M:%S'):
  return value.strftime(f)


def datetime_human(dt):
  """Converts a datetime.datetime to a user-friendly string."""
  if not dt:
    return '--'
  dt_date = dt.date()
  today = datetime.datetime.utcnow().date()
  if dt_date == today:
    return dt.strftime('Today, %H:%M:%S')
  if dt_date == today - datetime.timedelta(days=1):
    return dt.strftime('Yesterday, %H:%M:%S')
  return dt.strftime('%Y-%m-%d %H:%M:%S')


JINJA.filters['datetimeformat'] = datetimeformat
JINJA.filters['datetime_human'] = datetime_human


def get_defaults():
  """Returns parameters used by templates/base.html."""
  account = users.get_current_user()
  return {
    'nickname': account.email() if account else None,
    'signin_link': users.create_login_url('/') if not account else None,
    'user_is_admin': users.is_current_user_admin(),
  }


def render(name, params):
  """Shorthand to render a template."""
  data = get_defaults()
  data.update(params)
  return JINJA.get_template(name).render(data)
