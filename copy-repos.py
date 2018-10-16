#!/usr/bin/env python
""" Print all of the clone-urls for a GitHub organization.
It requires the pygithub3 module, which you can install like this::
    $ sudo yum -y install python-virtualenv
    $ mkdir scratch


    $ cd scratch
    $ virtualenv my-virtualenv
    $ source my-virtualenv/bin/activate
    $ pip install pygithub3
Usage example::
    $ python list-all-repos.py
Advanced usage.  This will actually clone all the repos for a
GitHub organization or user::
    $ for url in $(python list-all-repos.py); do git clone $url; done
"""

import os
import sys
import subprocess
import pygithub3
import argparse
import re

gh = None
git_dest_token = None
git_dest_url = None
git_dest_url_api = None
git_dest_org = None
git_source_url = None
git_source_username = None
git_source_password = None
git_source_org = None

filter_org_name = None

results = {
    'duration': None,
    'repos': {}
}


class StoreNameValuePair(argparse.Action):
  def __call__(self, parser, namespace, values, option_string=None):
    n, v = values.split('=')
    setattr(namespace, n, v)


def gather_clone_urls(organization, no_forks=True):
  # all_repos = gh.repos.list(user=organization).all()
  print("Listing Github organization: " + organization)
  all_repos = gh.repos.list_by_org(organization, type='all').all()
  for repo in all_repos:

    # Don't print the urls for repos that are forks.
    if no_forks and repo.fork:
      continue

    yield repo


def push_repo(repo):
  print "Pushing commit history for repo: " + repo.name
  global git_dest_url
  global git_dest_org

  base_path = os.path.abspath(os.path.join('repos', repo.owner.login))
  repo_path = os.path.join(base_path, repo.name)
  print "Changing remote.origin.url to " + git_dest_url
  change_server_cmd = "git config --replace-all remote.origin.url git@%s:%s/%s.git" % (git_dest_url, git_dest_org, repo.name)
  print "cmd: " + change_server_cmd
  try:
    p = None
    p = subprocess.Popen(change_server_cmd, shell=True, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # block for the output, should be multi-threaded
    out, err = p.communicate()

  except subprocess.CalledProcessError as e:
    # add an error for the exception
    print e
  except Exception, err:
    print err

  push_changes_cmd = "git push --force"
  try:
    p = None
    p = subprocess.Popen(push_changes_cmd, shell=True, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # block for the output, should be multi-threaded
    out, err = p.communicate()

  except subprocess.CalledProcessError as e:
    # add an error for the exception
    print e
  except Exception, err:
    print err


def create_repo(repo):
  global git_dest_url_api
  global git_dest_token
  global git_dest_org
  base_path = os.path.abspath(os.path.join('repos', repo.owner.login))
  repo_exists_api_url = "%s/repos/%s/%s" % (git_dest_url_api, git_dest_org, repo.name)
  repo_exists_query = "curl -X GET -k -H 'Authorization: bearer %s' -I '%s'" % (git_dest_token, repo_exists_api_url)

  # print "REPO API call: %s" % repo_exists_query
  out = None
  try:
    p = None
    p = subprocess.Popen(repo_exists_query, shell=True, cwd=base_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # block for the output, should be multi-threaded
    out, err = p.communicate()

  except subprocess.CalledProcessError as e:
    # add an error for the exception
    print e
  except Exception, err:
    print err

  # print "Queried to see if " + repo.name + " exists. Answer is: " + out
  if (out.find('HTTP/1.1 200 OK') == -1):
    print "No existing repo found! Creating new"
    create_json = "{ \"name\": \"%s\",\n \"description\": \"An app responsible for copying Github repos to our Evry Enterprise installation, created this repo. Code by your friendly nerd kjella\",\n \"homepage\": \"https://git.evry.cloud\",\n \"private\": true,\n \"has_issues\": true,\n \"has_projects\": false,\n \"has_wiki\": false }" % repo.name
    cmd = "curl -X POST -k -H 'Authorization: bearer %s' -i '%s/orgs/%s/repos' --data '%s'" % (git_dest_token, git_dest_url_api, git_dest_org, create_json)

    try:
      p = None
      p = subprocess.Popen(cmd, shell=True, cwd=base_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      # block for the output, should be multi-threaded
      out, err = p.communicate()

    except subprocess.CalledProcessError, e:
      # add an error for the exception
      return False
      print e
    except Exception, err:
      return False
      print err

    return True
  else:
    print "Repo with name '%s' already exists! Skipping..." % repo.name
    return False


def clone_repo(repo):
  base_path = os.path.abspath(os.path.join('repos', repo.owner.login))
  repo_path = os.path.join(base_path, repo.name)

  # set a repository name that accounts for forks
  repo_name = "%s/%s" % (repo.owner.login, repo.name)

  results['repos'][repo_name] = {}
  # create the base folders if needed
  if (not os.path.exists(base_path)):
    os.makedirs(base_path)

  try:
    p = None
    # check if the repository has already been cloned
    if (os.path.exists(repo_path)):
      # already have that repository, so do a pull
      cmd = "%s %s" % ('/usr/bin/git', 'pull')
      p = subprocess.Popen(cmd, shell=True, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
      # "new" repository, so do a clone
      cmd = "%s %s %s %s" % ('/usr/bin/git', 'clone', repo.ssh_url, repo.name)
      p = subprocess.Popen(cmd, shell=True, cwd=base_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # block for the output, should be multi-threaded
    out, err = p.communicate()

    # add the output to results
    results['repos'][repo_name]['path'] = repo_path

    if (len(out.strip()) > 0):
      results['repos'][repo_name]['out'] = out.strip().split('\n')

    if (len(err.strip()) > 0):
      results['repos'][repo_name]['err'] = err.strip().split('\n')

  except subprocess.CalledProcessError as e:
    # add an error for the exception
    results['repos'][repo_name]['path'] = repo_path
    results['repos'][repo_name]['err'] = e.output
  except Exception as err:
    results['repossub'][repo_name]['path'] = repo_path
    results['repos'][repo_name]['err'] = 'Unexpected exception: %s' % (str(err))

  if (create_repo(repo)):
    push_repo(repo)


def validate_variables():
  global git_dest_token
  global git_dest_url
  global git_dest_url_api
  global git_dest_org
  global git_source_url
  global git_source_username
  global git_source_password
  global git_source_org
  global filter_org_name

  parser = argparse.ArgumentParser()
  parser.add_argument("destination_token", help="Your token to gain access to GIT Enterprise destination repo", action=StoreNameValuePair)
  parser.add_argument("destination_url", help="The URL to GIT Enterprise. Example: git.company.com", action=StoreNameValuePair)
  parser.add_argument("destination_api", help="The URL to GIT Enterprise API. Example: https://api.git.company.com", action=StoreNameValuePair)
  parser.add_argument("destination_org", help="The name of the organization in the GIT Enterprise", action=StoreNameValuePair)

  parser.add_argument("source_url", help="The URL to the Github source", action=StoreNameValuePair)
  parser.add_argument("source_username", help="The username to access the Github source", action=StoreNameValuePair)
  parser.add_argument("source_password", help="The password to access the Github source", action=StoreNameValuePair)
  parser.add_argument("source_org", help="The organization you are copying from on Github source", action=StoreNameValuePair)
  parser.add_argument("filter_org_name", help="A very primitive name filter, backed by Reg Exp (.*[NAME].*)", action=StoreNameValuePair)
  args = parser.parse_args()

  try:
    git_dest_token = args.destination_token
    git_dest_url = args.destination_url  # ["GIT_DESTINATION_URL"] # git@git.evry.cloud:ILS
    git_dest_url_api = args.destination_api  # ["GIT_DESTINATION_API"] # https://api.git.evry.cloud/repos/ILS/
    git_dest_org = args.destination_org  # os.environ["GIT_DESTINATION_ORG"]

    git_source_url = args.source_url  # os.environ["GIT_SOURCE_URL"]

    git_source_username = args.source_username  # os.environ["GIT_SOURCE_USERNAME"]
    git_source_password = args.source_password  # os.environ["GIT_SOURCE_PASSWORD"]
    git_source_org = args.source_org  # os.environ["GIT_SOURCE_ORG"]

    filter_org_name = args.filter_org_name
  except Exception as err:
    print "An error happened when trying to load environment variable %s " % err
    print "Please ensure that the variable exists"
    sys.exit(2)


def main():
  validate_variables()
  global gh
  global filter_org_name

  gh = pygithub3.Github(login=git_source_username, password=git_source_password)
  repos = gather_clone_urls(git_source_org)

  p = re.compile(filter_org_name)

  filtered_repos = filter(lambda repo: p.match(repo.name), repos)
  for repo in filtered_repos:
    clone_repo(repo)


if __name__ == '__main__':
  main()
