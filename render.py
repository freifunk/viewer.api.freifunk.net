# -*- coding: utf-8 -*-

import os
import json

from jinja2 import Environment, FileSystemLoader
from urllib2 import urlopen

def is_dict(value):
    return isinstance(value, dict)


env = Environment(loader=FileSystemLoader('templates'))
env.tests['dict'] = is_dict


def gen_bbox(latlon):
    bbox = [latlon[1]-0.05,latlon[0]-0.01,latlon[1]+0.05,latlon[0]+0.01]
    return '%2C'.join(map(str,bbox))


def render_community(template_path, url):
  req = urlopen(url)
  data = json.load(req)

  if 'name' in data:
    community = data['name']
    del data['name']

  if 'url' in data:
    url = data['url']
    del data['url']

  latlon = (float(data['location']['lat']),float(data['location']['lon']))

  template = env.get_template(template_path)
  html = template.render(
            community=community,
            url=url,
            latlon=latlon,
            bbox=gen_bbox(latlon),
            data=data)

  return html.encode('utf-8')


def render_index(template_path, communities):
  template = env.get_template(template_path)
  html = template.render(communities=communities)

  return html.encode('utf-8')


if __name__ == "__main__":
  url = 'https://raw.github.com/freifunk/api.freifunk.net/master/directory/directory.json'
  req = urlopen(url)
  communities = json.load(req)
  rendered = []

  for name, url in communities.items():
    print("Rendering %s...\t" % name),
    path = os.path.join('build', '%s.html' % name)
    try:
      with open(path,'w') as f:
        f.write(render_community('community.html', url))
        rendered.append(name)
        print("ok")
    except:
        print("error")

  with open('build/index.html','w') as f:
    f.write(render_index('index.html', sorted(rendered)))

