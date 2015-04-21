# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: project_config.proto

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)




DESCRIPTOR = _descriptor.FileDescriptor(
  name='project_config.proto',
  package='config_service',
  serialized_pb='\n\x14project_config.proto\x12\x0e\x63onfig_service\"\x1a\n\nProjectCfg\x12\x0c\n\x04name\x18\x01 \x01(\t\"^\n\x07RefsCfg\x12)\n\x04refs\x18\x01 \x03(\x0b\x32\x1b.config_service.RefsCfg.Ref\x1a(\n\x03Ref\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x13\n\x0b\x63onfig_path\x18\x03 \x01(\t')




_PROJECTCFG = _descriptor.Descriptor(
  name='ProjectCfg',
  full_name='config_service.ProjectCfg',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='config_service.ProjectCfg.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=40,
  serialized_end=66,
)


_REFSCFG_REF = _descriptor.Descriptor(
  name='Ref',
  full_name='config_service.RefsCfg.Ref',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='config_service.RefsCfg.Ref.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='config_path', full_name='config_service.RefsCfg.Ref.config_path', index=1,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=122,
  serialized_end=162,
)

_REFSCFG = _descriptor.Descriptor(
  name='RefsCfg',
  full_name='config_service.RefsCfg',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='refs', full_name='config_service.RefsCfg.refs', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_REFSCFG_REF, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=68,
  serialized_end=162,
)

_REFSCFG_REF.containing_type = _REFSCFG;
_REFSCFG.fields_by_name['refs'].message_type = _REFSCFG_REF
DESCRIPTOR.message_types_by_name['ProjectCfg'] = _PROJECTCFG
DESCRIPTOR.message_types_by_name['RefsCfg'] = _REFSCFG

class ProjectCfg(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _PROJECTCFG

  # @@protoc_insertion_point(class_scope:config_service.ProjectCfg)

class RefsCfg(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType

  class Ref(_message.Message):
    __metaclass__ = _reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _REFSCFG_REF

    # @@protoc_insertion_point(class_scope:config_service.RefsCfg.Ref)
  DESCRIPTOR = _REFSCFG

  # @@protoc_insertion_point(class_scope:config_service.RefsCfg)


# @@protoc_insertion_point(module_scope)
