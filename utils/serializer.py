#!/usr/bin/env python
# Taken from unity2yaml in unitypack
import yaml
import unitypack
import unitypack.engine as engine
from unitypack.object import ObjectPointer
from unitypack.asset import Asset


def unityobj_representer(dumper, data):
	return dumper.represent_mapping("!unitypack:%s" % (data.__class__.__name__), data._obj)


def asset_representer(dumper, data):
	return dumper.represent_scalar("!asset", data.name)


def asset_constructor(loader, node):
	return loader.construct_scalar(node)


def objectpointer_representer(dumper, data):
	return dumper.represent_sequence("!PPtr", [data.file_id, data.path_id])


def objectpointer_constructor(loader, node):
	return loader.construct_sequence(node)


def shader_representer(dumper, data):
	obj = data._obj.copy()
	if "m_SubProgramBlob" in obj:
		obj["m_SubProgramBlob"] = "<stripped>"
	return dumper.represent_mapping("!unitypack:stripped:Shader", obj)


def textasset_representer(dumper, data):
	return dumper.represent_mapping("!unitypack:stripped:TextAsset", {data.name: None})


def texture2d_representer(dumper, data):
	return dumper.represent_mapping("!unitypack:stripped:Texture2D", {data.name: None})


def mesh_representer(dumper, data):
	return dumper.represent_mapping("!unitypack:stripped:Mesh", {data.name: None})


def movietexture_representer(dumper, data):
	obj = data._obj.copy()
	obj["m_MovieData"] = "<stripped>"
	return dumper.represent_mapping("!unitypack:stripped:MovieTexture", obj)


def serialize(obj):
	return yaml.dump(obj)


def deserialize(obj):
	return yaml.load(obj)


def mapping_constructor(loader, node):
	return loader.construct_mapping(node)


# define default representers and constructors for unity engine objects
for k, v in engine.__dict__.items():
	if isinstance(v, type) and issubclass(v, engine.object.Object):
		yaml.add_representer(v, unityobj_representer)
		yaml.add_constructor("!unitypack:%s" % (k), mapping_constructor)
# define for non engine objects
yaml.add_representer(Asset, asset_representer)
yaml.add_representer(ObjectPointer, objectpointer_representer)
# override set representer with stripped versions, for these objects
yaml.add_representer(engine.text.TextAsset, textasset_representer)
yaml.add_representer(engine.mesh.Mesh, mesh_representer)
yaml.add_representer(engine.movie.MovieTexture, movietexture_representer)
yaml.add_representer(engine.text.Shader, shader_representer)
yaml.add_representer(engine.texture.Texture2D, texture2d_representer)
# constructors
yaml.add_constructor("!asset", asset_constructor)
yaml.add_constructor("!PPtr", objectpointer_constructor)
# stripped versions
yaml.add_constructor("!unitypack:stripped:TextAsset", mapping_constructor)
yaml.add_constructor("!unitypack:stripped:Mesh", mapping_constructor)
yaml.add_constructor("!unitypack:stripped:MovieTexture", mapping_constructor)
yaml.add_constructor("!unitypack:stripped:Shader", mapping_constructor)
yaml.add_constructor("!unitypack:stripped:Texture2D", mapping_constructor)
