# -*- coding: utf-8 -*-

import os
import glob
import json
import shutil
import sys
import urllib2
import jsonschema
from distutils2.version import NormalizedVersion
from jinja2 import Environment, FileSystemLoader
from jinja2.utils import urlize
from datetime import datetime

def is_dict(value):
    return isinstance(value, dict)


def is_list(value):
    return isinstance(value, list)


env = Environment(loader=FileSystemLoader('templates'))
env.tests['dict'] = is_dict
env.tests['list'] = is_list


def gen_bbox(latlon):
    bbox = [latlon[1]-0.05,latlon[0]-0.01,latlon[1]+0.05,latlon[0]+0.01]
    return '%2C'.join(map(str,bbox))


def render_community(template_path, data):
  # extract community name
  try:
    community = data['name']
    del data['name']
  except:
    pass

  # extract url
  try:
    url = data['url']
    del data['url']
  except:
    pass

  # convert timestamp into human readable date form
  try:
    d = datetime.fromtimestamp(float(data['state']['lastchange']))
    data['state']['lastchange'] = d.ctime()
  except:
    pass

  latlon = (float(data['location']['lat']),float(data['location']['lon']))

  validation = data['validation']
  del data['validation']

  api = data['api']

  template = env.get_template(template_path)

  content = walk(data)

  html = template.render(community=community, url=url, latlon=latlon, bbox=gen_bbox(latlon), now=datetime.now().ctime(), validation=validation, api=api, data=content)

  return html.encode('utf-8')

def validate_community(specs, instance):
  validation_result = {}
  status_text = ''
  status = ''
  text_result = ''
  try:
    validator = jsonschema.validators.validator_for(specs[instance['api']]['schema']) 
    validator.check_schema(specs[instance['api']]['schema'])
    v = validator(specs[instance['api']]['schema'])
    result = v.iter_errors(instance)
    has_error = False
    for error in sorted(result,key=str):
      if not has_error:
        text_result = '<ul>'
      has_error = True
      text_result = '%s<li>Error in %s: %s</li>' % (text_result, '->'.join(str(path) for path in error.path), error.message)

    if has_error:
      text_result = '%s</ul>' % (text_result)
      status = 'invalid'
      status_text = 'Invalid'
    elif NormalizedVersion(instance['api']) < NormalizedVersion('0.4.0'):
      status = 'warning'
      status_text = 'Warning'
      text_result = 'API version too old! You should upgrade your file'
    # TODO: Check lastchange date
    #elif instance['lastchange']:
    #  status = 'warning'
    #  status_text = 'Warning'
    #  text_result = 'No Update on API file for more than 2 month!'
    else:
      status = 'valid'
      status_text = 'Valid'

    validation_result['status_text'] = status_text
    validation_result['status'] = status
    validation_result['result'] = text_result
    return validation_result

  except KeyError as e:
    print('Invalid or unknown API version %s: %s' % (api_content['api'], url))

def render_index(template_path, communities):
  template = env.get_template(template_path)
  html = template.render(
    communities=communities,
    now=datetime.now().ctime()
  )

  return html.encode('utf-8')

def walk(node):
	html="<dl>"
	for key, item in node.items():
		html+="<dt>" + key.capitalize() + "</dt>"
		if is_dict(item):
			html+="<dd>" + walk(item) + "</dd>"
		elif is_list(item):
			for element in item:
				if is_dict(element):
					html+="<dd>" + walk(element) + "</dd>"
				else:
					html+="<dd>" + urlize(element) + "</dd>"
		else:
			if type(item) is int or type(item) is float:
				item = str(item)
			html+="<dd>" + urlize(item) + "</dd>"
	return html + "</dl>"


if __name__ == "__main__":
  build_dir = 'build'

  if len(sys.argv) > 1:
    build_dir = sys.argv[1]

  if not os.path.isdir(build_dir):
    os.makedirs(build_dir)

  # api specs
  ff_api_specs = {}
  spec_dir = './api.freifunk.net/specs/*.json'
  spec_files = glob.glob(spec_dir)
  for spec_file in spec_files:
      spec_content = open(spec_file).read()
      ff_api_specs[os.path.splitext(os.path.basename(spec_file))[0]] = json.loads(spec_content)

  # communities
  try:
    url = 'http://freifunk.net/map/ffSummarizedDir.json'
    req = urllib2.urlopen(url)
    communities = json.load(req)
  except urllib2.HTTPError:
    sys.stderr.write("Error: JSON file could not be found (404)")
  except:
    sys.stderr.write("Invalid JSON file in %s" % url)
    raise SystemExit


  entries = {}
  rendered = {}

  print("Rendering communities")
  for name, data in communities.items():
		print("\t* %s...\t" % name)
		path = os.path.join(build_dir, '%s.html' % name)
		try:
			with open(path,'w') as f:
                                data['validation'] = validate_community(ff_api_specs, data) 
				f.write(render_community('community.html', data.copy()))
				rendered[name] = data
				print("ok")
		except Exception as e:
			print("error: ", str(e), data)

  # index
  print("\nRendering index page...\t"),
  try:
    index_path = os.path.join(build_dir, 'index.html')
    with open(index_path,'w') as f:
      f.write(render_index('index.html', rendered))
      print(index_path)
  except:
    print("error")

  # style
  print("\nCopying static files...")
  static_files = os.listdir('static')
  for name in static_files:
      src = os.path.join('static', name)
      target = os.path.join(build_dir, name)
      if (os.path.isfile(src)):
        shutil.copyfile(src, target)
        print("\t* %s" % target)

  print("\nSuccessfully generated pages in: %s/" % build_dir)
