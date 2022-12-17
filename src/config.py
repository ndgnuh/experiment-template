import re
from os import path

__all__ = ["load_configs", "read", "ModuleLoader"]

# Load module from config


class ModuleLoader:
    def __init__(self, *args, **kwarsg):
        self.references = args + [kwargs]

    def __call__(self, config):
        # Search for the caller
        key = config[":name"]
        for table in self.references:
            if isinstance(table, dict):
                if key not in table:
                    continue
                else:
                    value = table[key]
                    break
            else:
                if not hasattr(table, key):
                    continue
                else:
                    value = getattr(table, key)
                    break

        # Instantiate the
        kwargs = {
            k: v for k, v in config.items()
            if k != ":name"
        }
        return Module(**kwargs)


# READ FUNCTIONS


def read_yaml(fpath: str):
    import yaml
    with open(fpath, encoding='utf-8') as io:
        return yaml.load(io, Loader=yaml.FullLoader)


def read_json(fpath: str):
    import json
    with open(fpath, encoding="utf-8") as io:
        return json.load(io)


def read_toml(fpath: str):
    import toml
    with open(fpath, encoding="utf-8") as io:
        return toml.load(io)


def read(fpath: str):
    mapping = dict(
        yml=read_yaml,
        yaml=read_yaml,
        json=read_json,
        toml=read_toml
    )
    ext = path.splitext(fpath)[-1].lstrip(".")
    return mapping[ext](fpath)

# ARGPARSE


def add_config_argument(parser=None, **kw):
    kw.setdefault("required", True)
    kw.setdefault("action", "append")
    kw.setdefault("default", [])
    kw.setdefault("help", "List of configuration files")
    kw.setdefault("dest", "configs")
    if parser is None:
        return lambda parser: add_config_argument(parser, **kw)
    else:
        parser.add_argument("-c", "--config", "--cfg", **kw)

# LOADING


def replace_variables(config):
    variables = config.get("__variables__", dict())
    variables = {"${" + k + "}": v for k, v in variables.items()}

    def traverse(k, v, root):
        if isinstance(v, str):
            # Full match
            if v in variables:
                root[k] = variables[v]
                return

            # Partial match
            matches = re.finditer(r"(\${\w+})", v)
            for match in matches:
                var = match.group()
                var_name = var.strip("${}")
                if var_name in variables:
                    v = v.replace(var, str(variables[var_name]))
            root[k] = v
            return

        if isinstance(v, (int, bool, float, type(None))):
            return

        if isinstance(v, dict):
            iter_ = v.items()
        elif isinstance(v, (list, tuple)):
            iter_ = enumerate(v)

        for k_, v_ in iter_:
            traverse(k_, v_, root=v)

    traverse(None, config, None)
    return config


def get_experiment_name_from_file(fpath):
    return path.splitext(path.basename(fpath))[0]


def remove_enforcer(cfg):
    def process_key(k):
        return k.rstrip("!")

    def process_value(v):
        if isinstance(v, dict):
            return remove_enforcer(v)
        return v

    cfg = {process_key(k): process_value(v)
           for k, v in cfg.items()}
    return cfg


def parse_key(key):
    if key.endswith("!"):
        return key.rstrip("!"), True
    else:
        return key, False


def get_key(config, key):
    key = key.rstrip("!")
    return config.get(key, config.get(f'{key}!', None))


def set_key(config, key, value):
    key = key.rstrip("!")
    fkey = f"{key}!"
    if fkey in config:
        config.pop(fkey)
    config[key] = value
    return config


def merge_config(base, update, max_depth=100, depth=0):
    if depth > max_depth:
        print("Maximum recursion depth reached, returning base dict")
        return base

    for key, update_value in update.items():
        key, replace = parse_key(key)
        base_value = get_key(base, key)

        # If of different type, assign
        if replace or not isinstance(update_value, type(base_value)):
            set_key(base, key, update_value)
            continue

        # Both are dict
        if isinstance(update_value, dict):
            updated = merge_config(base_value, update_value,
                                   max_depth=max_depth,
                                   depth=depth+1)
            set_key(base, key, updated)
            continue

        # Both are list or tuples, just extend
        if isinstance(update_value, (list, tuple)):
            set_key(base, key, base_value + update_value)
            continue

        # Fallback, just assign
        set_key(base, key, update_value)

    return base


def resolve(files):
    def resolve_(files, graph=None):
        if graph is None:
            graph = []
        for file in files:
            cfg = read(file)
            root_dir = path.dirname(file)
            subfiles = cfg.get("__inherit__", [])
            subfiles = [path.join(root_dir, subfile)
                        for subfile in subfiles]
            for subfile in reversed(subfiles):
                graph.append((file, subfile))
            resolve_(subfiles, graph)
        return graph

    links = resolve_(files)
    load_order = []
    for (f1, f2) in reversed(links):
        if f2 not in load_order:
            load_order.append(f2)
    for (f1, f2) in reversed(links):
        if f1 not in load_order:
            load_order.append(f1)

    for file in files:
        if file not in load_order:
            load_order.append(file)
    return load_order


def load_configs(files):
    # from icecream import install
    # install()
    load_order = resolve(files)

    # Load files by order
    first_file = load_order.pop(0)
    cfg = read(first_file)
    if len(load_order) > 0:
        for file in load_order:
            cfg = merge_config(cfg, read(file))

    # Remove special stuff in the keys
    if "__inherit__" in cfg:
        cfg.pop("__inherit__")
    cfg = remove_enforcer(cfg)

    # Replace variables
    cfg = replace_variables(cfg)
    cfg.setdefault(
        "experiment_name",
        get_experiment_name_from_file(first_file)
    )
    return cfg
