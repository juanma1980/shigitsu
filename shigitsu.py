#!/usr/bin/python3
import urllib
from urllib.request import Request
from urllib.request import urlretrieve
import os
import sys
import tempfile
import shutil
import subprocess
from bs4 import BeautifulSoup
import git
from git import Repo
from collections import OrderedDict
import gettext
gettext.textdomain('sync_to_svn')
_=gettext.gettext

def _debug(msg):
	if dbg:
		print("%s"%msg)

def _get_git_repo(repo,repo_name):
	dest_path="/tmp/%s"%repo_name
	_debug("Cloning %s in %s"%(repo,dest_path))
	try:
		git.Repo.clone_from(repo,dest_path)
	except Exception as e:
		dest_path=""
		print(e)
	return dest_path
#def _get_git_repo

def _check_repo_consistency(repo_path):
	repo=Repo(repo_path)
	sw_ok=True
	#Change to debian/bionic
	try:
		repo.git.checkout('debian/xenial')
	except Exception as e:
		_debug(e)
		sw_ok=False
	#Merge with master
	if sw_ok:
		repo.git.merge("master")
	return sw_ok

def _sync_commits_with_svn(repo_path):
	repo=Repo(repo_path)
	commits=repo.git.rev_list("--first-parent","--pretty","master","debian/xenial")
	commits_array=commits.split('\n')
	commits_dict=OrderedDict()
	msg=''
	commit=''
	author=''
	date=''
	for data in commits_array:
		if data.startswith('Merge'):
			pass
		elif data.startswith('commit'):
			if commit:
				commits_dict.update({commit:{'author':author,'date':date,'msg':msg}})
				msg=''
				commit=''
				author=''
				date=''
			commit=data
		elif data.startswith('Author'):
			author=data
		elif data.startswith('Date'):
			date=data
		elif data=='':
			continue
		else:
			msg+="%s "%data.strip()
	print (commits_dict)

def _askpass():
	pass
#def _askpass

def _generate_svn_structure():
	pass
#def _generate_svn_structure

def _list_repos(repo_url):
	dest_path='/tmp/tmpfile'
	try:
		req=Request(repo_url, headers={'User-Agent':'Mozilla/5.0'})
		with urllib.request.urlopen(req) as f:
			content=(f.read().decode('utf-8'))
		soup=BeautifulSoup(content,"html.parser")
		available_repos=soup.findAll('a', attrs={ "itemprop" : "name codeRepository"})
		print("Available repos at %s"%git_repo)
		repo_names=[]
		for repo in available_repos:
			repo_name=''.join(repo['href'].split('/')[2:])
			repo_names.append(repo_name)
		available_repos=sorted(repo_names,key=str.lower)

	except Exception as e:
		print(e)
	return available_repos
#def _list_repos


#### MAIN PROGRAM ####
dbg=True
conf_file="./sync.conf"
delete_when_processed=0
sync_path='/tmp'
single_commit=0
svn_repo=''
#git_repo="https://github.com/juanma1980"
git_repo=""
#read config
with open(conf_file) as f:
	data=f.readlines()
for line in data:
	if line.startswith("sync_path"):
		sync_path=line.split('=')[-1].rstrip("\r\n").strip("\"")
	if line.startswith("delete_when_processed"):
		delete_when_processed=line.split('=')[-1].rstrip("\r\n").strip("\"")
	if line.startswith("single_commit"):
		single_commit=line.split('=')[-1].rstrip("\r\n").strip("\"")
	if line.startswith("git_repo"):
		git_repo=line.split('=')[-1].rstrip("\r\n").strip("\"")
	if line.startswith("svn_repo"):
		svn_repo=line.split('=')[-1].rstrip("\r\n").strip("\"")
git_server='/'.join(git_repo.split('/')[0:-1])

user_input=input(_("Insert the origin git repo [%s]: ")%git_repo)
if user_input:
	git_repo=user_input

available_repos=_list_repos("%s?tab=repositories"%git_repo)
first=''
for repo in available_repos:
	if repo[0:1].lower()!=first.lower():
		first=repo[0:1].lower()
		print("[%s]"%first)
	print ("%s"%(repo))
input_repos_to_update=input(_('Enter a repo name, letter index or "*" for all: '))
repos_to_update=[]
if input_repos_to_update in available_repos:
	repos_to_update.append(input_repos_to_update)
elif input_repos_to_update=='*':
	repos_to_update=available_repos
else:
	sw_match=False
	for repo in available_repos:
		if repo.startswith(input_repos_to_update):
			repos_to_update.append(repo)
			sw_match=True
		elif sw_match:
			break
input_user=input (_("We're going to sync these repos:\n%s\nProceed? y/n [n]: ")%repos_to_update)
if input_user.lower()=='y':
	for repo in repos_to_update:
		repo_path="%s/%s"%(git_repo,repo)
		if not repo_path.endswith('.git'):
			repo_path="%s.git"%repo_path
		local_git_repo=_get_git_repo(repo_path,repo)
		if _check_repo_consistency(local_git_repo):
			_sync_commits_with_svn(local_git_repo)
		else:
			print("Repo %s couldn't be added"%repo)
