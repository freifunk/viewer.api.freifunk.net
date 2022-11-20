"""Renders API file information for all communities"""

import sys
import os
import shutil
import glob
from zipfile import ZipFile
import json
from pathlib import Path
from datetime import datetime
from copy import deepcopy
import requests
import jsonschema
from packaging import version
from jinja2 import Environment, FileSystemLoader
from jinja2.utils import urlize
import dateutil.parser

env = Environment(loader=FileSystemLoader('templates'))

def is_list(var):
    """ check if variable is a list """
    return isinstance(var, list)


def is_dict(var):
    """ check if variable is a dict """
    return isinstance(var, dict)


env.tests['dict'] = is_dict
env.tests['list'] = is_list


def gen_bbox(latlon):
    """ creates a map box for the community"""
    bbox = [latlon[1]-0.05, latlon[0]-0.01, latlon[1]+0.05, latlon[0]+0.01]
    return '%2C'.join(map(str, bbox))


def render_index(template_path, communities):
    """ renders the index page """
    template = env.get_template(template_path)
    html = template.render(communities=communities, now=datetime.now().ctime())
    return html.encode("utf-8")


def walk(node):
    """ renders key-values and lists for single communities """
    html = ""
    for key, value in node.items():
        html += f"<dt>{key.capitalize()}</dt>"
        if is_dict(value):
            html += f"<dd>{walk(value)}</dd>"
        elif is_list(value):
            for val in value:
                if is_dict(val):
                    html += f"<dd>{walk(val)}</dd>"
                else:
                    html += f"<dd>{urlize(val)}</dd>"
        else:
            html += f"<dd>{urlize(str(value))}</dd>"
    return f"<dl>{html}</dl>"

def render_community(template_path, data):
    """ renders the community's api detail page """

    try:
        data['state']['lastchange'] = dateutil.parser.parse(
            data['state']['lastchange'])
    except dateutil.parser.ParserError:
        pass
    except TypeError:
        pass
    latlon = (float(data['location']['lat']), float(data['location']['lon']))

    community, url, api, validation = data['name'], data['url'], data['api'], data['validation']
    del data['name'], data['url'], data['api'], data['validation']

    template = env.get_template(template_path)

    content = walk(data)

    html = template.render(community=community, url=url, api=api, latlon=latlon, bbox=gen_bbox(
        latlon), now=datetime.now().ctime(), validation=validation, data=content)
    return html.encode('utf-8')

def validate_community(specs, instance):
    """ Validate a single community file """
    if instance['api'] not in specs.keys():
        print(
            f"[+] Invalid or unknown API version {instance['api']}: {instance['url']}")
        return {}

    try:
        del instance["mtime"]
    except KeyError:
        pass

    try:
        del instance["etime"]
    except KeyError:
        pass

    try:
        del instance["error"]
    except KeyError:
        pass

    if instance['api'].startswith("0.5."):
        try:
            del instance['location']['lat']
            del instance['location']['lon']
            for num, _ in enumerate(instance['location']['additionalLocations']):
                del instance['location']['additionalLocations'][num]['lat']
                del instance['location']['additionalLocations'][num]['lon']
        except KeyError:
            pass

    validation = jsonschema.Draft7Validator(specs[instance['api']])
    errors = sorted(validation.iter_errors(instance), key=str)

    validation_result = {}
    if errors:
        status = "invalid"
        status_text = "Invalid"
        for error in errors:
            joined_path = "->".join(str(path) for path in error.path)
            collected_errors = f"<li>Error in {joined_path}: {error.message}</li>"
        result = f"<ul>{collected_errors}</ul"
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

def remove_temp_file(_zip, extracted, build=0):
    """ To remove the temp files generated while building """
    try:
        print("\t[*] Removing temp files....", end="")
        if build:
            shutil.rmtree(build)
        os.remove(_zip)
        shutil.rmtree(extracted)
        print("Done!!")
    except Exception as exception:
        print("\n[+] Error while removing temp files")
        raise exception


def main():
    """ our main method """
    print("[*] Started.....")

    if len(sys.argv) < 2:
        print("[+] Usage: py render.py buildDir")
        sys.exit(0)

    build_dir = sys.argv[1]
    if not os.path.isdir(build_dir):
        os.makedirs(build_dir)

    # fetching github repo for the spec files
    print("\t[*] Fetching GH repo....", end="")
    ghub_repo = requests.get(
        "https://github.com/freifunk/api.freifunk.net/archive/refs/heads/master.zip", timeout=12)
    if ghub_repo.status_code != 200:
        print("\n\t[+] Can't fetch GH repo")
        sys.exit(0)

    file_name = extract_api(ghub_repo)

    ff_api_specs = get_api_specs()

    # communities
    communities = get_communities()

    rendered = {}

    render_communities(build_dir, ff_api_specs, communities, rendered)

    print("\t[*] Rendering index page....", end="")
    index = os.path.join(build_dir, "index.html")
    with open(index, "wb") as index_file:
        index_file.write(render_index("index.html", rendered))
    print("Done!!")

    print("\t[*] Copying static files.....", end="")
    static_files = os.listdir('static')
    for file in static_files:
        src = os.path.join('static', file)
        target = os.path.join(build_dir, file)
        if os.path.isfile(src):
            shutil.copyfile(src, target)
    print("Done!!")

    remove_temp_file(file_name, "api.freifunk.net-master")
    print(f"[*] Successfully generated pages in {build_dir}")

def render_communities(build_dir, ff_api_specs, communities, rendered):
    """ renders all community files """
    print("\t[*] Rendering communities.....", end="")
    for name, data in communities.items():
        path = os.path.join(build_dir, f"{name}.html")
        data['validation'] = validate_community(ff_api_specs, deepcopy(data))
        with open(path, 'wb') as community_file:
            community_file.write(render_community("community.html", deepcopy(data)))
            rendered[name] = data
    print("Done!!")

def get_communities():
    """ load all community data """
    print("\t[*] Loading Communities files........", end="")
    summ_file = requests.get(
        "https://api.freifunk.net/data/ffSummarizedDir.json", timeout=10)
    if summ_file.status_code != 200:
        print("\n\t[+] Can't fetch ffSummarizedDir file")
        sys.exit(0)
    communities = json.loads(summ_file.content)
    print("Done!!")
    return communities

def get_api_specs():
    """ open all api specifications """
    print("\t[*] Loading Specs......", end="")
    ff_api_specs = {}
    spec_dir = "./api.freifunk.net-master/specs/*.json"
    spec_files = glob.glob(spec_dir)
    for file in spec_files:
        with open(file, "r", encoding="utf8") as file_content:
            ff_api_specs[Path(file).stem] = json.loads(file_content.read())
    print("Done!!")
    return ff_api_specs

def extract_api(ghub_repo):
    """ Open API repository downloaded from github """
    file_name = os.path.join(os.getcwd(), "api_freifunk.zip")
    with open(file_name, "wb") as api_file:
        api_file.write(ghub_repo.content)
        print("Done!!")

    print("\t[*] Extracting files......", end="")
    with ZipFile(file_name, 'r') as repo:
        repo.extractall()
        print("Done!!")
    return file_name


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print("\n[+] Encountered Errors")
        remove_temp_file("api_freifunk.zip",
                       "api.freifunk.net-master", sys.argv[1])
        raise e
