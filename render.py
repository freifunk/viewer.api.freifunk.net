# -*- coding: utf-8 -*-

import os
import json
import shutil
import sys

from jinja2 import Environment, FileSystemLoader
from urllib2 import urlopen
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

  template = env.get_template(template_path)
  html = template.render(
            community=community,
            url=url,
            latlon=latlon,
            bbox=gen_bbox(latlon),
            now=datetime.now().ctime(),
            data=data)

  return html.encode('utf-8')


def render_index(template_path, communities):
  template = env.get_template(template_path)
  html = template.render(
    communities=communities,
    now=datetime.now().ctime()
  )

  return html.encode('utf-8')


if __name__ == "__main__":
  build_dir = 'build'

  if len(sys.argv) > 1:
    build_dir = sys.argv[1]

  if not os.path.isdir(build_dir):
    os.makedirs(build_dir)

  # communities
  url = 'http://weimarnetz.de/ffmap/ffSummarizedDir.json'
  req = urlopen(url)
  communities = json.load(req)
  entries = {}
  rendered = {}

  print("Rendering communities")
  for name, data in communities.items():
    print("\t* %s...\t" % name),
    path = os.path.join(build_dir, '%s.html' % name)
    try:
      with open(path,'w') as f:
        f.write(render_community('community.html', data.copy()))
        rendered[name] = data
        print("ok")
    except:
        print("error")

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
      path = os.path.join('static', name)
      if (os.path.isfile(path)):
        shutil.copyfile(path, os.path.join(build_dir, name))
        print("\t* %s" % path)
