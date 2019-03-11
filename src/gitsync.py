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
		self.log="/tmp/gitsync.log"
		self.dbg=True
		if self.dbg:
			f=open(self.log,'w')
			f.close()
		self.debian_branch="debian/bionic"
		self.sync_result={}
		self.commits_db="/usr/share/shigitsu/commits.sql"
		self.secrets="/usr/share/shigitsu/secrets"
		self.err=None
		self.time_between_syncs=2
		self.force=False
		self.usermap={}
		if 'force' in kwargs.keys():
			self.force=kwargs['force']
		if 'usermap' in kwargs.keys():
			if kwargs['usermap']:
				try:
					with open(self.secrets,'r') as f:
						usermap=f.readlines()
					for user in usermap:
						user=user.rstrip()
						gituser=user.split('=')[0]
						svnuser=user.split('=')[-1]
						svnpwd=svnuser.split(',')[1]
						svnuser=svnuser.split(',')[0]
						self.usermap.update({gituser:{'svnuser':svnuser,'svnpwd':svnpwd}})

				except Exception as e:
					print(e)
		self.svn_dir_postfix="/tmp/svn/"
	#def __init__

	def _debug(self,msg):
		if self.dbg:
			if (type(msg)==type('')):
				if '--password' in msg:
					msg=re.sub(r"'--password', '.*?'","'--password', '#####'",msg)
			print("Debug: %s"%msg)
			with open(self.log,'a') as f:
				f.write("%s\n"%msg)
	#def _debug
	
	def set_download_path(self,path):
		self.config.update({'download_path':path})
	#def set_download_path

	def set_download_path(self,path):
		self.config.update({'download_path':path})

	def sync(self):
		if self.config['download_path']:
			if not os.path.isdir(self.config['download_path']):
				try:
					os.makedirs(self.config['download_path'])
				except Exception as e:
					self._debug(e)
					self.sync_result.update({'ERROR':'Download path could not be created'})
					return(self.sync_result)
		else:
			self._debug("Theres no dest path")
			self.sync_result.update({'ERROR':'Download path is not set'})
			return(self.sync_result)

		self._set_db()
		repos=self._list_repos(self.config['orig_url'])
		not_whitelisted=[]
		blacklisted=[]
		inconsistent=[]
		no_master_branch=[]
		sync_error=[]
		if repos:
			if (type(repos)==type({})):
				if 'message' in repos.keys():
					self._debug("%s"%repos['message'])
				self._debug("Ending process. Bad response from Git")
				sys.exit(1)				
			for repo in repos:
				self.err=''
				repo_name=repo['clone_url'].split('/')[-1].replace('.git','')
				self._debug("Analyzing %s"%repo_name)
				if self.config['whitelist']:
					if repo_name not in self.config['whitelist']:
						self._debug("Not in whitelist %s"%repo_name)
						not_whitelisted.append(repo_name)
						continue
				if self.config['blacklist']:
					if repo_name in self.config['blacklist']:
						blacklisted.append(repo_name)
						self._debug("Blacklisted %s"%repo_name)
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
						if 'user_to_commit' in self.config.keys() and self.config['user_to_commit']:
							self._debug("user_to_commit: %s"%self.config['user_to_commit'])
						if not self._sync_repo(repo_path,repo_name):
							sync_error.append({repo_name:self.err})
					else:
						inconsistent.append({repo_name:self.err})
						self._debug("Discard for inconsistency %s"%repo_name)
				else:
					no_master_branch.append({repo_name:self.err})
					self._debug("Discard for no master branch %s"%repo_name)
				if self.config['delete_when_processed'].lower()=='true' and not self.err:
					shutil.rmtree("%s/%s"%(self.config['download_path'],repo_name))
					shutil.rmtree(repo_path)
				time.sleep(self.time_between_syncs)
		self.sync_result.update({'not_whitelisted':not_whitelisted})
		self.sync_result.update({'blacklisted':blacklisted})
		self.sync_result.update({'inconsistent':inconsistent})
		self.sync_result.update({'no_master_branch':no_master_branch})
		self.sync_result.update({'syncing_error':sync_error})
		return self.sync_result
	#def sync

	def set_config(self,conf_dict):
		self.config=conf_dict
		if 'local_commits_db' in self.config.keys() and self.config['local_commits_db'].lower()=='true':
			self.commits_db="%s/.commits.sql"%os.environ['HOME']
		if 'debian_branch' in self.config.keys():
			self.debian_branch=self.config['debian_branch']

	#def set_config

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
		download_path="%s/%s"%(self.config['download_path'],repo_name)
		self._debug("Cloning %s in %s"%(repo,download_path))
		if os.path.isdir(download_path):
			repo = git.Repo(download_path)
			try:
				repo.git.checkout("master")
				repo.remotes.origin.pull()
			except Exception as e:
				self.err=e
				download_path=""
				print(e)
		else:
			try:
				git.Repo.clone_from(repo,download_path)
				repo = git.Repo(download_path)
				repo.git.checkout("master")
			except Exception as e:
				self.err=e
				download_path=""
				print(e)
		return download_path
	#def _get_git_repo

	def _check_repo_consistency(self,repo_path):
		repo=Repo(repo_path)
		sw_ok=True
		#Change to debian/bionic
		try:
			repo.git.checkout(self.debian_branch)
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
			branches=["master",self.debian_branch]
		else:
			if type(branches)!=type([]):
				branches=[branches]
		args.extend(branches)
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
		debian_commits=self._get_commits(repo_path,self.debian_branch)
		svn_url="%s/%s"%(self.config['dest_url'],repo_name)
		if self.usermap:
		#Get first user commit
			for repository,data in commits.items():
				def_author=data['author']
				break
			if def_author in self.usermap.keys():
				print("*****")
				print(self.usermap[def_author])
				print("*****")
				user=self.usermap[def_author]['svnuser']
				pwd=self.usermap[def_author]['svnpwd']
			print (def_author)
		elif 'user_to_commit' in self.config.keys() and self.config['user_to_commit']:
				user=self.config['user_to_commit']

		try:
			self._debug("Checkout subversion")
			if 'user_to_commit' in self.config.keys() and self.config['user_to_commit']:
				self._debug("user_to_commit: %s"%self.config['user_to_commit'])
				subprocess.run(["svn","mkdir",svn_url,"-m","Create repo","--username",self.config['user_to_commit'],'--password',self.config['password']],check=True)
			else:
				subprocess.run(["svn","mkdir",svn_url,"-m","Create repo"],check=True)
		except subprocess.CalledProcessError as e:
			print(e.stderr)
		except Exception as e:
			print(e)
		self._debug("Connecting to svn at %s"%svn_url)
		r_svn=svn.remote.RemoteClient(svn_url)
		if 'user_to_commit' in self.config.keys() and self.config['user_to_commit']:
			self._debug("user_to_commit: %s"%self.config['user_to_commit'])
			r_svn._CommonClient__username=self.config['user_to_commit']
			r_svn._CommonClient__password=self.config['password']
		svn_local_repo=self._chk_svn_dir(repo_name,r_svn)
		l_svn_base_path="%s/../../"%svn_local_repo
		l_svn=svn.local.LocalClient(l_svn_base_path)
		if 'user_to_commit' in self.config.keys() and self.config['user_to_commit']:
			l_svn._CommonClient__username=self.config['user_to_commit']
			l_svn._CommonClient__password=self.config['password']
		sw_continue=True
		if self.config['single_commit'].lower()=='true':
			self._single_commit(debian_commits,repo_name,repo,repo_path,l_svn,r_svn,svn_local_repo)
		else:
			self._incremental_commits(commits,debian_commits,master_commits,repo_name,repo,repo_path,l_svn,r_svn,svn_local_repo)
	#def sync_commits

	def _single_commits(self,commits,repo_name,repo,repo_path,local_svn,remote_svn,svn_local_repo):
		if self.force:
			local_svn=self._reset_repo(repo_name,remote_svn)
			unpublished_commits=commits.copy()
		else:
			unpublished_commits=self._get_unpublished_commit(commits,repo_name)
		last_commit_key=list(unpublished_commits.keys())[-1]
		commit_id=last_commit_key(' ')[-1]

		repo.git.checkout(self.debian_branch)
		svnchanges=self._get_local_svn_changes(local_svn)
		self._do_commit(svnchanges,commit_id,commit_msg,repo_name,local_svn,remote_svn)

	def _incremental_commits(self,commits,debian_commits,master_commits,repo_name,repo,repo_path,local_svn,remote_svn,svn_local_repo):
		if self.force:
			local_svn=self._reset_repo(repo_name,remote_svn)
			unpublished_commits=commits.copy()
		else:
			unpublished_commits=self._get_unpublished_commit(commits,repo_name)
		for commit,data in unpublished_commits.items():
			commit_id=commit.split(' ')[-1]
			commit_msg="%s: %s %s %s"%(commit_id,data['msg'],data['date'],data['author'])
			if type(repo)==type(""):
				self._debug("Unknown error with repo %s"%repo)
				return
			repo.git.checkout(commit_id)
			self._debug("Copying data from %s to %s"%(repo_path,svn_local_repo))
			for f in os.listdir(svn_local_repo):
				if os.path.isdir("%s/%s"%(svn_local_repo,f)):
					shutil.rmtree("%s/%s"%(svn_local_repo,f))
				else:
					os.remove("%s/%s"%(svn_local_repo,f))
			self._copy_data(repo_path,svn_local_repo)
			self._debug("Accesing local svn at %s"%svn_local_repo)
			svnchanges=self._get_local_svn_changes(local_svn,commit,debian_commits,master_commits)
			self._debug("Commit %s"%commit_msg)
			self._do_commit(svnchanges,commit_id,commit_msg,repo_name,local_svn,remote_svn)
			if self.err:
				self._reset_repo(repo_name,remote_svn)
				self._do_commit(svnchanges,commit_id,commit_msg,repo_name,local_svn,remote_svn)

	def _reset_repo(self,repo_name,remote_svn):
		svn_tmpdir="%s%s%s"%(self.config['download_path'],self.svn_dir_postfix,repo_name)
		self._debug("Reset content of %s"%svn_tmpdir)
		shutil.rmtree("%s"%svn_tmpdir)
		svn_local_repo=self._chk_svn_dir(repo_name,remote_svn)
		l_svn_base_path="%s/../../"%svn_local_repo
		local_svn=svn.local.LocalClient(l_svn_base_path)
		if 'user_to_commit' in self.config.keys() and self.config['user_to_commit']:
			local_svn._CommonClient__username=self.config['user_to_commit']
			local_svn._CommonClient__password=self.config['password']
		remote_svn.checkout(repo_name)
		svnchanges=self._get_local_svn_changes(local_svn)
		self._debug("Reset repo")
		self._do_commit(svnchanges,"1","Reset repository",repo_name,local_svn,remote_svn)
#		local_svn.run_command("delete",["%s/../../*"%svn_local_repo,"--force"])
		local_svn.commit("Reset repository contents")

		return local_svn

	def _get_unpublished_commit(self,commits,repo_name):
		sw_continue=True
		unpublished_commits={}
		last_commit=self._get_last_commit(repo_name)
		for commit,data in commits.items():
			commit_id=commit.split(' ')[-1]
			if last_commit and sw_continue:
				self._debug("Skipping commit %s || %s"%(commit_id,last_commit))
				if last_commit!=commit_id:
					continue
				else:
					sw_continue=False
					continue
			else:
				unpublished_commits.update({commit:data})
				sw_continue=False
		return unpublished_commits

	def _get_local_svn_changes(self,local_svn,commit=None,debian_commits=None,master_commits=None):
		files_to_del=[]
		files_to_add=[]
		localchanges={}
		for st in local_svn.status():
			f=st.name
			if st.type_raw_name=='unversioned':
				if '@' in f:
					f="%s@"%f
				if commit:
					if ("debian" in f or "docs" in f) and commit not in debian_commits.keys():
						pass
					else:
						files_to_add.append(f)
				else:
					files_to_add.append(f)
			if st.type_raw_name=='missing':
				if commit:
					if ("debian" in f or "docs" in f) and commit in master_commits.keys():
						pass
					else:
						if '@' in f:
							f="%s@"%f
						files_to_del.append(f)
				else:
					if '@' in f:
						f="%s@"%f
					files_to_del.append(f)
			if st.type_raw_name=='obstructed':
				self._debug("Obstructed file: %s"%f)
				self._debug("Now I'll attempt to:")
				self._debug("1) Make a cleanup")
				self._debug("2) Move %s to /tmp"%f)
				self._debug("3) Create a new commit")
				self._debug("4) Add again %s"%f)
				local_svn.cleanup()
				dir_f=os.path.dirname(f)
				name_f=os.path.basename(f)
				shutil.move(f,"/tmp/%s"%name_f)
				try:
					local_svn.run_command('delete',[f,'--force'])
					local_svn.commit("Obstructed file %s"%f)
				except Exception as e:
					self._debug("Failed obstructed commit: %s"%e)
				shutil.move("/tmp/%s"%name_f,"%s"%dir_f)
				files_to_add.append(f)
				
		localchanges.update({'add':files_to_add})
		localchanges.update({'del':files_to_del})
		return(localchanges)

	def _do_commit(self,svnchanges,commit_id,commit_msg,repo_name,local_svn,remote_svn):
		self.err=None
		if svnchanges['del']:
			svnchanges['del'].sort(key = len,reverse=True)
			svnchanges['del'].append('--keep-local')
			try:
				remote_svn.run_command('delete',svnchanges['del'])
				local_svn.run_command('delete',svnchanges['del'])
			except Exception as e:
				self._debug("Failed to del: %s"%e)
		if svnchanges['add']:
			for f in svnchanges['add']:
				try:
					local_svn.add(f)
				except svn.exception.SvnException as e:
					if "conflict" in e.__str__():
						self._debug("Resolving conflict for file %s"%f)
						local_svn.run_command("resolve",["--accept","working",f])
						local_svn.add(f)
					else:
						self._debug("Could not add %s: %s"%(f,e))
				except Exception as e:
					self._debug("Could not add %s: %s"%(f,e))
		try:
			local_svn.commit(commit_msg)
			self._write_info(repo_name,commit_id)
		except Exception as e:
			try:
				self._debug("Error syncing: %s"%e)
				self._debug("Updating svn")
				local_svn.update()
				local_svn.commit(commit_msg)
			except Exception as e:
				self.err=e
				self._debug("Error processing %s"%repo_name)
				self._debug(e)
#				for k in master_commits.keys():
#					self._debug(k)

	def _chk_svn_dir(self,repo_name,r_svn):
		sw_ok=True
		svn_tmpdir="%s%s%s"%(self.config['download_path'],self.svn_dir_postfix,repo_name)
		try:
			os.makedirs(svn_tmpdir)
		except Exception as e:
			print(e)
		self._debug("Checkout subversion")
		try:
			r_svn.checkout(svn_tmpdir)
		except:
			self._debug("Repo %s doesn't exists"%repo_name)
			pass
		if not os.path.isdir("%s/trunk/fuentes"%svn_tmpdir):
			os.makedirs("%s/trunk/fuentes"%svn_tmpdir)
			os.makedirs("%s/trunk/docs"%svn_tmpdir)
		return ("%s/trunk/fuentes"%svn_tmpdir)
	#def _chk_svn_dir

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
				if '.git' not in src:
					shutil.copyfile(src, dest)
					shutil.copystat(src,dest)
			except:	
				pass
	#def _copy_data

	def _set_db(self):
		sw_db_exists=False
		if os.path.isfile(self.commits_db):
			sw_db_exists=True
		else:
			try:
				os.makedirs(os.path.dirname(self.commits_db))
			except Exception as e:
				self._debug(e)
		try:
			self.db=sqlite3.connect(self.commits_db)
		except Exception as e:
			self._debug(e)
			self._debug(self.commits_db)
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
	#def _write_info

	def _get_last_commit(self,repo):
		commit=None
		self.db_cursor.execute('''SELECT commit_id FROM data WHERE repo=?''',(repo,))
		row=self.db_cursor.fetchone()
		if row:
			#self._debug("Row: %s"%str(row))
			commit=str(row[0])
		return(commit)
	#def _get_last_commit
