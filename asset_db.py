#!/usr/bin/env python
import os
import sys
import glob
import sqlite3
import argparse
import unitypack
import obj_to_yaml
import utils


def create_db(db, files):
	conn = sqlite3.connect(db)
	c = conn.cursor()
	c.execute("DROP TABLE IF EXISTS assets")
	c.execute('''CREATE VIRTUAL TABLE assets USING
		fts4 (fid, name, bundle, type, yaml)''')

	yaml = obj_to_yaml.YamlWriter()
	for file in files:
		with open(file, "rb") as f:
			bundle = unitypack.load(f)
		# grab the file name from the full path
		fname = utils.filename_no_ext(file)

		for asset in bundle.assets:
			for id, obj in asset.objects.items():
				d = obj.read()
				# try name field
				name = "unknown"
				try:
					name = d.name
				except Exception:
					pass
				# try obj type
				type = "unknown"
				try:
					type = obj.type
				except Exception:
					pass
				# insert values
				c.execute("INSERT INTO assets VALUES (?,?,?,?,?)",
					(id, name, fname, type, yaml.write(d)))
	conn.commit()
	conn.close()


def query_db(path, query, yaml, search = None):
	print("%s [%s]\n" % (query, search))
	conn = sqlite3.connect(path)
	c = conn.cursor()
	if search:
		c.execute(query, [search])
	else:
		c.execute(query)
	for r in c.fetchall():
		print_row(r, yaml)
	conn.close()


def print_row(row, yaml):
	if len(row) == 5:
		print("{0:22} - {2:12}\t{3:>15.15} | {1}".format(row[0], row[1], row[2], row[3]))
		if yaml:
			print(r[4])
	else:
		print(row)


def create(args):
	files = glob.glob(args.bundle_dir + '/*.unity3d')
	create_db(args.db_file, files)


def query(args):
	query = ""
	with open(args.sql_file, "r") as f:
		for l in f.readlines():
			query  += l.strip() + " "
	query_db(args.db_file, query, None)


def search(args):
	query = "SELECT * FROM assets WHERE assets MATCH ?"
	param = args.search
	if args.id:
		query = "SELECT * FROM assets WHERE fid MATCH ?"
		param = '"%s"' % (param)
	elif args.name:
		query = "SELECT * FROM assets WHERE name MATCH ?"
	query_db(args.db_file, query, args.yaml, param)


def main():
	parser = argparse.ArgumentParser(description="Creates or queries a HS asset database.")
	subparsers = parser.add_subparsers()
	# create db
	parser_create = subparsers.add_parser("create", help="create a new db")
	parser_create.add_argument("db_file", help="the new db's file path")
	parser_create.add_argument("bundle_dir", help="path to bundle directory")
	parser_create.set_defaults(func=create)
	# query db
	parser_search = subparsers.add_parser("search", help="search assets in the db")
	parser_search.add_argument("db_file", help="path to the db to search")
	parser_search.add_argument("search", help="search string")
	parser_search.add_argument("--yaml", help="print yaml field for matches", action="store_true")
	grp = parser_search.add_mutually_exclusive_group()
	grp.add_argument("--id", help="search the id field only", action="store_true")
	grp.add_argument("--name", help="search the name field only", action="store_true")
	parser_search.set_defaults(func=search)
	# query db from file
	parser_file = subparsers.add_parser("file", help="load query from file")
	parser_file.add_argument("db_file", help="the db's file path")
	parser_file.add_argument("sql_file", help="the file containing the sql query")
	parser_file.set_defaults(func=query)
	# parse args
	args = parser.parse_args(sys.argv[1:])
	args.func(args)


if __name__ == "__main__":
	main()
