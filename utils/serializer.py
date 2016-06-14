#!/usr/bin/env python
# Taken from unity2yaml in unitypack
import yaml
import unitypack
import unitypack.engine as engine
from unitypack.object import ObjectPointer
from unitypack.asset import Asset


def asset_representer(dumper, data):
	return dumper.represent_scalar("!asset", data.name)


def objectpointer_representer(dumper, data):
	return dumper.represent_sequence("!PPtr", [data.file_id, data.path_id])


def unityobj_representer(dumper, data):
	return dumper.represent_mapping("!unitypack:%s" % (data.__class__.__name__), data._obj)


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


# define default representers
for k, v in engine.__dict__.items():
	if isinstance(v, type) and issubclass(v, engine.object.Object):
		yaml.add_representer(v, unityobj_representer)

yaml.add_representer(Asset, asset_representer)
yaml.add_representer(ObjectPointer, objectpointer_representer)

# use stripped versions for these objects
yaml.add_representer(engine.text.TextAsset, textasset_representer)
yaml.add_representer(engine.mesh.Mesh, mesh_representer)
yaml.add_representer(engine.movie.MovieTexture, movietexture_representer)
yaml.add_representer(engine.text.Shader, shader_representer)
yaml.add_representer(engine.texture.Texture2D, texture2d_representer)
