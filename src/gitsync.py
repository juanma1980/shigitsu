#!/usr/bin/env python3
#Plugin for syncing
#Any plugin must implement the following public methods:
#	* set_config
#	* sync
#Any plugin must implement the following public mmembers:
#	* config dict with the config values (as in config file)
import requests
import git
from git import Repo
import svn.remote
import svn.local
from collections import OrderedDict
import gettext
import subprocess
import os,stat
import shutil
import time
import datetime
gettext.textdomain('shigitsu')
_=gettext.gettext
import sys
import re
import sqlite3
class gitsync():

	def __init__(self,*args,**kwargs):
		self.config=[]
		self.dbg=True
		self.debian_release="debian/bionic"
		self.sync_result={}
		self.commits_db="/usr/share/shigitsu/commits.sql"
		self.err=None
	#def __init__

	def _debug(self,msg):
		if self.dbg:
			print("Debug: %s"%msg)

	def set_dest_path(self,path):
		self.config.update({'dest_path':path})

	def sync(self):
		if self.config['dest_path']:
			if not os.path.isdir(self.config['dest_path']):
				os.makedirs(self.config['dest_path'])
		else:
			self._debug("Theres no dest path")
			self.sync_result.update({'ERROR':'Destination path is not set'})
			return(self.sync_result)

		self._set_db()
		repos=self._list_repos(self.config['orig_url'])
		not_whitelisted=[]
		blacklisted=[]
		inconsistent=[]
		no_master_branch=[]
		if repos:
			for repo in repos:
				repo_name=repo['clone_url'].split('/')[-1].replace('.git','')
				print("Analyzing %s"%repo_name)
				if self.config['whitelist']:
					if repo_name not in self.config['whitelist']:
						print("Not in whitelist %s"%repo_name)
						not_whitelisted.append(repo_name)
						continue
				if self.config['blacklist']:
					if repo_name in self.config['blacklist']:
						blacklisted.append(repo_name)
						print("Blacklisted %s"%repo_name)
						continue
					else:
						sw_match=False
						for bl_repo in self.config['blacklist']:
							if re.search(bl_repo,repo_name):
								blacklisted.append(repo_name)
								sw_match=True
								break
						if sw_match:
							continue
				repo_path=self._get_repo(repo['clone_url'],repo_name)
				if repo_path:
					if self._check_repo_consistency(repo_path):
						self._sync_repo(repo_path,repo_name)
					else:
						inconsistent.append({repo_name:self.err})
						print("Discard for inconsistency %s"%repo_name)
				else:
					no_master_branch.append({repo_name:self.err})
					print("Discard for no master branch %s"%repo_name)
		self.sync_result.update({'not_whitelisted':not_whitelisted})
		self.sync_result.update({'blacklisted':blacklisted})
		self.sync_result.update({'inconsistent':inconsistent})
		self.sync_result.update({'no_master_branch':no_master_branch})
		return self.sync_result

	def set_config(self,conf_dict):
		self.config=conf_dict

	def _list_repos(self,repo_url):
		repos=None
		org=self.config['orig_url'].split('/')[-1]
		cont=1
		try:
			req = requests.get("http://api.github.com/orgs/%s/repos"%org, params = {"type":"all","per_page":100})
			repos=req.json()
			while 'next' in req.links.keys():

				cont+=1
				req = requests.get("http://api.github.com/orgs/%s/repos"%org, params = {"type":"all","per_page":100,"page":cont})
				repos.extend(req.json())


		except Exception as e:
			print(e)
		return repos
	#def _list_repos

	def _get_repo(self,repo,repo_name):
		dest_path=self.config['dest_path']
		self._debug("Cloning %s in %s"%(repo,dest_path))
		if os.path.isdir(dest_path):
			repo = git.Repo(dest_path)
			try:
				repo.git.checkout("master")
				repo.remotes.origin.pull()
			except Exception as e:
				self.err=e
				dest_path=""
				print(e)
		else:
			try:
				git.Repo.clone_from(repo,dest_path)
				repo = git.Repo(dest_path)
				repo.git.checkout("master")
			except Exception as e:
				self.err=e
				dest_path=""
				print(e)
		return dest_path
	#def _get_git_repo

	def _check_repo_consistency(self,repo_path):
		repo=Repo(repo_path)
		sw_ok=True
		#Change to debian/bionic
		try:
			repo.git.checkout(self.debian_release)
		except Exception as e:
			self.err=e
			sw_ok=False
		#Merge with master
		if sw_ok:
			try:
				repo.git.merge("master")
			except:
					try:
						repo.git.merge("origin/master")
					except Exception as e:
						self.err=e
						sw_ok=False
		try:
			repo.git.checkout('master')
		except Exception as e:
			#No master branch, discar repo
			self.err=e
			sw_ok=False

		return sw_ok
	#def _check_repo_consistency

	def _get_commits(self,repo_path,branches=None):
		repo=Repo(repo_path)
		args=['--reverse','--first-parent','--pretty']
		if branches == None:
			branches=["master","debian/bionic"]
		else:
			if type(branches)!=type([]):
				branches=[branches]
		args.extend(branches)
#		commits=repo.git.rev_list("--reverse","--first-parent","--pretty",' '.join(branches))
		commits=repo.git.rev_list(args)
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
				author=' '.join(data.split(' ')[1:])
			elif data.startswith('Date'):
				date=' '.join(data.split(' ')[1:])
			elif data=='':
				pass
			else:
				msg+="%s "%data.strip()
		#Last item
		commits_dict.update({commit:{'author':author,'date':date,'msg':msg}})
		return commits_dict
	#def _get_commits

	def _sync_repo(self,repo_path,repo_name):
		repo=Repo(repo_path)
		commits=self._get_commits(repo_path)
		master_commits=self._get_commits(repo_path,"master")
		debian_commits=self._get_commits(repo_path,self.debian_release)
		svn_url="%s/%s"%(self.config['dest_url'],repo_name)
		try:
			subprocess.run(["svn","mkdir",svn_url,"-m","Create repo"])
		except Exception as e:
			print(e)
		self._debug("Connecting to svn at %s"%svn_url)
		r_svn=svn.remote.RemoteClient(svn_url)
		svn_local_repo=self._chk_svn_dir(repo_name,r_svn)
		l_svn_base_path="%s/../../"%svn_local_repo
		l_svn=svn.local.LocalClient(l_svn_base_path)
#		for commit,data in commits.items():
		sw_continue=True
		for commit,data in commits.items():
			commit_id=commit.split(' ')[-1]
			last_commit=self._get_last_commit(repo_name)
			if last_commit and sw_continue:
				print("Skipping commit %s || %s"%(commit_id,last_commit))
				if last_commit!=commit_id:
					continue
				else:
					sw_continue=False
					continue
			else:
				sw_continue=False
			
			commit_msg="%s: %s %s %s"%(commit_id,data['msg'],data['date'],data['author'])
			repo.git.checkout(commit_id)
			self._debug("Copying data from %s to %s"%(repo_path,svn_local_repo))
			for f in os.listdir(svn_local_repo):
				if os.path.isdir("%s/%s"%(svn_local_repo,f)):
					shutil.rmtree("%s/%s"%(svn_local_repo,f))
				else:
					os.remove("%s/%s"%(svn_local_repo,f))
			self._copy_data(repo_path,svn_local_repo)
			self._debug("Accesing local svn at %s"%svn_local_repo)
			files_to_del=[]
			try:
				for st in l_svn.status():
#					print ("%s: %s"%(st.name,st.type_raw_name))
					if st.type_raw_name=='unversioned':
						f=st.name
						if '@' in f:
							f="%s@"%f
						if ("debian" in f or "docs" in f) and commit in debian_commits.keys():
							l_svn.add(f)
					if st.type_raw_name=='missing':
						f=st.name
						if ("debian" in f or "docs" in f) and commit in master_commits.keys():
							pass
						else:
							if '@' in f:
								f="%s@"%f
							files_to_del.append(f)
			except Exception as e:
				print(e)
			self._debug("Commit %s"%commit_msg)
			if files_to_del:
#				files_to_del.sort(key = len,reverse=True)
				files_to_del.sort(key = len)
#				print(files_to_del)
				l_svn.run_command('delete',files_to_del)
				r_svn.run_command('delete',files_to_del)
			try:
				l_svn.commit(commit_msg)
				self._write_info(repo_name,commit_id)
			except Exception as e:
				print("ERROR")
				print(e)
				for k in master_commits.keys():
					print(k)
				sys.exit(0)
	#def sync_commits

	def _chk_svn_dir(self,repo_name,r_svn):
		sw_ok=True
		svn_tmpdir="/tmp/svn/%s"%repo_name
		try:
			os.makedirs(svn_tmpdir)
		except Exception as e:
			print(e)
		self._debug("Checkout subversion")
		r_svn.checkout(svn_tmpdir)
		if not os.path.isdir("%s/trunk/fuentes"%svn_tmpdir):
			os.makedirs("%s/trunk/fuentes"%svn_tmpdir)
			os.makedirs("%s/trunk/docs"%svn_tmpdir)
		return ("%s/trunk/fuentes"%svn_tmpdir)

	def _copy_data(self,src,dest,ignore=None):
		if os.path.isdir(src):
			if not os.path.isdir(dest):
				os.makedirs(dest)
				try:
					shutil.copystat(src,dest)
				except:
					pass
			files = os.listdir(src)
			if ignore is not None:
				ignored = ignore(src, files)
			else:
				ignored = set()
			for f in files:
				if f not in ignored or '.git' not in f:
					self._copy_data(os.path.join(src, f), 
										os.path.join(dest, f), 
										ignore)
		else:
			try:
				shutil.copyfile(src, dest)
				shutil.copystat(src,dest)
			except:	
				pass

	def _set_db(self):
		sw_db_exists=False
		if os.path.isfile(self.commits_db):
			sw_db_exists=True
		else:
			try:
				os.makedirs(os.path.dirname(self.commits_db))
			except Exception as e:
				#self._debug(e)
				pass
		try:
			self.db=sqlite3.connect(self.commits_db)
		except Exception as e:
			#self._debug(e)
			pass
		self.db_cursor=self.db.cursor()
		if sw_db_exists==False:
			#self._debug("Creating cache table")
			self.db_cursor.execute('''CREATE TABLE data(repo TEXT PRIMARY KEY, commit_id TEXT)''')
		self.db_cursor.execute("SELECT count(*) FROM data")
		self.processed=self.db_cursor.fetchone()
		self._debug("%s repos present"%self.processed)
	#def _set_db

	def _write_info(self,repo,commit):
		self._debug("Insert %s -> %s"%(repo,commit))
		self.db_cursor.execute('''REPLACE into data values (?,?)''', (repo,commit))
		try:
			self.db.commit()
		except Exception as e:
			#self._debug("Commit error: %s. Rollback launched\n"%e)
			self.db.rollback()
	#def _commit_bd

	def _get_last_commit(self,repo):
		commit=None
		self.db_cursor.execute('''SELECT commit_id FROM data WHERE repo=?''',(repo,))
		row=self.db_cursor.fetchone()
		if row:
			#self._debug("Row: %s"%str(row))
			commit=str(row[0])
		return(commit)
