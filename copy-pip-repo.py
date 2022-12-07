# -*- coding: utf-8 -*-

"""
Create and clone repo in Nexus:
    python3 copy-pip-repo.py -m create -s production -d production-hotfix-1234 --fqdn nexus.company.com
Remove repository:
    python3 copy-pip-repo.py -m delete -d production-hotfix-1234 --fqdn nexus.company.com
"""


import requests
import json
import sys
import argparse
import os
import pprint
import time
import tempfile

parser = argparse.ArgumentParser(
                    prog = sys.argv[0],
                    description = 'Tool for clone pypi repos in nexus',
                    epilog = '')

auth_req = True
if os.getenv('NEXUS_USER', False):
    auth_req = False

parser.add_argument('-m', '--make', required=True, help='Specify what are you want do, delete or create repo, for example: create')
parser.add_argument('-s', '--source', help='Specify source repo name, for example: production')
parser.add_argument('-d', '--dest', required=True, help='Specify name of destination repo, for example: production-hotfix-1234')
parser.add_argument('-u', '--user', required=auth_req, help='Nexus login (or set NEXUS_USER enviroment var)')
parser.add_argument('-p', '--password', required=auth_req, help='Nexus password (or set NEXUS_PASSWORD enviroment var)')
parser.add_argument('-f', '--fqdn', required=auth_req, help='Nexus fqdn e.g. nexus.example.com')

args = parser.parse_args()

nex_user = os.getenv('NEXUS_USER', args.user)
nex_pass = os.getenv('NEXUS_PASSWORD', args.password)

def get_last_packages_urls_in_repo(repository=''):
    assets = {}
    downloads = {}
    url = "https://{}/service/rest/v1/components?repository={}".format(args.fqdn, repository)
    req = requests.get(url, auth=(nex_user, nex_pass))
    # pprint.pprint(json.loads(req.text)
    print("Getting infromation about last versions of packages, please wait...")
    while True:
        # pprint.pprint(json.loads(req.text)['downloadUrl'])
        for component in json.loads(req.text)["items"]:
            for asset in component["assets"]:
                if "pypi" in asset:
                    if not asset["pypi"]["name"] in assets:
                        assets[asset["pypi"]["name"]] = asset["pypi"]["version"]
                        downloads[asset["pypi"]["name"]] = asset["downloadUrl"]
                    elif int(assets[asset["pypi"]["name"]].split('.')[-1]) < int(asset["pypi"]["version"].split('.')[-1]):
                        assets[asset["pypi"]["name"]] = asset["pypi"]["version"]
                        downloads[asset["pypi"]["name"]] = asset["downloadUrl"]
                else:
                    pprint.pprint(asset)
        if not json.loads(req.text)["continuationToken"]:
            break
        req = requests.get('{}&continuationToken={}'.format(url, json.loads(req.text)["continuationToken"]), auth=(nex_user, nex_pass))
    return downloads

def download_package(pkg_url):
    req = requests.get(pkg_url, auth=(nex_user, nex_pass))
    file_save_path = os.path.join(tempfile.gettempdir(), pkg_url.split("/")[-1])
    with open(file_save_path, 'wb') as f:
        f.write(req.content)
    return file_save_path

def download_packages_with_threads(downloads):
    result = []
    for pkg_name, pkg_url in downloads.items():
        result.append(download_package(pkg_url))
        print("pkg {} downloaded".format(result[-1]))
    return result

def upload_package(file_path, repository=''):
    file = { 'pypi.asset': open(file_path, 'rb') }
    req = requests.post('https://{}/service/rest/v1/components?repository={}'.format(args.fqdn, repository),
                        files=file, auth=(nex_user, nex_pass))
    print("uploaded: {}".format(file_path))
    return req.status_code

def copy_download_packages_and_upload_to_repo(downloads, repository=''):
    file_paths = download_packages_with_threads(downloads)
    for file_path in file_paths:
        status_code = upload_package(file_path, repository)
        if status_code == 400:
            print("package already uploaded")
        elif status_code == 204:
            print("package uploaded succesfull")
        elif status_code == 500:
            print("It's can be BUG https://issues.sonatype.org/browse/NEXUS-31674, status: {}".format(status_code))
        else:
            print("upload: {}".format(status_code))
    return

def delete_repository(repository):
    req = requests.delete('https://{}/service/rest/v1/repositories/{}'.format(repository), auth=(args.fqdn, nex_user, nex_pass))

    if req.status_code == 404:
        print("Repository {} not found, status: {}".format(repository, req.status_code))
    elif req.status_code == 204:
        print("Repository {} deleted, status: {}".format(repository, req.status_code))
    elif req.status_code == 401:
        print("Can't delete repository {}. Autentification required, status: {}".format(repository, req.status_code))
    elif req.status_code == 403:
        print("Can't delete repository {}. User {} haven't permissions, status: {}".format(repository, nex_user, req.status_code))
    elif req.status_code == 500:
        print("It's can be BUG https://issues.sonatype.org/browse/NEXUS-31674, status: {}".format(req.status_code))
    else:
        print("Unhandled error with status: {}".format(req.status_code))
    return req.status_code

def create_repo(repository):
    data = { 'name': repository,
             'online': True,
             'storage': {
                'blobStoreName': 'default',
                'strictContentTypeValidation': True,
                'writePolicy': 'allow'
             },
             'cleanup': {
                 'policyNames': [
                     'string'
                 ]
             },
             'component': {
                 'proprietaryComponents': True
             }
            }

    req = requests.post('https://{}/service/rest/v1/repositories/pypi/hosted'.format(args.fqdn), data=json.dumps(data), headers={"Content-Type": "application/json"}, auth=(nex_user, nex_pass))
    if req.status_code == 415:
        print("repository {} already exist".format(repository))
    elif req.status_code == 201:
        print("repository {} created".format(repository))
    return req.status_code

if __name__ == '__main__':
    protected_repos = [
    ]
    if args.make == "create":
        if args.source:
            source_repo = args.source
        else:
            source_repo = 'production'
        try:
            create_repo(repository=args.dest)
            downloads = get_last_packages_urls_in_repo(repository=source_repo)
            copy_download_packages_and_upload_to_repo(downloads, repository=args.dest)
        except KeyboardInterrupt:
            exit(1)
    elif args.make == "delete":
        if not args.dest in protected_repos:
            delete_repository(repository=args.dest)
    exit(0)
