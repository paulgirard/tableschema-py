# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import pytest
from copy import deepcopy
from mock import Mock, patch
from tableschema import Schema, Table, Storage, exceptions


# General

BASE_URL = 'https://raw.githubusercontent.com/frictionlessdata/tableschema-py/master/%s'
DATA_MIN = [('key', 'value'), ('one', '1'), ('two', '2')]
SCHEMA_MIN = {'fields': [{'name': 'key'}, {'name': 'value', 'type': 'integer'}]}
SCHEMA_CSV = {
    'fields': [
        {'name': 'id', 'type': 'integer', 'format': 'default'},
        {'name': 'age', 'type': 'integer', 'format': 'default'},
        {'name': 'name', 'type': 'string', 'format': 'default'},
    ],
    'missingValues': [''],
}


def test_schema_instance(apply_defaults):
    schema_instance = Schema(SCHEMA_MIN)
    actual = Table(DATA_MIN, schema=schema_instance).schema.descriptor
    expect = apply_defaults(SCHEMA_MIN)
    assert actual == expect


def test_schema_descriptor(apply_defaults):
    actual = Table(DATA_MIN, schema=SCHEMA_MIN).schema.descriptor
    expect = apply_defaults(SCHEMA_MIN)
    assert actual == expect


def test_schema_infer_tabulator():
    table = Table('data/data_infer.csv')
    table.infer()
    assert table.headers == ['id', 'age', 'name']
    assert table.schema.descriptor == SCHEMA_CSV


@patch('tableschema.storage.import_module')
def test_schema_infer_storage(import_module, apply_defaults):
    import_module.return_value = Mock(Storage=Mock(return_value=Mock(
        describe=Mock(return_value=SCHEMA_MIN),
        iter=Mock(return_value=DATA_MIN[1:]),
    )))
    table = Table('table', storage='storage')
    table.infer()
    assert table.headers == ['key', 'value']
    assert table.schema.descriptor == apply_defaults(SCHEMA_MIN)


def test_infer_schema_empty_file():
    s = Table('data/empty.csv')
    d = s.infer()
    assert d == {
        'fields': [],
        'missingValues': [''],
    }


def test_iter():
    table = Table(DATA_MIN, schema=SCHEMA_MIN)
    expect = [['one', 1], ['two', 2]]
    actual = list(table.iter())


def test_iter_csv():
    table = Table('data/data_infer.csv', schema=SCHEMA_CSV)
    expect = [[1, 39, 'Paul'], [2, 23, 'Jimmy'], [3, 36, 'Jane'], [4, 28, 'Judy']]
    actual = list(table.iter())
    assert actual == expect


def test_iter_web_csv():
    table = Table(BASE_URL % 'data/data_infer.csv', schema=SCHEMA_CSV)
    expect = [[1, 39, 'Paul'], [2, 23, 'Jimmy'], [3, 36, 'Jane'], [4, 28, 'Judy']]
    actual = list(table.iter())
    assert actual == expect


def test_iter_keyed():
    table = Table(DATA_MIN, schema=SCHEMA_MIN)
    expect = [{'key': 'one', 'value': 1}, {'key': 'two', 'value': 2}]
    actual = list(table.iter(keyed=True))
    assert actual == expect


def test_read_keyed():
    table = Table(DATA_MIN, schema=SCHEMA_MIN)
    expect = [{'key': 'one', 'value': 1}, {'key': 'two', 'value': 2}]
    actual = table.read(keyed=True)
    assert actual == expect


def test_read_limit():
    table = Table(DATA_MIN, schema=SCHEMA_MIN)
    expect = [['one', 1]]
    actual = table.read(limit=1)
    assert actual == expect


@patch('tableschema.storage.import_module')
def test_read_storage(import_module):
    # Mocks
    import_module.return_value = Mock(Storage=Mock(return_value=Mock(
        describe=Mock(return_value=SCHEMA_MIN),
        iter=Mock(return_value=DATA_MIN[1:]),
    )))
    # Tests
    table = Table('table', storage='storage')
    table.infer()
    expect = [['one', 1], ['two', 2]]
    actual = table.read()
    assert actual == expect


def test_read_storage_passed_as_instance():
    # Mocks
    storage = Mock(
        describe=Mock(return_value=SCHEMA_MIN),
        iter=Mock(return_value=DATA_MIN[1:]),
        spec=Storage,
    )
    # Tests
    table = Table('table', storage=storage)
    table.infer()
    expect = [['one', 1], ['two', 2]]
    actual = table.read()
    assert actual == expect


def test_processors():
    # Processor
    def skip_under_30(erows):
        for row_number, headers, row in erows:
            krow = dict(zip(headers, row))
            if krow['age'] >= 30:
                yield (row_number, headers, row)
    # Create table
    table = Table('data/data_infer.csv', post_cast=[skip_under_30])
    table.infer()
    expect = [
        [1, 39, 'Paul'],
        [3, 36, 'Jane']]
    actual = table.read()
    assert actual == expect


def test_unique_constraint_violation():
    schema = deepcopy(SCHEMA_CSV)
    schema['fields'][0]['constraints'] = {'unique': True}
    source = [
        ['id', 'age', 'name'],
        [1, 39, 'Paul'],
        [1, 36, 'Jane'],
    ]
    table = Table(source, schema=schema)
    with pytest.raises(exceptions.TableSchemaException) as excinfo:
        table.read()
    assert 'duplicates' in str(excinfo.value)


def test_unique_primary_key_violation():
    schema = deepcopy(SCHEMA_CSV)
    schema['primaryKey'] = 'id'
    source = [
        ['id', 'age', 'name'],
        [1, 39, 'Paul'],
        [1, 36, 'Jane'],
    ]
    table = Table(source, schema=schema)
    with pytest.raises(exceptions.TableSchemaException) as excinfo:
        table.read()
    assert 'duplicates' in str(excinfo.value)


def test_read_with_headers_field_names_mismatch():
    source = [
        ['id', 'bad', 'name'],
        [1, 39, 'Paul'],
    ]
    table = Table(source, schema=SCHEMA_CSV)
    with pytest.raises(exceptions.CastError) as excinfo:
        table.read()
    assert 'match schema field names' in str(excinfo.value)


# Foreign keys

FK_SOURCE = [
  ['id', 'name', 'surname'],
  ['1', 'Alex', 'Martin'],
  ['2', 'John', 'Dockins'],
  ['3', 'Walter', 'White'],
]
FK_SCHEMA = {
  'fields': [
    {'name': 'id'},
    {'name': 'name'},
    {'name': 'surname'},
  ],
  'foreignKeys': [
    {
      'fields': 'name',
      'reference': {'resource': 'people', 'fields': 'firstname'},
    },
  ]
}
FK_RELATIONS = {
  'people': [
    {'firstname': 'Alex', 'surname': 'Martin'},
    {'firstname': 'John', 'surname': 'Dockins'},
    {'firstname': 'Walter', 'surname': 'White'},
  ]
}


def test_single_field_foreign_key():
    table = Table(FK_SOURCE, schema=FK_SCHEMA)
    rows = table.read(relations=FK_RELATIONS)
    assert rows == [
      ['1', {'firstname': 'Alex', 'surname': 'Martin'}, 'Martin'],
      ['2', {'firstname': 'John', 'surname': 'Dockins'}, 'Dockins'],
      ['3', {'firstname': 'Walter', 'surname': 'White'}, 'White'],
    ]

def test_single_field_foreign_key_invalid():
    relations = deepcopy(FK_RELATIONS)
    relations['people'][2]['firstname'] = 'Max'
    table = Table(FK_SOURCE, schema=FK_SCHEMA)
    with pytest.raises(exceptions.RelationError) as excinfo:
        table.read(relations=relations)
    assert 'Foreign key' in str(excinfo.value)


def test_multi_field_foreign_key():
    schema = deepcopy(FK_SCHEMA)
    schema['foreignKeys'][0]['fields'] = ['name', 'surname']
    schema['foreignKeys'][0]['reference']['fields'] = ['firstname', 'surname']
    table = Table(FK_SOURCE, schema=schema)
    keyed_rows = table.read(keyed=True, relations=FK_RELATIONS)
    assert keyed_rows == [
      {
          'id': '1',
          'name': {'firstname': 'Alex', 'surname': 'Martin'},
          'surname': {'firstname': 'Alex', 'surname': 'Martin'},
      },
      {
          'id': '2',
          'name': {'firstname': 'John', 'surname': 'Dockins'},
          'surname': {'firstname': 'John', 'surname': 'Dockins'},
      },
      {
          'id': '3',
          'name': {'firstname': 'Walter', 'surname': 'White'},
          'surname': {'firstname': 'Walter', 'surname': 'White'},
      },
    ]


def test_multi_field_foreign_key_invalid():
    schema = deepcopy(FK_SCHEMA)
    schema['foreignKeys'][0]['fields'] = ['name', 'surname']
    schema['foreignKeys'][0]['reference']['fields'] = ['firstname', 'surname']
    relations = deepcopy(FK_RELATIONS)
    del relations['people'][2]
    table = Table(FK_SOURCE, schema=schema)
    with pytest.raises(exceptions.RelationError) as excinfo:
        table.read(relations=relations)
    assert 'Foreign key' in str(excinfo.value)


# Issues

def test_composite_primary_key_issue_194():
    source = [
        ['id1', 'id2'],
        ['a', '1'],
        ['a', '2'],
    ]
    schema = {
        'fields': [
            {'name': 'id1'},
            {'name': 'id2'},
        ],
        'primaryKey': ['id1', 'id2']
    }
    table = Table(source, schema=schema)
    assert table.read() == source[1:]


def test_composite_primary_key_fails_unique_issue_194():
    source = [
        ['id1', 'id2'],
        ['a', '1'],
        ['a', '1'],
    ]
    schema = {
        'fields': [
            {'name': 'id1'},
            {'name': 'id2'},
        ],
        'primaryKey': ['id1', 'id2']
    }
    table = Table(source, schema=schema)
    with pytest.raises(exceptions.CastError) as excinfo:
        table.read()
    assert 'duplicates' in str(excinfo.value)

def test_multiple_foreign_keys_same_field():
    schema = deepcopy(FK_SCHEMA)
    relations = deepcopy(FK_RELATIONS)
    relations['gender'] = [
        {'firstname': 'Alex', 'gender': 'male/female'},
        {'firstname': 'John', 'gender': 'male'},
        {'firstname': 'Walter', 'gender': 'male'},
        {'firstname': 'Alice', 'gender': 'female'}
    ]
    # the main ressource now has tow foreignKeys using the same 'name' field
    schema['foreignKeys'].append({
            'fields': 'name',
            'reference': {'resource': 'gender', 'fields': 'firstname'},
          })
    table = Table(FK_SOURCE, schema=schema)
    keyed_rows = table.read(keyed=True, relations=relations)
    assert keyed_rows == [
      {
          'id': '1',
          'name': {'firstname': 'Alex', 'surname': 'Martin' ,'gender': 'male/female'},
          'surname': 'Martin'
      },
      {
          'id': '2',
          'name': {'firstname': 'John', 'surname': 'Dockins', 'gender': 'male'},
          'surname': 'Dockins'
      },
      {
          'id': '3',
          'name': {'firstname': 'Walter', 'surname': 'White', 'gender': 'male'},
          'surname': 'White'
      },
    ]


def test_multiple_foreign_keys_same_field_invalid():
    schema = deepcopy(FK_SCHEMA)
    relations = deepcopy(FK_RELATIONS)
    relations['gender'] = [
        {'firstname': 'Alex', 'gender': 'male/female'},
        {'firstname': 'Johny', 'gender': 'male'},
        {'firstname': 'Walter', 'gender': 'male'},
        {'firstname': 'Alice', 'gender': 'female'}
    ]
    # the main ressource now has tow foreignKeys using the same 'name' field
    schema['foreignKeys'].append({
            'fields': 'name',
            'reference': {'resource': 'gender', 'fields': 'firstname'},
          })
    table = Table(FK_SOURCE, schema=schema)
    with pytest.raises(exceptions.RelationError) as excinfo:
        table.read(relations=relations)
    assert 'Foreign key' in str(excinfo.value)    
    
