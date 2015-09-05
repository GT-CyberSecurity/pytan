#!/usr/bin/env python
"""
Create a group called All Windows Computers API Test
"""
# import the basic python packages we need
import os
import sys
import tempfile
import pprint
import traceback

# disable python from generating a .pyc file
sys.dont_write_bytecode = True

# change me to the path of pytan if this script is not running from EXAMPLES/PYTAN_API
pytan_loc = "~/gh/pytan"
pytan_static_path = os.path.join(os.path.expanduser(pytan_loc), 'lib')

# Determine our script name, script dir
my_file = os.path.abspath(sys.argv[0])
my_dir = os.path.dirname(my_file)

# try to automatically determine the pytan lib directory by assuming it is in '../../lib/'
parent_dir = os.path.dirname(my_dir)
pytan_root_dir = os.path.dirname(parent_dir)
lib_dir = os.path.join(pytan_root_dir, 'lib')

# add pytan_loc and lib_dir to the PYTHONPATH variable
path_adds = [lib_dir, pytan_static_path]
[sys.path.append(aa) for aa in path_adds if aa not in sys.path]

# import pytan
import pytan

# create a dictionary of arguments for the pytan handler
handler_args = {}

# establish our connection info for the Tanium Server
handler_args['username'] = "Administrator"
handler_args['password'] = "Tanium2015!"
handler_args['host'] = "10.0.1.240"
handler_args['port'] = "443"  # optional

# optional, level 0 is no output except warnings/errors
# level 1 through 12 are more and more verbose
handler_args['loglevel'] = 1

# optional, use a debug format for the logging output (uses two lines per log entry)
handler_args['debugformat'] = False

# optional, this saves all response objects to handler.session.ALL_REQUESTS_RESPONSES
# very useful for capturing the full exchange of XML requests and responses
handler_args['record_all_requests'] = True

# instantiate a handler using all of the arguments in the handler_args dictionary
print "...CALLING: pytan.handler() with args: {}".format(handler_args)
handler = pytan.Handler(**handler_args)

# print out the handler string
print "...OUTPUT: handler string: {}".format(handler)

# setup the arguments for the handler.delete() method
delete_kwargs = {}
delete_kwargs["objtype"] = u'group'
delete_kwargs["name"] = u'All Windows Computers API Test'

# setup the arguments for the handler() class
kwargs = {}
kwargs["groupname"] = u'All Windows Computers API Test'
kwargs["filters"] = [u'Operating System, that contains:Windows']
kwargs["filter_options"] = [u'and']

# delete the object in case it already exists
# catch and print the exception error if it does not exist
print "...CALLING: handler.delete() with args: {}".format(delete_kwargs)
try:
    handler.delete(**delete_kwargs)
except Exception as e:
    print "...EXCEPTION: {}".format(e)

print "...CALLING: handler.create_group() with args: {}".format(kwargs)
response = handler.create_group(**kwargs)

print "...OUTPUT: Type of response: ", type(response)
print "...OUTPUT: print of response:"
print response

# call the export_obj() method to convert response to JSON and store it in out
export_kwargs = {}
export_kwargs['obj'] = response
export_kwargs['export_format'] = 'json'
print "...CALLING: handler.export_obj() with args {}".format(export_kwargs)
out = handler.export_obj(**export_kwargs)

# trim the output if it is more than 15 lines long
if len(out.splitlines()) > 15:
    out = out.splitlines()[0:15]
    out.append('..trimmed for brevity..')
    out = '\n'.join(out)

print "...OUTPUT: print the objects returned in JSON format:"
print out

# delete the object, we are done with it now
print "...CALLING: handler.delete() with args: {}".format(delete_kwargs)
delete_response = handler.delete(**delete_kwargs)

print "...OUTPUT: print the delete response"
print delete_response

'''STDOUT from running this:
...CALLING: pytan.handler() with args: {'username': 'Administrator', 'record_all_requests': True, 'loglevel': 1, 'debugformat': False, 'host': '10.0.1.240', 'password': 'Tanium2015!', 'port': '443'}
...OUTPUT: handler string: PyTan v2.1.0 Handler for Session to 10.0.1.240:443, Authenticated: True, Platform Version: 6.5.314.4301
...CALLING: handler.delete() with args: {'objtype': u'group', 'name': u'All Windows Computers API Test'}
...EXCEPTION: No results found searching for Group, name: u'All Windows Computers API Test' (error: Response command GroupNotFound does not match request command GetObject)!!
...CALLING: handler.create_group() with args: {'groupname': u'All Windows Computers API Test', 'filters': [u'Operating System, that contains:Windows'], 'filter_options': [u'and']}
...OUTPUT: Type of response:  <class 'taniumpy.object_types.group.Group'>
...OUTPUT: print of response:
Group, name: 'All Windows Computers API Test', id: 3613
...CALLING: handler.export_obj() with args {'export_format': 'json', 'obj': <taniumpy.object_types.group.Group object at 0x10240a850>}
...OUTPUT: print the objects returned in JSON format:
{
  "_type": "group", 
  "and_flag": 1, 
  "deleted_flag": 0, 
  "filters": {
    "_type": "filters", 
    "filter": [
      {
        "_type": "filter", 
        "all_times_flag": 0, 
        "all_values_flag": 0, 
        "delimiter_index": 0, 
        "ignore_case_flag": 1, 
        "max_age_seconds": 0, 
        "not_flag": 0, 
..trimmed for brevity..
...CALLING: handler.delete() with args: {'objtype': u'group', 'name': u'All Windows Computers API Test'}
...OUTPUT: print the delete response
[<taniumpy.object_types.group.Group object at 0x10240afd0>]

'''

'''STDERR from running this:

'''
