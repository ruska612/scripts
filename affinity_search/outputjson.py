#!/usr/bin/env python

'''
Output the parameters that makemodel supports with their ranges
'''

import makemodel
import json, sys
from collections import OrderedDict

#extract from arguments to makemodel
opts = makemodel.getoptions()

d=OrderedDict()
for (name,vals) in sorted(opts.items()):
	paramsize=1
	if type(vals) == tuple:
		options=map(str,vals)
		paramtype="enum"
		data=OrderedDict([("name",name), ("type", paramtype), ("size", paramsize),("options",options)])
	elif isinstance(vals, makemodel.Range):
		parammin = vals.min
		parammax = vals.max
		paramtype="float"
		data=OrderedDict([("name",name), ("type", paramtype), ("min", parammin), ("max", parammax), ("size", paramsize)])
	else:
		print "Unknown type"
		sys.exit(-1)
	d[name]=data
sys.stdout.write(json.dumps(d, indent=4)+'\n')

