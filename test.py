import sys, os
from difflib import unified_diff
from collections import OrderedDict
from tempfile import NamedTemporaryFile
from runpy import run_module
from io import StringIO

from plist import *

def diff(a, b):
	a = a.split('\n')
	b = b.split('\n')
	return '\n'.join(unified_diff(a, b, 'expected', 'got'))

class TestPlist:
	example = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN"
	"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Year Of Birth</key>
	<integer>1965</integer>
	<key>Pets Names</key>
	<array/>
	<key>Picture</key>
	<data>
		PEKBpYGlmYFCPA==
	</data>
	<key>City of Birth</key>
	<string>Springfield</string>
	<key>Name</key>
	<string>John Doe</string>
	<key>Kids Names</key>
	<array>
		<string>John</string>
		<string>Kyra</string>
	</array>
</dict>
</plist>
"""
	
	converted = OrderedDict([
		('Year Of Birth', 1965),
		('Pets Names',    []),
		('Picture',       b'<B\x81\xa5\x81\xa5\x99\x81B<'),
		('City of Birth', 'Springfield'),
		('Name',          'John Doe'),
		('Kids Names',    ['John', 'Kyra']),
	])
	
	def test_canon_example(self):
		"""basic tests if apple’s standard example can be converted properly"""
		data = loads(self.example)
		assert isinstance(data, OrderedDict)
		assert data == self.converted, 'conversion failed:\n' + diff(self.converted, data)
	
	def test_canon_back_conversion(self):
		"""tests if the back-conversion yields the same format as the reference"""
		converted = dumps(self.converted)
		assert converted == self.example, 'back-conversion failed:\n' + diff(self.example, converted)
	
	def test_all_types(self):
		"""Tests for multiple, partially nested, types"""
		a = {
			'bool':    True,
			'None':    None,
			'float':   1.0,
			'int':     5,
			'bytes':   b'\x00\x01\x02\x03\x04\x05\x06',
			'string':  'world',
			'list':    [0, 1, 2, 3, 4, 5],
			'nesting': [['is', 'possible'], 'too', ['of', 'course']],
			'dict':    {'example': 'nesting'},
		}
		b = dumps(a)
		c = loads(b)
		assert a == c, 'back-conversion failed:\n' + diff(a, c)
	
	def test_cmdline(self):
		"""This little monstrosity tests the “python -m plist” call. Because I can."""
		argv_bak = sys.argv
		stdo_bak = sys.stdout
		
		out = StringIO()
		with NamedTemporaryFile(mode='w') as tmp:
			tmp.write(self.example)
			tmp.flush()
			
			sys.argv   = [sys.argv[0], tmp.name]
			sys.stdout = out
			run_module('plist') #reads tmp and writes to sys.stdout
		
		sys.argv   = argv_bak
		sys.stdout = stdo_bak
		
		r = repr(self.converted)
		c = out.getvalue().strip()
		assert r == c, 'script failed:\n' + diff(r, c)

if __name__ == '__main__':
	import nose
	nose.run()