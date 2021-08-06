import sys
import os
import shutil
import glob
import requests
import time
from zipfile import ZipFile
import glob
import json
from pathlib import Path
import jsonschema
from packaging import version
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from jinja2.utils import urlize
import dateutil.parser

env = Environment(loader=FileSystemLoader('templates'))

def is_list(var):
  return type(var) is dict

def is_dict(var):
  return type(var) is list

env.tests['dict'] = is_dict
env.tests['list'] = is_list

def gen_bbox(latlon):
  bbox = [latlon[1]-0.05,latlon[0]-0.01,latlon[1]+0.05,latlon[0]+0.01]
  return '%2C'.join(map(str,bbox))

def render_index(template_path, communities):
  template = env.get_template(template_path)
  html = template.render(communities=communities, now = datetime.now().ctime())
  return html.encode("utf-8")

def walk(node):
  html = ""
  for key, value in node.items():
    html += "<dt>{}</dt>".format(key.capitalize())
    if type(value) is dict:
      html += "<dd>{}</dd>".format(walk(value))
    elif type(value) is list:
      for val in value:
        if type(val) is dict:
          html += "<dd>{}</dd>".format(walk(val))
        else:
          html += "<dd>{}</dd>".format(urlize(val))
    else:
      html += "<dd>{}</dd>".format(urlize(str(value)))
  return "<dl>{}</dl>".format(html)



def render_community(template_path, data):
  
  # d = datetime.fromtimestamp(float(data['state']['lastchange']))
  try:
    data['state']['lastchange'] = dateutil.parser.parse(data['state']['lastchange'], tzinfos=tzoffset(None, 18000)) 
  except:
    pass
  latlon = (float(data['location']['lat']),float(data['location']['lon']))

  community, url, api, validation = data['name'], data['url'], data['api'], data['validation']
  del data['name'], data['url'], data['api'], data['validation']

  template = env.get_template(template_path)

  content = walk(data)

  html = template.render(community = community, url = url, api = api, latlon = latlon, bbox=gen_bbox(latlon), now = datetime.now().ctime(), validation = validation, data = content)
  return html.encode('utf-8')





def validate_community(specs, instance):
  if instance['api'] not in specs.keys():
    print("[+] Invalid or unknown API version {}: {}".format(instance['api'], instance['url']))
    return

  try:
    del instance["mtime"]
  except Exception as e:
    pass

  validation = jsonschema.Draft7Validator(specs[instance['api']])
  errors = sorted(validation.iter_errors(instance), key = str)

  validation_result = {}
  if errors:
    status = "invalid"
    status_text = "Invalid"
    result = "<ul>{}</ul".format(''.join("<li>Error in {}: {}</li>".format("->".join(str(path) for path in err.path), err.message) for err in errors))
  elif version.parse(instance['api']) < version.parse("0.4.0"):
    status = "warning"
    status_text = "Warning"
    result = "API version too old! You should upgrade your file"
  else:
    status = "valid"
    status_text = "Valid"
    result = ""

  validation_result["status"] = status
  validation_result["status_text"] = status_text
  validation_result["result"] = result

  return validation_result


##To remove the temp files generated while building
def removeTempFile(_zip, extracted, build = 0):
  try:
    print("\t[*] Removing temp files....", end = "")
    if build:
      shutil.rmtree(build)
    os.remove(_zip)
    shutil.rmtree(extracted)
    print("Done!!")
  except Exception as e:
    print("\n[+] Error while removing temp files")
    raise e


def main():
  print("[*] Started.....")

  if len(sys.argv) < 2:
    print("[+] Usage: py render.py buildDir")
    sys.exit(0)


  build_dir = sys.argv[1]
  if not os.path.isdir(build_dir):
    os.makedirs(build_dir)


  #fetching github repo for the spec files
  print("\t[*] Fetching GH repo....", end = "")
  ghub_repo = requests.get("https://github.com/freifunk/api.freifunk.net/archive/refs/heads/master.zip")
  if ghub_repo.status_code != 200:
    print("\n\t[+] Can't fetch GH repo")
    sys.exit(0)

  file_name = os.path.join(os.getcwd(), "api_freifunk.zip")
  with open(file_name, "wb") as f:
    f.write(ghub_repo.content)
    print("Done!!")

  print("\t[*] Extracting files......", end = "")
  with ZipFile(file_name, 'r') as repo:
    repo.extractall()
    print("Done!!")


    # api specs
  print("\t[*] Loading Specs......", end = "")
  ff_api_specs = {}
  spec_dir = "./api.freifunk.net-master/specs/*.json"
  spec_files = glob.glob(spec_dir)
  for file in spec_files:
    file_content = open(file).read()
    ff_api_specs[Path(file).stem] = json.loads(file_content)
  print("Done!!")
    
    # communities
  print("\t[*] Loading Communities files........", end = "")
  summ_file = requests.get("https://api.freifunk.net/data/ffSummarizedDir.json")
  if summ_file.status_code != 200:
    print("\n\t[+] Can't fetch ffSummarizedDir file")
    sys.exit(0)
  communities = json.loads(summ_file.content)
  print("Done!!")


  entries = {}
  rendered = {}

  print("\t[*] Rendering communities.....", end = "")
  for name, data in communities.items():
    path = os.path.join(build_dir, "{}.html".format(name))
    data['validation'] = validate_community(ff_api_specs,data)
    with open(path, 'wb') as f: 
      f.write(render_community("community.html", data.copy()))
      rendered[name] = data
  print("Done!!")
  
  print("\t[*] Rendering index page....", end = "")
  index = os.path.join(build_dir, "index.html")
  with open(index, "wb") as f:
    f.write(render_index("index.html", rendered))
  print("Done!!")

  print("\t[*] Copying static files.....", end = "")
  static_files = os.listdir('static')
  for file in static_files:
    src = os.path.join('static', file)
    target = os.path.join(build_dir, file)
    if (os.path.isfile(src)):
      shutil.copyfile(src, target)
  print("Done!!")

  removeTempFile(file_name, "api.freifunk.net-master")
  print("[*] Successfully generated pages in {}".format(build_dir))

if __name__ == '__main__':
  try:
    main()
  except Exception as e:
    print("\n[+] Encountered Errors")
    removeTempFile("api_freifunk.zip", "api.freifunk.net-master", sys.argv[1])
    raise e