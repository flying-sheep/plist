"""
Library to read and write apple property lists,
and convert them from/to python datatypes.
Data tags are represented as bytes.

The following types can be converted to PLists, or –
in case of dicts and lists – similarly-behaving ones:

* dict | collections.OrderedDict
* list | tuple
* str
* bytes
* int
* float
* bool

OrderedDicts are used to represent dicts read from PLists.

Exception details:
------------------
Serialization throws a TypeError if it encounters a nonconvertible type.

Deserialization generally throws a ValueError in case of malformed data.
(e.g. if it is valid XML, but not adhering to the PropertyList spec),
but can also throw an IndexError if dicts have incomplete key/value pairs.
"""

import re
from io import StringIO
from datetime import datetime
from itertools import tee
from collections import OrderedDict
from collections.abc import Sequence, Mapping
from xml.etree import ElementTree as etree

from .iso8601 import parse_date

__all__ = ['load', 'loads', 'fromtree', 'dump', 'dumps', 'totree']

# Utils

PLISTHEADER = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN"
	"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
"""

def tree2xml(elem, write, i=0, init_increment=1):
	"""
	Converts a ElementTree Element to indented XML.
	Intended to be used on a filelike object’s “write” function.
	init_increment can be used to e.g. suppress indentation of the first level.
	"""
	tag = elem.tag
	text = elem.text
	I = i * '\t'
	
	if tag is None:
		if text:
			write(I + text + '\n')
		for e in elem:
			tree2xml(e, write, i + init_increment)
	else:
		write(I + '<' + tag)
		for k, v in elem.items():
			write(' {}="{}"'.format(k, v))
		if text or len(elem):
			write('>')
			if text:
				write(text)
			else:
				write('\n')
			for e in elem:
				tree2xml(e, write, i + init_increment)
			if not text:
				write(I)
			write('</' + tag + '>\n')
		else:
			write('/>\n')

class _b64:
	"""convenience class to b64transcode strings"""
	from base64 import decodebytes, encodebytes
	
	@staticmethod
	def encodeb2s(b):
		"""bytes data to base64 string"""
		return _b64.encodebytes(b).decode()
	
	#String to bytes
	@staticmethod
	def decodes2b(s):
		"""base64 string to bytes data"""
		return _b64.decodebytes(s.encode())

# Serialization

def load(file_or_path):
	"""Read PList file into a python object"""
	return fromtree(etree.parse(file_or_path))

def loads(data):
	"""Convert PList string to a python object"""
	return fromtree(etree.fromstring(data.strip()))

def fromtree(tree):
	"""Convert PList element tree to a python object"""
	if hasattr(tree, 'getroot'):
		tree = tree.getroot()
	if tree.tag != 'plist' or len(tree) != 1:
		raise ValueError('Bad property list')
	return deserialize(tree[0])

WHITESPACE_RE = re.compile(r'^\s+|\n|\r|\s+$')

TYPES_STATIC = {
	True:  'true',
	False: 'false',
	None:  'undef',
}

TYPES_WRAP = {
	str:      'string',
	int:      'integer',
	float:    'real', #needs repr
}

class PListBuilder(etree.TreeBuilder):
	"""Used to convert a object hierarchy to a PList ElementTree Element"""
	def __init__(self, data):
		etree.TreeBuilder.__init__(self)
		self.start('plist', dict(version='1.0'))
		self.data_elem = self.serialize(data)
		self.end('plist')
	
	def tag(self, name, data=None):
		self.start(name)
		data = str(data)
		if data:
			self.data(data)
		return self.end(name)
	
	def serialize(self, data):
		typ = (t for t in TYPES_WRAP if isinstance(data, t))
		typ = TYPES_WRAP.get(next(typ, None))
		
		if any(data is s for s in TYPES_STATIC):
			return self.tag(TYPES_STATIC[data])
		elif typ:
			return self.tag(typ, data if typ != 'real' else repr(data))
		elif isinstance(data, datetime):
			return self.tag('date', data.isoformat())
		elif isinstance(data, bytes):
			self.start('data')
			self.tag(None, WHITESPACE_RE.sub('', _b64.encodeb2s(data)))
			return self.end('data')
		elif isinstance(data, Mapping): #dictlike
			tags = data.keys()
			if not isinstance(data, OrderedDict):
				tags = sorted(tags)
			self.start('dict')
			for key in tags:
				value = data[key]
				self.tag('key', key)
				self.serialize(value)
			return self.end('dict')
		elif isinstance(data, Sequence): #listlike
			self.start('array')
			for element in data:
				self.serialize(element)
			return self.end('array')
		
		raise TypeError('Unknown type: Can’t handle {} of type {}'.format(data, type(data)))

# Deserialization

def dump(data, file_or_path):
	"""Write compatible python object to PList file"""
	if isinstance(file_or_path, str):
		file_or_path = open(file_or_path, 'w')
	file_or_path.write(PLISTHEADER)
	tree2xml(totree(data), file_or_path.write, init_increment=0)

def dumps(data):
	"""Convert compatible python object to PList string"""
	b = StringIO()
	dump(data, b)
	return b.getvalue()

def totree(data):
	"""Convert compatible python object to PList element tree"""
	return PListBuilder(data).close()

TAGS_STATIC = {
	'true':  True,
	'false': False,
	'undef': None,
}

TAGS_TEXT = {
	'integer': int,
	'real':    float,
	'date':    parse_date,
	'data':    _b64.decodes2b,
	'string':  str, #no-op
}

def deserialize(element):
	"""Used to convert a PList ElementTree Element to a object hierarchy"""
	tag = element.tag
	
	if tag in TAGS_STATIC:
		return TAGS_STATIC[tag]
	elif tag in TAGS_TEXT:
		return TAGS_TEXT[tag](element.text)
	elif tag == 'array':
		return [deserialize(child) for child in element]
	elif tag == 'dict':
		data     = OrderedDict()
		children = list(element)
		if len(children) % 2 != 0:
			raise IndexError('Incomplete dictionary')
		c = iter(children)
		for key, value in zip(c, c):
			if key.tag != 'key':
				raise ValueError('No dictionary key where expected')
			data[key.text] = deserialize(value)
		return data
	
	raise ValueError('Unknown tag: {} isn’t in the PList spec'.format(element.tag))