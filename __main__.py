#!/usr/bin/env python3

"""
Pretty useless script, mainly to quickly check how conversion turned out.
A pity that OrderedDict doesn’t get prettyprinted, else we could use pprint.
"""

import sys
from . import *

if len(sys.argv) > 1:
	filename = sys.argv[1]
	plist = load(filename)
else:
	plist = load(sys.stdin)

print(repr(plist))